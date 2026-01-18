"""
Device detection utility for auto CPU/GPU switching with component-specific assignment.
"""

import torch


def get_device():
    """
    Detect and return the best available device.
    
    Returns:
        str: "cuda" if GPU is available, otherwise "cpu"
    """
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


def get_device_for_component(component: str):
    """
    Get device assignment for specific components.
    
    Component assignments:
    - LLM inference (Mistral, etc.) → GPU
    - Embeddings → GPU (if available, else CPU)
    - ChromaDB → CPU (always)
    - Preprocessing → CPU (always)
    - Vector search → CPU (always)
    
    Args:
        component: Component name ('llm', 'embeddings', 'chromadb', 'preprocessing', 'vector_search')
        
    Returns:
        str: Device assignment ("cuda" or "cpu")
    """
    component = component.lower()
    
    # Components that should always use CPU
    cpu_only_components = ['chromadb', 'preprocessing', 'vector_search', 'vector_store']
    
    if component in cpu_only_components:
        return "cpu"
    
    # Components that can use GPU if available
    gpu_components = ['llm', 'mistral', 'embeddings', 'clip', 'sdxl', 'generation']
    
    if component in gpu_components:
        return get_device()
    
    # Default to auto-detect
    return get_device()


def get_device_info():
    """
    Get detailed device information.
    
    Returns:
        dict: Device information including name, memory, etc.
    """
    device = get_device()
    info = {
        "device": device,
        "cuda_available": torch.cuda.is_available()
    }
    
    if device == "cuda":
        info["gpu_name"] = torch.cuda.get_device_name(0)
        info["gpu_count"] = torch.cuda.device_count()
        props = torch.cuda.get_device_properties(0)
        info["total_memory_gb"] = props.total_memory / 1e9
        info["cuda_version"] = torch.version.cuda
        info["cudnn_version"] = torch.backends.cudnn.version() if torch.backends.cudnn.is_available() else None
    
    return info


def log_device_info():
    """Print detailed device information."""
    info = get_device_info()
    print("\n" + "="*60)
    print("DEVICE INFORMATION")
    print("="*60)
    print(f"Device: {info['device'].upper()}")
    
    if info['device'] == 'cuda':
        print(f"GPU Name: {info['gpu_name']}")
        print(f"GPU Count: {info['gpu_count']}")
        print(f"Total VRAM: {info['total_memory_gb']:.2f} GB")
        print(f"CUDA Version: {info['cuda_version']}")
        if info['cudnn_version']:
            print(f"cuDNN Version: {info['cudnn_version']}")
        print("\n✅ GPU ACCELERATION ENABLED")
    else:
        print("\n⚠️  No GPU detected - using CPU fallback")
        print("For GPU acceleration, ensure:")
        print("  1. NVIDIA GPU is installed")
        print("  2. CUDA toolkit is installed")
        print("  3. PyTorch with CUDA support is installed")
    
    print("="*60 + "\n")
