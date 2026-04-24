# CLIP Scoring: Image-Text Semantic Alignment

## Overview

CLIP (Contrastive Language-Image Pre-training) scoring measures how well a generated image semantically aligns with the proverb meaning and visual prompt. This provides an **objective quality metric** (0-100 scale) for image generation results.

---

## How It Works

### 1. **The CLIP Model**
```
Model: openai/clip-vit-base-patch32
- Trained on 400M image-text pairs
- Understands semantic relationships between images and text
- Can score alignment even for culturally-specific concepts
```

### 2. **Scoring Process**
```
Generated Image + Visual Prompt → CLIP Encoder → Similarity Score → Scale to 0-100
```

**Steps:**
1. Load generated PNG image from disk
2. Extract the detailed visual prompt used for generation
3. Encode both image and prompt using CLIP encoders (separate)
4. Compute cosine similarity between embeddings
5. Normalize to 0-100 scale
6. Return score + detailed metrics

### 3. **Text Variation Strategy**
The CLIP scorer tests 5 variations of the text to handle semantic robustness:
```python
variations = [
    prompt,
    f"represents {prompt}",
    f"depicts {prompt}",
    f"illustrates {prompt}",
    f"visualizes {prompt}"
]
```

**Why?** Different phrasing can affect CLIP's understanding. We take the maximum score across variations to ensure fair assessment.

---

## Scale Interpretation

| Score | Interpretation | Example |
|-------|----------------|---------|
| **90-100** | 🟢 Excellent | Image perfectly embodies proverb wisdom |
| **70-89** | 🟡 Good | Image well represents core concept |
| **50-69** | 🟠 Fair | Image captures some aspects but incomplete |
| **0-49** | 🔴 Needs Improvement | Image doesn't align well with meaning |

---

## Implementation Details

### Class: `CLIPScorer`

```python
class CLIPScorer:
    """Scores semantic alignment between images and text (0-100 scale)"""
    
    def __init__(self):
        # Lazy-load model on first use
        self.model = None
        self.processor = None
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
    
    def score_image_text_pair(image_path: str, text: str) -> Tuple[float, dict]:
        """
        Calculate CLIP score for image-text pair.
        
        Returns:
            - score_0_100 (float): 0-100 scale
            - details (dict): Raw metrics including per-variation scores
        """
```

### Key Features

1. **Lazy Initialization**: Model loads on first use, not on import
2. **Device Flexibility**: Uses CUDA if available, falls back to CPU
3. **Multi-Variation Testing**: Tests 5 text variations for robustness
4. **Feature Normalization**: L2 normalization for fair cosine similarity
5. **Error Handling**: Graceful fallback (returns 50.0 on error)

---

## Integration into Generation Pipeline

### Before Fix (Incoherent)
```python
# ❌ WRONG: Using short proverb text for scoring
clip_score = calculate_clip_score(
    image_path,
    proverb_text  # "من قال سلام قال سلام" - too generic
)
# Result: All scores similar because text is too generic
```

### After Fix (Current)
```python
# ✅ CORRECT: Using detailed visual prompt
scoring_text = output.generated_prompt or proverb_text
clip_score = calculate_clip_score(
    image_path,
    scoring_text  # "A serene desert with peaceful figures..." - specific!
)
# Result: Scores vary based on actual image quality
```

**Impact:** Scores now properly reflect image-text alignment instead of being static/duplicate.

---

## Storage & Retrieval

### Database Schema
```sql
CREATE TABLE generated_content (
    content_id TEXT PRIMARY KEY,
    proverb_id TEXT,
    clip_score REAL,  -- Stored as 0-1 float (0.85 = 85/100)
    ...
);
```

### API Endpoints

**Calculate Score (On-Demand):**
```
POST /api/clip-score
{
    "image_path": "website/generated/image_abc123.png",
    "text": "Visual prompt describing the image"
}
→ {
    "score": 87.5,
    "label": "Good",
    "emoji": "🟡",
    "details": {...}
}
```

**Retrieve Stored Score:**
```
GET /api/content/{content_id}/clip-score
→ {
    "content_id": "content_abc123",
    "score": 87.5,
    "label": "Good",
    "emoji": "🟡"
}
```

---

## Performance Characteristics

| Aspect | Value |
|--------|-------|
| **Time per Image** | 1-2 seconds |
| **Memory** | ~2GB (GPU) or ~500MB (CPU) |
| **Device** | CUDA (GPU) preferred, CPU supported |
| **Concurrent Scores** | Limited by device memory |

### Optimization Strategies

1. **Lazy Loading**: Model only loads when first score needed
2. **Batch Processing**: Can score multiple images efficiently
3. **Caching**: Scores persisted in database to avoid rescoring
4. **Device Selection**: Automatic CUDA/CPU selection based on hardware

---

## Use Cases

### 1. **Quality Assurance**
- Filter out low-quality generations (< 50 score)
- Identify which prompts generate better images
- Track quality trends over time

### 2. **User Feedback**
- Show quality indicator in UI: 🟢🟡🟠🔴
- Help users understand image-text alignment
- Transparent quality metrics

### 3. **Data Analysis**
- Which proverbs get highest scoring images?
- How does prompt length affect CLIP scores?
- Model performance tracking

### 4. **Debugging**
- Identify when CLIP scoring is working correctly
- Verify prompt quality before image generation
- Troubleshoot cultural/linguistic understanding issues

---

## Known Limitations

1. **Western Bias**: CLIP trained on English image-text pairs, may not understand all Tunisian cultural concepts perfectly

2. **Abstract Concepts**: Proverbs often contain metaphorical meaning that's harder to visualize objectively

3. **Cultural Context**: CLIP may not recognize culturally-specific imagery or symbolism

4. **Prompt Quality**: If visual prompt is poor, CLIP score will reflect that

### Mitigation

- Use detailed, specific visual prompts (not generic descriptions)
- Consider human review for important content
- Track which proverbs consistently get low scores
- Iterate on prompt engineering for better results

---

## Future Improvements

1. **Fine-tuning**: Train CLIP on Arabic cultural images
2. **Multi-Modal**: Combine CLIP with other quality metrics
3. **Human Feedback**: Learn from user ratings
4. **Weighted Scoring**: Different weights for different proverb categories
5. **Batch Scoring**: Efficiently score entire generation batches

---

## Related Documentation

- [ARCHITECTURE.md](ARCHITECTURE.md) - System design
- [FEEDBACK_LOOP.md](FEEDBACK_LOOP.md) - How scores enable learning
- [app.py](app.py#L789) - Implementation in generation pipeline
- [clip_scorer.py](clip_scorer.py) - Source code

---

## Troubleshooting

### "CLIP model failed to load"
**Solution**: Install `torch` and `transformers`
```bash
pip install torch transformers
```

### "All CLIP scores are the same"
**Solution**: Ensure visual prompt varies between generations (check `output.generated_prompt`)

### "CLIP scoring is slow"
**Solution**: CLIP runs on CPU by default. Install CUDA for GPU acceleration
```bash
# Check if CUDA available
python -c "import torch; print(torch.cuda.is_available())"
```

### "CLIP scores don't match my perception"
**Solution**: CLIP is objective but imperfect. Use scores as one metric among many. Review low-scoring images manually.
