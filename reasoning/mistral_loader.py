"""Mistral model loader with automatic CPU/GPU detection and quantization.

This module is performance-sensitive in Streamlit: it can be imported and
executed multiple times due to reruns. To keep the app responsive, we cache the
loaded tokenizer/model per device.
"""

from __future__ import annotations

import importlib
from functools import lru_cache
from typing import Tuple

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

from utils.device import get_device

MODEL_NAME = "mistralai/Mistral-7B-Instruct-v0.2"

_CACHED_DEVICE: str | None = None


def _configure_tokenizer(tokenizer):
    # Many decoder-only models ship without an explicit pad token.
    if getattr(tokenizer, "pad_token_id", None) is None and getattr(tokenizer, "eos_token_id", None) is not None:
        tokenizer.pad_token = tokenizer.eos_token
    return tokenizer


@lru_cache(maxsize=1)
def _load_mistral_cached(device: str) -> Tuple[object, object]:
    print(f"\n{'='*60}")
    print(f"Loading Mistral-7B on {device.upper()}...")
    print(f"{'='*60}")

    tokenizer = _configure_tokenizer(AutoTokenizer.from_pretrained(MODEL_NAME))

    if device == "cuda":
        # Safe speed knobs for inference; may slightly change floating point math but not functionality.
        try:
            torch.backends.cuda.matmul.allow_tf32 = True
            torch.backends.cudnn.allow_tf32 = True
        except Exception:
            pass

        print("🚀 GPU MODE: Enabling optimizations...")
        print("  • Float16 compute dtype")
        print("  • Automatic device mapping")

        bnb_available = False
        try:
            # On Windows bitsandbytes is often unavailable; keep it optional.
            importlib.import_module("bitsandbytes")
            bnb_available = True
        except Exception:
            bnb_available = False

        bnb_config = None
        if bnb_available:
            print("  • 4-bit quantization (NF4) via bitsandbytes")
            bnb_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_compute_dtype=torch.float16,
                bnb_4bit_use_double_quant=True,
            )
        else:
            print("  • bitsandbytes not installed; loading without 4-bit quantization")

        try:
            model_kwargs = {
                "device_map": "auto",
                "dtype": torch.float16,
                "low_cpu_mem_usage": True,
            }
            if bnb_config is not None:
                model_kwargs["quantization_config"] = bnb_config

            model = AutoModelForCausalLM.from_pretrained(MODEL_NAME, **model_kwargs)
            print("✅ Mistral loaded on GPU" + (" (4-bit)" if bnb_config is not None else ""))

            if torch.cuda.is_available():
                memory_allocated = torch.cuda.memory_allocated(0) / 1e9
                memory_reserved = torch.cuda.memory_reserved(0) / 1e9
                print(f"  GPU Memory: {memory_allocated:.2f} GB allocated, {memory_reserved:.2f} GB reserved")

        except Exception as e:
            print(f"⚠️  4-bit loading failed: {e}")
            print("  Falling back to float16 without quantization...")
            model = AutoModelForCausalLM.from_pretrained(
                MODEL_NAME,
                device_map="auto",
                dtype=torch.float16,
                low_cpu_mem_usage=True,
            )
            print("✅ Mistral loaded with float16")
    else:
        print("💻 CPU MODE: Loading with full precision...")
        print("  • Float32 for stability")
        print("  • This will be slower than GPU")

        model = AutoModelForCausalLM.from_pretrained(
            MODEL_NAME,
            device_map={"": "cpu"},
            dtype=torch.float32,
            low_cpu_mem_usage=True,
        )
        print("✅ Mistral loaded on CPU")

    try:
        model.eval()
    except Exception:
        pass

    print(f"{'='*60}\n")
    return tokenizer, model


def load_mistral(force_reload: bool = False):
    """Load Mistral model with automatic device detection.

    - GPU: Uses optional 4-bit quantization + float16 for efficiency
    - CPU: Uses float32 for stability

    Caches the loaded model/tokenizer to avoid repeated reloads.
    """

    device = get_device()
    global _CACHED_DEVICE
    if force_reload or (_CACHED_DEVICE is not None and device != _CACHED_DEVICE):
        _load_mistral_cached.cache_clear()
    _CACHED_DEVICE = device
    return _load_mistral_cached(device)
