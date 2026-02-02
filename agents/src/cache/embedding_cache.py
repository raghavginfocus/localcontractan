"""
Embedding Cache using Redis.

Caches vector embeddings to avoid redundant embedding computations.
"""

import hashlib
import json
import numpy as np
from typing import Optional
import redis
from logger import get_module_logger

logger = get_module_logger(__name__)


class EmbeddingCache:
    """
    Redis-based cache for vector embeddings.
    
    Features:
    - TTL-based expiration
    - Text normalization for better hit rates
    - Efficient numpy array serialization
    - Cache statistics tracking
    """
    
    def __init__(
        self,
        redis_url: str = "redis://localhost:6379/1",
        default_ttl: int = 86400,  # 24 hours
        enable_stats: bool = True,
    ):
        """
        Initialize embedding cache.
        
        Args:
            redis_url: Redis connection URL (using DB 1)
            default_ttl: Default TTL in seconds
            enable_stats: Whether to track cache statistics
        """
        self.redis_client = redis.from_url(
            redis_url,
            decode_responses=False,  # Binary mode for numpy arrays
            socket_connect_timeout=5,
            socket_timeout=5,
        )
        self.default_ttl = default_ttl
        self.enable_stats = enable_stats
        
        # Test connection
        try:
            self.redis_client.ping()
            logger.info(
                "Embedding cache initialized",
                redis_url=redis_url,
                default_ttl=default_ttl
            )
        except redis.ConnectionError as e:
            logger.error("Failed to connect to Redis", error=str(e))
            raise
    
    def _get_cache_key(
        self,
        text: str,
        model: str = "default",
    ) -> str:
        """
        Generate cache key from text and model.
        
        Args:
            text: Text to embed
            model: Embedding model name
            
        Returns:
            Cache key string
        """
        # Normalize text (remove extra whitespace)
        normalized_text = " ".join(text.split())
        
        # Include model in key
        cache_input = f"{model}:{normalized_text}"
        
        # Use hash for compact key
        key_hash = hashlib.sha256(cache_input.encode()).hexdigest()
        
        return f"emb:{model}:{key_hash}".encode()
    
    def _serialize_embedding(self, embedding: list[float]) -> bytes:
        """
        Serialize embedding to bytes.
        
        Args:
            embedding: Embedding vector
            
        Returns:
            Serialized bytes
        """
        # Convert to numpy array and serialize
        arr = np.array(embedding, dtype=np.float32)
        return arr.tobytes()
    
    def _deserialize_embedding(self, data: bytes) -> list[float]:
        """
        Deserialize embedding from bytes.
        
        Args:
            data: Serialized bytes
            
        Returns:
            Embedding vector
        """
        # Deserialize numpy array
        arr = np.frombuffer(data, dtype=np.float32)
        return arr.tolist()
    
    def get(
        self,
        text: str,
        model: str = "default",
    ) -> Optional[list[float]]:
        """
        Get cached embedding.
        
        Args:
            text: Text to embed
            model: Embedding model name
            
        Returns:
            Cached embedding or None if not found
        """
        cache_key = self._get_cache_key(text, model)
        
        try:
            cached_value = self.redis_client.get(cache_key)
            
            if cached_value:
                # Update stats
                if self.enable_stats:
                    self.redis_client.incr(b"emb_cache:hits")
                
                embedding = self._deserialize_embedding(cached_value)
                
                logger.debug(
                    "Embedding cache hit",
                    model=model,
                    key_hash=cache_key.decode()[-8:],
                    embedding_dim=len(embedding),
                )
                
                return embedding
            else:
                # Update stats
                if self.enable_stats:
                    self.redis_client.incr(b"emb_cache:misses")
                
                return None
                
        except redis.RedisError as e:
            logger.warning("Redis get failed", error=str(e))
            return None
        except Exception as e:
            logger.warning("Embedding deserialization failed", error=str(e))
            return None
    
    def set(
        self,
        text: str,
        embedding: list[float],
        model: str = "default",
        ttl: Optional[int] = None,
    ) -> bool:
        """
        Cache embedding.
        
        Args:
            text: Text to embed
            embedding: Embedding vector to cache
            model: Embedding model name
            ttl: Optional custom TTL (uses default if None)
            
        Returns:
            True if cached successfully
        """
        cache_key = self._get_cache_key(text, model)
        
        if ttl is None:
            ttl = self.default_ttl
        
        try:
            serialized = self._serialize_embedding(embedding)
            self.redis_client.setex(cache_key, ttl, serialized)
            
            logger.debug(
                "Embedding cached",
                model=model,
                key_hash=cache_key.decode()[-8:],
                ttl=ttl,
                embedding_dim=len(embedding),
            )
            
            return True
            
        except redis.RedisError as e:
            logger.warning("Redis set failed", error=str(e))
            return False
        except Exception as e:
            logger.warning("Embedding serialization failed", error=str(e))
            return False
    
    def invalidate(
        self,
        text: str,
        model: str = "default",
    ) -> bool:
        """
        Invalidate a specific cached embedding.
        
        Args:
            text: Text to embed
            model: Embedding model name
            
        Returns:
            True if entry was found and removed
        """
        cache_key = self._get_cache_key(text, model)
        
        try:
            result = self.redis_client.delete(cache_key)
            return result > 0
        except redis.RedisError as e:
            logger.warning("Redis delete failed", error=str(e))
            return False
    
    def clear_all(self) -> int:
        """
        Clear all embedding cache entries.
        
        Returns:
            Number of entries removed
        """
        try:
            keys = self.redis_client.keys(b"emb:*")
            if keys:
                count = self.redis_client.delete(*keys)
                logger.info("Embedding cache cleared", entries_removed=count)
                return count
            return 0
        except redis.RedisError as e:
            logger.warning("Redis clear failed", error=str(e))
            return 0
    
    def get_stats(self) -> dict[str, any]:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with cache stats
        """
        try:
            hits = int(self.redis_client.get(b"emb_cache:hits") or 0)
            misses = int(self.redis_client.get(b"emb_cache:misses") or 0)
            total_requests = hits + misses
            hit_rate = hits / total_requests if total_requests > 0 else 0.0
            
            # Count total cached entries
            size = len(self.redis_client.keys(b"emb:*"))
            
            stats = {
                "size": size,
                "hits": hits,
                "misses": misses,
                "hit_rate": hit_rate,
                "total_requests": total_requests,
            }
            
            # Log stats periodically
            if total_requests > 0 and total_requests % 100 == 0:
                logger.info(
                    "Embedding cache statistics",
                    **stats,
                    hit_rate_pct=f"{hit_rate:.1%}",
                )
            
            return stats
            
        except redis.RedisError as e:
            logger.warning("Failed to get cache stats", error=str(e))
            return {
                "size": 0,
                "hits": 0,
                "misses": 0,
                "hit_rate": 0.0,
                "total_requests": 0,
            }
    
    def reset_stats(self) -> None:
        """Reset cache statistics."""
        try:
            self.redis_client.delete(b"emb_cache:hits", b"emb_cache:misses")
            logger.debug("Embedding cache statistics reset")
        except redis.RedisError as e:
            logger.warning("Failed to reset stats", error=str(e))


# Global cache instance
_embedding_cache: Optional[EmbeddingCache] = None


def get_embedding_cache(
    redis_url: str = "redis://localhost:6379/1",
    default_ttl: int = 86400,
) -> EmbeddingCache:
    """
    Get or create global embedding cache instance.
    
    Args:
        redis_url: Redis connection URL
        default_ttl: Default TTL in seconds
        
    Returns:
        EmbeddingCache instance
    """
    global _embedding_cache
    
    if _embedding_cache is None:
        _embedding_cache = EmbeddingCache(
            redis_url=redis_url,
            default_ttl=default_ttl,
        )
    
    return _embedding_cache


