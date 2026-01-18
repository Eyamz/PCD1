"""
Preprocessing module for proverb data processing.
Device: CPU (always)
"""

from utils.device import get_device_for_component

# Preprocessing always runs on CPU
PREPROCESSING_DEVICE = get_device_for_component('preprocessing')


def preprocess_text(text: str) -> str:
    """
    Preprocess input text for further processing.
    Runs on CPU.
    
    Args:
        text: Raw input text
        
    Returns:
        Preprocessed text
    """
    # CPU-based preprocessing
    return text.strip()


def extract_proverbs(document: str) -> list:
    """
    Extract proverbs from a document.
    
    Args:
        document: Input document text
        
    Returns:
        List of extracted proverbs
    """
    # Add proverb extraction logic here
    return []
