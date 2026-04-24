# Tunisian Proverbs - Architecture & Current Implementation

## Current Stack (Production)

### Backend: FastAPI (Port 8888)
- `app.py` - REST API server with async processing
- `rag_groq_pipeline.py` - **RAG System**: Groq LLM + FAISS semantic search + Arabic vocabulary enrichment
- `database.py` - SQLite persistence for generated content
- `clip_scorer.py` - **CLIP Score**: Image-text semantic alignment (0-100 scale)
- `proverb_pipeline_lite.py` - Stable Diffusion XL image generation
- `run.py` - Startup orchestrator

### Frontend: HTML/CSS/JavaScript  
- `website/index.html` + `website/homeTuniSaid.html` - Main responsive UI
- `website/script.js` - Client logic (API_BASE = "http://localhost:8888/api")
- `website/proverbs.json` - 999 Tunisian proverbs dataset
- `website/generated/` - Generated images and audio narrations

### Configuration & Data
- `config.json` - Runtime settings
- `requirements.txt` - Python dependencies
- `data/proverbs.db` - SQLite database
- `data/arabic_vocabulary_reference.csv` - Vocabulary for RAG context
- `faiss_vectorstore_proverbs/` - FAISS vector index (persistent)

---

## Generation Pipeline

### 1. **Proverb Retrieval**
```
999 Proverbs (JSON) → Load into FAISS with embeddings (all-MiniLM-L6-v2)
```
- Local semantic search via FAISS
- Top 4 similar proverbs retrieved as context

### 2. **AI Explanation Generation**
```
Proverb + Context → Groq API (Llama 3.3 70B) → Structured Output:
  - explanation (cultural & linguistic context)
  - narrative_story (story embodying the lesson)
  - hidden_meaning (deep spiritual wisdom)
  - moral_lesson (life application)
  - key_phrases (thematic vocabulary)
  - visual_prompt (detailed scene description)
  - visual_summary (concise image description)
```
- **Model**: Llama 3.3 70B (via Groq API)
- **Cost**: FREE (Groq free tier, no rate limits)
- **Speed**: 1-3 seconds per explanation
- **Language Support**: Arabic, French, English

### 3. **Image Generation**
```
visual_prompt (from Groq) → Stable Diffusion XL (HF Inference API) → PNG Image
```
- **Speed**: 5-15 seconds
- **Quality**: SDXL generation with 3-step refinement
- **Rate Limiting**: Token rotation (multiple HF tokens to avoid limits)

### 4. **CLIP Scoring** ✨ NEW
```
Generated Image + visual_prompt → CLIP (openai/clip-vit-base-patch32) → Score (0-100)
```
- **Purpose**: Measure semantic alignment between image and proverb meaning
- **Scale**: 0-100 (0=poor match, 100=perfect alignment)
- **Device**: CUDA if available, else CPU
- **Impact**: Quality metric stored in database for future filtering

### 5. **Feedback Loop** ✨ NEW
```
Generated Content → Embed with FAISS → Add to Index → Persist to Disk
```
- After generation, new insights are added back to FAISS
- Future queries retrieve both original proverbs AND previously generated content
- Enables iterative knowledge base enrichment
- Self-improving system over time

### 6. **Audio Narration**
```
Generated text → gTTS (Arabic) | ElevenLabs (EN/FR) → MP3 Audio
```
- Language-specific voice synthesis
- Stored in `website/generated/`

---

## Key Improvements Over Previous Iterations

### Why Groq API instead of Mistral/Phi-2?
| Aspect | Mistral-7B | Phi-2 | Llama 3.3 70B (Groq) |
|--------|-----------|-------|---------------------|
| Quality | Good | Fair | **Excellent** |
| Speed | Slow (GPU needed) | Medium | **Very Fast** |
| Cost | Free (but GPU) | Free (but GPU) | **Free (cloud)** |
| Setup | Complex | Complex | **Simple** |
| Cultural Understanding | Good | Limited | **Excellent** |

Groq enables us to use a **much larger model (70B) without GPU hardware costs**, with better cultural understanding.

### Why FAISS instead of ChromaDB?
| Aspect | ChromaDB | FAISS |
|--------|----------|-------|
| Setup | Requires server | Lightweight |
| Persistence | Optional | Built-in (`save_local`) |
| Speed | Network latency | Local, instant |
| Scalability | Better for large scale | Better for single-server |
| Integration | Third-party | First-class support |

**Result**: Simpler, faster local semantic search without extra infrastructure.

### CLIP Scoring Benefits
- **Dynamic Quality Metrics**: Know which images represent proverbs well
- **Database Tracking**: All scores stored in SQLite for future analysis
- **User Feedback**: Can show quality indicator in UI
- **Filtering**: Filter results by quality score threshold

### Feedback Loop Benefits
- **Self-Improvement**: Generated insights become future context
- **Knowledge Enrichment**: System learns from its own outputs
- **Cumulative Wisdom**: Each generation makes next generation better
- **Cost Efficiency**: Better results without more API calls

---

## API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/proverbs` | GET | Browse all 999 proverbs |
| `/api/explain` | POST | Generate explanation + story |
| `/api/generate-image` | POST | Create illustration (DEPRECATED) |
| `/api/narrate` | POST | Generate audio narration |
| `/api/clip-score` | POST | Calculate image-text alignment |
| `/api/status` | GET | Generation task progress |
| `/api/content/{id}/clip-score` | GET | Retrieve stored CLIP score |

---

## Performance Characteristics

**Generation Time Breakdown:**
- Proverb retrieval (FAISS): <100ms
- Groq explanation: 1-3 seconds  
- Image generation: 5-15 seconds
- CLIP scoring: 1-2 seconds
- **Total**: 7-20 seconds per full generation

**Storage Requirements:**
- FAISS index: ~500MB
- SQLite database: ~50MB  
- Generated images: ~5MB each
- Generated audio: ~1-2MB each

**Concurrency:**
- FastAPI handles 10+ concurrent requests
- Background task queue for image/audio generation
- Non-blocking feedback loop additions

---

## Data Flow Diagram

```
┌─────────────────┐
│  User Browser   │
└────────┬────────┘
         │ HTTP
         ▼
┌──────────────────────────────┐
│   FastAPI (localhost:8888)   │
├──────────────────────────────┤
│  /api/explain              ◄─┼─ POST: proverb_id, language
│  /api/generate-image        │
│  /api/narrate               │
└──┬─────────────────────────┬┘
   │                         │
   ▼ Query                   ▼ Generate  
┌─────────────┐         ┌────────────────┐
│ FAISS Index │         │  Groq API LLM  │
│  (Semantic) │         │ (Llama 3.3 70B)│
└─────────────┘         └────────────────┘
                               │
                               ▼ visual_prompt
                        ┌────────────────────┐
                        │ Hugging Face SDXL  │
                        │ (Image Generation) │
                        └────────────────────┘
                               │
                               ▼ Image Path
                        ┌────────────────────┐
                        │  CLIP Scorer       │
                        │ (openai/clip)      │
                        └────────────────────┘
                               │
                               ▼ Score (0-100)
                        ┌────────────────────┐
                        │  SQLite Database   │
                        │ (Persist Results)  │
                        └────────────────────┘
                               │
                               ▼ Add to Index
                        ┌────────────────────┐
                        │  FAISS (Feedback)  │
                        │ (Enriched Index)   │
                        └────────────────────┘
```

---

## Configuration

Key settings in `config.json`:
```json
{
  "model_name": "llama-3.3-70b-versatile",
  "temperature": 0.8,
  "max_tokens": 4000,
  "sdxl_device": "cuda",
  "image_gen_enabled": true
}
```

Environment variables in `.env`:
```
GROQ_API_KEY=gsk_...
HF_API_TOKEN=hf_...
ELEVENLABS_API_KEY=sk_...
```

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

