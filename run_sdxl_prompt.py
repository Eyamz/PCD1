"""Reasoning-only entrypoint.

Goal:
- Validate input
- Retrieve helpful context from existing ChromaDB collections (multi-RAG)
- Run Mistral reasoning (GPU if available)
- Output the full structured reasoning JSON (including `sdxl_prompt`)

Usage:
  python run_sdxl_prompt.py "اللي ما عندوش كلب يصيد بالقط"
    python run_sdxl_prompt.py --repl

Optional env vars:
  PCD_CHROMA_DIR=data/chromadb
  PCD_COLLECTIONS=tunisian_generated,tunisian_proverbs,tunisian_cultural_pdfs
    PCD_PRETTY=1  (pretty-print JSON)
    PCD_VERBOSE=1 (show internal logs)
"""

from __future__ import annotations

import json
import os
import sys
import io
import contextlib
import argparse
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple

from preprocessing.input_validation import sanitize_input, validate_input
from preprocessing.preprocessing import preprocess_text
from rag.retriever import Retriever
from rag.vector_store import VectorStore
from reasoning.mistral_reasoner import MistralReasoner


@dataclass
class RagSource:
    name: str
    collection: str
    top_k: int = 4
    max_chars: int = 1400


DEFAULT_SOURCES: List[RagSource] = [
    RagSource(name="previous_generations", collection="tunisian_generated", top_k=6, max_chars=2200),
    RagSource(name="proverbs", collection="tunisian_proverbs", top_k=4, max_chars=1400),
    RagSource(name="pdf_corpus", collection="tunisian_cultural_pdfs", top_k=3, max_chars=1600),
]


def _parse_csv_env(value: str) -> List[str]:
    return [v.strip() for v in (value or "").split(",") if v.strip()]


def _best_effort_extract_generated(doc: Dict) -> str:
    """Turn a stored generated JSON payload into useful context."""

    text = doc.get("text") or ""
    meta = doc.get("metadata") or {}

    # Many of your generated docs store the reasoning JSON as the document text.
    try:
        payload = json.loads(text)
        if isinstance(payload, dict):
            proverb = payload.get("proverb") or meta.get("proverb") or ""
            sdxl_prompt = payload.get("sdxl_prompt") or meta.get("image_prompt") or ""
            core = payload.get("core_meaning") or payload.get("interpretation") or ""
            style = payload.get("art_style") or ""
            clip = meta.get("clip_score")
            image_path = meta.get("image_path")

            lines = []
            if proverb:
                lines.append(f"Proverb: {proverb}")
            if core:
                lines.append(f"Meaning: {core}")
            if style:
                lines.append(f"Style: {style}")
            if sdxl_prompt:
                lines.append(f"SDXL prompt used: {sdxl_prompt}")
            if clip is not None:
                lines.append(f"CLIP score: {clip}")
            if image_path:
                lines.append(f"Image path: {image_path}")

            return "\n".join(lines).strip()
    except Exception:
        pass

    # Fallback: keep whatever text exists, but trimmed.
    return str(text).strip()


def build_multirag_context(
    query: str,
    persist_directory: str,
    embedding_model: str = "all-MiniLM-L6-v2",
    sources: Optional[List[RagSource]] = None,
) -> Tuple[str, Dict[str, int]]:
    """Retrieve context from multiple ChromaDB collections.

    If a collection is missing/empty/unavailable, it is skipped.

    Returns:
        (context_text, stats)
    """

    sources = sources or DEFAULT_SOURCES
    blocks: List[str] = []
    stats: Dict[str, int] = {}

    for src in sources:
        try:
            store = VectorStore(persist_directory=persist_directory, model_name=embedding_model, collection_name=src.collection)
            store.initialize(collection_name=src.collection)
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
            # Skip silently: user asked to skip if nothing helpful is available.
            stats[src.name] = 0
            continue

    return "\n\n".join(blocks).strip(), stats


def generate_reasoning(
    proverb: str,
    persist_directory: str = "data/chromadb",
    collections: Optional[Iterable[str]] = None,
    max_new_tokens: int = 640,
    max_time_s: int = 120,
) -> Dict:
    """Main API: returns the full reasoning output dict."""

    is_valid, error = validate_input(proverb)
    if not is_valid:
        raise ValueError(error or "Invalid input")

    clean = preprocess_text(sanitize_input(proverb))

    verbose = os.getenv("PCD_VERBOSE", "").strip() in {"1", "true", "True", "yes", "YES"}

    # Allow overriding which collections participate.
    sources = DEFAULT_SOURCES
    if collections is not None:
        coll = set(collections)
        sources = [s for s in DEFAULT_SOURCES if s.collection in coll]

    # Keep stdout clean: user wants ONLY the final JSON as output.
    # Internal progress/noise goes to /dev/null unless PCD_VERBOSE=1.
    sink = None if verbose else io.StringIO()
    with contextlib.redirect_stdout(sink or sys.stdout), contextlib.redirect_stderr(sink or sys.stderr):
        context, _stats = build_multirag_context(clean, persist_directory=persist_directory, sources=sources)

        reasoner = MistralReasoner()
        reasoner.initialize()

        result = reasoner.reason(clean, context, max_new_tokens=max_new_tokens, max_time_s=max_time_s)

    if not isinstance(result, dict) or not result:
        raise RuntimeError("Model did not produce a structured reasoning output")

    return result


def _env_truthy(name: str) -> bool:
    return os.getenv(name, "").strip() in {"1", "true", "True", "yes", "YES"}


def _print_json(obj: Dict, pretty: bool) -> None:
    if pretty:
        sys.stdout.write(json.dumps(obj, ensure_ascii=False, indent=2))
    else:
        sys.stdout.write(json.dumps(obj, ensure_ascii=False))


def main(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(description="Generate full reasoning JSON for a Tunisian proverb (includes sdxl_prompt).")
    parser.add_argument(
        "proverb",
        nargs="*",
        help="Tunisian proverb text. If it contains spaces, you can either quote it or pass it as multiple words.",
    )
    parser.add_argument("--chroma-dir", default=os.getenv("PCD_CHROMA_DIR", "data/chromadb"), help="ChromaDB persist directory")
    parser.add_argument(
        "--collections",
        default=os.getenv("PCD_COLLECTIONS", ""),
        help="Comma-separated collection override (default uses built-ins)",
    )
    parser.add_argument("--pretty", action="store_true", default=_env_truthy("PCD_PRETTY"), help="Pretty-print JSON")
    parser.add_argument("--verbose", action="store_true", default=_env_truthy("PCD_VERBOSE"), help="Show internal logs")
    parser.add_argument(
        "--max-new-tokens",
        type=int,
        default=int(os.getenv("PCD_MAX_NEW_TOKENS", "640")),
        help="Max new tokens to generate (default: 640).",
    )
    parser.add_argument(
        "--max-time",
        type=int,
        default=int(os.getenv("PCD_MAX_TIME_S", "120")),
        help="Maximum generation time in seconds (default: 120).",
    )
    parser.add_argument("--dry-run", action="store_true", help="Only test multi-RAG retrieval; do not run Mistral")
    parser.add_argument("--repl", action="store_true", help="Interactive mode (keeps model loaded between queries)")
    args = parser.parse_args(argv[1:])

    collections = _parse_csv_env(args.collections) if args.collections else None
    pretty = bool(args.pretty)

    if args.repl:
        # Interactive loop keeps model loaded in this process.
        if not sys.stdin.isatty():
            sys.stderr.write(
                "REPL mode requires an interactive terminal (TTY).\n"
                "Run without --repl to process a single proverb, or run this from a normal VS Code terminal.\n"
            )
            return 2

        sys.stdout.write("Loading Mistral (first run can take a while)...\n")
        sys.stdout.flush()

        sink = None if args.verbose else io.StringIO()
        with contextlib.redirect_stdout(sink or sys.stdout), contextlib.redirect_stderr(sink or sys.stderr):
            reasoner = MistralReasoner()
            reasoner.initialize()

        sys.stdout.write("Ready. Type a proverb, or 'quit'.\n")
        sys.stdout.flush()

        while True:
            try:
                line = input("Proverb> ").strip()
            except (EOFError, KeyboardInterrupt):
                return 0
            if not line:
                continue
            if line.lower() in {"exit", "quit"}:
                return 0

            # RAG context
            clean = preprocess_text(sanitize_input(line))
            sink = None if args.verbose else io.StringIO()
            with contextlib.redirect_stdout(sink or sys.stdout), contextlib.redirect_stderr(sink or sys.stderr):
                context, stats = build_multirag_context(clean, persist_directory=args.chroma_dir, sources=None)
                result = reasoner.reason(
                    clean,
                    context,
                    max_new_tokens=int(args.max_new_tokens),
                    max_time_s=int(args.max_time),
                )
            if isinstance(result, dict):
                # Attach stats so you can see if RAG helped.
                result.setdefault("rag_stats", stats)
                _print_json(result, pretty=pretty)
                sys.stdout.write("\n")
            else:
                sys.stdout.write(str(result) + "\n")

    if not args.proverb:
        parser.print_usage()
        return 2

    proverb = " ".join(args.proverb).strip()
    if not proverb:
        parser.print_usage()
        return 2

    if args.dry_run:
        clean = preprocess_text(sanitize_input(proverb))
        sink = None if args.verbose else io.StringIO()
        with contextlib.redirect_stdout(sink or sys.stdout), contextlib.redirect_stderr(sink or sys.stderr):
            context, stats = build_multirag_context(clean, persist_directory=args.chroma_dir, sources=None)
        _print_json({"query": proverb, "rag_stats": stats, "context_preview": context[:800]}, pretty=pretty)
        return 0

    # Full run
    result = generate_reasoning(
        proverb,
        persist_directory=args.chroma_dir,
        collections=collections,
        max_new_tokens=int(args.max_new_tokens),
        max_time_s=int(args.max_time),
    )
    # Attach RAG stats (helpful for debugging / iterating on retrieval).
    try:
        clean = preprocess_text(sanitize_input(proverb))
        sink = None if args.verbose else io.StringIO()
        with contextlib.redirect_stdout(sink or sys.stdout), contextlib.redirect_stderr(sink or sys.stderr):
            _ctx, stats = build_multirag_context(clean, persist_directory=args.chroma_dir, sources=None)
        if isinstance(result, dict):
            result.setdefault("rag_stats", stats)
    except Exception:
        pass

    _print_json(result, pretty=pretty)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
