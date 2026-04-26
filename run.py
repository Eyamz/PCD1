#!/usr/bin/env python3
"""
Startup script for Tunisian Proverbs Web Application

FIXES:
- Checks for CUDA availability and warns clearly if not present
- Checks config.json and prints active settings before starting
- Clears stale ChromaDB lock files that can block restarts
- Better error messages with actionable instructions
"""

import sys
import os
import logging
import json
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

REQUIRED_PACKAGES = [
    "fastapi",
    "uvicorn",
    "torch",
    "transformers",
    "chromadb",
    "sentence_transformers",
    "diffusers",
    "accelerate",
    "PIL",       # pillow
]


def check_requirements() -> bool:
    logger.info("Checking Python packages...")
    missing = []
    for pkg in REQUIRED_PACKAGES:
        try:
            __import__(pkg)
            logger.info(f"  ✓ {pkg}")
        except ImportError:
            logger.error(f"  ✗ {pkg}  ← MISSING")
            missing.append(pkg)

    if missing:
        logger.error("")
        logger.error("Install missing packages:")
        logger.error("  pip install -r requirements.txt")
        return False

    logger.info("All packages present")
    return True


def check_cuda():
    """Warn if CUDA is unavailable — pipeline will fall back to CPU (slow)"""
    try:
        import torch
        if torch.cuda.is_available():
            name = torch.cuda.get_device_name(0)
            vram = torch.cuda.get_device_properties(0).total_memory / 1024**3
            logger.info(f"GPU: {name}  ({vram:.1f} GB VRAM)")
        else:
            logger.warning("CUDA not available — pipeline will run on CPU (very slow)")
            logger.warning("Set device=cpu in config.json and disable image generation")
    except Exception:
        pass


def ensure_directories():
    dirs = ["data", "data/chromadb", "website/generated", "logs"]
    for d in dirs:
        Path(d).mkdir(parents=True, exist_ok=True)
    logger.info("Data directories ready")


def clear_chromadb_locks():
    """Remove stale lock files that prevent ChromaDB from starting after a crash"""
    lock_files = list(Path("data/chromadb").glob("*.lock"))
    for lf in lock_files:
        try:
            lf.unlink()
            logger.info(f"Cleared stale lock: {lf}")
        except Exception:
            pass


def check_proverbs() -> bool:
    path = Path("website/proverbs.json")
    if not path.exists():
        logger.error(f"Proverbs data not found: {path}")
        logger.error("Place your proverbs.json inside the website/ folder")
        return False
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        logger.info(f"Proverbs dataset: {len(data)} entries")
        return True
    except json.JSONDecodeError as e:
        logger.error(f"proverbs.json is invalid JSON: {e}")
        return False


def load_and_print_config() -> dict:
    path = Path("config.json")
    if not path.exists():
        logger.warning("config.json not found — using defaults")
        return {}
    with open(path) as f:
        config = json.load(f)

    system = config.get("system", {})
    logger.info(f"Config  device={system.get('device','cuda')}  "
                f"image_gen={system.get('enable_image_generation', False)}")
    return config


def main():
    logger.info("=" * 55)
    logger.info("  Tunisian Proverbs — Web Application")
    logger.info("=" * 55)

    if not check_requirements():
        sys.exit(1)

    check_cuda()
    ensure_directories()
    clear_chromadb_locks()

    if not check_proverbs():
        sys.exit(1)

    config = load_and_print_config()

    api = config.get("api", {})
    host = api.get("host", "0.0.0.0")
    port = api.get("port", 8000)

    logger.info("=" * 55)
    logger.info(f"Starting server at  http://localhost:{port}")
    logger.info("Press Ctrl+C to stop")
    logger.info("=" * 55)

    try:
        import uvicorn
        from app import app
        uvicorn.run(
            app,
            host=host,
            port=port,
            log_level="info",
            reload=api.get("debug", False),
        )
    except KeyboardInterrupt:
        logger.info("Server stopped")
    except Exception as e:
        logger.error(f"Server failed to start: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()