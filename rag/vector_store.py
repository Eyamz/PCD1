"""
Vector store management using ChromaDB.
Embeddings: GPU (if available) | ChromaDB & Vector Search: CPU
"""

import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
from typing import Callable, List, Dict, Optional
import os
from utils.device import get_device_for_component


_EMBEDDER_CACHE = {}


def _configure_hf_timeouts() -> None:
    # Hugging Face HEAD/etag requests can timeout on slow networks; raise the defaults.
    os.environ.setdefault("HF_HUB_ETAG_TIMEOUT", "60")
    os.environ.setdefault("HF_HUB_DOWNLOAD_TIMEOUT", "300")


class VectorStore:
    """
    Vector store for document embeddings using ChromaDB.
    
    Device assignments:
    - Embeddings (SentenceTransformer): GPU if available
    - ChromaDB storage: CPU (always)
    - Vector search: CPU (always)
    """
    
    def __init__(
        self,
        persist_directory: str = "data/chromadb",
        model_name: str = "all-MiniLM-L6-v2",
        collection_name: str = "proverbs",
    ):
        """
        Initialize vector store.
        
        Args:
            persist_directory: Directory to persist ChromaDB
            model_name: Sentence transformer model name
            collection_name: Default ChromaDB collection name
        """
        self.persist_directory = persist_directory
        self.model_name = model_name
        self.collection_name = collection_name
        self.client = None
        self.collection = None
        self.embedder = None
        self.embeddings_device = get_device_for_component('embeddings')
        print(f"VectorStore: Embeddings will use {self.embeddings_device}, ChromaDB on CPU")
        
    def initialize(
        self,
        collection_name: Optional[str] = None,
        on_update: Optional[Callable[[str, Optional[float]], None]] = None,
    ):
        """
        Initialize ChromaDB client and collection.
        
        Args:
            collection_name: Name of the collection
            on_update: Optional callback (message, progress 0..1)
        """
        def update(message: str, progress: Optional[float] = None) -> None:
            if on_update is not None:
                try:
                    on_update(message, progress)
                except Exception:
                    pass

        # Create persist directory if it doesn't exist
        os.makedirs(self.persist_directory, exist_ok=True)

        update("Connecting to ChromaDB...", 0.05)
        
        # Initialize ChromaDB client with persistence
        self.client = chromadb.PersistentClient(
            path=self.persist_directory,
            settings=Settings(anonymized_telemetry=False)
        )
        
        # Get or create collection
        name = collection_name if collection_name else self.collection_name
        update(f"Opening collection: {name}", 0.10)
        self.collection = self.client.get_or_create_collection(
            name=name,
            metadata={"hnsw:space": "cosine"}
        )
        
        # Initialize embedder on GPU if available (cached per model+device)
        _configure_hf_timeouts()
        cache_key = (self.model_name, self.embeddings_device)
        if cache_key in _EMBEDDER_CACHE:
            self.embedder = _EMBEDDER_CACHE[cache_key]
            print(f"✓ Embeddings model reused from cache on {self.embeddings_device}")
            update(f"Embeddings model ready (cached) on {self.embeddings_device}", 0.95)
        else:
            update(f"Loading embeddings model ({self.model_name}) on {self.embeddings_device}...", 0.40)
            self.embedder = SentenceTransformer(self.model_name, device=self.embeddings_device)
            _EMBEDDER_CACHE[cache_key] = self.embedder
            print(f"✓ Embeddings model loaded on {self.embeddings_device}")
            update(f"Embeddings model loaded on {self.embeddings_device}", 0.95)

        update("Vector store ready.", 1.0)
        
    def add_documents(self, documents: List[Dict], ids: Optional[List[str]] = None) -> None:
        """
        Add documents to vector store.
        
        Args:
            documents: List of documents with 'text' and optional 'metadata'
        """
        if not self.collection or not self.embedder:
            raise RuntimeError("VectorStore not initialized. Call initialize() first.")
        
        texts = [doc.get("text", "") for doc in documents]
        metadatas = [doc.get("metadata", {}) for doc in documents]
        
        # Generate embeddings
        embeddings = self.embedder.encode(texts, show_progress_bar=True).tolist()
        
        # Generate IDs (unless provided)
        if ids is None:
            existing_count = self.collection.count()
            ids = [f"doc_{existing_count + i}" for i in range(len(texts))]
        
        # Add to collection
        self.collection.add(
            documents=texts,
            embeddings=embeddings,
            metadatas=metadatas,
            ids=ids
        )
    
    def query(self, query_text: str, n_results: int = 5) -> List[Dict]:
        """
        Query vector store for similar documents.
        
        Args:
            query_text: Query text
            n_results: Number of results to return
            
        Returns:
            List of relevant documents with metadata and distances
        """
        if not self.collection or not self.embedder:
            raise RuntimeError("VectorStore not initialized. Call initialize() first.")
        
        # Generate query embedding
        query_embedding = self.embedder.encode([query_text]).tolist()
        
        # Query collection
        results = self.collection.query(
            query_embeddings=query_embedding,
            n_results=n_results
        )
        
        # Format results
        formatted_results = []
        for i in range(len(results["ids"][0])):
            formatted_results.append({
                "id": results["ids"][0][i],
                "text": results["documents"][0][i],
                "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                "distance": results["distances"][0][i] if results["distances"] else None
            })
        
        return formatted_results
    
    def delete_collection(self):
        """Delete the collection."""
        if self.client and self.collection:
            self.client.delete_collection(self.collection.name)
            self.collection = None
    
    def get_collection_count(self) -> int:
        """
        Get number of documents in collection.
        
        Returns:
            Document count
        """
        if not self.collection:
            return 0
        return self.collection.count()