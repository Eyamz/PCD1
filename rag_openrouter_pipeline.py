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
from typing import Optional, List, Tuple
import requests

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
            vectorstore = FAISS.load_local("faiss_vectorstore_proverbs", embedding_model)
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
    
    prompt = f"""You are a cultural expert specializing in Tunisian/Arabic proverbs, traditions, and wisdom.

Your task: Provide a rich, nuanced explanation of this Tunisian proverb that helps readers understand its cultural depth.

TARGET PROVERB: "{proverb}"

KNOWLEDGE BASE CONTEXT (Similar Proverbs from our Collection):
{context}
{themes_text}

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


def generate_explanation(proverb: str, max_tokens: int = 512) -> str:
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


def initialize_pipeline(proverbs_path: str = "website/proverbs.json") -> None:
    """
    Initialize the complete RAG pipeline.
    
    This should be called once during app startup.
    Initializes local FAISS embeddings and validates Groq API access.
    
    Args:
        proverbs_path: Path to proverbs.json
    """
    logger.info("=" * 70)
    logger.info("Initializing Groq RAG Pipeline")
    logger.info("=" * 70)
    
    try:
        # Step 1: Initialize embeddings (CPU-based, local)
        logger.info("\n[1/3] Initializing local embeddings...")
        initialize_embedding_model()
        logger.info("✓ Embeddings initialized")
        
        # Step 2: Initialize FAISS vector store (local, no internet)
        logger.info("\n[2/3] Initializing FAISS vector store...")
        initialize_faiss_vectorstore(proverbs_path)
        logger.info("✓ FAISS vector store ready")
        
        # Step 3: Validate Groq API key
        logger.info("\n[3/3] Validating Groq API key...")
        api_key = get_groq_api_key()
        logger.info(f"✓ Groq API key found: {api_key[:15]}...")
        
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
