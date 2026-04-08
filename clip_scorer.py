"""
CLIP Score Module - Semantic Similarity between Images and Text
Dynamically calculates how well generated images match the proverb meaning
"""

import logging
import torch
from typing import Optional, Tuple
from PIL import Image
import numpy as np

logger = logging.getLogger(__name__)

class CLIPScorer:
    """
    Calculates semantic similarity between images and text using CLIP model.
    Measures how well generated images represent proverb meanings (0-100 scale).
    """
    
    def __init__(self):
        self.model = None
        self.processor = None
        self.device = None
        self.model_name = "openai/clip-vit-base-patch32"
        self._initialize()
    
    def _initialize(self):
        """Lazy-load CLIP model on first use"""
        try:
            from transformers import CLIPProcessor, CLIPModel
            
            # Determine device
            if torch.cuda.is_available():
                self.device = torch.device("cuda")
                logger.info("🎯 CLIP: Using CUDA (GPU)")
            else:
                self.device = torch.device("cpu")
                logger.info("🎯 CLIP: Using CPU")
            
            # Load model and processor
            logger.info(f"Loading CLIP model: {self.model_name}...")
            self.processor = CLIPProcessor.from_pretrained(self.model_name)
            self.model = CLIPModel.from_pretrained(self.model_name)
            self.model.to(self.device)
            self.model.eval()
            
            logger.info("✅ CLIP model loaded successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize CLIP model: {e}")
            self.model = None
            self.processor = None
    
    def score_image_text_pair(
        self, 
        image_path: str, 
        text: str,
        verbose: bool = False
    ) -> Tuple[float, dict]:
        """
        Calculate CLIP similarity score between image and text.
        
        Args:
            image_path: Path to the generated image
            text: Proverb text or description
            verbose: Return detailed metrics
        
        Returns:
            Tuple of (score_0_100, details_dict)
        """
        
        if not self.model or not self.processor:
            logger.warning("CLIP model not available, returning default score")
            return 50.0, {"error": "Model not initialized", "score_raw": 0.5}
        
        try:
            # Load and prepare image
            image = Image.open(image_path).convert("RGB")
            
            # Prepare text variations for context
            text_variations = [
                text,
                f"represents {text}",
                f"depicts the meaning of: {text}",
                f"illustrates: {text}",
                f"visualizes: {text}"
            ]
            
            # Tokenize and compute embeddings
            with torch.no_grad():
                # Image embedding
                image_inputs = self.processor(
                    images=image, 
                    return_tensors="pt",
                    padding=True,
                    truncation=True
                ).to(self.device)
                image_features = self.model.get_image_features(**image_inputs)
                
                # Text embeddings (batch process all variations)
                text_inputs = self.processor(
                    text=text_variations,
                    return_tensors="pt",
                    padding=True,
                    truncation=True
                ).to(self.device)
                text_features = self.model.get_text_features(**text_inputs)
                
                # Normalize features
                image_features = image_features / image_features.norm(p=2, dim=-1, keepdim=True)
                text_features = text_features / text_features.norm(p=2, dim=-1, keepdim=True)
                
                # Compute similarity scores
                similarity_scores = (image_features @ text_features.T)[0].cpu().numpy()
                
                # Get max similarity and average
                max_similarity = float(np.max(similarity_scores))
                avg_similarity = float(np.mean(similarity_scores))
                
                # Convert to 0-100 scale
                score_100 = max_similarity * 100
                
                details = {
                    "score_raw": max_similarity,
                    "score_normalized": score_100,
                    "similarities": {
                        f"var_{i}": float(s) * 100 
                        for i, s in enumerate(similarity_scores)
                    },
                    "max_sim": max_similarity,
                    "avg_sim": avg_similarity,
                    "model": self.model_name,
                    "status": "success"
                }
                
                if verbose:
                    logger.info(f"📊 CLIP Score: {score_100:.1f}/100 | Raw: {max_similarity:.3f}")
                
                return score_100, details
        
        except Exception as e:
            logger.error(f"Error computing CLIP score: {e}")
            return 50.0, {"error": str(e), "score_raw": 0.5}
    
    def batch_score_images(
        self,
        image_paths: list,
        texts: list,
    ) -> list:
        """
        Score multiple image-text pairs efficiently.
        
        Args:
            image_paths: List of image paths
            texts: List of text descriptions
        
        Returns:
            List of (score, details) tuples
        """
        results = []
        for img_path, text in zip(image_paths, texts):
            score, details = self.score_image_text_pair(img_path, text)
            results.append({
                "image": img_path,
                "text": text,
                "score": score,
                "details": details
            })
        return results
    
    def get_quality_label(self, score: float) -> Tuple[str, str]:
        """
        Convert numeric score to quality label and emoji.
        
        Args:
            score: Score 0-100
        
        Returns:
            Tuple of (label, emoji)
        """
        if score >= 85:
            return "Excellent", "🟢"
        elif score >= 70:
            return "Good", "🟡"
        elif score >= 50:
            return "Fair", "🟠"
        else:
            return "Needs Improvement", "🔴"


# Global instance
_clip_scorer: Optional[CLIPScorer] = None

def get_scorer() -> CLIPScorer:
    """Get or create global CLIP scorer instance"""
    global _clip_scorer
    if _clip_scorer is None:
        _clip_scorer = CLIPScorer()
    return _clip_scorer

def calculate_clip_score(image_path: str, text: str) -> Tuple[float, dict]:
    """
    Quick interface to calculate CLIP score.
    
    Args:
        image_path: Path to image
        text: Text to compare against
    
    Returns:
        Tuple of (score_0_100, details)
    """
    scorer = get_scorer()
    return scorer.score_image_text_pair(image_path, text, verbose=True)
