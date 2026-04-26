"""
Batch CLIP Score Calculator - Process multiple image-prompt pairs efficiently
Uses HuggingFace Inference API for real semantic similarity scoring
"""

import logging
import numpy as np
import torch
from typing import List, Tuple, Union
from pathlib import Path

logger = logging.getLogger(__name__)


def calculate_clip_score(
    images: Union[np.ndarray, torch.Tensor],
    prompts: List[str],
    hf_token: str = None,
    model_name: str = "openai/clip-vit-base-patch32"
) -> np.ndarray:
    """
    Calculate CLIP scores for a batch of images and prompts.
    
    Args:
        images: Batch of images as numpy array or tensor
                Expected shape: (batch_size, height, width, 3) with values in [0, 1] or [0, 255]
                or (batch_size, 3, height, width) as torch tensor
        prompts: List of text prompts (one per image)
        hf_token: HuggingFace API token for Inference API
        model_name: CLIP model to use (default: openai/clip-vit-base-patch32)
    
    Returns:
        numpy array of CLIP scores in range [0, 1], shape (batch_size,)
    
    Example:
        >>> images = np.random.rand(4, 512, 512, 3)  # 4 images
        >>> prompts = ["a cat", "a dog", "a bird", "a tree"]
        >>> scores = calculate_clip_score(images, prompts, hf_token="hf_...")
        >>> print(scores)  # [0.75, 0.82, 0.68, 0.71]
    """
    
    if not hf_token:
        logger.error("HF_TOKEN required for CLIP scoring")
        raise ValueError("hf_token must be provided")
    
    from huggingface_hub import InferenceClient
    
    # Convert torch tensor to numpy if needed
    if isinstance(images, torch.Tensor):
        images = images.cpu().numpy()
    
    # Validate input shape
    if len(images.shape) != 4:
        raise ValueError(f"Expected 4D array, got shape {images.shape}")
    
    batch_size = images.shape[0]
    
    # Check if images are in CHW or HWC format
    if images.shape[1] == 3:
        # CHW format - convert to HWC
        images = images.transpose(0, 2, 3, 1)
    
    # Normalize to [0, 255] uint8 if in [0, 1] range
    if images.max() <= 1.0:
        images_uint8 = (images * 255).astype("uint8")
    else:
        images_uint8 = images.astype("uint8")
    
    logger.info(f"Processing batch of {batch_size} images with {len(prompts)} prompts")
    
    if batch_size != len(prompts):
        raise ValueError(
            f"Number of images ({batch_size}) must match number of prompts ({len(prompts)})"
        )
    
    # Initialize HF client
    client = InferenceClient(api_key=hf_token)
    
    clip_scores = np.zeros(batch_size)
    
    # Process each image-prompt pair
    for i, (img, prompt) in enumerate(zip(images_uint8, prompts)):
        try:
            # Extract image embedding (pass numpy array as first positional argument)
            image_embedding = client.feature_extraction(img, model=model_name)
            
            # Extract text embedding
            text_embedding = client.feature_extraction(prompt, model=model_name)
            
            # Normalize embeddings
            img_emb = np.array(image_embedding).flatten()
            text_emb = np.array(text_embedding).flatten()
            
            img_emb = img_emb / (np.linalg.norm(img_emb) + 1e-8)
            text_emb = text_emb / (np.linalg.norm(text_emb) + 1e-8)
            
            # Compute cosine similarity
            similarity = float(np.dot(img_emb, text_emb))
            
            # Convert to [0, 1] scale
            score = (similarity + 1.0) / 2.0
            clip_scores[i] = np.clip(score, 0.0, 1.0)
            
            logger.info(f"[{i+1}/{batch_size}] Prompt: '{prompt[:50]}...' → CLIP Score: {clip_scores[i]:.2f}")
            
        except Exception as e:
            logger.warning(f"Error processing image {i}: {e}. Using fallback score 0.5")
            clip_scores[i] = 0.5
    
    return clip_scores


def calculate_clip_scores_from_paths(
    image_paths: List[str],
    prompts: List[str],
    hf_token: str = None,
    model_name: str = "openai/clip-vit-base-patch32"
) -> np.ndarray:
    """
    Calculate CLIP scores from image file paths.
    
    Args:
        image_paths: List of paths to image files
        prompts: List of text prompts (one per image)
        hf_token: HuggingFace API token
        model_name: CLIP model name
    
    Returns:
        numpy array of CLIP scores in range [0, 1]
    """
    from PIL import Image
    
    images = []
    for path in image_paths:
        img = Image.open(path).convert("RGB")
        img_array = np.array(img).astype("uint8")
        images.append(img_array)
    
    images = np.array(images)
    return calculate_clip_score(images, prompts, hf_token, model_name)


# Compatibility with existing code
def batch_clip_score(
    image_tensors: Union[np.ndarray, torch.Tensor],
    text_prompts: List[str],
    clip_score_fn=None,
    hf_token: str = None
) -> np.ndarray:
    """
    Legacy interface for batch CLIP scoring.
    
    Args:
        image_tensors: Batch of images [B, H, W, 3] in range [0, 1]
        text_prompts: List of prompts
        clip_score_fn: (deprecated, for compatibility)
        hf_token: HuggingFace token
    
    Returns:
        Array of scores
    """
    return calculate_clip_score(image_tensors, text_prompts, hf_token)
