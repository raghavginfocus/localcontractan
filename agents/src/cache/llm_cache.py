"""
LLM Response Cache using Redis.

Caches LLM responses to avoid redundant API calls for identical prompts.
"""

import hashlib
import json
from typing import Any, Optional
import redis
from logger import get_module_logger

logger = get_module_logger(__name__)


class LLMCache:
    """
    Redis-based cache for LLM responses.
    
    Features:
    - TTL-based expiration
    - Prompt normalization for better hit rates
    - Separate namespaces for different LLM providers
    - Cache statistics tracking
    """
    
    def __init__(
        self,
        redis_url: str = "redis://localhost:6379/0",
        default_ttl: int = 3600,  # 1 hour
        enable_stats: bool = True,
    ):
        """
        Initialize LLM cache.
        
        Args:
            redis_url: Redis connection URL
            default_ttl: Default TTL in seconds
            enable_stats: Whether to track cache statistics
        """
        self.redis_client = redis.from_url(
            redis_url,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
        )
        self.default_ttl = default_ttl
        self.enable_stats = enable_stats
        
        # Test connection
        try:
            self.redis_client.ping()
            logger.info(
                "LLM cache initialized",
                redis_url=redis_url,
                default_ttl=default_ttl
            )
        except redis.ConnectionError as e:
            logger.error("Failed to connect to Redis", error=str(e))
            raise
    
    def _get_cache_key(
        self,
        prompt: str,
        provider: str = "default",
        model: str = "default",
        temperature: float = 0.0,
    ) -> str:
        """
        Generate cache key from prompt and parameters.
        
        Args:
            prompt: LLM prompt
            provider: LLM provider name
            model: Model name
            temperature: Temperature parameter
            
        Returns:
            Cache key string
        """
        # Normalize prompt (remove extra whitespace)
        normalized_prompt = " ".join(prompt.split())
        
        # Include parameters in key
        cache_input = f"{provider}:{model}:{temperature}:{normalized_prompt}"
        
        # Use hash for compact key
        key_hash = hashlib.sha256(cache_input.encode()).hexdigest()
        
        return f"llm:{provider}:{model}:{key_hash}"
    
    def get(
        self,
        prompt: str,
        provider: str = "default",
        model: str = "default",
        temperature: float = 0.0,
    ) -> Optional[str]:
        """
        Get cached LLM response.
        
        Args:
            prompt: LLM prompt
            provider: LLM provider name
            model: Model name
            temperature: Temperature parameter
            
        Returns:
            Cached response or None if not found
        """
        cache_key = self._get_cache_key(prompt, provider, model, temperature)
        
        try:
            cached_value = self.redis_client.get(cache_key)
            
            if cached_value:
                # Update stats
                if self.enable_stats:
                    self.redis_client.incr("llm_cache:hits")
                
                logger.debug(
                    "LLM cache hit",
                    provider=provider,
                    model=model,
                    key_hash=cache_key[-8:],
                )
                
                return cached_value
            else:
                # Update stats
                if self.enable_stats:
                    self.redis_client.incr("llm_cache:misses")
                
                return None
                
        except redis.RedisError as e:
            logger.warning("Redis get failed", error=str(e))
            return None
    
    def set(
        self,
        prompt: str,
        response: str,
        provider: str = "default",
        model: str = "default",
        temperature: float = 0.0,
        ttl: Optional[int] = None,
    ) -> bool:
        """
        Cache LLM response.
        
        Args:
            prompt: LLM prompt
            response: LLM response to cache
            provider: LLM provider name
            model: Model name
            temperature: Temperature parameter
            ttl: Optional custom TTL (uses default if None)
            
        Returns:
            True if cached successfully
        """
        cache_key = self._get_cache_key(prompt, provider, model, temperature)
        
        if ttl is None:
            ttl = self.default_ttl
        
        try:
            self.redis_client.setex(cache_key, ttl, response)
            
            logger.debug(
                "LLM response cached",
                provider=provider,
                model=model,
                key_hash=cache_key[-8:],
                ttl=ttl,
                response_length=len(response),
            )
            
            return True
            
        except redis.RedisError as e:
            logger.warning("Redis set failed", error=str(e))
            return False
    
    def invalidate(
        self,
        prompt: str,
        provider: str = "default",
        model: str = "default",
        temperature: float = 0.0,
    ) -> bool:
        """
        Invalidate a specific cached response.
        
        Args:
            prompt: LLM prompt
            provider: LLM provider name
            model: Model name
            temperature: Temperature parameter
            
        Returns:
            True if entry was found and removed
        """
        cache_key = self._get_cache_key(prompt, provider, model, temperature)
        
        try:
            result = self.redis_client.delete(cache_key)
            return result > 0
        except redis.RedisError as e:
            logger.warning("Redis delete failed", error=str(e))
            return False
    
    def clear_all(self) -> int:
        """
        Clear all LLM cache entries.
        
        Returns:
            Number of entries removed
        """
        try:
            keys = self.redis_client.keys("llm:*")
            if keys:
                count = self.redis_client.delete(*keys)
                logger.info("LLM cache cleared", entries_removed=count)
                return count
            return 0
        except redis.RedisError as e:
            logger.warning("Redis clear failed", error=str(e))
            return 0
    
    def get_stats(self) -> dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with cache stats
        """
        try:
            hits = int(self.redis_client.get("llm_cache:hits") or 0)
            misses = int(self.redis_client.get("llm_cache:misses") or 0)
            total_requests = hits + misses
            hit_rate = hits / total_requests if total_requests > 0 else 0.0
            
            # Count total cached entries
            size = len(self.redis_client.keys("llm:*"))
            
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
                    "LLM cache statistics",
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
            self.redis_client.delete("llm_cache:hits", "llm_cache:misses")
            logger.debug("LLM cache statistics reset")
        except redis.RedisError as e:
            logger.warning("Failed to reset stats", error=str(e))


# Global cache instance
_llm_cache: Optional[LLMCache] = None


def get_llm_cache(
    redis_url: str = "redis://localhost:6379/0",
    default_ttl: int = 3600,
) -> LLMCache:
    """
    Get or create global LLM cache instance.
    
    Args:
        redis_url: Redis connection URL
        default_ttl: Default TTL in seconds
        
    Returns:
        LLMCache instance
    """
    global _llm_cache
    
    if _llm_cache is None:
        _llm_cache = LLMCache(
            redis_url=redis_url,
            default_ttl=default_ttl,
        )
    
    return _llm_cache


