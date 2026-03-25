# Tunisian Proverbs - Architecture & Evolution

## Current Stack (Active)

### Backend: FastAPI
- `app.py` - REST API server (8 endpoints)
- `database.py` - SQLite + ChromaDB persistence
- `proverb_pipeline_lite.py` - AI/image generation pipeline
- `run.py` - Startup orchestrator

### Frontend: HTML/CSS/JavaScript
- `website/homeTuniSaid.html` - Main UI
- `website/script.js` - Client logic with async polling
- `website/proverbs.json` - 999 Tunisian proverbs dataset

### Configuration
- `config.json` - Runtime settings (device, generation flags, model params)
- `requirements.txt` - Python dependencies

---

## Learning from Previous Iterations

### ✅ Patterns Kept & Evolved

**1. Device Management Strategy** (from `utils/device.py`)
- Originally: Component-specific assignment (GPU→generation, CPU→search)
- Current: Integrated into proverb_pipeline_lite.py with dynamic device selection
- Improvement: Simplified while maintaining efficiency

**2. Model Caching** (from `reasoning/mistral_loader.py`)
- Originally: Used lru_cache for Mistral-7B model
- Current: Lazy-load Phi-2 and SDXL on first use via ProverbPipeline
- Improvement: Handles multiple models, cleaner initialization

**3. Quantization & Memory Optimization** (from `mistral_loader.py`)
- Originally: 4-bit NF4 quantization via bitsandbytes for Mistral
- Current: FP16 precision + sequential CPU offload for SDXL
- Improvement: More suitable for RTX 2050 constraints

**4. RAG Context Retrieval** (from `rag/` folder)
- Originally: Multi-source RAG (ChromaDB collections)
- Current: Single ChromaDB instance with semantic embedding search
- Improvement: Simplified architecture, faster retrieval

**5. Input Validation Pipeline** (from `preprocessing/`)
- Originally: Separate preprocessing + validation modules
- Current: Integrated into PromptBuilder in pipeline
- Improvement: Fewer moving parts, less overhead

### ❌ Why Old Approaches Were Replaced

**Mistral-7B → Phi-2**
- Mistral-7B: 7B params, 14GB VRAM minimum
- Phi-2: 2.7B params, 4GB VRAM (fits RTX 2050)
- Tradeoff: Smaller but still capable for semantic analysis

**Streamlit → FastAPI**
- Streamlit: Heavy UI framework, slow restart, not ideal for image generation
- FastAPI: Lightweight, async support, proper background tasks
- Gain: Faster, more control, better UX

**Standalone Scripts → Unified Pipeline**
- Old: `run_sdxl_prompt.py`, `streamlit_app.py` (separate entry points)
- Current: Single `app.py` handling all requests
- Gain: Single source of truth, no code duplication

---

## File Cleanup

### Deleted (Superseded)
- `reasoning/` - Mistral code (replaced by Phi-2)
- `preprocessing/` - Old validation (integrated into pipeline)
- `rag/` - Old RAG implementation (replaced by ChromaDB in pipeline)
- `streamlit_app.py` - Old UI framework
- `run_sdxl_prompt.py` - Old standalone script
- `website/export.py` - Dataset export utility (not needed at runtime)
- `utils/device.py` - Simplified into pipeline (device mgmt now inline)

### Kept & Active
- **Core Code**: app.py, database.py, proverb_pipeline_lite.py, run.py
- **Data**: website/, data/chromadb/, data/proverbs.db
- **Config**: config.json, requirements.txt
- **Documentation**: README.md (if exists)

---

## Performance Insights

**Model Loading**
- First run: Models download from HuggingFace (~7GB for SDXL, ~5GB for Phi-2)
- Subsequent: Cached locally, ~30-60s for full generation on RTX 2050

**Optimization Chain**
1. Phi-2: 2.7B params (vs 7B for Mistral) → 4GB VRAM
2. SDXL: FP16 dtype + sequential offload → fits in 4GB
3. Embeddings: all-MiniLM-L6-v2 (22M params) → CPU efficient
4. ChromaDB: Local SQLite, no network latency

**Bottleneck**: Image generation (30-60s) → UX shows timer, users know to wait

---

## API Contract (App ↔ Website)

```json
{
  "endpoints": [
    "GET /api/health",
    "GET /api/proverbs?limit=500",
    "GET /api/proverbs/{id}",
    "POST /api/generate (starts async task)",
    "GET /api/generate/{task_id}/status",
    "GET /api/proverbs/{id}/generated",
    "POST /api/search",
    "GET /api/proverbs/{id}/generated"
  ]
}
```

**Website → App**: Polls generation status, displays results when ready
**Database**: SQLite for persistence, ChromaDB for semantic search

