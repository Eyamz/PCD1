"""
Groq RAG Pipeline for Tunisian Proverbs

This module implements a Retrieval-Augmented Generation (RAG) system that:
- Uses FAISS for local semantic similarity search (no internet needed)
- Uses Groq API for explanation generation (free tier, no rate limits)

Key Features:
    - Local FAISS retrieval keeps cultural context processing local/private
    - Groq API handles text generation with Llama 3.3 70B
    - No GPU required - runs on CPU
    - Fast (~1-3 seconds per explanation)
    - Cost: FREE (Groq API free tier, no rate limits)

Key Functions:
    initialize_pipeline() - Load FAISS embeddings
    generate_explanation() - Generate explanation using RAG + Groq
"""

import json
import logging
import os
from pathlib import Path
from typing import Optional, List, Tuple, Dict
import requests
import csv

# Try to load from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv not installed, will use environment variables

from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS

logger = logging.getLogger(__name__)

# Global state
vectorstore: Optional[FAISS] = None
retriever: Optional[object] = None
embedding_model: Optional[HuggingFaceEmbeddings] = None
groq_api_key: Optional[str] = None
vocabulary_cache: Optional[Dict] = None  # Vocabulary reference for enhanced RAG


def load_vocabulary_reference(vocab_path: str = "data/arabic_vocabulary_reference.csv") -> Dict:
    """Load Arabic vocabulary reference from CSV for context enhancement."""
    global vocabulary_cache
    
    if vocabulary_cache is not None:
        return vocabulary_cache
    
    vocabulary_cache = {}
    vocab_file = Path(vocab_path)
    
    if not vocab_file.exists():
        logger.warning(f"Vocabulary file not found at {vocab_path}, skipping vocabulary enhancement")
        return {}
    
    try:
        with open(vocab_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                arabic_word = row.get('arabic_word', '').strip()
                if arabic_word:
                    vocabulary_cache[arabic_word] = {
                        'transliteration': row.get('transliteration', ''),
                        'english_translation': row.get('english_translation', ''),
                        'tunisian_variant': row.get('tunisian_dialect_variant', ''),
                        'category': row.get('category', ''),
                        'notes': row.get('notes', '')
                    }
        logger.info(f"✓ Loaded {len(vocabulary_cache)} vocabulary entries")
        return vocabulary_cache
    except Exception as e:
        logger.error(f"Failed to load vocabulary: {e}")
        return {}


def extract_vocabulary_context(proverb: str, max_entries: int = 10) -> str:
    """Extract relevant vocabulary from proverb to provide additional context."""
    if not vocabulary_cache:
        return ""
    
    # Find words in the proverb that exist in vocabulary
    relevant_vocab = []
    for word in proverb.split():
        word_clean = word.strip('؛،\"\'')
        if word_clean in vocabulary_cache:
            vocab_entry = vocabulary_cache[word_clean]
            relevant_vocab.append({
                'word': word_clean,
                'english': vocab_entry.get('english_translation', ''),
                'tunisian': vocab_entry.get('tunisian_variant', ''),
                'category': vocab_entry.get('category', '')
            })
    
    if not relevant_vocab:
        return ""
    
    # Limit to most relevant entries
    relevant_vocab = relevant_vocab[:max_entries]
    
    vocab_context = "\n\nVOCABULARY REFERENCE FROM KNOWLEDGE BASE:"
    for entry in relevant_vocab:
        vocab_context += f"\n- {entry['word']} ({entry['english']}) - Tunisian: {entry['tunisian']} - Category: {entry['category']}"
    
    return vocab_context


def load_proverbs_from_json(proverbs_path: str = "website/proverbs.json") -> List[Document]:
    """Load proverbs from JSON file and convert to LangChain documents."""
    logger.info(f"Loading proverbs from {proverbs_path}")
    
    with open(proverbs_path, 'r', encoding='utf-8') as f:
        proverbs_data = json.load(f)
    
    documents = []
    for proverb in proverbs_data:
        content = f"""
المثل: {proverb.get('tunisan_proverb', '')}
الموضوع: {proverb.get('context', 'غير محدد')}
الشرح: {proverb.get('proverb_arabic_explaination', '')}
        """.strip()
        
        doc = Document(
            page_content=content,
            metadata={
                "proverb": proverb.get("tunisan_proverb", ""),
                "context": proverb.get("context", ""),
                "explanation": proverb.get("proverb_arabic_explaination", "")
            }
        )
        documents.append(doc)
    
    logger.info(f"✓ Loaded {len(documents)} proverbs")
    return documents


def initialize_embedding_model() -> HuggingFaceEmbeddings:
    """Initialize sentence transformer embedding model (CPU-optimized)."""
    global embedding_model
    
    if embedding_model is not None:
        logger.info("Embedding model already loaded")
        return embedding_model
    
    logger.info("Loading embedding model (all-MiniLM-L6-v2)...")
    embedding_model = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2",
        model_kwargs={"device": "cpu"}
    )
    logger.info("✓ Embedding model loaded")
    return embedding_model


def initialize_faiss_vectorstore(proverbs_path: str = "website/proverbs.json") -> FAISS:
    """Create or load FAISS vector store from proverbs."""
    global vectorstore, retriever, embedding_model
    
    vectorstore_path = Path("faiss_vectorstore_proverbs")
    
    # Try to load existing vectorstore
    if vectorstore_path.exists():
        logger.info("Loading existing FAISS vector store...")
        try:
            embedding_model = initialize_embedding_model()
            vectorstore = FAISS.load_local(
                "faiss_vectorstore_proverbs", 
                embedding_model,
                allow_dangerous_deserialization=True
            )
            retriever = vectorstore.as_retriever(
                search_type="similarity",
                search_kwargs={"k": 4}
            )
            logger.info("✓ FAISS vector store loaded from disk")
            return vectorstore
        except Exception as e:
            logger.warning(f"Failed to load existing vectorstore: {e}. Rebuilding...")
    
    # Build new vectorstore
    logger.info("Building new FAISS vector store...")
    embedding_model = initialize_embedding_model()
    documents = load_proverbs_from_json(proverbs_path)
    
    vectorstore = FAISS.from_documents(documents, embedding_model)
    retriever = vectorstore.as_retriever(
        search_type="similarity",
        search_kwargs={"k": 4}
    )
    
    # Save for future reuse
    vectorstore.save_local("faiss_vectorstore_proverbs")
    logger.info("✓ FAISS vector store created and saved")
    
    return vectorstore


def get_groq_api_key() -> str:
    """Get Groq API key from environment."""
    global groq_api_key
    
    if groq_api_key is None:
        # Try to get from environment
        groq_api_key = os.getenv("GROQ_API_KEY")
        
        if not groq_api_key:
            raise ValueError(
                "Groq API key not found!\n"
                "Set environment variable: GROQ_API_KEY=gsk_...\n"
                "Or add to .env file: GROQ_API_KEY=gsk_..."
            )
    
    return groq_api_key


def retrieve_context(proverb: str) -> Tuple[str, List]:
    """
    Retrieve similar proverbs from FAISS vector store with enriched context.
    
    Returns:
        Tuple of (formatted_context_string, list_of_similar_proverbs)
    """
    if retriever is None:
        raise RuntimeError("Retriever not initialized. Call initialize_pipeline() first.")
    
    results = retriever.invoke(proverb)
    context = ""
    similar_proverbs = []
    
    for i, doc in enumerate(results, 1):
        metadata = doc.metadata
        proverb_text = metadata.get("proverb", "")
        proverb_context = metadata.get("context", "")
        proverb_explanation = metadata.get("explanation", "")
        
        # Store for potential later use
        similar_proverbs.append({
            "proverb": proverb_text,
            "context": proverb_context,
            "explanation": proverb_explanation
        })
        
        # Build enriched context
        context += f"\n{'═' * 70}"
        context += f"\n📌 Related Proverb {i}:"
        context += f"\n  Text: {proverb_text}"
        if proverb_context:
            context += f"\n  Theme: {proverb_context}"
        if proverb_explanation:
            context += f"\n  Explanation: {proverb_explanation}"
        context += f"\n{'═' * 70}\n"
    
    return context, similar_proverbs


def build_prompt(proverb: str, context: str, similar_proverbs: list = None) -> str:
    """
    Build enriched RAG prompt with cultural and contextual knowledge.
    
    This prompt leverages:
    - Similar proverbs from knowledge base
    - Cultural themes and contexts
    - Arabic vocabulary reference from knowledge base
    - Existing explanations for cross-referencing
    """
    
    # Build context themes section
    themes = set()
    if similar_proverbs:
        for p in similar_proverbs:
            if p.get("context"):
                themes.add(p["context"])
    
    themes_text = ""
    if themes:
        themes_text = f"\n\nCultural Themes Found in Similar Proverbs:\n"
        for theme in sorted(themes):
            themes_text += f"  • {theme}\n"
    
    # Extract vocabulary context from the proverb
    vocab_context = extract_vocabulary_context(proverb, max_entries=8)
    
    prompt = f"""You are a cultural expert specializing in Tunisian/Arabic proverbs, traditions, and wisdom.

Your task: Provide a rich, nuanced explanation of this Tunisian proverb that helps readers understand its cultural depth.

TARGET PROVERB: "{proverb}"

KNOWLEDGE BASE CONTEXT (Similar Proverbs from our Collection):
{context}
{themes_text}
{vocab_context}

Generate a comprehensive explanation following this structure:

## 1. LITERAL & METAPHORICAL MEANING
- Direct translation and word-by-word meaning
- Deeper metaphorical or symbolic interpretation

## 2. CULTURAL & HISTORICAL CONTEXT
- Where and when this proverb originates
- Social values it represents in Tunisian/Maghrebi culture
- Connection to Islamic traditions and Arab heritage

## 3. PRACTICAL USAGE
- Real-life situations where Tunisians use this proverb
- How it's used in family, community, or social contexts
- Tone: Warning, encouragement, wisdom, etc.

## 4. CONNECTIONS TO THE KNOWLEDGE BASE
- How this proverb relates to the similar proverbs above
- Shared themes or lessons
- Unique aspects of this particular proverb

## 5. MODERN RELEVANCE
- Why this wisdom matters in contemporary life
- Lessons for today's generation
- Universal human truths it conveys

## 6. EXAMPLE OR SCENARIO
- One concrete, relatable example of when/how to use this proverb

Write in a clear, engaging style. Include both Arabic and English phrases where appropriate.
Be insightful and educational while remaining concise."""
    
    return prompt


def generate_explanation_groq(proverb: str, max_tokens: int = 800) -> str:
    """
    Generate explanation using Groq API with enhanced RAG context.
    
    Process:
    1. Retrieve similar proverbs from local FAISS (cultural knowledge base)
    2. Build enriched prompt using retrieved context
    3. Send to Google Gemini API for generation
    4. Return high-quality explanation
    
    Args:
        proverb: Tunisian proverb in Arabic
        max_tokens: Maximum tokens to generate (increased for better explanations)
    
    Returns:
        Detailed explanation from Gemini API
    """
    global retriever
    
    if retriever is None:
        raise RuntimeError("Pipeline not initialized. Call initialize_pipeline() first.")
    
    logger.info(f"Generating enriched explanation via Gemini for: {proverb[:50]}...")
    
    # Step 1: Retrieve context from local FAISS with enrichment
    context, similar_proverbs = retrieve_context(proverb)
    logger.info(f"✓ Retrieved {len(similar_proverbs)} similar proverbs from knowledge base")
    
    # Step 2: Build enhanced prompt using context
    prompt = build_prompt(proverb, context, similar_proverbs)
    logger.info("✓ Enhanced prompt built with cultural context")
    
    # Step 3: Call Groq API with improved prompt
    api_key = get_groq_api_key()
    
    url = "https://api.groq.com/openai/v1/chat/completions"
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0.8,  # Higher temp for more creative, nuanced explanations
        "max_tokens": max_tokens
    }
    
    try:
        logger.info("Sending enriched context to Groq API...")
        response = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=30
        )
        
        logger.info(f"Groq response status: {response.status_code}")
        
        # Check HTTP status first
        if response.status_code != 200:
            logger.error(f"Groq API returned {response.status_code}: {response.text[:500]}")
            raise RuntimeError(f"Groq API error: HTTP {response.status_code}")
        
        # Now parse JSON
        try:
            result = response.json()
        except Exception as json_error:
            logger.error(f"Failed to parse Groq JSON response: {json_error}")
            logger.error(f"Response text: {response.text[:500]}")
            raise RuntimeError(f"Invalid JSON from Groq: {str(json_error)}")
        
        # Check for API errors in response
        if "error" in result:
            error_msg = result.get("error", {}).get("message", "Unknown error")
            logger.error(f"Groq API error: {error_msg}")
            logger.error(f"Full response: {result}")
            raise RuntimeError(f"Groq error: {error_msg}")
        
        # Extract the generated text
        try:
            explanation = result["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError) as e:
            logger.error(f"Unexpected Groq response structure: {e}")
            logger.error(f"Full response: {result}")
            raise RuntimeError(f"Invalid Groq response format: {str(e)}")
        
        logger.info(f"✓ Explanation generated successfully")
        logger.info(f"  - Response tokens: {len(explanation.split())}")
        
        return explanation
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Request error calling Groq: {e}")
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_detail = e.response.json()
                logger.error(f"Response JSON: {error_detail}")
            except:
                logger.error(f"Response text: {e.response.text[:500]}")
        raise RuntimeError(f"Failed to call Groq API: {str(e)}")
    except (KeyError, IndexError) as e:
        logger.error(f"Unexpected response structure from Groq: {e}")
        raise RuntimeError(f"Invalid Groq response: {str(e)}")


def generate_explanation(proverb: str, max_tokens: int = 1500) -> str:
    """
    Generate a detailed explanation for a proverb using RAG + Groq.
    
    This is the main entry point. Uses local FAISS for retrieval and
    Groq API for generation.
    
    Args:
        proverb: Tunisian proverb in Arabic
        max_tokens: Maximum tokens to generate (default 512)
    
    Returns:
        Detailed explanation combining retrieved knowledge + Gemini generation
    """
    return generate_explanation_groq(proverb, max_tokens)


def generate_explanation_with_visual_prompt(proverb: str, max_tokens: int = 3000) -> dict:
    """
    Generate comprehensive proverb analysis including explanation, visual prompt, story, and reasoning.
    
    Returns structured output with:
    - explanation: Full cultural/contextual explanation
    - visual_prompt: Detailed SDXL image generation prompt
    - visual_summary: 1-2 sentence summary of how image relates to proverb
    - literal_meaning: Direct/literal interpretation
    - hidden_meaning: Deep cultural wisdom and hidden truths
    - moral_lesson: Important life lesson
    - key_phrases: List of important thematic words
    - narrative: Story embodying the lesson
    
    Args:
        proverb: Tunisian proverb in Arabic
        max_tokens: Maximum tokens for Groq response
    
    Returns:
        Dict with all fields above
    """
    global retriever
    
    if retriever is None:
        raise RuntimeError("Pipeline not initialized. Call initialize_pipeline() first.")
    
    logger.info(f"Generating full analysis for: {proverb[:50]}...")
    
    # Retrieve context
    context, similar_proverbs = retrieve_context(proverb)
    logger.info(f"✓ Retrieved {len(similar_proverbs)} similar proverbs")
    
    # Load vocabulary reference for enhanced context
    load_vocabulary_reference()
    
    # Build themes section
    themes = set()
    if similar_proverbs:
        for p in similar_proverbs:
            if p.get("context"):
                themes.add(p["context"])
    
    themes_text = ""
    if themes:
        themes_text = f"\n\nCultural Themes:\n"
        for theme in sorted(themes):
            themes_text += f"  • {theme}\n"
    
    # Extract relevant vocabulary for this proverb
    vocab_context = extract_vocabulary_context(proverb)
    
    # Build comprehensive prompt asking for trilingual output
    combined_prompt = f"""You are a cultural expert in Tunisian proverbs and a creative visual storyteller.

TARGET PROVERB: "{proverb}"

KNOWLEDGE BASE CONTEXT:
{context}
{themes_text}
{vocab_context}

IMPORTANT VOCABULARY CLARIFICATIONS FOR TUNISIAN PROVERBS:
- بهيم (bhim) / بهيمة (bhima) = DONKEY (stubborn, hardworking pack animal) - NOT camel
- حصان (hissan) = HORSE (noble, swift, faster than donkey) - NOT mule
- جمل (jamal) = CAMEL (desert animal, used for long journeys) - different from horse and donkey
- نكاس / عنيد = stubborn, obstinate (adjective describing the animal's nature)

When you see these animals in the proverb, interpret them correctly. Do NOT confuse them:
- If the proverb mentions "بهيمك" = about YOUR DONKEY (not camel)
- If the proverb mentions "حصان" = about a HORSE (not camel, not mule)
- If the proverb mentions "جمل" = about a CAMEL (used for desert/travel)

Generate the following sections in THREE LANGUAGES: ARABIC, FRENCH, and ENGLISH.
Use clear markers for each language and section. Use format: [SECTION_NUMBER_LETTER: SECTION_NAME (LANGUAGE)]

1. LITERAL MEANING - The direct, word-for-word interpretation of the proverb (1-2 sentences in each language)
2. HIDDEN MEANING - Deep cultural wisdom and hidden truths behind the proverb (2-3 sentences in each language)
3. MORAL LESSON - An important life lesson for personal growth and wisdom (1-2 sentences in each language)
4. KEY PHRASES - List 4-5 key phrases separated by commas that capture the proverb's essence (in each language)
5. NARRATIVE STORY - Write a short story (4-5 sentences) that embodies and demonstrates this proverb's lesson (in each language)
6. CULTURAL EXPLANATION - Provide a rich explanation covering contextual background, historical significance, practical usage in Tunisian culture
7. VISUAL PROMPT FOR SDXL - Detailed prompt describing a visual scene illustrating this proverb's meaning (must be in English for SDXL)
8. VISUAL SUMMARY - How the image represents the proverb in 1-2 sentences (in each language)

FORMAT EXAMPLE:
[1A: LITERAL MEANING (ARABIC)]
النص العربي هنا...

[1B: LITERAL MEANING (FRENCH)]
Le texte français ici...

[1C: LITERAL MEANING (ENGLISH)]
The English text here...

[2A: HIDDEN MEANING (ARABIC)]
...and so on for each section

IMPORTANT: Use these exact markers so output can be parsed programmatically. Sections 7 (Visual Prompt) and 6 (Cultural Explanation) can be English-only if needed for clarity."""
    
    api_key = get_groq_api_key()
    url = "https://api.groq.com/openai/v1/chat/completions"
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [{"role": "user", "content": combined_prompt}],
        "temperature": 0.8,
        "max_tokens": max_tokens
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        
        if response.status_code != 200:
            logger.error(f"Groq API returned {response.status_code}: {response.text[:500]}")
            raise RuntimeError(f"Groq API error: HTTP {response.status_code}")
        
        result = response.json()
        
        if "error" in result:
            error_msg = result.get("error", {}).get("message", "Unknown error")
            logger.error(f"Groq API error: {error_msg}")
            raise RuntimeError(f"Groq error: {error_msg}")
        
        full_response = result["choices"][0]["message"]["content"].strip()
        
        logger.info(f"Groq response length: {len(full_response)} chars")
        
        # Parse trilingual sections using the new format markers
        # Structure: sections[section_num][language_code] = content
        sections = {
            1: {"ar": "", "fr": "", "en": ""},  # literal_meaning
            2: {"ar": "", "fr": "", "en": ""},  # hidden_meaning
            3: {"ar": "", "fr": "", "en": ""},  # moral_lesson
            4: {"ar": "", "fr": "", "en": ""},  # key_phrases
            5: {"ar": "", "fr": "", "en": ""},  # narrative
            6: {"ar": "", "fr": "", "en": ""},  # explanation
            7: {"en": ""},  # visual_prompt (English only)
            8: {"ar": "", "fr": "", "en": ""}   # visual_summary
        }
        
        language_map = {"ARABIC": "ar", "FRENCH": "fr", "ENGLISH": "en"}
        current_section = None
        current_lang = None
        
        lines = full_response.split("\n")
        for line in lines:
            # Check for section markers [1A: ... (ARABIC)]
            if "[1" in line and "LITERAL" in line:
                if "ARABIC" in line:
                    current_section, current_lang = 1, "ar"
                elif "FRENCH" in line:
                    current_section, current_lang = 1, "fr"
                elif "ENGLISH" in line:
                    current_section, current_lang = 1, "en"
            elif "[2" in line and "HIDDEN" in line:
                if "ARABIC" in line:
                    current_section, current_lang = 2, "ar"
                elif "FRENCH" in line:
                    current_section, current_lang = 2, "fr"
                elif "ENGLISH" in line:
                    current_section, current_lang = 2, "en"
            elif "[3" in line and "MORAL" in line:
                if "ARABIC" in line:
                    current_section, current_lang = 3, "ar"
                elif "FRENCH" in line:
                    current_section, current_lang = 3, "fr"
                elif "ENGLISH" in line:
                    current_section, current_lang = 3, "en"
            elif "[4" in line and "KEY" in line:
                if "ARABIC" in line:
                    current_section, current_lang = 4, "ar"
                elif "FRENCH" in line:
                    current_section, current_lang = 4, "fr"
                elif "ENGLISH" in line:
                    current_section, current_lang = 4, "en"
            elif "[5" in line and "NARRATIVE" in line:
                if "ARABIC" in line:
                    current_section, current_lang = 5, "ar"
                elif "FRENCH" in line:
                    current_section, current_lang = 5, "fr"
                elif "ENGLISH" in line:
                    current_section, current_lang = 5, "en"
            elif "[6" in line and "CULTURAL" in line:
                if "ARABIC" in line:
                    current_section, current_lang = 6, "ar"
                elif "FRENCH" in line:
                    current_section, current_lang = 6, "fr"
                elif "ENGLISH" in line:
                    current_section, current_lang = 6, "en"
            elif "[7" in line and "VISUAL PROMPT" in line:
                current_section, current_lang = 7, "en"  # Visual prompt English only
            elif "[8" in line and "VISUAL SUMMARY" in line:
                if "ARABIC" in line:
                    current_section, current_lang = 8, "ar"
                elif "FRENCH" in line:
                    current_section, current_lang = 8, "fr"
                elif "ENGLISH" in line:
                    current_section, current_lang = 8, "en"
            elif line.strip() and current_section and current_lang:
                # Add content to current section/language
                sections[current_section][current_lang] += line + "\n"
        
        # Clean all sections
        for section_num in sections:
            for lang_code in sections[section_num]:
                sections[section_num][lang_code] = sections[section_num][lang_code].strip()
        
        # Log parsing results
        logger.info(f"✓ Parsed {len([s for s in sections if any(sections[s].values())])} sections")
        
        # Fallback if visual_prompt is empty
        visual_prompt = sections[7].get("en", "").strip()
        if not visual_prompt:
            logger.warning("⚠️ Visual prompt is empty, generating fallback")
            explanation_en = sections[6].get("en", "").strip()
            visual_prompt = f"An artistic illustration representing: {explanation_en[:200]}. Tunisian style, cultural, meaningful."
            sections[7]["en"] = visual_prompt
        
        return {
            "literal_meaning": sections[1],
            "hidden_meaning": sections[2],
            "moral_lesson": sections[3],
            "key_phrases": sections[4],
            "narrative": sections[5],
            "explanation": sections[6],
            "visual_prompt": sections[7].get("en", ""),
            "visual_summary": sections[8]
        }
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Request error calling Groq: {e}")
        raise RuntimeError(f"Failed to call Groq API: {str(e)}")
    except Exception as e:
        logger.error(f"Error parsing Groq response: {e}", exc_info=True)
        raise RuntimeError(f"Error processing Groq response: {str(e)}")


def initialize_pipeline(proverbs_path: str = "website/proverbs.json") -> None:
    """
    Initialize the complete RAG pipeline.
    
    This should be called once during app startup.
    Initializes local FAISS embeddings, vocabulary reference, and validates Groq API access.
    
    Args:
        proverbs_path: Path to proverbs.json
    """
    logger.info("=" * 70)
    logger.info("Initializing Groq RAG Pipeline")
    logger.info("=" * 70)
    
    try:
        # Step 1: Initialize embeddings (CPU-based, local)
        logger.info("\n[1/4] Initializing local embeddings...")
        initialize_embedding_model()
        logger.info("✓ Embeddings initialized")
        
        # Step 2: Initialize FAISS vector store (local, no internet)
        logger.info("\n[2/4] Initializing FAISS vector store...")
        initialize_faiss_vectorstore(proverbs_path)
        logger.info("✓ FAISS vector store ready")
        
        # Step 3: Load Arabic vocabulary reference
        logger.info("\n[3/4] Loading Arabic vocabulary reference...")
        load_vocabulary_reference()
        logger.info("✓ Vocabulary knowledge base loaded")
        
        # Step 4: Validate Groq API key
        logger.info("\n[4/4] Validating Groq API key...")
        try:
            api_key = get_groq_api_key()
            logger.info(f"✓ Groq API key found: {api_key[:15]}...")
        except ValueError as e:
            logger.warning(f"⚠️  Groq API key not configured: {e}")
            logger.warning("   The /api/explain endpoint will fail until GROQ_API_KEY is set")
            logger.warning("   Set GROQ_API_KEY in .env or environment variables to enable")
        
        logger.info("\n" + "=" * 70)
        logger.info("✅ Groq RAG Pipeline initialized successfully!")
        logger.info("=" * 70)
        logger.info("\nPipeline Details:")
        logger.info("  • Retrieval: Local FAISS (all-MiniLM-L6-v2)")
        logger.info("  • Generation: Groq API (Llama 3.3 70B)")
        logger.info("  • Memory: ~100MB (CPU only)")
        logger.info("  • Speed: ~1-3 seconds per explanation")
        logger.info("  • Cost: FREE (Groq API free tier, no rate limits)")
        logger.info("=" * 70 + "\n")
        
    except Exception as e:
        logger.error(f"\n❌ Pipeline initialization failed: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    # Test the pipeline
    logging.basicConfig(level=logging.INFO)
    
    try:
        print("\n🚀 Initializing Groq RAG pipeline...")
        initialize_pipeline()
        
        print("\n📝 Testing with sample proverb...")
        test_proverb = "من قال سلام قال سلام"  # "Who says peace, says peace"
        
        print(f"Proverb: {test_proverb}\n")
        explanation = generate_explanation(test_proverb)
        
        print("Explanation:")
        print("-" * 70)
        print(explanation)
        print("-" * 70)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
