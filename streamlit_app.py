"""Streamlit UI for the proverb → RAG → Mistral reasoning pipeline.

Run:
  streamlit run streamlit_app.py

Notes:
- Model loading is cached via st.cache_resource.
- First run may download Hugging Face models and take a while.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import asdict
from typing import Dict, List, Optional, Tuple

import streamlit as st

from preprocessing.input_validation import sanitize_input, validate_input
from preprocessing.preprocessing import preprocess_text
from rag.retriever import Retriever
from rag.vector_store import VectorStore
from reasoning.mistral_reasoner import MistralReasoner
from run_sdxl_prompt import DEFAULT_SOURCES, RagSource, _best_effort_extract_generated
from utils.device import get_device_info


def _set_env_from_ui(verbose: bool, fast_prompt: bool) -> None:
    os.environ["PCD_VERBOSE"] = "1" if verbose else "0"
    os.environ["PCD_FAST_PROMPT"] = "1" if fast_prompt else "0"


@st.cache_resource(show_spinner=False)
def get_reasoner() -> MistralReasoner:
    reasoner = MistralReasoner()
    reasoner.initialize()
    return reasoner


def build_multirag_context_ui(
    query: str,
    persist_directory: str,
    sources: List[RagSource],
    embedding_model: str = "all-MiniLM-L6-v2",
    on_update=None,
) -> Tuple[str, Dict[str, int]]:
    blocks: List[str] = []
    stats: Dict[str, int] = {}

    for i, src in enumerate(sources):
        try:
            if on_update is not None:
                on_update(f"RAG: {src.collection}…", 0.05 + 0.55 * (i / max(1, len(sources))))

            store = VectorStore(
                persist_directory=persist_directory,
                model_name=embedding_model,
                collection_name=src.collection,
            )
            store.initialize(collection_name=src.collection, on_update=on_update)
            if store.get_collection_count() <= 0:
                stats[src.name] = 0
                continue

            retriever = Retriever(store)
            docs = retriever.retrieve(query, top_k=src.top_k)
            stats[src.name] = len(docs)
            if not docs:
                continue

            if src.name == "previous_generations":
                snippets = [_best_effort_extract_generated(d) for d in docs]
            else:
                snippets = [d.get("text", "") for d in docs]

            joined = "\n\n".join(s.strip() for s in snippets if s and s.strip())
            joined = joined[: src.max_chars]
            if joined.strip():
                blocks.append(f"### {src.name}\n{joined}")
        except Exception:
            stats[src.name] = 0
            continue

    if on_update is not None:
        on_update("RAG: done.", 0.65)

    return "\n\n".join(blocks).strip(), stats


def run_pipeline(
    proverb: str,
    chroma_dir: str,
    collections: List[str],
    max_new_tokens: int,
    max_time_s: int,
    dry_run: bool,
    verbose: bool,
    fast_prompt: bool,
) -> Dict:
    _set_env_from_ui(verbose=verbose, fast_prompt=fast_prompt)

    is_valid, error = validate_input(proverb)
    if not is_valid:
        raise ValueError(error or "Invalid input")

    clean = preprocess_text(sanitize_input(proverb))

    # Restrict sources by selected collections.
    selected = set(collections)
    sources = [s for s in DEFAULT_SOURCES if s.collection in selected]
    if not sources:
        sources = DEFAULT_SOURCES

    progress = st.progress(0)
    status = st.empty()

    def on_update(message: str, p: Optional[float] = None) -> None:
        if message:
            status.write(message)
        if p is not None:
            progress.progress(min(1.0, max(0.0, float(p))))

    # RAG
    context, rag_stats = build_multirag_context_ui(
        clean,
        persist_directory=chroma_dir,
        sources=sources,
        on_update=on_update,
    )

    if dry_run:
        progress.progress(1.0)
        return {
            "query": proverb,
            "rag_stats": rag_stats,
            "context_preview": context[:2000],
        }

    # Reasoning
    on_update("Mistral: initializing…", 0.70)
    reasoner = get_reasoner()

    result = reasoner.reason(
        clean,
        context,
        on_update=on_update,
        max_new_tokens=max_new_tokens,
        max_time_s=max_time_s,
    )

    if isinstance(result, dict):
        result.setdefault("rag_stats", rag_stats)

    progress.progress(1.0)
    status.empty()
    return result


def main() -> None:
    st.set_page_config(page_title="Proverb → Mistral Reasoner", layout="wide")

    st.title("Proverb → RAG → Mistral Reasoner")

    with st.sidebar:
        st.subheader("Runtime")
        dev = get_device_info()
        st.write({k: v for k, v in dev.items() if k != "total_memory_gb"})

        # Your current environment shows torch CPU-only; Mistral-7B will often time out and fall back.
        if not dev.get("cuda_available", False):
            st.warning(
                "CUDA is not available (CPU-only). Mistral-7B is very slow on CPU, so outputs may be generic/fallback. "
                "Enable Fast prompt and increase Max time, or install a CUDA-enabled PyTorch build for real results."
            )

        chroma_dir = st.text_input("ChromaDB directory", value=os.getenv("PCD_CHROMA_DIR", "data/chromadb"))

        st.subheader("Collections")
        default_colls = [s.collection for s in DEFAULT_SOURCES]
        selected = st.multiselect(
            "Query these collections",
            options=default_colls,
            default=default_colls,
        )

        st.subheader("Generation")
        dry_run = st.toggle("Dry run (RAG only)", value=False)
        fast_prompt = st.toggle("Fast prompt (recommended on CPU)", value=not bool(dev.get("cuda_available", False)))
        verbose = st.toggle("Verbose logs", value=False)

        default_time = 360 if not dev.get("cuda_available", False) else 120
        default_tokens = 320 if not dev.get("cuda_available", False) else 640
        max_time_s = st.slider("Max time (seconds)", min_value=30, max_value=600, value=int(default_time), step=30)
        max_new_tokens = st.slider("Max new tokens", min_value=128, max_value=1024, value=int(default_tokens), step=64)

    col1, col2 = st.columns([2, 1])

    with col1:
        proverb = st.text_input(
            "Enter a Tunisian proverb",
            value="اللي ما عندوش كلب يصيد بالقط",
        )

        run = st.button("Run", type="primary")

        if run:
            try:
                start = time.time()
                result = run_pipeline(
                    proverb=proverb,
                    chroma_dir=chroma_dir,
                    collections=selected,
                    max_new_tokens=int(max_new_tokens),
                    max_time_s=int(max_time_s),
                    dry_run=bool(dry_run),
                    verbose=bool(verbose),
                    fast_prompt=bool(fast_prompt),
                )
                elapsed = time.time() - start

                st.success(f"Done in {elapsed:.1f}s")
                st.json(result)

                # Convenience outputs
                if isinstance(result, dict) and "sdxl_prompt" in result:
                    st.subheader("SDXL prompt")
                    st.code(str(result.get("sdxl_prompt") or ""), language="text")

                st.download_button(
                    "Download JSON",
                    data=json.dumps(result, ensure_ascii=False, indent=2),
                    file_name="proverb_reasoning.json",
                    mime="application/json",
                )

            except Exception as e:
                st.error(str(e))

    with col2:
        st.subheader("Tips")
        st.write(
            "- First run can take a while (HF downloads).\n"
            "- If you only have CPU PyTorch, enable **Fast prompt** and lower max tokens/time.\n"
            "- Use **Dry run** to test RAG without loading Mistral."
        )


if __name__ == "__main__":
    main()
