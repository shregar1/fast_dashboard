"""Tests for Smart Caching System."""

import asyncio
import pytest
from unittest.mock import AsyncMock, Mock

from fast_dashboards.core.smart_cache import (
    SmartCacheManager,
    CacheConfig,
    InMemoryCacheBackend,
    InvalidationEvent,
    cache_invalidator,
)


class TestSmartCacheManager:
    """Tests for SmartCacheManager."""

    @pytest.fixture
    def cache(self):
        """Create a fresh cache manager."""
        return SmartCacheManager(
            config=CacheConfig(
                default_ttl_seconds=60,
                stale_while_revalidate_seconds=10,
                request_deduplication=True,
            ),
            backend=InMemoryCacheBackend(max_size=100),
        )

    @pytest.mark.asyncio
    async def test_get_set_basic(self, cache):
        """Test basic get and set operations."""
        # Set a value
        await cache.set("key1", "value1")

        # Get the value
        result = await cache.get("key1")
        assert result == "value1"

    @pytest.mark.asyncio
    async def test_get_missing_key(self, cache):
        """Test getting a non-existent key."""
        result = await cache.get("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_or_set_cache_miss(self, cache):
        """Test get_or_set with cache miss."""
        factory = AsyncMock(return_value="computed_value")

        result = await cache.get_or_set("key", factory)

        assert result == "computed_value"
        factory.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_or_set_cache_hit(self, cache):
        """Test get_or_set with cache hit."""
        # Pre-populate cache
        await cache.set("key", "cached_value")

        factory = AsyncMock(return_value="computed_value")

        result = await cache.get_or_set("key", factory)

        assert result == "cached_value"
        factory.assert_not_called()

    @pytest.mark.asyncio
    async def test_delete(self, cache):
        """Test deleting a key."""
        await cache.set("key1", "value1")

        result = await cache.delete("key1")
        assert result is True

        # Verify deletion
        assert await cache.get("key1") is None

    @pytest.mark.asyncio
    async def test_delete_pattern(self, cache):
        """Test deleting keys by pattern."""
        await cache.set("user:1", "value1")
        await cache.set("user:2", "value2")
        await cache.set("product:1", "value3")

        deleted = await cache.delete_pattern("user:*")

        assert deleted == 2
        assert await cache.get("user:1") is None
        assert await cache.get("user:2") is None
        assert await cache.get("product:1") == "value3"

    @pytest.mark.asyncio
    async def test_request_deduplication(self, cache):
        """Test that concurrent requests for same key are deduplicated."""
        call_count = 0

        async def slow_factory():
            """Execute slow_factory operation.

            Returns:
                The result of the operation.
            """
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.1)
            return f"result_{call_count}"

        # Start multiple concurrent requests
        results = await asyncio.gather(
            cache.get_or_set("key", slow_factory),
            cache.get_or_set("key", slow_factory),
            cache.get_or_set("key", slow_factory),
        )

        # All should get the same result
        assert results[0] == results[1] == results[2]
        # Factory should only be called once
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_cached_decorator(self, cache):
        """Test the cached decorator."""
        call_count = 0

        @cache.cached(ttl=60, key_prefix="test")
        async def test_function(x):
            """Execute test_function operation.

            Args:
                x: The x parameter.

            Returns:
                The result of the operation.
            """
            nonlocal call_count
            call_count += 1
            return x * 2

        # First call
        result1 = await test_function(5)
        assert result1 == 10
        assert call_count == 1

        # Second call - should use cache
        result2 = await test_function(5)
        assert result2 == 10
        assert call_count == 1  # Not called again

        # Different argument - should compute
        result3 = await test_function(3)
        assert result3 == 6
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_stats_tracking(self, cache):
        """Test that stats are tracked correctly."""
        # Generate hits and misses
        await cache.set("key1", "value1")
        await cache.get("key1")  # Hit
        await cache.get("key1")  # Hit
        await cache.get("key2")  # Miss

        stats = cache.get_stats()

        assert stats["hits"] == 2
        assert stats["misses"] == 1
        assert stats["total_requests"] == 3
        assert stats["hit_rate"] == 66.67

    @pytest.mark.asyncio
    async def test_compression(self, cache):
        """Test that large values are compressed."""
        # Create a large value
        large_value = "x" * 10000

        # Store it
        await cache.set("large_key", large_value)

        # Retrieve it
        result = await cache.get("large_key")
        assert result == large_value


class TestInMemoryCacheBackend:
    """Tests for InMemoryCacheBackend."""

    @pytest.fixture
    def backend(self):
        """Execute backend operation.

        Returns:
            The result of the operation.
        """
        return InMemoryCacheBackend(max_size=10)

    @pytest.mark.asyncio
    async def test_basic_operations(self, backend):
        """Test basic get/set/delete operations."""
        # Set
        result = await backend.set("key1", b"value1")
        assert result is True

        # Get
        value = await backend.get("key1")
        assert value == b"value1"

        # Delete
        deleted = await backend.delete("key1")
        assert deleted is True

        # Verify deletion
        assert await backend.get("key1") is None

    @pytest.mark.asyncio
    async def test_expiration(self, backend):
        """Test that expired entries are removed."""
        # Set with short TTL
        await backend.set("key1", b"value1", ttl=0)

        # Wait a bit
        await asyncio.sleep(0.1)

        # Should be expired
        assert await backend.get("key1") is None

    @pytest.mark.asyncio
    async def test_lru_eviction(self, backend):
        """Test LRU eviction when max size is reached."""
        backend = InMemoryCacheBackend(max_size=3)

        # Fill cache
        await backend.set("key1", b"value1")
        await backend.set("key2", b"value2")
        await backend.set("key3", b"value3")

        # Access key1 to make it recently used
        await backend.get("key1")

        # Add another item to trigger eviction
        await backend.set("key4", b"value4")

        # key2 should be evicted (least recently used)
        assert await backend.get("key2") is None
        assert await backend.get("key1") == b"value1"
        assert await backend.get("key3") == b"value3"
        assert await backend.get("key4") == b"value4"


class TestInvalidationEvent:
    """Tests for InvalidationEvent."""

    def test_event_creation(self):
        """Test creating an invalidation event."""
        event = InvalidationEvent(
            event_type="update",
            resource_type="user",
            resource_id="123",
            tenant_id="tenant1",
        )

        assert event.event_type == "update"
        assert event.resource_type == "user"
        assert event.resource_id == "123"
        assert event.tenant_id == "tenant1"

    def test_pattern_matching(self):
        """Test pattern matching for events."""
        event = InvalidationEvent(
            event_type="update", resource_type="user", resource_id="123"
        )

        # Exact match
        assert event.matches("user:123:update") is True

        # Wildcard match
        assert event.matches("user:*:update") is True
        assert event.matches("*:123:update") is True
        assert event.matches("*:*:update") is True

        # Non-match
        assert event.matches("user:456:update") is False
        assert event.matches("product:123:update") is False
        assert event.matches("user:123:delete") is False


class TestCacheInvalidator:
    """Tests for CacheInvalidator."""

    @pytest.mark.asyncio
    async def test_invalidate_resource(self):
        """Test invalidating resources."""
        cache = SmartCacheManager(backend=InMemoryCacheBackend())

        # Populate cache
        await cache.set("user:1", "value1")
        await cache.set("user:2", "value2")
        await cache.set("product:1", "value3")

        # Invalidate users
        deleted = await cache_invalidator.invalidate_resource("user")

        assert deleted == 2
        assert await cache.get("user:1") is None
        assert await cache.get("user:2") is None
        assert await cache.get("product:1") == "value3"

    @pytest.mark.asyncio
    async def test_invalidate_tenant(self):
        """Test invalidating by tenant."""
        cache = SmartCacheManager(backend=InMemoryCacheBackend())

        # Populate cache with tenant-scoped keys
        await cache.set("data:tenant:abc123", "value1")
        await cache.set("user:tenant:abc123", "value2")
        await cache.set("data:tenant:xyz789", "value3")

        # Invalidate tenant
        deleted = await cache_invalidator.invalidate_tenant("abc123")

        assert deleted == 2
        assert await cache.get("data:tenant:abc123") is None
        assert await cache.get("data:tenant:xyz789") == "value3"


class TestIntegration:
    """Integration tests for smart caching."""

    @pytest.mark.asyncio
    async def test_full_workflow(self):
        """Test a complete caching workflow."""
        cache = SmartCacheManager(
            config=CacheConfig(
                default_ttl_seconds=60,
                stale_while_revalidate_seconds=10,
            ),
            backend=InMemoryCacheBackend(),
        )

        # Simulate a database fetch
        db_call_count = 0

        async def fetch_from_db():
            """Execute fetch_from_db operation.

            Returns:
                The result of the operation.
            """
            nonlocal db_call_count
            db_call_count += 1
            await asyncio.sleep(0.01)  # Simulate latency
            return {"id": 1, "name": "Test User"}

        # First call - should hit database
        result1 = await cache.get_or_set("user:1", fetch_from_db)
        assert result1["name"] == "Test User"
        assert db_call_count == 1

        # Second call - should hit cache
        result2 = await cache.get_or_set("user:1", fetch_from_db)
        assert result2["name"] == "Test User"
        assert db_call_count == 1  # No additional DB call

        # Invalidate
        await cache.delete("user:1")

        # Third call - should hit database again
        result3 = await cache.get_or_set("user:1", fetch_from_db)
        assert result3["name"] == "Test User"
        assert db_call_count == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
