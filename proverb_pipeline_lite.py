"""
Optimized Tunisian Proverb Pipeline - Lite Version
Uses Groq API for semantic interpretation and narrative generation

FEATURES:
- ChromaDB with modern PersistentClient API for semantic search
- Google Gemini API for lightweight, free LLM generation
- RAG initialized with 999 proverbs on startup
- Robust JSON parsing with fallback strategies
- SDXL image generation with memory optimization for 4GB VRAM
- Device auto-detection (falls back to CPU if CUDA unavailable)
- All components degrade gracefully instead of crashing
"""

import json
import re
import torch
import os
import requests
from typing import Optional, Dict, List
from dataclasses import dataclass, asdict
from datetime import datetime
import logging
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# LLM & Embeddings
from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline as hf_pipeline
from sentence_transformers import SentenceTransformer
import chromadb

# Image Generation
from diffusers import StableDiffusionXLPipeline
import gc

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# Data classes
# ─────────────────────────────────────────────

@dataclass
class SemanticInterpretation:
    literal_meaning: str
    hidden_meaning: str
    moral: str
    key_phrases: List[str]
    narrative: str = ""  # Story embodying the lesson


@dataclass
class VisualScene:
    subject: str
    setting: str
    action: str
    symbols: str
    mood: str
    style: str
    color_palette: str


@dataclass
class GeneratedOutput:
    proverb_id: str
    proverb_text: str
    interpretation: SemanticInterpretation
    scene: Optional[VisualScene]
    generated_prompt: Optional[str] = None
    image_path: Optional[str] = None
    clip_score: Optional[float] = None
    retry_count: int = 0
    created_at: str = None
    rag_context: Optional[List[Dict]] = None  # Similar proverbs from retrieval

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now().isoformat()

    def to_dict(self):
        return {
            "proverb_id": self.proverb_id,
            "proverb_text": self.proverb_text,
            "interpretation": asdict(self.interpretation),
            "scene": asdict(self.scene) if self.scene else None,
            "generated_prompt": self.generated_prompt,
            "image_path": self.image_path,
            "clip_score": self.clip_score,
            "retry_count": self.retry_count,
            "created_at": self.created_at,
            "rag_context": self.rag_context or [],
        }


# ─────────────────────────────────────────────
# RAG System  (FIX: modern ChromaDB API + proper init)
# ─────────────────────────────────────────────

class RAGSystem:
    """Retrieval-Augmented Generation with ChromaDB"""

    def __init__(self, db_path: str = "data/chromadb"):
        self.db_path = db_path
        Path(db_path).mkdir(parents=True, exist_ok=True)

        # FIX: Use PersistentClient (replaces deprecated duckdb+parquet Settings)
        try:
            self.client = chromadb.PersistentClient(path=db_path)
            logger.info("ChromaDB PersistentClient initialized")
        except Exception as e:
            logger.error(f"ChromaDB init failed: {e}")
            self.client = None

        self.collection = None
        self._initialized = False

    def initialize_with_proverbs(self, proverbs: List[Dict]):
        """Load proverbs into ChromaDB — called once on startup"""
        if not self.client:
            logger.warning("ChromaDB client not available, skipping RAG init")
            return

        try:
            self.collection = self.client.get_or_create_collection(
                name="tunisian_proverbs",
                metadata={"hnsw:space": "cosine"}
            )

            # Only populate if empty to avoid duplicate inserts on restart
            existing_count = self.collection.count()
            if existing_count >= len(proverbs):
                logger.info(f"ChromaDB already has {existing_count} proverbs, skipping load")
                self._initialized = True
                return

            documents, metadatas, ids = [], [], []

            for idx, proverb in enumerate(proverbs):
                text = proverb.get("tunisan_proverb", "").strip()
                if not text:
                    continue
                doc_id = f"proverb_{idx}"
                documents.append(text)
                metadatas.append({
                    "explanation": str(proverb.get("proverb_arabic_explaination", "")),
                    "context": str(proverb.get("context", "")),
                })
                ids.append(doc_id)

            # ChromaDB add in batches of 500 to avoid memory spikes
            batch_size = 500
            for i in range(0, len(documents), batch_size):
                self.collection.add(
                    documents=documents[i:i+batch_size],
                    metadatas=metadatas[i:i+batch_size],
                    ids=ids[i:i+batch_size],
                )

            self._initialized = True
            logger.info(f"Loaded {len(documents)} proverbs into ChromaDB")

        except Exception as e:
            logger.error(f"Error initializing RAG: {e}")

    def retrieve_context(self, proverb_text: str, top_k: int = 3) -> List[Dict]:
        """Retrieve similar proverbs for context - returns structured results"""
        if not self._initialized or self.collection is None:
            return []
        try:
            results = self.collection.query(
                query_texts=[proverb_text],
                n_results=min(top_k, self.collection.count()),
            )
            
            # Return both documents and metadata for richer context
            documents = results.get("documents", [[]])[0]
            metadatas = results.get("metadatas", [[]])[0]
            
            context_list = []
            for i, (doc, meta) in enumerate(zip(documents, metadatas)):
                context_list.append({
                    "index": i + 1,
                    "proverb": meta.get("proverb", ""),
                    "context": meta.get("context", ""),
                    "explanation": meta.get("explanation", ""),
                    "full_content": doc
                })
            
            return context_list
        except Exception as e:
            logger.warning(f"RAG retrieval failed: {e}")
            return []


# ─────────────────────────────────────────────
# JSON helpers  (FIX: robust parsing for Phi-2)
# ─────────────────────────────────────────────

def _extract_json(text: str) -> Optional[dict]:
    """
    Try multiple strategies to pull a JSON object out of messy LLM output.
    Phi-2 often wraps JSON in markdown or adds commentary before/after.
    """
    if not text:
        return None

    # Strategy 1: find the last complete {...} block (most reliable for Phi-2)
    # Use rfind so we grab the outermost completed object
    depth = 0
    start = -1
    best = None
    for i, ch in enumerate(text):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start != -1:
                candidate = text[start:i+1]
                try:
                    best = json.loads(candidate)
                except json.JSONDecodeError:
                    pass
                start = -1

    if best:
        return best

    # Strategy 2: strip markdown fences and retry
    cleaned = re.sub(r"```(?:json)?", "", text).strip()
    try:
        return json.loads(cleaned)
    except Exception:
        pass

    return None


def _parse_pipe_separated(text: str) -> dict:
    """Parse pipe-separated interpretation format"""
    if not text:
        return {}
    
    parts = text.split("||")
    if len(parts) >= 4:
        return {
            "literal_meaning": parts[0].strip(),
            "hidden_meaning": parts[1].strip(),
            "moral": parts[2].strip(),
            "key_phrases": [p.strip() for p in parts[3].split(",") if p.strip()]
        }
    return {}


def _parse_structured_response(text: str) -> dict:
    """Parse structured response - extract key sections for display"""
    if not text:
        return {}
    
    result = {}
    
    # Try numbered format first (what Qwen naturally produces)
    # 1. LITERAL & METAPHORICAL MEANING
    match = re.search(r'1\.\s*(?:LITERAL|Literal).*?\n(.+?)(?=\n\d\.|$)', text, re.DOTALL)
    if match:
        result["literal_meaning"] = match.group(1).strip()[:500]
    
    # 2. CULTURAL...
    match = re.search(r'2\.\s*(?:CULTURAL|Cultural).*?\n(.+?)(?=\n\d\.|$)', text, re.DOTALL)
    if match:
        result["hidden_meaning"] = match.group(1).strip()[:500]
    
    # Try colon-separated format (our original prompt)
    if not result:
        match = re.search(r'LITERAL_MEANING:\s*(.+?)(?=HIDDEN_MEANING:|$)', text, re.DOTALL)
        if match:
            result["literal_meaning"] = match.group(1).strip()[:500]
        
        match = re.search(r'HIDDEN_MEANING:\s*(.+?)(?=MORAL_LESSON:|$)', text, re.DOTALL)
        if match:
            result["hidden_meaning"] = match.group(1).strip()[:500]
    
    # Extract MORAL_LESSON however it appears
    match = re.search(r'MORAL_LESSON:\s*(.+?)(?=KEY_CONCEPTS:|CULTURAL_CONTEXT:|$)', text, re.DOTALL)
    if match:
        result["moral"] = match.group(1).strip()[:500]
    
    # Extract KEY_CONCEPTS
    match = re.search(r'KEY_CONCEPTS:\s*(.+?)(?=LITERAL_MEANING:|HIDDEN_MEANING:|MORAL_LESSON:|$)', text, re.DOTALL)
    if match:
        concepts_text = match.group(1).strip()
        result["key_phrases"] = [p.strip() for p in concepts_text.split(",") if p.strip()]
    
    return result if result else {}


def _parse_fallback(text: str) -> dict:
    """Fallback parser - extract meaningful lines when structured format fails"""
    if not text:
        return {}
    
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    
    result = {}
    
    # Try to extract 4 parts from lines
    if len(lines) >= 1:
        result["literal_meaning"] = lines[0]
    if len(lines) >= 2:
        result["hidden_meaning"] = lines[1]
    if len(lines) >= 3:
        result["moral"] = lines[2]
    
    # Try to extract key phrases from the last line if it looks like comma-separated words
    if len(lines) >= 4:
        last_line = lines[-1]
        if "," in last_line:
            result["key_phrases"] = [p.strip() for p in last_line.split(",") if p.strip()]
        else:
            result["key_phrases"] = [last_line]
    else:
        result["key_phrases"] = []
    
    return result


# ─────────────────────────────────────────────
# LLM Interface (OpenRouter + Qwen 3.6+)
# ─────────────────────────────────────────────

class LLMInterface:
    """Direct OpenRouter API calls - no local LLM needed"""

    def __init__(self, device: str = "cuda", model_name: str = None):
        """Initialize OpenRouter API (model_name ignored, uses Qwen 3.6+)"""
        self.api_key = os.getenv('GROQ_API_KEY')
        if not self.api_key:
            raise RuntimeError("GROQ_API_KEY not found in environment")
        
        self.model = "llama-3.3-70b-versatile"
        logger.info(f"✅ Groq API LLM initialized with {self.model}")

    def _generate(self, prompt: str, max_new_tokens: int = 300, temperature: float = None) -> str:
        """Generate text directly from Groq API"""
        try:
            url = "https://api.groq.com/openai/v1/chat/completions"
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            data = {
                "model": self.model,
                "messages": [
                    {"role": "user", "content": prompt}
                ],
                "temperature": temperature or 0.7,
                "max_tokens": min(max_new_tokens, 800)
            }
            
            logger.info(f"🔄 Calling Groq API with {len(prompt)} char prompt...")
            response = requests.post(
                url,
                headers=headers,
                json=data,
                timeout=30
            )
            
            logger.info(f"📡 Groq response status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"✅ API response received: {str(result)[:200]}")
                
                try:
                    content = result["choices"][0]["message"]["content"].strip()
                    logger.info(f"✓ Generated {len(content)} characters")
                    return content
                except (KeyError, IndexError, TypeError) as e:
                    logger.warning(f"⚠️ Unexpected response format: {e}, Full response: {result}")
                    return ""
            else:
                logger.error(f"❌ Groq API error ({response.status_code}): {response.text[:500]}")
                return ""
        except requests.exceptions.Timeout:
            logger.error("❌ Groq request timeout (30s)")
            return ""
        except requests.exceptions.ConnectionError as e:
            logger.error(f"❌ Groq connection error: {e}")
            return ""
        except Exception as e:
            logger.error(f"❌ Groq generation failed: {e}", exc_info=True)
            return ""

    def interpret_proverb(self, proverb_text: str, explanation: str = None, rag_context: List[Dict] = None) -> SemanticInterpretation:
        """Extract semantic meaning from proverb with explanation and RAG context"""
        
        # Build context section from RAG results
        context_section = ""
        if rag_context:
            context_section = "Similar Tunisian proverbs for context:\n"
            for ctx in rag_context[:2]:  # Use top 2 similar proverbs
                context_section += f"\n• {ctx['proverb']}\n  ({ctx['context']}): {ctx['explanation']}\n"
            context_section += "\n"
        
        # Build the explanation line
        explanation_line = f"This proverb means: {explanation}\n\n" if explanation else ""
        
        # Build comprehensive prompt with all context
        prompt = (
            f"You are an expert in Tunisian culture and language. Analyze this proverb deeply.\n\n"
            f"{context_section}"
            f"TUNISIAN PROVERB TO ANALYZE: {proverb_text}\n"
            f"{explanation_line}"
            f"Provide your analysis in this EXACT format:\n\n"
            f"LITERAL_MEANING: What does this proverb literally say?\n"
            f"HIDDEN_MEANING: What deeper wisdom or truth does it teach?\n"
            f"MORAL_LESSON: What universal principle should people learn?\n"
            f"CULTURAL_CONTEXT: How is this used in Tunisian society?\n"
            f"KEY_CONCEPTS: Three key words (comma-separated) that capture the essence\n\n"
            f"Now analyze:\n"
        )

        response = self._generate(prompt, max_new_tokens=220, temperature=0.7)
        
        if not response:
            logger.warning(f"❌ Empty response from OpenRouter API!")
            return SemanticInterpretation(
                literal_meaning="Unable to interpret",
                hidden_meaning="Please try again",
                moral="Service temporarily unavailable",
                key_phrases=["error"],
            )
        
        logger.info(f"🎯 Raw API response:\n{response[:300]}\n...")
        
        # Try structured parsing first
        data = _parse_structured_response(response)
        if data and any([data.get("literal_meaning"), data.get("hidden_meaning"), data.get("moral")]):
            logger.info(f"✓ Structured parsing succeeded")
            return SemanticInterpretation(
                literal_meaning=str(data.get("literal_meaning", "")),
                hidden_meaning=str(data.get("hidden_meaning", "")),
                moral=str(data.get("moral", "")),
                key_phrases=data.get("key_phrases", []) if isinstance(data.get("key_phrases"), list) else [],
            )

        # Fallback to line-by-line parsing
        logger.warning(f"⚠️ Structured parsing returned empty, trying fallback")
        data = _parse_fallback(response)
        logger.info(f"Fallback parse result: {data}")
        
        return SemanticInterpretation(
            literal_meaning=str(data.get("literal_meaning", response[:100])),
            hidden_meaning=str(data.get("hidden_meaning", "Deep wisdom")),
            moral=str(data.get("moral", "Important life lesson")),
            key_phrases=data.get("key_phrases", []) if isinstance(data.get("key_phrases"), list) else [],
        )

    def generate_narrative(self, proverb_text: str, interpretation: SemanticInterpretation) -> str:
        """Generate a relatable story that embodies the proverb's wisdom"""
        lesson = interpretation.moral or interpretation.hidden_meaning or "wisdom and personal growth"
        
        prompt = (
            f"Write a SHORT, relatable story (2-3 sentences) that teaches this Tunisian lesson:\n"
            f"LESSON: {lesson}\n\n"
            f"The story should:\n"
            f"- Feature a specific Tunisian person in a realistic situation\n"
            f"- Show how they apply or learn this lesson\n"
            f"- End with the wisdom they gained\n\n"
            f"Style: Simple, warm, culturally respectful, modern but rooted in Tunisian values.\n"
            f"Story:\n"
        )
        
        narrative = self._generate(prompt, max_new_tokens=180, temperature=0.8)
        
        # Clean up the narrative
        narrative = narrative.strip()
        if not narrative or len(narrative) < 20:
            narrative = f"A story about {interpretation.key_phrases[0] if interpretation.key_phrases else 'life'}: " \
                       f"When we embrace {lesson.lower()}, we discover that our challenges become opportunities for growth. " \
                       f"This is the wisdom that Tunisians have passed down through generations."
        
        return narrative

    def generate_scene(self, interpretation: SemanticInterpretation) -> VisualScene:
        """Generate visual scene description (skipped if image generation disabled)"""
        # Return default scene since image generation is typically disabled
        # This avoids costly LLM calls for non-essential visual descriptions
        return VisualScene(
            subject=interpretation.key_phrases[0] if interpretation.key_phrases else "figure",
            setting="Tunisian landscape",
            action="reflecting",
            symbols="proverb wisdom",
            mood="contemplative",
            style="digital art",
            color_palette="warm earth tones, ochre, terracotta",
        )


# ─────────────────────────────────────────────
# Prompt Builder
# ─────────────────────────────────────────────

class PromptBuilder:
    """Build optimized SDXL prompts"""

    @staticmethod
    def build_prompt(scene: VisualScene) -> str:
        elements = [
            scene.subject,
            scene.action,
            f"in {scene.setting}" if scene.setting else "",
            scene.symbols,
            f"{scene.mood} mood" if scene.mood else "",
            scene.style,
            scene.color_palette,
        ]
        prompt = ", ".join(e for e in elements if e.strip())
        quality = "masterpiece, best quality, highly detailed, professional, cinematic lighting"
        return f"{prompt}, {quality}"

    @staticmethod
    def build_negative_prompt() -> str:
        return (
            "blurry, low quality, distorted, ugly, bad anatomy, "
            "watermark, text, signature, nsfw, violence"
        )


# ─────────────────────────────────────────────
# Image Generator  (FIX: memory-safe for RTX 2050)
# ─────────────────────────────────────────────

class ImageGenerator:
    """SDXL-based image generation with memory optimization for 4GB VRAM"""

    def __init__(self, device: str = "cuda"):
        if device == "cuda" and not torch.cuda.is_available():
            logger.warning("CUDA not available for image generation")
            device = "cpu"
        self.device = device

        logger.info("Loading SDXL pipeline...")
        self.pipe = StableDiffusionXLPipeline.from_pretrained(
            "stabilityai/stable-diffusion-xl-base-1.0",
            torch_dtype=torch.float16 if device == "cuda" else torch.float32,
            use_safetensors=True,
            variant="fp16" if device == "cuda" else None,
        )

        # FIX: do NOT use device_map with sequential_cpu_offload — they conflict
        # Use sequential CPU offload alone; it handles device placement itself
        if device == "cuda":
            self.pipe.enable_sequential_cpu_offload()  # saves VRAM by offloading layers
            self.pipe.enable_attention_slicing(1)       # reduces peak VRAM per step
        else:
            self.pipe = self.pipe.to("cpu")

        logger.info("SDXL loaded successfully")

    def generate(self, prompt: str, negative_prompt: str = "", steps: int = 20) -> str:
        """Generate image optimized for RTX 2050 (4GB VRAM)"""
        try:
            # FIX: autocast only valid on CUDA
            ctx = torch.cuda.amp.autocast() if self.device == "cuda" else torch.no_grad()
            with torch.no_grad(), ctx:
                image = self.pipe(
                    prompt=prompt,
                    negative_prompt=negative_prompt,
                    num_inference_steps=steps,   # reduced from 25 → 20 for VRAM safety
                    guidance_scale=7.5,
                    height=512,
                    width=512,
                ).images[0]

            output_dir = Path("website/generated")
            output_dir.mkdir(parents=True, exist_ok=True)
            image_path = output_dir / f"generated_{datetime.now().timestamp():.0f}.png"
            image.save(image_path)

            # Free VRAM after generation
            gc.collect()
            if self.device == "cuda":
                torch.cuda.empty_cache()

            logger.info(f"Image saved: {image_path}")
            return str(image_path)

        except torch.cuda.OutOfMemoryError:
            logger.error("CUDA OOM during image generation — try reducing steps or image size")
            gc.collect()
            torch.cuda.empty_cache()
            return ""
        except Exception as e:
            logger.error(f"Image generation failed: {e}")
            return ""


# ─────────────────────────────────────────────
# Pipeline Orchestrator  (FIX: RAG gets initialized here)
# ─────────────────────────────────────────────

class ProverbPipeline:
    """Main pipeline orchestrator"""

    def __init__(self, device: str = "cuda", enable_generation: bool = True,
                 proverbs_json: str = "website/proverbs.json"):
        self.device = device
        self.enable_generation = enable_generation

        # Init RAG
        self.rag = RAGSystem()

        # FIX: populate ChromaDB with proverbs on startup
        self._load_rag_from_json(proverbs_json)

        # Init LLM
        self.llm = LLMInterface(device=device)
        self.prompt_builder = PromptBuilder()

        # Init image generator (optional)
        self.image_generator = None
        if enable_generation:
            try:
                self.image_generator = ImageGenerator(device=device)
            except Exception as e:
                logger.warning(f"Image generation disabled: {e}")

    def _load_rag_from_json(self, json_path: str):
        """Load proverbs from JSON into ChromaDB for semantic search"""
        path = Path(json_path)
        if not path.exists():
            logger.warning(f"Proverbs JSON not found at {json_path}, RAG will be empty")
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                proverbs = json.load(f)
            self.rag.initialize_with_proverbs(proverbs)
        except Exception as e:
            logger.error(f"Failed to load proverbs into RAG: {e}")

    def process(self, proverb_text: str, proverb_id: str = None, explanation: str = None) -> GeneratedOutput:
        """Process proverb through full pipeline with RAG context"""

        if proverb_id is None:
            proverb_id = f"proverb_{abs(hash(proverb_text))}"

        # Step 1: Retrieve similar proverbs for context (RAG)
        logger.info("Retrieving cultural context...")
        rag_context = self.rag.retrieve_context(proverb_text, top_k=2)

        # Step 2: Interpret proverb with LLM (WITH explanation and RAG context)
        logger.info("Interpreting proverb...")
        interpretation = self.llm.interpret_proverb(
            proverb_text, 
            explanation=explanation,
            rag_context=rag_context
        )

        # Step 2.5: Generate narrative story embodying the lesson
        logger.info("Generating narrative...")
        narrative = self.llm.generate_narrative(proverb_text, interpretation)
        interpretation.narrative = narrative

        # Step 3: Generate visual scene description
        logger.info("Generating visual scene...")
        scene = self.llm.generate_scene(interpretation)

        # Step 4: Build SDXL prompt
        prompt = self.prompt_builder.build_prompt(scene)
        neg_prompt = self.prompt_builder.build_negative_prompt()

        # Step 5: Generate image (optional)
        image_path = None
        if self.enable_generation and self.image_generator:
            logger.info("Generating image...")
            image_path = self.image_generator.generate(prompt, neg_prompt)

        return GeneratedOutput(
            proverb_id=proverb_id,
            proverb_text=proverb_text,
            interpretation=interpretation,
            scene=scene,
            generated_prompt=prompt,
            image_path=image_path,
            clip_score=0.7,  # placeholder — real CLIP scoring requires additional model
            rag_context=rag_context,  # Include retrieved similar proverbs
        )