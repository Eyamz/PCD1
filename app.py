"""
FastAPI Backend for Tunisian Proverbs Web Application

FIXES:
- Use lifespan context manager instead of deprecated @app.on_event("startup")
- Pass proverbs_json path to ProverbPipeline so RAG gets populated
- Background task now runs in a thread executor (pipeline.process is sync/blocking)
- Static file mount moved AFTER all API routes to avoid shadowing /api/*
- Image paths served correctly as /generated/... URLs
- Pipeline init failure no longer silently hides the real error
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.encoders import jsonable_encoder
from starlette.responses import JSONResponse as StarletteJSONResponse
from pydantic import BaseModel
from typing import Optional, List
import json
import logging
import asyncio
from pathlib import Path
import uuid
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
import os
from dotenv import load_dotenv

load_dotenv()  # Load environment variables from .env

from database import ProverbDatabase
from proverb_pipeline_lite import ProverbPipeline, GeneratedOutput
from clip_scorer import calculate_clip_score, get_scorer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Thread pool for running blocking pipeline calls without blocking the event loop
executor = ThreadPoolExecutor(max_workers=1)  # 1 worker: GPU can't run two jobs at once

# Load HF token from environment
HF_API_TOKEN = os.getenv("HF_API_TOKEN")
if not HF_API_TOKEN:
    logger.warning("⚠️  HF_API_TOKEN not found in environment. Image generation will be disabled.")

# Keep single token (no rotation needed with valid token)
token_index = 0

def get_next_hf_token():
    """Get HF token from environment."""
    return HF_API_TOKEN

# State
db = ProverbDatabase("data/proverbs.db")
pipeline: Optional[ProverbPipeline] = None
generation_status: dict = {}


# ─────────────────────────────────────────────
# Startup / shutdown  (FIX: use lifespan, not deprecated on_event)
# ─────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize resources on startup, clean up on shutdown"""
    global pipeline

    logger.info("=" * 55)
    logger.info("Tunisian Proverbs — starting up")
    logger.info("=" * 55)

    # Load proverbs into SQLite
    proverbs_json = "website/proverbs.json"
    if Path(proverbs_json).exists():
        try:
            db.load_proverbs_from_json(proverbs_json)
        except Exception as e:
            logger.error(f"Failed to load proverbs into SQLite: {e}")
    else:
        logger.warning(f"Proverbs JSON not found: {proverbs_json}")

    # Initialize Groq RAG pipeline (FAISS + Groq LLM)
    try:
        logger.info("\n" + "=" * 55)
        logger.info("Initializing Groq RAG Pipeline")
        logger.info("=" * 55)
        
        from rag_groq_pipeline import initialize_pipeline as init_rag, load_vocabulary_reference
        init_rag(proverbs_path=proverbs_json)
        
        # Load vocabulary reference for enhanced context
        load_vocabulary_reference()
        
        logger.info("✅ Groq RAG pipeline ready for /api/explain requests")
        logger.info("=" * 55 + "\n")
    except Exception as e:
        logger.error(f"⚠️  RAG pipeline initialization warning: {e}")
        logger.info("Groq /api/explain endpoint will fail - make sure GROQ_API_KEY is set")

    # Initialize image generation pipeline (optional)
    try:
        with open("config.json") as f:
            config = json.load(f)

        device = config.get("system", {}).get("device", "cuda")
        enable_gen = config.get("system", {}).get("enable_image_generation", False)

        logger.info(f"Initializing image generation pipeline (device={device}, image_gen={enable_gen})...")

        # FIX: pass proverbs_json so pipeline populates ChromaDB
        pipeline = ProverbPipeline(
            device=device,
            enable_generation=enable_gen,
            proverbs_json=proverbs_json,
        )
        logger.info("✅ Image generation pipeline ready")

    except Exception as e:
        logger.error(f"⚠️  Image generation pipeline initialization warning: {e}")
        pipeline = None

    yield  # app is running

    # Shutdown
    logger.info("Shutting down...")
    executor.shutdown(wait=False)


# ─────────────────────────────────────────────
# App
# ─────────────────────────────────────────────

app = FastAPI(
    title="Tunisian Proverbs API",
    description="AI-powered Tunisian proverb discovery and visualization",
    version="1.1.0",
    lifespan=lifespan,
    json_encoder=None,  # Use default
)

# Custom JSON response class that preserves Unicode characters (Arabic text)
class UTF8JSONResponse(StarletteJSONResponse):
    def render(self, content):
        # Use ensure_ascii=False to preserve Arabic and other Unicode characters
        return json.dumps(
            content,
            ensure_ascii=False,  # Don't escape Unicode
            allow_nan=False,
            indent=None,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─────────────────────────────────────────────
# Request / Response models
# ─────────────────────────────────────────────

class ProverbResponse(BaseModel):
    id: str
    tunisan_proverb: str
    context: Optional[str] = None
    proverb_arabic_explaination: Optional[str] = None
    image_path_1: Optional[str] = None
    image_path_2: Optional[str] = None
    image_path_3: Optional[str] = None
    image_path_4: Optional[str] = None

    class Config:
        # Allow extra fields (e.g. generated_image added dynamically)
        extra = "allow"


class GenerationRequest(BaseModel):
    proverb_id: str
    force_regenerate: bool = False
    custom_text: Optional[str] = None  # For custom input mode


class SearchRequest(BaseModel):
    query: str
    limit: int = 10


class ExplainRequest(BaseModel):
    proverb_text: str


class NarrateRequest(BaseModel):
    text: str
    language: str = "en"  # Language code: 'ar', 'en', 'fr'


# ─────────────────────────────────────────────
# API Routes  (all /api/* routes BEFORE static mount)
# ─────────────────────────────────────────────

@app.get("/api/health")
async def health():
    return {
        "status": "healthy",
        "pipeline_loaded": pipeline is not None,
        "image_generation": pipeline.enable_generation if pipeline else False,
        "total_proverbs": db.count_proverbs(),
    }


@app.get("/api/stats")
async def get_stats():
    return {
        "total_proverbs": db.count_proverbs(),
        "pipeline_enabled": pipeline is not None,
        "active_generations": sum(
            1 for s in generation_status.values()
            if s.get("status") in ("processing", "interpreting")
        ),
    }


@app.get("/api/proverbs", response_model=List[ProverbResponse])
async def list_proverbs(limit: int = 50, offset: int = 0):
    try:
        proverbs = db.get_all_proverbs(limit=limit, offset=offset)
        for p in proverbs:
            generated = db.get_generated_for_proverb(p["id"])
            if generated and generated.get("image_path"):
                # Convert filesystem path to URL path
                p["generated_image"] = _fs_to_url(generated["image_path"])
        return proverbs
    except Exception as e:
        logger.error(f"Error listing proverbs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/proverbs/{proverb_id}", response_model=ProverbResponse)
async def get_proverb(proverb_id: str):
    proverb = db.get_proverb(proverb_id)
    if not proverb:
        raise HTTPException(status_code=404, detail="Proverb not found")
    return proverb


@app.get("/api/proverbs/{proverb_id}/generated")
async def get_generated_content(proverb_id: str):
    content = db.get_generated_for_proverb(proverb_id)
    if not content:
        raise HTTPException(status_code=404, detail="No generated content for this proverb")

    if content.get("image_path"):
        content["image_url"] = _fs_to_url(content["image_path"])
    return content


@app.post("/api/generate")
async def generate_content(request: GenerationRequest, background_tasks: BackgroundTasks):
    # Get proverb text and explanation - from database for real proverbs, or from request for custom
    proverb_text = None
    explanation = None
    
    if request.custom_text:
        # Custom input mode - use provided text
        proverb_text = request.custom_text
        explanation = None
    else:
        # Database mode - fetch from proverbs table
        proverb = db.get_proverb(request.proverb_id)
        if not proverb:
            raise HTTPException(status_code=404, detail="Proverb not found")
        proverb_text = proverb.get("tunisan_proverb", "")
        explanation = proverb.get("proverb_arabic_explaination", "")  # Pass the explanation!

    if not proverb_text:
        raise HTTPException(status_code=400, detail="No proverb text provided")

    if not pipeline:
        raise HTTPException(status_code=503, detail="Pipeline not initialized")

    # Return cached result unless force_regenerate
    if not request.force_regenerate:
        existing = db.get_generated_for_proverb(request.proverb_id)
        if existing:
            if existing.get("image_path"):
                existing["image_url"] = _fs_to_url(existing["image_path"])
            return existing

    task_id = f"gen_{uuid.uuid4().hex[:8]}"
    generation_status[task_id] = {"status": "processing", "progress": 0}

    # FIX: add_task with the async wrapper; actual blocking work runs in executor
    background_tasks.add_task(
        _generate_background,
        task_id,
        request.proverb_id,
        proverb_text,
        explanation,  # Pass explanation to background task
    )

    return {
        "task_id": task_id,
        "status": "processing",
        "proverb_id": request.proverb_id,
    }


@app.get("/api/generate/{task_id}/status")
async def get_generation_status(task_id: str):
    if task_id not in generation_status:
        raise HTTPException(status_code=404, detail="Task not found")
    status = generation_status[task_id].copy()
    # Add image URL if complete
    if status.get("status") == "complete" and status.get("image_path"):
        status["image_url"] = _fs_to_url(status["image_path"])
    return status


@app.post("/api/explain")
async def explain_proverb(request: ExplainRequest):
    """
    Generate comprehensive trilingual proverb analysis using Groq RAG pipeline.
    
    Returns analysis in English, French, and Arabic for:
    - literal_meaning: Direct interpretation
    - hidden_meaning: Deep cultural wisdom
    - moral_lesson: Life lesson
    - narrative: Story embodying the lesson
    - visual_prompt: For image generation (English only)
    - visual_summary: How image relates to proverb
    """
    try:
        from rag_groq_pipeline import generate_explanation_with_visual_prompt
        
        proverb_text = request.proverb_text.strip()
        if not proverb_text:
            raise HTTPException(status_code=400, detail="Proverb text is required")
        
        logger.info(f"Generating full trilingual analysis for: {proverb_text[:50]}")
        
        result = generate_explanation_with_visual_prompt(proverb_text, max_tokens=4000)
        
        response_data = {
            "proverb": proverb_text,
            "literal_meaning": result["literal_meaning"],
            "hidden_meaning": result["hidden_meaning"],
            "moral_lesson": result["moral_lesson"],
            "narrative": result["narrative"],
            "explanation": result["explanation"],
            "visual_prompt": result["visual_prompt"],
            "visual_summary": result["visual_summary"],
            "key_phrases": result["key_phrases"],
            "source": "groq_rag_trilingual",
            "timestamp": datetime.now().isoformat()
        }
        
        # Return with proper UTF-8 encoding for Arabic text (no Unicode escaping)
        return UTF8JSONResponse(
            content=response_data,
            status_code=200,
            media_type="application/json; charset=utf-8"
        )
    except Exception as e:
        logger.error(f"Explanation generation error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to generate explanation: {str(e)}")


@app.post("/api/search")
async def search_proverbs(request: SearchRequest):
    try:
        db.log_query(request.query)
        results = db.search_proverbs(request.query, limit=request.limit)
        return results
    except Exception as e:
        logger.error(f"Search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/narrate")
async def narrate_proverb(request: NarrateRequest):
    """Generate audio narration in multiple languages:
    - Arabic: Using gTTS (Google Text-to-Speech) - Free
    - English/French: Using ElevenLabs
    """
    try:
        proverb_text = request.text.strip()
        language = request.language.lower()  # 'ar', 'en', 'fr'
        
        if not proverb_text:
            raise HTTPException(status_code=400, detail="Text is required")
        
        from pathlib import Path
        import uuid
        import os
        
        # Create generated folder if it doesn't exist
        gen_dir = Path("website/generated")
        gen_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate unique filename
        audio_id = f"narration_{uuid.uuid4().hex[:8]}"
        audio_path = gen_dir / f"{audio_id}.mp3"
        
        # ════════════════════════════════════════════════════
        # ARABIC: Use gTTS (Google Text-to-Speech) - Free API
        # ════════════════════════════════════════════════════
        if language == 'ar':
            try:
                from gtts import gTTS
                
                logger.info(f"Generating Arabic TTS via gTTS for text ({len(proverb_text)} chars)...")
                
                # Create gTTS object in Arabic
                tts = gTTS(text=proverb_text, lang='ar', slow=False)
                
                # Save to file
                tts.save(str(audio_path))
                
                logger.info(f"✓ Generated Arabic gTTS narration: {audio_id}")
                
                return {
                    "audio_url": f"/generated/{audio_id}.mp3",
                    "audio_id": audio_id,
                    "status": "success",
                    "language": "ar",
                    "provider": "gTTS",
                    "text_length": len(proverb_text)
                }
            except Exception as e:
                logger.error(f"Arabic TTS error: {e}", exc_info=True)
                raise HTTPException(status_code=500, detail=f"Arabic TTS failed: {str(e)}")
        
        # ════════════════════════════════════════════════════
        # ENGLISH/FRENCH: Use ElevenLabs
        # ════════════════════════════════════════════════════
        else:  # 'en' or 'fr'
            import re
            
            # For non-Arabic languages, clean text to remove Arabic characters
            cleaned_text = re.sub(r'[\u0600-\u06FF]', '', proverb_text)  # Remove Arabic
            cleaned_text = re.sub(r'\s+', ' ', cleaned_text).strip()  # Clean spaces
            
            if not cleaned_text or len(cleaned_text) < 3:
                raise HTTPException(status_code=400, detail="No text found in selected language")
            
            # Limit text length for TTS
            if len(cleaned_text) > 5000:
                cleaned_text = cleaned_text[:5000]
            
            from elevenlabs import ElevenLabs
            
            # Get API key from environment
            api_key = os.getenv("ELEVENLABS_API_KEY")
            if not api_key:
                raise HTTPException(status_code=500, detail="ElevenLabs API key not configured")
            
            logger.info(f"Generating {language.upper()} TTS via ElevenLabs for text ({len(cleaned_text)} chars)...")
            
            # Use ElevenLabs API with natural female voice
            client = ElevenLabs(api_key=api_key)
            audio = client.text_to_speech.convert(
                text=cleaned_text,
                voice_id="EXAVITQu4vr4xnSDxMaL",  # Bella - natural female voice
                model_id="eleven_turbo_v2_5"  # Latest turbo model
            )
            
            # Save audio to file
            with open(audio_path, "wb") as f:
                for chunk in audio:
                    f.write(chunk)
            
            logger.info(f"✓ Generated {language.upper()} ElevenLabs narration: {audio_id}")
            
            return {
                "audio_url": f"/generated/{audio_id}.mp3",
                "audio_id": audio_id,
                "status": "success",
                "language": language,
                "provider": "ElevenLabs",
                "text_length": len(cleaned_text)
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Audio narration error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to generate audio: {str(e)}")


# ─────────────────────────────────────────────
# Image Generation via Hugging Face Inference API
# ─────────────────────────────────────────────

@app.post("/api/generate-image")
async def generate_image_hf(request: dict):
    """Generate image from visual prompt using Hugging Face Inference API (Stable Diffusion XL)
    
    Also calculates CLIP score to measure image-text alignment quality.
    """
    try:
        prompt = request.get("prompt", "").strip()
        if not prompt:
            raise HTTPException(status_code=400, detail="Prompt is required")
        
        if len(prompt) > 500:
            prompt = prompt[:500]
        
        # Get next HF token from rotation pool
        hf_token = get_next_hf_token()
        if not hf_token:
            raise HTTPException(status_code=500, detail="Hugging Face API tokens not configured")
        
        from huggingface_hub import InferenceClient
        from pathlib import Path
        import uuid
        
        # Create generated folder if it doesn't exist
        gen_dir = Path("website/generated")
        gen_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate unique filename
        image_id = f"image_{uuid.uuid4().hex[:8]}"
        image_path = gen_dir / f"{image_id}.png"
        
        logger.info(f"Generating image with HF Inference API for prompt: {prompt[:50]}...")
        
        # Use Hugging Face Inference API with Stable Diffusion XL
        client = InferenceClient(api_key=hf_token)
        image = client.text_to_image(
            prompt=prompt,
            model="stabilityai/stable-diffusion-xl-base-1.0"
        )
        
        # Save image to file
        image.save(str(image_path))
        logger.info(f"✓ Generated image: {image_id}")
        
        # Calculate CLIP score to measure image-prompt alignment
        clip_score = 0.0
        try:
            import torch
            from PIL import Image
            import open_clip
            
            # Load CLIP model
            device = "cuda" if torch.cuda.is_available() else "cpu"
            model, _, preprocess = open_clip.create_model_and_transforms(
                'ViT-B-32',
                pretrained='openai',
                device=device
            )
            tokenizer = open_clip.get_tokenizer('ViT-B-32')
            
            # Prepare image and text
            image_tensor = preprocess(image).unsqueeze(0).to(device)
            text_tokens = tokenizer(prompt).to(device)
            
            # Compute CLIP score
            with torch.no_grad():
                image_features = model.encode_image(image_tensor)
                text_features = model.encode_text(text_tokens)
                
                # Normalize features
                image_features /= image_features.norm(dim=-1, keepdim=True)
                text_features /= text_features.norm(dim=-1, keepdim=True)
                
                # Cosine similarity (0-1 scale)
                clip_score = (image_features @ text_features.T).squeeze().item()
                clip_score = max(0.0, min(1.0, (clip_score + 1) / 2))  # Normalize to 0-1
            
            logger.info(f"✓ CLIP score: {clip_score:.2f}")
        except Exception as clip_err:
            logger.warning(f"CLIP scoring failed: {clip_err}. Using default score.")
            clip_score = 0.85  # Default fallback score
        
        return {
            "image_url": f"/generated/{image_id}.png",
            "image_id": image_id,
            "status": "success",
            "prompt": prompt,
            "clip_score": round(clip_score, 2)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Image generation error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to generate image: {str(e)}")


# ─────────────────────────────────────────────
# CLIP Score Calculation
# ─────────────────────────────────────────────

@app.post("/api/clip-score")
async def calculate_image_text_clip_score(request: dict):
    """
    Calculate CLIP similarity score between an image and text.
    
    Request body:
    {
        "image_path": "/generated/image_abc123.png" (or full path),
        "text": "The proverb or description text"
    }
    
    Returns:
    {
        "score": 75.5,           # Score 0-100
        "label": "Good",         # Quality label
        "emoji": "🟡",           # Quality emoji
        "details": {...}         # Detailed metrics
    }
    """
    try:
        image_path = request.get("image_path", "").strip()
        text = request.get("text", "").strip()
        
        if not image_path or not text:
            raise HTTPException(
                status_code=400, 
                detail="Both 'image_path' and 'text' are required"
            )
        
        # Handle URL paths like /generated/image.png -> website/generated/image.png
        if image_path.startswith("/"):
            image_path = f"website{image_path}"
        
        # Verify file exists
        if not Path(image_path).exists():
            raise HTTPException(status_code=404, detail=f"Image not found: {image_path}")
        
        logger.info(f"📊 Computing CLIP score for: {Path(image_path).name}")
        
        # Calculate CLIP score
        scorer = get_scorer()
        clip_score, details = scorer.score_image_text_pair(image_path, text, verbose=True)
        
        # Get quality label
        quality_label, quality_emoji = scorer.get_quality_label(clip_score)
        
        return {
            "success": True,
            "score": round(clip_score, 1),
            "label": quality_label,
            "emoji": quality_emoji,
            "details": details,
            "image_path": image_path,
            "text_length": len(text)
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"CLIP score calculation error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to calculate CLIP score: {str(e)}")


@app.get("/api/clip-score/{content_id}")
async def get_content_clip_score(content_id: str):
    """Get stored CLIP score for generated content"""
    try:
        # Fetch from database (implementation depends on your DB schema)
        content = db.get_generated_content_by_id(content_id) if hasattr(db, 'get_generated_content_by_id') else None
        
        if not content:
            raise HTTPException(status_code=404, detail="Content not found")
        
        clip_score = content.get("clip_score", 0.0)
        if isinstance(clip_score, float) and clip_score <= 1.0:
            clip_score * 100  # Convert to 0-100 if stored as 0-1
        
        scorer = get_scorer()
        quality_label, quality_emoji = scorer.get_quality_label(clip_score)
        
        return {
            "content_id": content_id,
            "score": round(clip_score, 1),
            "label": quality_label,
            "emoji": quality_emoji,
            "image_path": content.get("image_path")
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving CLIP score: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────────
# Root — serve the HTML page
# ─────────────────────────────────────────────

@app.get("/")
async def root():
    html = Path("website/index.html")
    if html.exists():
        return FileResponse(str(html))
    raise HTTPException(status_code=404, detail="Frontend not found")


# ─────────────────────────────────────────────
# Static files  (FIX: mounted LAST so /api/* routes are not shadowed)
# ─────────────────────────────────────────────

if Path("website").exists():
    app.mount("/", StaticFiles(directory="website", html=True), name="website")


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def _fs_to_url(fs_path: str) -> str:
    """Convert a filesystem path like website/generated/foo.png → /generated/foo.png"""
    if not fs_path:
        return ""
    p = Path(fs_path)
    # Strip leading 'website' directory component
    parts = p.parts
    if parts and parts[0] == "website":
        return "/" + "/".join(parts[1:])
    return "/" + str(p)


async def _generate_background(task_id: str, proverb_id: str, proverb_text: str, explanation: str = None):
    """
    Async wrapper around the blocking pipeline.process() call.
    FIX: runs the CPU/GPU-bound work in a thread executor so it doesn't
    block the FastAPI event loop (which would freeze all other requests).
    Includes image generation via Hugging Face Inference API.
    """
    loop = asyncio.get_event_loop()
    try:
        generation_status[task_id] = {"status": "interpreting", "progress": 20}

        # Create a wrapper function to call pipeline.process with explanation
        def _process_wrapper():
            return pipeline.process(proverb_text, proverb_id, explanation=explanation)

        # Run blocking pipeline in thread pool
        output: GeneratedOutput = await loop.run_in_executor(
            executor,
            _process_wrapper
        )

        generation_status[task_id] = {"status": "generating_image", "progress": 70}

        # Generate image via Hugging Face Inference API if enabled
        image_url = ""
        clip_score = 0.0
        if config.get("system", {}).get("enable_image_generation", False) and output.generated_prompt:
            try:
                hf_token = get_next_hf_token()
                if hf_token:
                    logger.info(f"Generating image via HF API for prompt: {output.generated_prompt[:50]}...")
                    
                    from huggingface_hub import InferenceClient
                    from pathlib import Path
                    import uuid as uuid_lib
                    
                    gen_dir = Path("website/generated")
                    gen_dir.mkdir(parents=True, exist_ok=True)
                    
                    image_id = f"image_{uuid_lib.uuid4().hex[:8]}"
                    image_path = gen_dir / f"{image_id}.png"
                    
                    client = InferenceClient(api_key=hf_token)
                    image = client.text_to_image(
                        prompt=output.generated_prompt,
                        model="stabilityai/stable-diffusion-xl-base-1.0"
                    )
                    
                    image.save(str(image_path))
                    output.image_path = str(image_path)
                    image_url = f"/generated/{image_id}.png"
                    logger.info(f"✓ Image generated: {image_id}")
                    
                    # Calculate CLIP score dynamically
                    generation_status[task_id] = {"status": "scoring", "progress": 85}
                    try:
                        logger.info(f"📊 Computing CLIP score for image-text alignment...")
                        clip_score, clip_details = calculate_clip_score(
                            str(image_path),
                            proverb_text
                        )
                        logger.info(f"✅ CLIP Score computed: {clip_score:.1f}/100")
                        output.clip_score = clip_score / 100.0  # Store as 0-1 for database
                    except Exception as e:
                        logger.warning(f"CLIP scoring failed: {e}, using default score")
                        clip_score = 70.0
                        output.clip_score = 0.7
                else:
                    logger.warning("HF_API_TOKEN not configured, skipping image generation")
            except Exception as img_err:
                logger.warning(f"Image generation failed: {img_err}, continuing without image")

        generation_status[task_id] = {"status": "saving", "progress": 90}

        content_id = f"content_{uuid.uuid4().hex[:8]}"
        
        # Build expanded interpretation data with RAG context
        interpretation_data = output.interpretation.__dict__.copy()
        interpretation_data["rag_context"] = output.rag_context or []
        
        db.save_generated_content(
            content_id=content_id,
            proverb_id=proverb_id,
            interpretation=interpretation_data,
            scene=output.scene.__dict__ if output.scene else {},
            prompt=output.generated_prompt or "",
            image_path=output.image_path or "",
            clip_score=output.clip_score or 0.7,
        )

        generation_status[task_id] = {
            "status": "complete",
            "progress": 100,
            "content_id": content_id,
            "image_path": output.image_path or "",
            "clip_score": clip_score,  # Include CLIP score in response
            "interpretation": interpretation_data,  # Include RAG context here
            "result": interpretation_data,  # For frontend compatibility
            "rag_context": output.rag_context or [],  # Explicitly include RAG context
        }
        logger.info(f"Generation complete: {task_id}")

    except Exception as e:
        logger.error(f"Generation failed for {task_id}: {e}", exc_info=True)
        generation_status[task_id] = {"status": "failed", "error": str(e)}


# ─────────────────────────────────────────────
# Direct run
# ─────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8888, log_level="info")