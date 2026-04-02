"""
⚠️  BACKUP/LEGACY FILE - NOT IN USE

This module is kept as a reference/backup for local Llama 2 inference.
The project now uses: rag_openrouter_pipeline.py (OpenRouter + Qwen 3.6)

Original Llama 2 RAG Pipeline for Tunisian Proverbs
────────────────────────────────────────────────────
This implementation used:
- FAISS for semantic similarity search
- Sentence transformers for embeddings
- Llama 2 7B for explanation generation

⬇️  CURRENT PIPELINE (in use):
See: rag_openrouter_pipeline.py
- Uses OpenRouter API (Qwen 3.6+)
- Local FAISS retrieval (no internet for embeddings)
- No GPU required
- Faster and cheaper

Key Functions (LEGACY - DO NOT USE):
    initialize_pipeline() - Load models and FAISS vector store
    generate_explanation() - Generate detailed explanation for a proverb
"""

import json
import logging
from pathlib import Path
from typing import Optional, List
import torch
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

logger = logging.getLogger(__name__)

# Global state
vectorstore: Optional[FAISS] = None
retriever: Optional[object] = None
model: Optional[AutoModelForCausalLM] = None
tokenizer: Optional[AutoTokenizer] = None
embedding_model: Optional[HuggingFaceEmbeddings] = None


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


def initialize_llama2_model(device: str = "cuda") -> tuple:
    """Initialize Llama 2 7B with 4-bit quantization."""
    global model, tokenizer
    
    if model is not None and tokenizer is not None:
        logger.info("Llama 2 model already loaded")
        return model, tokenizer
    
    model_name = "meta-llama/Llama-2-7b-chat-hf"
    
    logger.info(f"Loading Llama 2 tokenizer from {model_name}...")
    logger.info("NOTE: This model requires HuggingFace authentication.")
    logger.info("Run: huggingface-cli login")
    logger.info("Or set HF_TOKEN environment variable")
    
    try:
        tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
    except Exception as e:
        logger.error(f"Failed to load Llama 2: {e}")
        logger.info("Falling back to TinyLlama (no auth required)...")
        model_name = "TinyLlama/TinyLlama-1.1B-Chat-v1.0"
        tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
    
    logger.info("Setting up 4-bit quantization...")
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_use_double_quant=True,
        bnb_4bit_compute_dtype=torch.bfloat16
    )
    
    logger.info(f"Loading {model_name} with 4-bit quantization on {device}...")
    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        quantization_config=bnb_config,
        device_map="auto",
        trust_remote_code=True
    )
    model.eval()
    
    logger.info(f"✓ Model loaded with 4-bit quantization")
    return model, tokenizer


def retrieve_context(proverb: str) -> str:
    """Retrieve similar proverbs from FAISS vector store."""
    if retriever is None:
        raise RuntimeError("Retriever not initialized. Call initialize_pipeline() first.")
    
    results = retriever.invoke(proverb)
    context = ""
    
    for i, doc in enumerate(results, 1):
        context += f"\n--- Similar Proverb {i} ---\n"
        context += doc.page_content
        context += "\n"
    
    return context


def build_prompt(proverb: str, context: str) -> str:
    """Build RAG prompt with context for Llama 2."""
    prompt = f"""<s>[INST]
You are an expert on Tunisian culture, Arabic language, and proverbs.

Explain this Tunisian proverb in detail:

PROVERB: "{proverb}"

KNOWLEDGE BASE CONTEXT (similar proverbs from our database):
{context}

Provide a detailed explanation that includes:
1. Literal meaning of the proverb
2. Cultural and contextual significance in Tunisian society
3. When and how people use this proverb
4. Connection to the related proverbs in the knowledge base
5. One concrete example of its usage
6. Why it's important to Tunisian identity

Write in both Arabic and English for clarity.
[/INST]

Here is a detailed explanation:

"""
    return prompt


def generate_explanation(proverb: str, max_tokens: int = 512) -> str:
    """
    Generate a detailed explanation for a proverb using RAG + Llama 2.
    
    Args:
        proverb: Tunisian proverb in Arabic
        max_tokens: Maximum tokens to generate (default 512)
    
    Returns:
        Detailed explanation combining retrieved knowledge + AI generation
    """
    if model is None or tokenizer is None:
        raise RuntimeError("Model not initialized. Call initialize_pipeline() first.")
    
    logger.info(f"Generating explanation for: {proverb[:50]}...")
    
    # Step 1: Retrieve context
    context = retrieve_context(proverb)
    
    # Step 2: Build prompt
    prompt = build_prompt(proverb, context)
    
    # Step 3: Tokenize
    inputs = tokenizer(
        prompt,
        return_tensors="pt",
        truncation=True,
        max_length=2048
    ).to("cuda" if torch.cuda.is_available() else "cpu")
    
    # Step 4: Generate
    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=max_tokens,
            temperature=0.7,
            do_sample=True,
            top_p=0.9,
            pad_token_id=tokenizer.eos_token_id,
            repetition_penalty=1.1
        )
    
    # Step 5: Decode and clean
    full_output = tokenizer.decode(outputs[0], skip_special_tokens=True)
    response = full_output[len(prompt):].strip()
    response = response.replace("[/INST]", "").replace("<s>", "").strip()
    
    logger.info("✓ Explanation generated successfully")
    return response


def initialize_pipeline(
    device: str = "cuda",
    proverbs_path: str = "website/proverbs.json"
) -> None:
    """
    Initialize the complete RAG pipeline.
    
    This should be called once during app startup.
    
    Args:
        device: Device to use ('cuda' or 'cpu')
        proverbs_path: Path to proverbs.json
    """
    logger.info("=" * 70)
    logger.info("Initializing Llama 2 RAG Pipeline")
    logger.info("=" * 70)
    
    try:
        # Initialize embeddings
        initialize_embedding_model()
        
        # Initialize FAISS vector store
        initialize_faiss_vectorstore(proverbs_path)
        
        # Initialize Llama 2
        initialize_llama2_model(device)
        
        logger.info("=" * 70)
        logger.info("✅ RAG Pipeline initialized successfully!")
        logger.info("=" * 70)
        
    except Exception as e:
        logger.error(f"Pipeline initialization failed: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    # Test the pipeline
    logging.basicConfig(level=logging.INFO)
    
    initialize_pipeline()
    
    test_proverb = "الجار قبل الدار"
    print(f"\nTest: {test_proverb}")
    explanation = generate_explanation(test_proverb)
    print(f"\nExplanation:\n{explanation}")
