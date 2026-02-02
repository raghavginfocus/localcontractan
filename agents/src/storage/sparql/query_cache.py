"""
SPARQL Query Cache with TTL

Provides caching for frequent SPARQL queries to reduce database load.
Uses in-memory cache with TTL (Time To Live) for automatic expiration.
"""

import hashlib
import time
from typing import Any, Optional
from dataclasses import dataclass
from collections import OrderedDict
from logger import get_module_logger

logger = get_module_logger(__name__)


@dataclass
class CacheEntry:
    """Cache entry with TTL and metadata."""
    
    query: str
    results: list[dict[str, Any]]
    timestamp: float
    ttl: int
    hit_count: int = 0
    
    def is_expired(self) -> bool:
        """Check if entry has expired."""
        return time.time() - self.timestamp > self.ttl
    
    def refresh(self) -> None:
        """Refresh timestamp and increment hit count."""
        self.hit_count += 1
        self.timestamp = time.time()


class SPARQLQueryCache:
    """
    LRU cache with TTL for SPARQL query results.
    
    Features:
    - TTL-based expiration
    - LRU eviction when cache is full
    - Query normalization for better hit rates
    - Cache statistics tracking
    """
    
    def __init__(
        self,
        max_size: int = 1000,
        default_ttl: int = 300,  # 5 minutes
        enable_stats: bool = True,
    ):
        """
        Initialize SPARQL query cache.
        
        Args:
            max_size: Maximum number of cached queries
            default_ttl: Default TTL in seconds
            enable_stats: Whether to track cache statistics
        """
        self.max_size = max_size
        self.default_ttl = default_ttl
        self.enable_stats = enable_stats
        
        # OrderedDict for LRU behavior
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        
        # Statistics
        self._hits = 0
        self._misses = 0
        self._evictions = 0
        
        logger.info(
            "SPARQL query cache initialized",
            max_size=max_size,
            default_ttl=default_ttl
        )
    
    def _normalize_query(self, query: str) -> str:
        """
        Normalize SPARQL query for consistent caching.
        
        Removes extra whitespace and standardizes formatting.
        """
        # Remove comments
        lines = [
            line.split('#')[0] if '#' in line else line
            for line in query.split('\n')
        ]
        
        # Join and normalize whitespace
        normalized = ' '.join(' '.join(lines).split())
        
        return normalized.strip()
    
    def _get_cache_key(self, query: str, graph_uri: Optional[str] = None) -> str:
        """Generate cache key from query and graph URI."""
        normalized = self._normalize_query(query)
        
        # Include graph URI in key if provided
        if graph_uri:
            cache_input = f"{normalized}|{graph_uri}"
        else:
            cache_input = normalized
        
        # Use hash for compact key
        return hashlib.sha256(cache_input.encode()).hexdigest()
    
    def get(
        self,
        query: str,
        graph_uri: Optional[str] = None
    ) -> Optional[list[dict[str, Any]]]:
        """
        Get cached query results if available and not expired.
        
        Args:
            query: SPARQL query string
            graph_uri: Optional graph URI
            
        Returns:
            Cached results or None if not found/expired
        """
        cache_key = self._get_cache_key(query, graph_uri)
        
        # Check if entry exists
        if cache_key not in self._cache:
            if self.enable_stats:
                self._misses += 1
            return None
        
        entry = self._cache[cache_key]
        
        # Check if expired
        if entry.is_expired():
            del self._cache[cache_key]
            if self.enable_stats:
                self._misses += 1
            logger.debug("Cache entry expired", query_hash=cache_key[:8])
            return None
        
        # Move to end (most recently used)
        self._cache.move_to_end(cache_key)
        
        # Update stats
        entry.refresh()
        if self.enable_stats:
            self._hits += 1
        
        # Log cache hit with hit rate
        total_requests = self._hits + self._misses
        hit_rate = self._hits / total_requests if total_requests > 0 else 0.0
        
        logger.debug(
            "Cache hit",
            query_hash=cache_key[:8],
            hit_count=entry.hit_count,
            age_seconds=int(time.time() - entry.timestamp),
            cache_hit_rate=f"{hit_rate:.1%}",
        )
        
        return entry.results
    
    def set(
        self,
        query: str,
        results: list[dict[str, Any]],
        graph_uri: Optional[str] = None,
        ttl: Optional[int] = None,
    ) -> None:
        """
        Cache query results with TTL.
        
        Args:
            query: SPARQL query string
            results: Query results to cache
            graph_uri: Optional graph URI
            ttl: Optional custom TTL (uses default if None)
        """
        cache_key = self._get_cache_key(query, graph_uri)
        
        # Use default TTL if not specified
        if ttl is None:
            ttl = self.default_ttl
        
        # Create cache entry
        entry = CacheEntry(
            query=query,
            results=results,
            timestamp=time.time(),
            ttl=ttl,
        )
        
        # Check if we need to evict
        if len(self._cache) >= self.max_size and cache_key not in self._cache:
            # Remove oldest entry (LRU)
            evicted_key, evicted_entry = self._cache.popitem(last=False)
            if self.enable_stats:
                self._evictions += 1
            logger.debug(
                "Cache eviction",
                evicted_hash=evicted_key[:8],
                hit_count=evicted_entry.hit_count
            )
        
        # Add/update entry
        self._cache[cache_key] = entry
        self._cache.move_to_end(cache_key)
        
        logger.debug(
            "Query cached",
            query_hash=cache_key[:8],
            result_count=len(results),
            ttl=ttl
        )
    
    def invalidate(self, query: str, graph_uri: Optional[str] = None) -> bool:
        """
        Invalidate a specific cached query.
        
        Args:
            query: SPARQL query string
            graph_uri: Optional graph URI
            
        Returns:
            True if entry was found and removed
        """
        cache_key = self._get_cache_key(query, graph_uri)
        
        if cache_key in self._cache:
            del self._cache[cache_key]
            logger.debug("Cache entry invalidated", query_hash=cache_key[:8])
            return True
        
        return False
    
    def clear(self) -> None:
        """Clear all cached entries."""
        count = len(self._cache)
        self._cache.clear()
        logger.info("Cache cleared", entries_removed=count)
    
    def cleanup_expired(self) -> int:
        """
        Remove all expired entries.
        
        Returns:
            Number of entries removed
        """
        expired_keys = [
            key for key, entry in self._cache.items()
            if entry.is_expired()
        ]
        
        for key in expired_keys:
            del self._cache[key]
        
        if expired_keys:
            logger.debug("Expired entries cleaned up", count=len(expired_keys))
        
        return len(expired_keys)
    
    def get_stats(self) -> dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with cache stats
        """
        total_requests = self._hits + self._misses
        hit_rate = self._hits / total_requests if total_requests > 0 else 0.0
        
        stats = {
            "size": len(self._cache),
            "max_size": self.max_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": hit_rate,
            "evictions": self._evictions,
            "total_requests": total_requests,
        }
        
        # Log stats periodically (every 100 requests)
        if total_requests > 0 and total_requests % 100 == 0:
            logger.info(
                "SPARQL cache statistics",
                **stats,
                hit_rate_pct=f"{hit_rate:.1%}",
            )
        
        return stats
    
    def reset_stats(self) -> None:
        """Reset cache statistics."""
        self._hits = 0
        self._misses = 0
        self._evictions = 0
        logger.debug("Cache statistics reset")


# Global cache instance
_query_cache: Optional[SPARQLQueryCache] = None


def get_query_cache(
    max_size: int = 1000,
    default_ttl: int = 300,
) -> SPARQLQueryCache:
    """
    Get or create global SPARQL query cache instance.
    
    Args:
        max_size: Maximum cache size
        default_ttl: Default TTL in seconds
        
    Returns:
        SPARQLQueryCache instance
    """
    global _query_cache
    
    if _query_cache is None:
        _query_cache = SPARQLQueryCache(
            max_size=max_size,
            default_ttl=default_ttl,
        )
    
    return _query_cache


