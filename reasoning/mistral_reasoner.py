"""Mistral-based reasoning module with auto CPU/GPU switching.

Important: This module must not load large models at import time.
Streamlit imports modules eagerly, so model loading is deferred to
MistralReasoner.initialize().
"""

from __future__ import annotations

import json
import re
from typing import Dict, Optional, Tuple

import torch

from reasoning.mistral_loader import load_mistral


class MistralReasoner:
    """
    Reasoning module using Mistral models.
    """
    
    def __init__(self):
        """
        Initialize Mistral reasoner.

        Model loading is deferred to initialize().
        """
        self.tokenizer = None
        self.model = None
        self._initialized = False
    
    def initialize(self):
        """
        Initialize Mistral model and tokenizer.
        """
        if self._initialized:
            return

        self.tokenizer, self.model = load_mistral()
        self._initialized = True

    def _infer_input_device(self) -> str:
        """Choose an input device compatible with the loaded model.

        With `device_map="auto"`, the model may be partially on CPU even if CUDA exists.
        Sending inputs to CUDA in that case will crash with device-mismatch errors.
        """

        if self.model is None:
            return "cuda" if torch.cuda.is_available() else "cpu"

        # Best signal: device of the input embedding weights.
        # With Accelerate offloading, this is what inputs must match.
        try:
            emb = self.model.get_input_embeddings()  # type: ignore[attr-defined]
            weight = getattr(emb, "weight", None)
            if isinstance(weight, torch.Tensor):
                d = weight.device
                if getattr(d, "type", None) == "cuda":
                    return "cuda"
                if getattr(d, "type", None) == "cpu":
                    return "cpu"
        except Exception:
            pass

        try:
            device_map = getattr(self.model, "hf_device_map", None)
            if isinstance(device_map, dict):
                has_cuda = False
                has_cpu = False
                for v in device_map.values():
                    if v is None:
                        continue
                    # accelerate may store devices as strings ('cuda:0'/'cpu'), ints (0), or torch.device
                    if isinstance(v, int):
                        has_cuda = True
                        continue
                    if isinstance(v, torch.device):
                        if v.type == "cuda":
                            has_cuda = True
                        elif v.type == "cpu":
                            has_cpu = True
                        continue
                    s = str(v)
                    if s.startswith("cuda"):
                        has_cuda = True
                    elif s == "cpu":
                        has_cpu = True

                if has_cuda:
                    return "cuda"
                if has_cpu:
                    return "cpu"
        except Exception:
            pass

        model_device = getattr(self.model, "device", None)
        if model_device is not None:
            return "cuda" if str(model_device).startswith("cuda") else "cpu"

        return "cuda" if torch.cuda.is_available() else "cpu"
    
    def _format_prompt(self, query: str, context: str) -> str:
        """
        Format prompt for Mistral with instruction template.
        
        Args:
            query: User query
            context: Retrieved context
            
        Returns:
            Formatted prompt string
        """
        safe_context = (context or "").strip()

        # CLIP-optimized prompt: concrete entities/actions + explicit metaphor + strict SDXL prompt structure.
        # Keep strict JSON output so downstream code can reliably extract `sdxl_prompt`.
        prompt = f"""<s>[INST]
    Role

    You are a friendly, wise Tunisian cultural expert with deep knowledge of Tunisian proverbs, dialects, traditions, symbolism, and everyday life.
    Your explanations must be precise, culturally grounded, and visually concrete.

    Your task is to explain a Tunisian proverb and generate a highly descriptive image prompt optimized for SDXL-Lightning and CLIP evaluation.

    Inputs

    - User Proverb: "{query}"
    - Retrieved Cultural Context (RAG): "{safe_context}"

    You MUST base your reasoning on the retrieved context. If the context is empty or not helpful, skip using it.

    Step 1 — Proverb Understanding (Semantic Clarity)

    - Give the literal translation (if applicable).
    - Explain the core meaning using clear cause–effect language.
    - Keep Tunisian dialect nuance but avoid abstract wording.

    Step 2 — Cultural Deconstruction (Concrete Usage)

    - State the life lesson or warning explicitly.
    - Describe one realistic Tunisian situation where the proverb is said.
    - Mention who says it to whom and why (parent → child, friend → friend, elder → youth).

    Step 3 — Visual Scene Synthesis (CLIP-Oriented)

    Translate the meaning into a clear visual metaphor.

    Scene Construction Rules (MANDATORY)

    - Use one main scene.
    - Use 1–2 characters maximum.
    - Characters must be doing an action.
    - Include visible objects tied to the metaphor.
    - Avoid abstract concepts without physical representation.

    Scene Elements (Explicit)

    Clearly specify:

    - Environment (street, house, café, field, market, coast, etc.)
    - Characters (age, posture, clothing style if relevant)
    - Objects (tools, food, doors, light, shadows, animals, etc.)
    - Action (waiting, walking away, holding, watching, struggling…)

    Metaphor & Mood (CLIP Alignment)

    - Explicitly state what the visual metaphor represents.
    - Define the mood using visual adjectives (warm light, muted colors, strong contrast, calm atmosphere, tense moment…).

    Art Style (Single, Clear Choice)

    Choose one style only:

    - Vibrant Tunisian folk art
    - Cinematic realism
    - Soft painterly realism
    - Symbolic surrealism

    Step 4 — Final Output

    1) Short Story (2–3 sentences)

    - Grounded in Tunisian daily life.
    - Matches the same scene as the image.
    - Avoid moralizing language; let the scene imply the lesson.

    2) SDXL-Lightning Prompt (CLIP-Optimized)

    You MUST produce one single prompt following this exact structure (copy the structure exactly, fill in the brackets):

    ```
    A [Art Style] illustration depicting [specific environment].
    A [clearly described character or characters] performing [specific action] with [key objects].
    The scene symbolizes [explicit metaphor meaning] through [visual cues such as light, posture, contrast, or setting].
    Mood: [clear emotional tone].
    High-resolution, sharp focus, detailed textures, professional illustration.
    ```

    Do NOT include explanations, bullet points, or cultural analysis inside the image prompt.
    Use concrete nouns and actions. Avoid vague words.
    Ensure textual overlap between story and image description.
    No mention of AI, models, prompts, or tools.

    Return ONLY valid JSON with exactly these keys:
    {{
      "proverb": string,
      "literal_translation": string,
      "core_meaning": string,
      "life_lesson": string,
      "usage_example": string,
      "scene_description": string,
      "scene_elements": [string, ...],
      "metaphor_and_mood": string,
      "art_style": string,
      "story": string,
      "sdxl_prompt": string
    }}

    Respond only with JSON, no extra text.
    [/INST]"""

        return prompt
    
    def reason(
        self,
        query: str,
        context: str,
        on_update=None,
        max_new_tokens: int = 640,
        max_time_s: int = 120,
    ) -> Dict:
        """
        Generate reasoning based on query and context.
        
        Args:
            query: Input query
            context: Retrieved context from RAG
            
        Returns:
            Reasoning result dictionary
        """
        if not self._initialized:
            raise RuntimeError("MistralReasoner not initialized. Call initialize() first.")
        
        if on_update is not None:
            try:
                on_update("Mistral: building prompt...", 0.73)
            except Exception:
                pass

        prompt = self._format_prompt(query, context)
        
        # Tokenize input
        if on_update is not None:
            try:
                on_update("Mistral: tokenizing...", 0.74)
            except Exception:
                pass
        inputs = self.tokenizer(prompt, return_tensors="pt")

        # For generate() the input tensors must live on the same device as the model's first shard.
        # With device_map="auto" the safest default is cuda when available.
        inputs = inputs.to(self._infer_input_device())
        
        # Generate response
        if on_update is not None:
            try:
                on_update("Mistral: generating response...", 0.76)
            except Exception:
                pass

        with torch.inference_mode():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                do_sample=False,
                max_time=max_time_s,
                pad_token_id=self.tokenizer.eos_token_id
            )

        if on_update is not None:
            try:
                on_update("Mistral: decoding output...", 0.86)
            except Exception:
                pass
        
        # Decode only the newly generated tokens (otherwise we re-parse the JSON example inside the prompt)
        prompt_len = inputs["input_ids"].shape[1]
        generated_ids = outputs[0][prompt_len:]
        response = self.tokenizer.decode(generated_ids, skip_special_tokens=True)

        if on_update is not None:
            try:
                on_update("Mistral: parsing JSON...", 0.90)
            except Exception:
                pass
        
        # Extract JSON from response
        try:
            start_idx = response.find('{')
            end_idx = response.rfind('}') + 1
            if start_idx != -1 and end_idx > start_idx:
                json_str = response[start_idx:end_idx]
                result = json.loads(json_str)
            else:
                result = self._create_fallback_response(response, query, context)
        
        except json.JSONDecodeError:
            result = self._create_fallback_response(response, query, context)
        
        # Ensure we always return a CLIP-friendly SDXL prompt.
        try:
            if isinstance(result, dict):
                result = self._ensure_clip_sdxl_prompt(result)
        except Exception:
            pass

        return result

    def _ensure_clip_sdxl_prompt(self, data: Dict) -> Dict:
        sdxl_prompt = (data.get("sdxl_prompt") or "").strip()
        art_style = (data.get("art_style") or "Vibrant Tunisian folk art").strip()
        scene_description = (data.get("scene_description") or "").strip()
        metaphor_and_mood = (data.get("metaphor_and_mood") or "").strip()
        core_meaning = (data.get("core_meaning") or "").strip()

        def has_required_shape(p: str) -> bool:
            # Minimal structural checks aligned with the spec.
            required = ["A ", "illustration", "depicting", "performing", "The scene symbolizes", "Mood:", "High-resolution"]
            return all(token in p for token in required)

        if not sdxl_prompt or not has_required_shape(sdxl_prompt):
            # Build a compliant prompt from available fields.
            env = scene_description or "a Tunisian everyday environment"
            mood = metaphor_and_mood or ("wise and warm" if core_meaning else "warm light, calm atmosphere")
            metaphor = core_meaning or "the proverb's meaning"
            sdxl_prompt = (
                f"A {art_style} illustration depicting {env}. "
                "A Tunisian character performing a clear action with key visible objects. "
                f"The scene symbolizes {metaphor} through visual cues like posture, lighting, and setting. "
                f"Mood: {mood}. "
                "High-resolution, sharp focus, detailed textures, professional illustration."
            )

        data["sdxl_prompt"] = sdxl_prompt
        return data
    
    def _extract_partial_v2(self, response: str) -> Dict:
        """Best-effort extraction when model output is truncated/invalid JSON."""

        def grab(key: str) -> str:
            # Try a normal JSON-string pattern first.
            m = re.search(rf'"{re.escape(key)}"\s*:\s*"(.*?)"\s*(,|\}}|$)', response, flags=re.DOTALL)
            if m:
                return m.group(1).replace("\\n", " ").strip()
            # Handle truncation: capture until end of line / end of string.
            m = re.search(rf'"{re.escape(key)}"\s*:\s*"([^\r\n\}}]*)', response)
            if m:
                return m.group(1).replace("\\n", " ").strip()
            return ""

        proverb = grab("proverb")
        literal_translation = grab("literal_translation")
        core_meaning = grab("core_meaning")
        life_lesson = grab("life_lesson")
        usage_example = grab("usage_example")
        scene_description = grab("scene_description")
        metaphor_and_mood = grab("metaphor_and_mood")
        art_style = grab("art_style")
        story = grab("story")
        sdxl_prompt = grab("sdxl_prompt")

        # Scene elements: accept either JSON list or a comma-separated string.
        scene_elements: list[str] = []
        m_list = re.search(r'"scene_elements"\s*:\s*\[(.*?)\]', response, flags=re.DOTALL)
        if m_list:
            inner = m_list.group(1)
            scene_elements = [s.strip().strip('"') for s in inner.split(',') if s.strip()]

        return {
            "proverb": proverb,
            "literal_translation": literal_translation,
            "core_meaning": core_meaning,
            "life_lesson": life_lesson,
            "usage_example": usage_example,
            "scene_description": scene_description,
            "scene_elements": scene_elements,
            "metaphor_and_mood": metaphor_and_mood,
            "art_style": art_style,
            "story": story,
            "sdxl_prompt": sdxl_prompt,
        }

    def _create_fallback_response(self, response: str, query: str, context: str) -> Dict:
        """
        Create fallback structured response when JSON parsing fails.
        
        Args:
            response: Raw model response
            query: Original query
            
        Returns:
            Structured dictionary
        """
        # If the model started producing JSON (often truncated), salvage v2 fields.
        # This prevents "image_prompt" from degrading into "Illustration of: <arabic proverb>".
        if response.lstrip().startswith("{") or ('"literal_translation"' in response) or ('"core_meaning"' in response):
            partial = self._extract_partial_v2(response)
            proverb = partial.get("proverb") or query
            art_style = partial.get("art_style") or "Vibrant Tunisian folk art"
            core_meaning = partial.get("core_meaning") or "A Tunisian proverb about patience and eventual relief."
            life_lesson = partial.get("life_lesson") or "Patience and persistence help you reach better outcomes."
            scene_description = partial.get("scene_description") or (
                f"A metaphorical Tunisian scene expressing: {core_meaning}"
            )
            mood = partial.get("metaphor_and_mood") or "wise, hopeful"

            # Build a high-quality SDXL prompt even if the model didn't reach that key.
            sdxl_prompt = partial.get("sdxl_prompt")
            if not sdxl_prompt:
                sdxl_prompt = (
                    f"A {art_style} illustration. {scene_description}. {mood}. "
                    "High-resolution, detailed, professional artwork."
                )

            scene_elements = partial.get("scene_elements")
            if not isinstance(scene_elements, list) or not scene_elements:
                scene_elements = ["Tunisian setting", "people", "subtle symbolic object", "warm light"]

            story = partial.get("story")
            if not story:
                story = (
                    "In a Tunisian neighborhood, someone keeps working quietly through setbacks. "
                    "When the moment finally arrives, the reward feels earned and peaceful."
                )

            # Return v2 shape; pipeline normalizer will also backfill legacy keys.
            return {
                "proverb": proverb,
                "literal_translation": partial.get("literal_translation") or "(Extracted)",
                "core_meaning": core_meaning,
                "life_lesson": life_lesson,
                "usage_example": partial.get("usage_example")
                or "Example: Someone says this after a long wait finally pays off.",
                "scene_description": scene_description,
                "scene_elements": scene_elements,
                "metaphor_and_mood": mood,
                "art_style": art_style,
                "story": story,
                "sdxl_prompt": sdxl_prompt,
            }

        # Otherwise, basic legacy fallback
        return {
            "proverb": query,
            "interpretation": response[:500] if len(response) > 500 else response,
            "cultural_context": (context or "Unable to extract specific cultural context")[:500],
            "image_prompt": (
                "A vibrant Tunisian folk art illustration. "
                f"A metaphorical scene inspired by the proverb: {query}. "
                "Warm light, rich textures, expressive characters. High-resolution, detailed, professional artwork."
            ),
        }
    
    def generate_structured_output(self, query: str, context: str) -> Dict:
        """
        Generate structured JSON output from reasoning.
        
        Args:
            query: Input query
            context: Retrieved context
            
        Returns:
            Structured dictionary with proverb analysis
        """
        return self.reason(query, context)
    
    def unload(self):
        """
        Unload model from memory.
        """
        if self.model:
            del self.model
            del self.tokenizer
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            self._initialized = False
            print("Mistral model unloaded")