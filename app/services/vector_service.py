import os
import numpy as np
import faiss
import hashlib
from typing import List, Tuple, Optional, Dict, Any
from sentence_transformers import SentenceTransformer
import json
import logging
from app.config import settings
from app.core.redis_client import cache_service

logger = logging.getLogger(__name__)


class VectorService:
    """Service for managing FAISS vector database operations."""

    def __init__(self):
        self.embedding_model = SentenceTransformer(settings.embedding_model)
        self.dimension = settings.embedding_dimension
        self.index_path = settings.faiss_index_path

        # Ensure index directory exists
        os.makedirs(self.index_path, exist_ok=True)

        # Initialize FAISS indices (one per user for now)
        self.indices = {}
        self.id_mappings = {}  # Map FAISS IDs to memory IDs

    def _get_user_index_path(self, user_id: int) -> str:
        """Get the path for user's FAISS index."""
        return os.path.join(self.index_path, f"user_{user_id}_index.faiss")

    def _get_user_mapping_path(self, user_id: int) -> str:
        """Get the path for user's ID mapping."""
        return os.path.join(self.index_path, f"user_{user_id}_mapping.json")

    def _load_user_index(self, user_id: int) -> faiss.Index:
        """Load or create FAISS index for user."""
        index_path = self._get_user_index_path(user_id)
        mapping_path = self._get_user_mapping_path(user_id)

        if os.path.exists(index_path):
            # Load existing index
            index = faiss.read_index(index_path)
            # Load ID mapping
            if os.path.exists(mapping_path):
                with open(mapping_path, 'r') as f:
                    self.id_mappings[user_id] = json.load(f)
        else:
            # Create new index
            index = faiss.IndexFlatIP(self.dimension)  # Inner product for cosine similarity
            self.id_mappings[user_id] = {}

        self.indices[user_id] = index
        return index

    def _save_user_index(self, user_id: int):
        """Save FAISS index and ID mapping for user."""
        if user_id in self.indices:
            index_path = self._get_user_index_path(user_id)
            mapping_path = self._get_user_mapping_path(user_id)

            faiss.write_index(self.indices[user_id], index_path)
            with open(mapping_path, 'w') as f:
                json.dump(self.id_mappings[user_id], f)

    def generate_embedding(self, text: str, use_cache: bool = True) -> List[float]:
        """
        Generate embedding for text using sentence transformer.
        
        Args:
            text: Text to generate embedding for
            use_cache: Whether to use cache for embeddings (sync function, cache check happens in async wrapper)
        
        Returns:
            List[float]: Normalized embedding vector
        """
        # Generate embedding
        embedding = self.embedding_model.encode(text, convert_to_numpy=True)
        # Normalize for cosine similarity
        embedding = embedding / np.linalg.norm(embedding)
        return embedding.tolist()
    
    async def generate_embedding_async(self, text: str, use_cache: bool = True) -> List[float]:
        """
        Generate embedding for text with caching support (async version).
        
        Args:
            text: Text to generate embedding for
            use_cache: Whether to use cache for embeddings
        
        Returns:
            List[float]: Normalized embedding vector
        """
        # Check cache first if enabled
        if use_cache:
            cache_key = f"embedding:{hashlib.md5(text.encode()).hexdigest()}"
            cached = await cache_service.get(cache_key)
            if cached:
                logger.debug("Embedding cache hit", extra={"text_length": len(text)})
                return cached
        
        # Generate embedding (synchronous call)
        embedding_list = self.generate_embedding(text, use_cache=False)
        
        # Cache the result
        if use_cache:
            cache_key = f"embedding:{hashlib.md5(text.encode()).hexdigest()}"
            await cache_service.set(cache_key, embedding_list, ttl=86400)  # Cache for 24 hours
        
        return embedding_list
    
    def generate_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts in batch (more efficient).
        
        Args:
            texts: List of texts to generate embeddings for
        
        Returns:
            List[List[float]]: List of normalized embedding vectors
        """
        if not texts:
            return []
        
        # Batch encode (more efficient than individual calls)
        embeddings = self.embedding_model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
        
        # Normalize each embedding
        normalized_embeddings = []
        for embedding in embeddings:
            normalized = embedding / np.linalg.norm(embedding)
            normalized_embeddings.append(normalized.tolist())
        
        return normalized_embeddings

    def add_memory_embedding(self, user_id: int, memory_id: int, embedding: List[float]):
        """Add memory embedding to FAISS index."""
        index = self._load_user_index(user_id)

        # Convert to numpy array
        embedding_np = np.array([embedding], dtype=np.float32)

        # Add to index
        index.add(embedding_np)

        # Update ID mapping
        faiss_id = index.ntotal - 1
        self.id_mappings[user_id][str(faiss_id)] = memory_id

        # Save index
        self._save_user_index(user_id)

    def add_memory_embeddings_batch(self, user_id: int, memory_embeddings: List[Tuple[int, List[float]]]):
        """Add multiple memory embeddings to FAISS index."""
        if not memory_embeddings:
            return

        index = self._load_user_index(user_id)

        # Convert to numpy array
        embeddings = np.array([emb for _, emb in memory_embeddings], dtype=np.float32)

        # Add to index
        index.add(embeddings)

        # Update ID mappings
        start_id = index.ntotal - len(memory_embeddings)
        for i, (memory_id, _) in enumerate(memory_embeddings):
            faiss_id = start_id + i
            self.id_mappings[user_id][str(faiss_id)] = memory_id

        # Save index
        self._save_user_index(user_id)

    def search_similar(self, user_id: int, query_embedding: List[float], top_k: int = 10) -> List[Tuple[int, float]]:
        """Search for similar memories using embedding."""
        index = self._load_user_index(user_id)

        if index.ntotal == 0:
            return []

        # Convert query to numpy
        query_np = np.array([query_embedding], dtype=np.float32)

        # Search
        scores, indices = index.search(query_np, min(top_k, index.ntotal))

        results = []
        for score, faiss_id in zip(scores[0], indices[0]):
            if faiss_id != -1:  # Valid result
                memory_id = self.id_mappings[user_id].get(str(faiss_id))
                if memory_id is not None:
                    results.append((memory_id, float(score)))

        return results

    def update_memory_embedding(self, user_id: int, memory_id: int, new_embedding: List[float]):
        """Update embedding for existing memory (rebuilds index)."""
        # For now, we'll rebuild the index - this is inefficient but simple
        # In production, consider using IndexIVF or other updatable indices
        index = self._load_user_index(user_id)

        # Find the FAISS ID for this memory
        faiss_id_to_update = None
        for faiss_id, mem_id in self.id_mappings[user_id].items():
            if mem_id == memory_id:
                faiss_id_to_update = int(faiss_id)
                break

        if faiss_id_to_update is not None:
            # Remove old embedding and rebuild index
            # This is a simplified approach - in production use proper index updates
            self._rebuild_user_index(user_id)
            self.add_memory_embedding(user_id, memory_id, new_embedding)

    def _rebuild_user_index(self, user_id: int, embeddings_data: Optional[List[Tuple[int, List[float]]]] = None):
        """
        Rebuild index for user with optional embeddings data.
        
        Args:
            user_id: User ID
            embeddings_data: Optional list of (memory_id, embedding) tuples to rebuild with
        """
        # Create new index
        self.indices[user_id] = faiss.IndexFlatIP(self.dimension)
        self.id_mappings[user_id] = {}
        
        # If embeddings data provided, add them
        if embeddings_data:
            self.add_memory_embeddings_batch(user_id, embeddings_data)
            logger.info(f"Rebuilt index for user {user_id} with {len(embeddings_data)} embeddings")
        else:
            logger.warning(f"Rebuilt empty index for user {user_id} - embeddings may be lost")

    def delete_memory_embedding(self, user_id: int, memory_id: int):
        """Delete embedding from index (requires rebuild)."""
        # Remove from mapping
        faiss_ids_to_remove = [
            faiss_id for faiss_id, mem_id in self.id_mappings[user_id].items()
            if mem_id == memory_id
        ]

        for faiss_id in faiss_ids_to_remove:
            del self.id_mappings[user_id][faiss_id]

        # Rebuild index if needed
        if faiss_ids_to_remove:
            self._rebuild_user_index(user_id)

    def get_cluster_embeddings(self, user_id: int, memory_ids: List[int]) -> List[List[float]]:
        """Get embeddings for a cluster of memories."""
        # This would typically query the database for embeddings
        # For now, return empty list
        return []

    def calculate_similarity(self, embedding1: List[float], embedding2: List[float]) -> float:
        """Calculate cosine similarity between two embeddings."""
        vec1 = np.array(embedding1)
        vec2 = np.array(embedding2)
        return float(np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2)))


# Global vector service instance
vector_service = VectorService()
