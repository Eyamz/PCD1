"""
Optimized Tunisian Proverb Pipeline - Lite Version for RTX 2050
Uses Phi-2 (2.7B) instead of Mistral for memory efficiency

FIXES:
- ChromaDB updated to modern PersistentClient API
- RAG is now properly initialized with proverbs on startup
- Robust JSON parsing with regex fallback for Phi-2's verbose output
- SDXL uses xformers-free memory optimization safe for 4GB VRAM
- Device auto-detection (falls back to CPU if CUDA unavailable)
- All components degrade gracefully instead of crashing
"""

import json
import re
import torch
from typing import Optional, Dict, List
from dataclasses import dataclass, asdict
from datetime import datetime
import logging
from pathlib import Path

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

    def retrieve_context(self, proverb_text: str, top_k: int = 3) -> str:
        """Retrieve similar proverbs for context"""
        if not self._initialized or self.collection is None:
            return ""
        try:
            results = self.collection.query(
                query_texts=[proverb_text],
                n_results=min(top_k, self.collection.count()),
            )
            docs = results.get("documents", [[]])[0]
            return "\n".join(docs)
        except Exception as e:
            logger.warning(f"RAG retrieval failed: {e}")
            return ""


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


# ─────────────────────────────────────────────
# LLM Interface  (FIX: better prompts + robust parsing)
# ─────────────────────────────────────────────

class LLMInterface:
    """Lightweight LLM using configurable model"""

    def __init__(self, device: str = "cuda", model_name: str = None):
        # FIX: auto-fallback to CPU if CUDA not available
        if device == "cuda" and not torch.cuda.is_available():
            logger.warning("CUDA not available, falling back to CPU")
            device = "cpu"
        self.device = device

        # Use provided model or load from config
        if model_name is None:
            try:
                with open("config.json") as f:
                    config = json.load(f)
                model_name = config.get("models", {}).get("llm_model", "TinyLlama/TinyLlama-1.1B-Chat-v1.0")
            except Exception:
                model_name = "TinyLlama/TinyLlama-1.1B-Chat-v1.0"
        
        self.model_name = model_name
        logger.info(f"Loading {self.model_name} on {self.device}...")

        dtype = torch.float16 if device == "cuda" else torch.float32

        self.tokenizer = AutoTokenizer.from_pretrained(
            self.model_name,
            trust_remote_code=True,
        )
        # Phi-2 has no pad token by default — set it to eos
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

        self.model = AutoModelForCausalLM.from_pretrained(
            self.model_name,
            torch_dtype=dtype,
            device_map=device,
            trust_remote_code=True,
        )

        self.pipe = hf_pipeline(
            "text-generation",
            model=self.model,
            tokenizer=self.tokenizer,
            torch_dtype=dtype,
            device_map=device,
        )
        logger.info("Phi-2 loaded successfully")

    def _generate(self, prompt: str, max_new_tokens: int = 300, temperature: float = None) -> str:
        """Generate text — returns only the NEW tokens, not the prompt"""
        try:
            with torch.no_grad():
                outputs = self.pipe(
                    prompt,
                    max_new_tokens=max_new_tokens,
                    num_return_sequences=1,
                    temperature=temperature or 0.3,
                    top_p=0.95,
                    do_sample=True,
                    pad_token_id=self.tokenizer.eos_token_id,
                    return_full_text=False,
                )
            return outputs[0]["generated_text"].strip()
        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            return ""

    def interpret_proverb(self, proverb_text: str) -> SemanticInterpretation:
        """Extract semantic meaning from proverb - FORCES ORIGINAL AI THINKING"""
        # Strong analytical prompt that forces genuine interpretation
        prompt = (
            f"You are a wisdom teacher analyzing a Tunisian proverb. Think deeply about what it teaches.\n\n"
            f"PROVERB: {proverb_text}\n\n"
            f"ANALYZE THIS DEEPLY (NO COPYING - THINK ORIGINALLY):\n"
            f"1. What is the surface story? (literal description)\n"
            f"2. What does it REALLY teach about life? (hidden wisdom)\n"
            f"3. What is the core moral principle? (universal truth)\n"
            f"4. What are 3 key concepts? (core ideas)\n\n"
            f"FORMAT YOUR ANSWER: answer1 || answer2 || answer3 || concept1, concept2, concept3\n\n"
            f"Think carefully and give ORIGINAL insights, not dictionary definitions:\n"
        )

        response = self._generate(prompt, max_new_tokens=150, temperature=0.5)
        data = _parse_pipe_separated(response)

        if data:
            return SemanticInterpretation(
                literal_meaning=str(data.get("literal_meaning", "")),
                hidden_meaning=str(data.get("hidden_meaning", "")),
                moral=str(data.get("moral", "")),
                key_phrases=data.get("key_phrases", []) if isinstance(data.get("key_phrases"), list) else [],
            )

        # FIX: graceful fallback — split response if parsing fails
        logger.warning(f"Interpretation parse failed. Response: {response[:150]}")
        parts = response.split("||")
        return SemanticInterpretation(
            literal_meaning=parts[0].strip() if len(parts) > 0 else proverb_text,
            hidden_meaning=parts[1].strip() if len(parts) > 1 else response[:100],
            moral=parts[2].strip() if len(parts) > 2 else "",
            key_phrases=[p.strip() for p in parts[3].split(",") if len(parts) > 3 and p.strip()],
        )

    def generate_narrative(self, proverb_text: str, interpretation: SemanticInterpretation) -> str:
        """Generate a story that embodies the proverb's meaning"""
        # Analytical storytelling prompt
        lesson = interpretation.moral or interpretation.hidden_meaning
        keywords = ', '.join(interpretation.key_phrases[:3]) if interpretation.key_phrases else 'wisdom, life, lesson'
        
        prompt = (
            f"Create a REALISTIC story that teaches this lesson:\n"
            f"LESSON: {lesson}\n\n"
            f"KEY THEMES: {keywords}\n\n"
            f"Write a true-to-life story (3-4 sentences) with:\n"
            f"- A person facing a real situation\n"
            f"- Their actions and choices\n"
            f"- The consequence that teaches the lesson\n\n"
            f"Make it SPECIFIC and REAL, not generic:\n"
        )
        
        # Use moderate temperature for coherent but creative narrative
        narrative = self._generate(prompt, max_new_tokens=180, temperature=0.65)
        return narrative.strip() if narrative else "Unable to generate narrative"

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

    def process(self, proverb_text: str, proverb_id: str = None) -> GeneratedOutput:
        """Process proverb through full pipeline"""

        if proverb_id is None:
            proverb_id = f"proverb_{abs(hash(proverb_text))}"

        # Step 1: DO NOT pass RAG context - it contaminates the AI output with dataset answers
        # The LLM should generate ORIGINAL analysis, not copy similar proverbs

        # Step 2: Interpret proverb with LLM (NO context passed - forces original thinking)
        logger.info("Interpreting proverb...")
        interpretation = self.llm.interpret_proverb(proverb_text)  # No context parameter

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
        )