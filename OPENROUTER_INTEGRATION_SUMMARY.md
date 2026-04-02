╔══════════════════════════════════════════════════════════════════════════════╗
║     OPENROUTER + QWEN 3.6+ INTEGRATION - FILE COORDINATION SUMMARY           ║
║                           ✅ All Systems Connected                           ║
╚══════════════════════════════════════════════════════════════════════════════╝

🎯 PROJECT SCOPE
────────────────
Replace: Llama 2 RAG (local GPU inference)
With:    OpenRouter + Qwen 3.6+ (API-based, no GPU needed)

Architecture:
  • Retrieval:   Local FAISS (CPU-only, sentence-transformers embeddings)
  • Generation:  OpenRouter API (Qwen 3.6+ model)
  • Website:     HTML/CSS/JS frontend displaying AIoT explanations

═══════════════════════════════════════════════════════════════════════════════

📋 ACTIVE PIPELINE FILES
========================

✅ rag_openrouter_pipeline.py (PRIMARY - IN USE)
   ├─ Functions:
   │  ├─ initialize_pipeline() → Loads FAISS + validates OpenRouter API key
   │  ├─ generate_explanation(proverb) → RAG + Qwen generation
   │  ├─ retrieve_context(proverb) → FAISS semantic search
   │  └─ build_prompt(proverb, context) → Crafts Qwen prompt
   │
   ├─ Dependencies:
   │  ├─ langchain (FAISS vector store)
   │  ├─ sentence-transformers (embeddings)
   │  ├─ requests (OpenRouter API calls)
   │  └─ python-dotenv (load .env)
   │
   └─ Configuration:
      └─ API Key: Loads from environment var OPENROUTER_API_KEY
         (can be set in .env file or system env)

═══════════════════════════════════════════════════════════════════════════════

📚 SUPPORTING FILES
===================

✅ .env (CONFIGURATION)
   ├─ OPENROUTER_API_KEY=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
   └─ Status: Loaded by python-dotenv on startup

✅ requirements.txt (DEPENDENCIES)
   ├─ Added:      python-dotenv, requests
   ├─ Removed:    bitsandbytes (was for local Llama 2 quantization)
   ├─ Kept:       langchain, sentence-transformers, faiss-cpu
   └─ Image Gen:  torch, transformers, diffusers (for TinyLlama image pipeline)

✅ app.py (FASTAPI BACKEND)
   ├─ Startup (lifespan):
   │  └─ Line 72: from rag_openrouter_pipeline import initialize_pipeline as init_rag
   │     Initializes FAISS + validates OpenRouter API key on app startup
   │
   └─ API Endpoint:
      └─ POST /api/explain (Line 297)
         ├─ Accepts: {"proverb_text": "..."}
         ├─ Calls: generate_explanation() from rag_openrouter_pipeline
         ├─ Returns: {"proverb": "...", "explanation": "...", "source": "openrouter_qwen_rag", "timestamp": "..."}
         └─ Response Time: ~5-10 seconds (Qwen inference time)

═══════════════════════════════════════════════════════════════════════════════

🌐 WEBSITE INTEGRATION
======================

✅ website/homeTuniSaid.html
   └─ Buttons/Actions:
      ├─ "Explore a Proverb" → displays proverb list
      ├─ "Enter a Proverb" → custom proverb input
      └─ Auto-triggers RAG explanation fetch (via JavaScript)

✅ website/script.js
   ├─ Function: fetchAndDisplayRAGExplanation(proverbText)
   │  ├─ Line 544: fetch(`${API_BASE}/explain`, POST with proverb_text)
   │  └─ Triggered automatically after proverb display
   │
   └─ Function: displayRAGExplanation(explanation)
      ├─ Creates card with header: "✨ Qwen 3.6+ AI Explanation"
      ├─ Formats text with paragraph breaks
      └─ Appends to results-grid on page

✅ website/homeTuniSaid.css
   ├─ Class: .rag-explanation-text
   │  └─ Styling for explanation display (already exists)
   └─ Card layout: .result-card (shared with other results)

═══════════════════════════════════════════════════════════════════════════════

⚠️  LEGACY FILES (KEPT AS BACKUP)
==================================

📦 rag_llama2_pipeline.py (BACKUP - DO NOT USE)
   ├─ Status: Marked as legacy/backup in docstring
   ├─ Reason: Kept for reference if we ever revert to local Llama 2
   ├─ Uses: Local GPU inference (Llama 2 7B)
   ├─ Why deprecated: Too slow, requires GPU+auth, expensive in compute
   └─ Migration: All callers switched to rag_openrouter_pipeline.py

📦 proverb_pipeline_lite.py (IMAGE GENERATION PIPELINE)
   ├─ Status: Still active for image generation (separate feature)
   ├─ Model: TinyLlama-1.1B-Chat-v1.0 (for story/narrative generation)
   ├─ Integration: Handled by app.py's ProverbPipeline class
   └─ Note: Does NOT use RAG - separate from explanation pipeline

═══════════════════════════════════════════════════════════════════════════════

🔄 DATA FLOW DIAGRAM
====================

User clicks "Explore a Proverb"
    ↓
JavaScript displayProverb() fetches proverb from database
    ↓
Triggers fetchAndDisplayRAGExplanation(proverb_text)
    ↓
POST to /api/explain with {"proverb_text": "..."}
    ↓
app.py /api/explain endpoint
    ↓
Calls: from rag_openrouter_pipeline import generate_explanation
    ↓
generate_explanation() executes:
   1. retrieve_context() → FAISS semantic search (local, ~100ms)
   2. build_prompt() → Format prompt with context
   3. requests.post() → OpenRouter API call (Qwen 3.6+) (~5-10s)
   4. Parse response → Extract explanation text
    ↓
Returns JSON: {"proverb": "...", "explanation": "...", "source": "openrouter_qwen_rag"}
    ↓
script.js displayRAGExplanation() creates card in results-grid
    ↓
User sees: Proverb + Story + Explanation (Qwen-generated)

═══════════════════════════════════════════════════════════════════════════════

✅ FILE COORDINATION STATUS
===========================

Communication Paths:
[✓] app.py → rag_openrouter_pipeline.py (import at lines 72, 297)
[✓] rag_openrouter_pipeline.py → FAISS local (no external calls)
[✓] rag_openrouter_pipeline.py → OpenRouter API (requests.post)
[✓] script.js → app.py /api/explain endpoint (fetch)
[✓] .env → rag_openrouter_pipeline.py (OPENROUTER_API_KEY)
[✓] run.py → app.py (uvicorn startup)
[✓] proverb_pipeline_lite.py → independent (image gen only)
[✓] database.py → independent (no RAG dependency)

No Circular Dependencies: ✓
All Imports Correct: ✓
Legacy File Isolated: ✓

═══════════════════════════════════════════════════════════════════════════════

🚀 HOW TO RUN
=============

1. Set API Key (already in .env):
   OPENROUTER_API_KEY=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

2. Install dependencies:
   pip install -r requirements.txt

3. Start server:
   python -m uvicorn app:app --host 127.0.0.1 --port 8000

4. Open website:
   http://127.0.0.1:8000/
   or http://localhost:8000/

5. Click "Explore a Proverb" or "Enter a Proverb"
   → Explanation auto-fetches from OpenRouter
   → Displays in card with "✨ Qwen 3.6+ AI Explanation"

═══════════════════════════════════════════════════════════════════════════════

📊 PERFORMANCE EXPECTATIONS
============================

Latency per Proverb:
  ├─ FAISS Retrieval:      ~100ms (local CPU)
  ├─ Prompt Building:      ~10ms  (local)
  ├─ OpenRouter API Call:  ~5-10s (network + Qwen inference)
  └─ Total:                ~5-10 seconds per explanation

Cost per Explanation:
  ├─ Model: Qwen 3.6+ :free tier
  ├─ Typical tokens: ~250 prompt + 200 completion
  └─ Cost: FREE (OpenRouter $5 starter credit)

Memory Usage:
  ├─ FAISS vectorstore: ~50MB
  ├─ Embeddings model: ~30MB
  ├─ FAISS index: ~20MB
  └─ Total: ~100MB (vs 4GB+ for local Llama 2)

═══════════════════════════════════════════════════════════════════════════════

✨ READY FOR PRODUCTION
=======================

All files are coordinated and integrated.
✅ Backend ready
✅ Frontend ready
✅ API keys configured
✅ Dependencies specified
✅ Legacy files isolated

You can now run the application!

═══════════════════════════════════════════════════════════════════════════════
