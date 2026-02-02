"""
Resource Manager - Handles rate limiting, resource monitoring, and coordination.

Provides:
- LLM rate limiting (tokens/second, requests/second)
- Memory monitoring
- Schema evolution coordination (prevents conflicts)
- Connection pool management
"""

import asyncio
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any
from threading import Lock

from logger import get_module_logger

logger = get_module_logger(__name__)


@dataclass
class RateLimiter:
    """Token bucket rate limiter for LLM API calls."""
    
    max_tokens: int
    tokens_per_second: float
    max_requests: int | None = None
    requests_per_second: float | None = None
    
    _tokens: float = field(default=0, init=False)
    _requests: deque = field(default_factory=deque, init=False)
    _lock: Lock = field(default_factory=Lock, init=False)
    _last_update: float = field(default_factory=time.time, init=False)
    
    async def acquire(self, tokens: int = 1) -> None:
        """
        Acquire tokens from the rate limiter.
        
        Args:
            tokens: Number of tokens to acquire
        """
        with self._lock:
            now = time.time()
            elapsed = now - self._last_update
            
            # Refill tokens based on time elapsed
            self._tokens = min(self.max_tokens, self._tokens + elapsed * self.tokens_per_second)
            self._last_update = now
            
            # Clean old requests from the window
            if self.requests_per_second:
                cutoff = now - 1.0
                while self._requests and self._requests[0] < cutoff:
                    self._requests.popleft()
            
            # Check if we can proceed
            if self._tokens < tokens:
                # Need to wait
                wait_time = (tokens - self._tokens) / self.tokens_per_second
                logger.debug(
                    "Rate limit: waiting for tokens",
                    wait_time=wait_time,
                    available=self._tokens,
                    requested=tokens
                )
                await asyncio.sleep(wait_time)
                # Refill after waiting
                now = time.time()
                elapsed = now - self._last_update
                self._tokens = min(self.max_tokens, self._tokens + elapsed * self.tokens_per_second)
                self._last_update = now
            
            if self.requests_per_second and len(self._requests) >= self.max_requests:
                # Need to wait for request window
                oldest_request = self._requests[0]
                wait_time = 1.0 - (now - oldest_request)
                if wait_time > 0:
                    logger.debug(
                        "Rate limit: waiting for request window",
                        wait_time=wait_time
                    )
                    await asyncio.sleep(wait_time)
                    # Clean up after waiting
                    now = time.time()
                    cutoff = now - 1.0
                    while self._requests and self._requests[0] < cutoff:
                        self._requests.popleft()
            
            # Consume tokens and record request
            self._tokens -= tokens
            if self.requests_per_second:
                self._requests.append(time.time())


@dataclass
class SchemaEvolutionLock:
    """Coordinates schema evolution to prevent conflicts."""
    
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False)
    _pending_changes: list[dict[str, Any]] = field(default_factory=list, init=False)
    _processing: bool = field(default=False, init=False)
    
    async def acquire(self) -> bool:
        """
        Try to acquire the schema evolution lock.
        
        Returns:
            True if lock acquired, False if already processing
        """
        if self._processing:
            return False
        
        await self._lock.acquire()
        if self._processing:
            self._lock.release()
            return False
        
        self._processing = True
        return True
    
    def release(self) -> None:
        """Release the schema evolution lock."""
        self._processing = False
        if self._lock.locked():
            self._lock.release()
    
    def queue_change(self, change: dict[str, Any]) -> None:
        """Queue a schema change for later processing."""
        self._pending_changes.append(change)
    
    def get_pending_changes(self) -> list[dict[str, Any]]:
        """Get all pending schema changes."""
        return self._pending_changes.copy()
    
    def clear_pending(self) -> None:
        """Clear pending changes."""
        self._pending_changes.clear()


class ResourceManager:
    """
    Manages resources for parallel document processing.
    
    Features:
    - Schema evolution coordination (prevents conflicts)
    - Memory monitoring (optional)
    - Connection pool tracking
    
    Note: We don't do proactive LLM rate limiting because:
    - Cloud providers (OpenAI, WatsonX) already have built-in rate limits
    - We handle 429 errors with retry logic (exponential backoff)
    - Provider's limits are more accurate than our estimates
    - Proactive limiting adds unnecessary delays and complexity
    """
    
    def __init__(self, settings: Any = None):
        """
        Initialize resource manager.
        
        Args:
            settings: Application settings for rate limit configuration
        """
        self.settings = settings
        self.logger = logger.bind(component="ResourceManager")
        
        # Schema evolution coordination
        self.schema_lock = SchemaEvolutionLock()
        
        # Memory monitoring (optional)
        self._memory_threshold_mb = 8192  # 8GB default
        self._enable_memory_monitoring = False
    
    # Note: Rate limiting methods removed - we rely on provider's built-in limits
    # Cloud providers (OpenAI, WatsonX) already rate limit and return 429 errors
    # We handle 429s with retry logic (exponential backoff) which is more accurate
    
    async def coordinate_schema_evolution(
        self,
        change: dict[str, Any],
    ) -> bool:
        """
        Coordinate schema evolution to prevent conflicts.
        
        Args:
            change: Schema change proposal
            
        Returns:
            True if change can proceed, False if queued
        """
        acquired = await self.schema_lock.acquire()
        
        if acquired:
            # We have the lock, can proceed
            return True
        else:
            # Lock is held, queue the change
            self.schema_lock.queue_change(change)
            self.logger.debug(
                "Schema evolution locked, queued change",
                change_type=change.get("type"),
                change_name=change.get("name"),
            )
            return False
    
    def release_schema_evolution(self) -> None:
        """Release schema evolution lock."""
        self.schema_lock.release()
        pending = self.schema_lock.get_pending_changes()
        if pending:
            self.logger.info(
                "Schema evolution lock released",
                pending_changes=len(pending)
            )
    
    def get_memory_usage_mb(self) -> float:
        """Get current memory usage in MB."""
        try:
            import psutil
            process = psutil.Process()
            return process.memory_info().rss / 1024 / 1024
        except ImportError:
            return 0.0
    
    def check_memory_available(self) -> bool:
        """
        Check if memory is available for processing.
        
        Returns:
            True if memory is available, False if threshold exceeded
        """
        if not self._enable_memory_monitoring:
            return True
        
        usage = self.get_memory_usage_mb()
        if usage > self._memory_threshold_mb:
            self.logger.warning(
                "Memory threshold exceeded",
                usage_mb=usage,
                threshold_mb=self._memory_threshold_mb
            )
            return False
        
        return True


# Global resource manager instance
_resource_manager: ResourceManager | None = None


def get_resource_manager(settings: Any = None) -> ResourceManager:
    """
    Get or create global resource manager instance.
    
    Args:
        settings: Application settings
        
    Returns:
        ResourceManager instance
    """
    global _resource_manager
    if _resource_manager is None:
        _resource_manager = ResourceManager(settings)
    return _resource_manager
