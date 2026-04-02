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
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
import json
import logging
import asyncio
from pathlib import Path
import uuid
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

from database import ProverbDatabase
from proverb_pipeline_lite import ProverbPipeline, GeneratedOutput

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Thread pool for running blocking pipeline calls without blocking the event loop
executor = ThreadPoolExecutor(max_workers=1)  # 1 worker: GPU can't run two jobs at once

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

    # Initialize OpenRouter RAG pipeline
    try:
        logger.info("\n" + "=" * 55)
        logger.info("Initializing OpenRouter RAG Pipeline")
        logger.info("=" * 55)
        
        from rag_openrouter_pipeline import initialize_pipeline as init_rag
        init_rag(proverbs_path=proverbs_json)
        
        logger.info("✅ OpenRouter RAG pipeline ready for /api/explain requests")
        logger.info("=" * 55 + "\n")
    except Exception as e:
        logger.error(f"⚠️  RAG pipeline initialization warning: {e}")
        logger.info("OpenRouter /api/explain endpoint will fail - make sure OPENROUTER_API_KEY is set")

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
)

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
    Generate a detailed explanation for a proverb using OpenRouter RAG pipeline.
    
    Uses local FAISS for semantic search to find related proverbs, then uses
    OpenRouter + Qwen to generate a comprehensive explanation with cultural,
    linguistic, and historical context.
    """
    try:
        # Import here to avoid loading models on startup
        from rag_openrouter_pipeline import generate_explanation
        
        proverb_text = request.proverb_text.strip()
        if not proverb_text:
            raise HTTPException(status_code=400, detail="Proverb text is required")
        
        logger.info(f"Generating RAG explanation for: {proverb_text[:50]}")
        
        # Generate explanation using OpenRouter + Qwen (5-10 seconds)
        explanation = generate_explanation(proverb_text, max_tokens=512)
        
        return {
            "proverb": proverb_text,
            "explanation": explanation,
            "source": "openrouter_qwen_rag",
            "timestamp": datetime.now().isoformat()
        }
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


# ─────────────────────────────────────────────
# Root — serve the HTML page
# ─────────────────────────────────────────────

@app.get("/")
async def root():
    html = Path("website/homeTuniSaid.html")
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

        generation_status[task_id] = {"status": "saving", "progress": 80}

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
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")