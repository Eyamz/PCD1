# Proverb Reasoner → SDXL Prompt (Multi‑RAG + Mistral)

This repo is a minimal, **reasoning-only** tool that takes a Tunisian proverb and produces a **structured JSON** output that includes:

- Human-facing interpretation fields (meaning, life lesson, usage example, etc.)
- A **CLIP-oriented SDXL prompt** (`sdxl_prompt`) suitable for image generation

It reuses your existing local **ChromaDB** database for retrieval (multi‑RAG) and runs **Mistral 7B Instruct** for reasoning (GPU if available).

## Quickstart (Windows)

From the project folder:

```powershell
pip install -r requirements.txt
```

Single proverb (prints JSON and exits):

```powershell
$env:PCD_PRETTY="1"; C:/Users/eyamz/OneDrive/Desktop/pcd/.venv/Scripts/python.exe C:/Users/eyamz/OneDrive/Desktop/pcd/run_sdxl_prompt.py "اللي ما عندوش كلب يصيد بالقط"
```

Interactive mode (loads Mistral once, then you paste many proverbs):

```powershell
$env:PCD_PRETTY="1"; C:/Users/eyamz/OneDrive/Desktop/pcd/.venv/Scripts/python.exe C:/Users/eyamz/OneDrive/Desktop/pcd/run_sdxl_prompt.py --repl
```

If you only want to verify retrieval (no model run):

```powershell
$env:PCD_PRETTY="1"; C:/Users/eyamz/OneDrive/Desktop/pcd/.venv/Scripts/python.exe C:/Users/eyamz/OneDrive/Desktop/pcd/run_sdxl_prompt.py --dry-run "اختبار"
```

## What This Project Does (Pipeline)

The entrypoint is [run_sdxl_prompt.py](run_sdxl_prompt.py). For each proverb it executes:

1) **Input validation**
    - Rejects empty/too-long/obviously invalid input.
    - Normalizes the text (light preprocessing).

2) **Multi‑RAG retrieval from local ChromaDB**
    - Queries multiple ChromaDB collections.
    - Skips a collection if it doesn’t exist or is empty.
    - Concatenates the best matching snippets into a single context block.

3) **LLM reasoning (Mistral 7B Instruct)**
    - Builds a strict prompt that asks the model to produce **JSON only**.
    - The prompt is designed to generate a single-scene, concrete, CLIP-friendly SDXL prompt.

4) **Output**
    - Prints the full JSON object to stdout.
    - Adds `rag_stats` in the CLI path so you can see whether retrieval returned anything.

## Repo Layout

```
pcd/
├── run_sdxl_prompt.py          # CLI entrypoint (single-run, dry-run, REPL)
├── requirements.txt
├── README.md
├── data/
│   └── chromadb/               # Existing ChromaDB DB (persisted locally)
├── preprocessing/
│   ├── input_validation.py     # validate_input(), sanitize_input()
│   └── preprocessing.py        # preprocess_text()
├── rag/
│   ├── vector_store.py         # ChromaDB client + embedder
│   └── retriever.py            # top-k retrieval wrapper
├── reasoning/
│   ├── mistral_loader.py       # cached tokenizer/model loading
│   └── mistral_reasoner.py     # prompt + generate + JSON parsing/repair
└── utils/
     └── device.py               # CPU/GPU selection
```

## Multi‑RAG Collections (ChromaDB)

By default the tool attempts these collections (and skips any missing/empty ones):

- `tunisian_generated`: previously generated proverb → prompt pairs (used as “good examples” context)
- `tunisian_proverbs`: a proverb corpus for semantic grounding
- `tunisian_cultural_pdfs`: optional cultural/background text

You can override which collections participate:

```powershell
$env:PCD_COLLECTIONS="tunisian_generated,tunisian_proverbs";
C:/Users/eyamz/OneDrive/Desktop/pcd/.venv/Scripts/python.exe C:/Users/eyamz/OneDrive/Desktop/pcd/run_sdxl_prompt.py "..."
```

## Configuration

Environment variables:

- `PCD_CHROMA_DIR` (default: `data/chromadb`) — where the persistent ChromaDB lives
- `PCD_COLLECTIONS` — comma-separated list to restrict which collections are queried
- `PCD_PRETTY=1` — pretty JSON output
- `PCD_VERBOSE=1` — show internal logs (otherwise they’re suppressed so JSON stays clean)

CLI flags (see `--help`):

- `--dry-run` retrieval only
- `--repl` interactive loop
- `--pretty` and `--verbose` equivalents of the env vars
- `--chroma-dir` overrides the Chroma path

## Output Schema

The tool prints a single JSON object. The keys are designed to be stable for downstream code.

Core keys:

- `proverb`
- `literal_translation`
- `core_meaning`
- `life_lesson`
- `usage_example`
- `scene_description`
- `scene_elements`
- `metaphor_and_mood`
- `art_style`
- `story`
- `sdxl_prompt` (the prompt you feed to SDXL)

CLI-only diagnostic key:

- `rag_stats` (e.g. how many hits came back per collection)

## Notes on Performance

- Model loading is cached within the running process. REPL mode exists specifically to avoid reloading Mistral for each proverb.
- First run may be slow because Hugging Face assets are downloaded and the model is initialized.

## Troubleshooting

**REPL prints “Loading Mistral…” and seems stuck**
- First load can take minutes (model download + GPU init). Try `PCD_VERBOSE=1` to see progress.

**No GPU / GPU not used**
- The tool will fall back to CPU if CUDA isn’t available.
- On Windows, `bitsandbytes` is often unavailable; the loader supports it optionally.

**Install CUDA-enabled PyTorch (Windows)**

If `torch.cuda.is_available()` is `False`, you likely installed a CPU-only PyTorch wheel.

In your project venv, reinstall PyTorch from the CUDA wheel index (example: CUDA 12.4):

```powershell
python -m pip uninstall -y torch
python -m pip install --index-url https://download.pytorch.org/whl/cu124 torch
python -c "import torch; print(torch.__version__); print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else None)"
```

If you’re not sure which CUDA wheel index to use, check the official selector on https://pytorch.org.

**ChromaDB returns 0 hits**
- Confirm `data/chromadb` exists and contains your collections.
- Try `--dry-run` to see what retrieval is returning.

## For Coworkers (What to Run)

- “Give me JSON for one proverb”: run [run_sdxl_prompt.py](run_sdxl_prompt.py) with a proverb string.
- “Let me test many proverbs quickly”: run with `--repl`.
- “Only test retrieval”: run with `--dry-run`.
