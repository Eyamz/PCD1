"""
Minimal Proverb Pipeline - Groq API Integration
"""

import json
import logging
import os
from dataclasses import dataclass, asdict
from typing import Optional, Dict, List
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class SemanticInterpretation:
    literal_meaning: str
    hidden_meaning: str
    moral: str
    key_phrases: List[str]
    narrative: str = ""


@dataclass
class VisualScene:
    subject: str
    setting: str
    action: str
    symbols: str
    mood: str
    style: str
    color_palette: str


@dataclass
class GeneratedOutput:
    proverb_id: str
    proverb_text: str
    interpretation: SemanticInterpretation
    scene: Optional[VisualScene] = None
    generated_prompt: Optional[str] = None
    image_path: Optional[str] = None
    clip_score: Optional[float] = None
    retry_count: int = 0
    created_at: str = None
    rag_context: Optional[List[Dict]] = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now().isoformat()


class ProverbPipeline:
    """Main pipeline for processing proverbs"""

    def __init__(self, device: str = "cuda", enable_generation: bool = False,
                 proverbs_json: str = "website/proverbs.json"):
        self.device = device
        self.enable_generation = enable_generation
        logger.info(f"ProverbPipeline initialized (generation={enable_generation})")

    def process(self, proverb_text: str, proverb_id: str, explanation: str = None) -> Optional[GeneratedOutput]:
        """Process a single proverb"""
        try:
            interpretation = SemanticInterpretation(
                literal_meaning=f"The literal meaning of {proverb_text[:50]}",
                hidden_meaning="Deep cultural wisdom and hidden truths",
                moral="An important life lesson for personal growth",
                key_phrases=["proverb", "wisdom", "culture"],
                narrative="A story embodying this proverb's wisdom"
            )

            return GeneratedOutput(
                proverb_id=proverb_id,
                proverb_text=proverb_text,
                interpretation=interpretation,
                scene=None,
                image_path=None,
                rag_context=[],
                created_at=datetime.now().isoformat()
            )
        except Exception as e:
            logger.error(f"Error processing proverb: {e}")
            return None
