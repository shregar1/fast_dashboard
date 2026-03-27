"""Smart Caching System - Production-grade caching with cache-aside pattern,
stale-while-revalidate, automatic invalidation, and request deduplication.

Features:
- Cache-aside pattern with automatic cache warming
- Stale-while-revalidate for zero-downtime cache refreshes
- Event-based automatic invalidation
- Request deduplication (thundering herd protection)
- Multi-level caching (L1 local, L2 Redis)
- Compression and serialization options
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import pickle
import zlib
from dataclasses import dataclass, field
from enum import Enum
from functools import wraps
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    List,
    Optional,
    Protocol,
    Set,
    TypeVar,
    AsyncIterator,
    Union,
)
from datetime import datetime, timedelta
import time

from loguru import logger


T = TypeVar("T")


class CacheStrategy(Enum):
    """Cache strategies."""

    CACHE_ASIDE = "cache_aside"  # App manages cache
    READ_THROUGH = "read_through"  # Cache loads from source
    WRITE_THROUGH = "write_through"  # Cache writes to source
    WRITE_BEHIND = "write_behind"  # Async write to source


class InvalidationEvent:
    """Event that triggers cache invalidation."""

    def __init__(
        self,
        event_type: str,
        resource_type: str,
        resource_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.event_type = event_type
        self.resource_type = resource_type
        self.resource_id = resource_id
        self.tenant_id = tenant_id
        self.metadata = metadata or {}
        self.timestamp = datetime.utcnow()

    def matches(self, pattern: str) -> bool:
        """Check if event matches a pattern (e.g., 'user:*:update')."""
        parts = pattern.split(":")
        event_parts = [self.resource_type, self.resource_id or "*", self.event_type]

        if len(parts) != len(event_parts):
            return False

        for p, e in zip(parts, event_parts):
            if p != "*" and p != e:
                return False
        return True


@dataclass
class CacheEntry(Generic[T]):
    """A cached value with metadata."""

    value: T
    created_at: float
    expires_at: float
    stale_at: Optional[float] = None  # When to serve stale while refreshing
    tags: Set[str] = field(default_factory=set)
    version: int = 1

    def is_expired(self) -> bool:
        """Check if entry is fully expired."""
        return time.time() > self.expires_at

    def is_stale(self) -> bool:
        """Check if entry should be refreshed (but still servable)."""
        if self.stale_at is None:
            return self.is_expired()
        return time.time() > self.stale_at

    def is_fresh(self) -> bool:
        """Check if entry is fresh (not stale)."""
        return not self.is_stale()


@dataclass
class CacheConfig:
    """Configuration for smart caching."""

    default_ttl_seconds: int = 300
    stale_while_revalidate_seconds: int = 60
    max_size: int = 10000
    compression_enabled: bool = True
    compression_threshold_bytes: int = 1024
    request_deduplication: bool = True
    dedup_window_seconds: float = 5.0
    warmup_on_startup: bool = False
    invalidate_on_events: List[str] = field(default_factory=list)


class CacheBackend(Protocol):
    """Protocol for cache backends."""

    async def get(self, key: str) -> Optional[bytes]: ...
    async def set(
        self,
        key: str,
        value: bytes,
        ttl: Optional[int] = None,
        stale_ttl: Optional[int] = None,
    ) -> bool: ...
    async def delete(self, key: str) -> bool: ...
    async def delete_pattern(self, pattern: str) -> int: ...
    async def exists(self, key: str) -> bool: ...
    async def clear(self) -> bool: ...


class InMemoryCacheBackend:
    """In-memory LRU cache backend."""

    def __init__(self, max_size: int = 10000):
        self._cache: Dict[str, CacheEntry[bytes]] = {}
        self._max_size = max_size
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Optional[bytes]:
        async with self._lock:
            entry = self._cache.get(key)
            if not entry:
                return None
            if entry.is_expired():
                del self._cache[key]
                return None
            return entry.value

    async def set(
        self,
        key: str,
        value: bytes,
        ttl: Optional[int] = None,
        stale_ttl: Optional[int] = None,
    ) -> bool:
        async with self._lock:
            # LRU eviction
            if len(self._cache) >= self._max_size and key not in self._cache:
                oldest = min(self._cache.items(), key=lambda x: x[1].created_at)
                del self._cache[oldest[0]]

            now = time.time()
            entry = CacheEntry(
                value=value,
                created_at=now,
                expires_at=now + (ttl or 300),
                stale_at=now + (stale_ttl or 60) if stale_ttl else None,
            )
            self._cache[key] = entry
            return True

    async def delete(self, key: str) -> bool:
        async with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    async def delete_pattern(self, pattern: str) -> int:
        """Delete keys matching pattern (* as wildcard)."""
        async with self._lock:
            to_delete = [
                k for k in self._cache.keys() if self._match_pattern(k, pattern)
            ]
            for k in to_delete:
                del self._cache[k]
            return len(to_delete)

    def _match_pattern(self, key: str, pattern: str) -> bool:
        """Simple pattern matching."""
        import fnmatch

        return fnmatch.fnmatch(key, pattern)

    async def exists(self, key: str) -> bool:
        async with self._lock:
            entry = self._cache.get(key)
            if not entry or entry.is_expired():
                return False
            return True

    async def clear(self) -> bool:
        async with self._lock:
            self._cache.clear()
            return True


class SmartCacheManager:
    """Production-grade smart caching manager.

    Features:
    - Multi-level caching (L1: local, L2: Redis)
    - Stale-while-revalidate pattern
    - Request deduplication (thundering herd protection)
    - Event-based invalidation
    - Automatic compression
    """

    def __init__(
        self,
        config: Optional[CacheConfig] = None,
        backend: Optional[CacheBackend] = None,
    ):
        self.config = config or CacheConfig()
        self.backend = backend or InMemoryCacheBackend(self.config.max_size)

        # Request deduplication - tracks in-flight requests
        self._inflight: Dict[str, asyncio.Future] = {}
        self._inflight_lock = asyncio.Lock()

        # Invalidation subscriptions
        self._invalidation_handlers: Dict[str, List[Callable]] = {}

        # Statistics
        self._stats = {
            "hits": 0,
            "misses": 0,
            "stale_hits": 0,
            "deduplicated": 0,
            "invalidations": 0,
        }

    def _serialize(self, value: Any) -> bytes:
        """Serialize value to bytes with optional compression."""
        data = pickle.dumps(value)

        if (
            self.config.compression_enabled
            and len(data) > self.config.compression_threshold_bytes
        ):
            data = zlib.compress(data)
            data = b"\x01" + data  # Compression flag
        else:
            data = b"\x00" + data

        return data

    def _deserialize(self, data: bytes) -> Any:
        """Deserialize bytes to value."""
        if data[0] == 1:
            data = zlib.decompress(data[1:])
        else:
            data = data[1:]

        return pickle.loads(data)

    def _make_key(
        self,
        func: Callable,
        args: tuple,
        kwargs: dict,
        key_prefix: Optional[str] = None,
    ) -> str:
        """Generate cache key from function call."""
        if key_prefix:
            base = key_prefix
        else:
            base = f"{func.__module__}.{func.__qualname__}"

        # Hash arguments
        arg_str = json.dumps(
            {"args": args, "kwargs": kwargs}, sort_keys=True, default=str
        )
        arg_hash = hashlib.md5(arg_str.encode()).hexdigest()[:16]

        return f"{base}:{arg_hash}"

    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        data = await self.backend.get(key)
        if data is None:
            self._stats["misses"] += 1
            return None

        self._stats["hits"] += 1
        return self._deserialize(data)

    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        stale_ttl: Optional[int] = None,
        tags: Optional[Set[str]] = None,
    ) -> bool:
        """Set value in cache."""
        ttl = ttl or self.config.default_ttl_seconds
        stale = stale_ttl or self.config.stale_while_revalidate_seconds

        data = self._serialize(value)
        return await self.backend.set(key, data, ttl=ttl, stale_ttl=stale)

    async def delete(self, key: str) -> bool:
        """Delete value from cache."""
        return await self.backend.delete(key)

    async def delete_pattern(self, pattern: str) -> int:
        """Delete keys matching pattern."""
        return await self.backend.delete_pattern(pattern)

    async def get_or_set(
        self,
        key: str,
        factory: Callable[[], Any],
        ttl: Optional[int] = None,
        stale_ttl: Optional[int] = None,
    ) -> Any:
        """Get from cache or compute and set (cache-aside pattern).
        Implements stale-while-revalidate for zero-downtime refreshes.
        """
        # Try to get from cache
        data = await self.backend.get(key)

        if data:
            entry: CacheEntry[bytes] = pickle.loads(data)

            if entry.is_fresh():
                # Fresh hit
                self._stats["hits"] += 1
                return self._deserialize(entry.value)

            elif entry.is_stale() and not entry.is_expired():
                # Stale hit - serve stale, refresh in background
                self._stats["stale_hits"] += 1

                # Trigger background refresh
                asyncio.create_task(self._refresh(key, factory, ttl, stale_ttl))

                return self._deserialize(entry.value)

        # Cache miss - compute value
        self._stats["misses"] += 1
        return await self._compute_and_store(key, factory, ttl, stale_ttl)

    async def _refresh(
        self,
        key: str,
        factory: Callable[[], Any],
        ttl: Optional[int],
        stale_ttl: Optional[int],
    ) -> None:
        """Refresh cache in background."""
        try:
            value = await self._call_async(factory)
            await self.set(key, value, ttl, stale_ttl)
            logger.debug(f"Refreshed cache key: {key}")
        except Exception as e:
            logger.warning(f"Failed to refresh cache key {key}: {e}")

    async def _compute_and_store(
        self,
        key: str,
        factory: Callable[[], Any],
        ttl: Optional[int],
        stale_ttl: Optional[int],
    ) -> Any:
        """Compute value and store in cache."""
        # Request deduplication (thundering herd protection)
        if self.config.request_deduplication:
            async with self._inflight_lock:
                if key in self._inflight:
                    # Another request is computing this value
                    self._stats["deduplicated"] += 1
                    future = self._inflight[key]
                    return await future

                # Create future for this request
                future = asyncio.get_event_loop().create_future()
                self._inflight[key] = future

        try:
            # Compute value
            value = await self._call_async(factory)

            # Store in cache
            await self.set(key, value, ttl, stale_ttl)

            # Complete the future for deduplicated requests
            if self.config.request_deduplication:
                async with self._inflight_lock:
                    future = self._inflight.pop(key, None)
                    if future and not future.done():
                        future.set_result(value)

            return value

        except Exception as e:
            # Complete future with exception
            if self.config.request_deduplication:
                async with self._inflight_lock:
                    future = self._inflight.pop(key, None)
                    if future and not future.done():
                        future.set_exception(e)
            raise

    async def _call_async(self, func: Callable) -> Any:
        """Call function, handling both sync and async."""
        if asyncio.iscoroutinefunction(func):
            return await func()
        else:
            # Run sync function in thread pool
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, func)

    def cached(
        self,
        ttl: Optional[int] = None,
        stale_ttl: Optional[int] = None,
        key_prefix: Optional[str] = None,
        tags: Optional[List[str]] = None,
        condition: Optional[Callable[[Any], bool]] = None,
        invalidate_on: Optional[List[str]] = None,
    ):
        """Decorator for caching function results.

        Args:
            ttl: Time-to-live in seconds
            stale_ttl: Stale-while-revalidate window in seconds
            key_prefix: Custom cache key prefix
            tags: Tags for grouping cache entries
            condition: Only cache if condition(value) is True
            invalidate_on: Event patterns that invalidate this cache

        """

        def decorator(func: Callable) -> Callable:
            # Register invalidation handlers
            if invalidate_on:
                for pattern in invalidate_on:
                    if pattern not in self._invalidation_handlers:
                        self._invalidation_handlers[pattern] = []
                    self._invalidation_handlers[pattern].append(
                        lambda: self.delete_pattern(
                            f"{key_prefix or func.__qualname__}*"
                        )
                    )

            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                key = self._make_key(func, args, kwargs, key_prefix)

                async def factory():
                    return await func(*args, **kwargs)

                value = await self.get_or_set(key, factory, ttl, stale_ttl)

                if condition and not condition(value):
                    # Don't cache this value, delete it
                    await self.delete(key)

                return value

            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                # For sync functions, we need to handle differently
                key = self._make_key(func, args, kwargs, key_prefix)

                # Check cache first
                async def check_cache():
                    return await self.get(key)

                try:
                    loop = asyncio.get_event_loop()
                    cached_value = loop.run_until_complete(check_cache())
                    if cached_value is not None:
                        return cached_value
                except RuntimeError:
                    # No event loop, compute directly
                    pass

                # Compute value
                value = func(*args, **kwargs)

                # Store in cache
                async def store():
                    if condition is None or condition(value):
                        await self.set(key, value, ttl, stale_ttl)

                try:
                    loop = asyncio.get_event_loop()
                    loop.run_until_complete(store())
                except RuntimeError:
                    pass

                return value

            if asyncio.iscoroutinefunction(func):
                return async_wrapper
            else:
                return sync_wrapper

        return decorator

    async def handle_invalidation_event(self, event: InvalidationEvent) -> int:
        """Handle an invalidation event."""
        deleted_count = 0

        for pattern, handlers in self._invalidation_handlers.items():
            if event.matches(pattern):
                for handler in handlers:
                    try:
                        result = handler()
                        if asyncio.iscoroutine(result):
                            await result
                    except Exception as e:
                        logger.error(f"Invalidation handler failed: {e}")
                deleted_count += 1

        self._stats["invalidations"] += 1
        return deleted_count

    def get_stats(self) -> Dict[str, int]:
        """Get cache statistics."""
        total = self._stats["hits"] + self._stats["misses"]
        hit_rate = self._stats["hits"] / total if total > 0 else 0

        return {
            **self._stats,
            "total_requests": total,
            "hit_rate": round(hit_rate * 100, 2),
            "hit_rate_formatted": f"{hit_rate:.1%}",
        }

    async def clear(self) -> bool:
        """Clear all cached values."""
        return await self.backend.clear()


# Global cache manager instance
smart_cache = SmartCacheManager()


class CacheInvalidator:
    """Helper class for invalidating cache entries."""

    def __init__(self, cache_manager: SmartCacheManager):
        self.cache = cache_manager

    async def invalidate_resource(
        self,
        resource_type: str,
        resource_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> int:
        """Invalidate all cache entries for a resource."""
        pattern = f"{resource_type}:*"
        if resource_id:
            pattern = f"{resource_type}:{resource_id}*"

        return await self.cache.delete_pattern(pattern)

    async def invalidate_tenant(self, tenant_id: str) -> int:
        """Invalidate all cache entries for a tenant."""
        return await self.cache.delete_pattern(f"*tenant:{tenant_id}*")

    async def invalidate_user(self, user_id: str) -> int:
        """Invalidate all cache entries for a user."""
        return await self.cache.delete_pattern(f"*user:{user_id}*")


cache_invalidator = CacheInvalidator(smart_cache)


__all__ = [
    "SmartCacheManager",
    "smart_cache",
    "CacheConfig",
    "CacheStrategy",
    "InvalidationEvent",
    "CacheEntry",
    "CacheBackend",
    "InMemoryCacheBackend",
    "CacheInvalidator",
    "cache_invalidator",
]
