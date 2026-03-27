"""Tests for N+1 Query Detection and Batching."""

import asyncio
import pytest
from unittest.mock import Mock, patch

from fast_dashboards.core.nplus1_detector import (
    NPlus1Detector,
    NPlus1Pattern,
    NPlus1Severity,
    QueryContext,
    BatchLoader,
    RelationshipPrefetch,
    detect_nplus1,
    detector,
)


class TestNPlus1Detector:
    """Tests for NPlus1Detector."""

    @pytest.fixture
    def nplus1_detector(self):
        """Create a fresh detector."""
        return NPlus1Detector(
            warning_threshold=3,
            error_threshold=10,
            enable_auto_batch=True,
        )

    def test_start_end_operation(self, nplus1_detector):
        """Test starting and ending an operation."""
        ctx = nplus1_detector.start_operation("test_op")
        assert ctx is not None
        assert ctx.operation_id == "test_op"

        patterns = nplus1_detector.end_operation()
        assert isinstance(patterns, list)

    def test_record_query(self, nplus1_detector):
        """Test recording queries."""
        nplus1_detector.start_operation("test_op")

        info = nplus1_detector.record_query("SELECT * FROM users", ())
        assert info is not None
        assert "SELECT * FROM users" in info.sql

        nplus1_detector.finish_query(info)
        assert info.duration_ms >= 0

    def test_pattern_detection(self, nplus1_detector):
        """Test detecting N+1 patterns."""
        nplus1_detector.start_operation("test_op")

        # Simulate N+1 queries
        for i in range(5):
            info = nplus1_detector.record_query(
                f"SELECT * FROM orders WHERE user_id = {i}", (i,)
            )
            nplus1_detector.finish_query(info)

        patterns = nplus1_detector.end_operation()

        assert len(patterns) > 0
        assert patterns[0].severity in (NPlus1Severity.WARNING, NPlus1Severity.ERROR)
        assert patterns[0].query_count >= 3

    def test_context_manager(self, nplus1_detector):
        """Test the monitor context manager."""
        with nplus1_detector.monitor("test_op") as det:
            # Record some queries
            info = det.record_query("SELECT * FROM users", ())
            det.finish_query(info)

        # Should complete without exception
        assert nplus1_detector.get_stats()["total_queries"] >= 1

    def test_extract_pattern_key(self, nplus1_detector):
        """Test SQL pattern extraction."""
        # Similar queries should have same pattern key
        key1 = nplus1_detector._extract_pattern_key("SELECT * FROM users WHERE id = 1")
        key2 = nplus1_detector._extract_pattern_key("SELECT * FROM users WHERE id = 2")
        assert key1 == key2

        # Different queries should have different keys
        key3 = nplus1_detector._extract_pattern_key(
            "SELECT * FROM products WHERE id = 1"
        )
        assert key1 != key3

    def test_suggest_fix(self, nplus1_detector):
        """Test fix suggestion generation."""
        # With model and attribute
        fix = nplus1_detector._suggest_fix("User", "orders")
        assert "selectinload" in fix.lower()
        assert "User" in fix
        assert "orders" in fix

        # With only model
        fix = nplus1_detector._suggest_fix("Product", None)
        assert "eager loading" in fix.lower()

        # With nothing
        fix = nplus1_detector._suggest_fix(None, None)
        assert "eager loading" in fix.lower()


class TestQueryContext:
    """Tests for QueryContext."""

    def test_record_query(self):
        """Test recording queries in context."""
        ctx = QueryContext(operation_id="test")

        info = ctx.record_query("SELECT * FROM users", ())
        assert len(ctx.queries) == 1
        assert info.sql == "SELECT * FROM users"

    def test_finish_query(self):
        """Test finishing a query."""
        ctx = QueryContext(operation_id="test")

        info = ctx.record_query("SELECT * FROM users", ())
        ctx.finish_query(info)

        assert info.end_time > 0
        assert info.duration_ms >= 0


class TestBatchLoader:
    """Tests for BatchLoader."""

    @pytest.mark.asyncio
    async def test_batch_loading(self):
        """Test batch loading functionality."""
        loader = BatchLoader(max_batch_size=3, batch_delay_ms=10)

        load_count = 0
        loaded_keys = []

        async def load_func(keys):
            """Execute load_func operation.

            Args:
                keys: The keys parameter.

            Returns:
                The result of the operation.
            """
            nonlocal load_count, loaded_keys
            load_count += 1
            loaded_keys.extend(keys)
            return [f"result_{k}" for k in keys]

        # Load multiple items concurrently
        results = await asyncio.gather(
            loader.load("test", 1, load_func),
            loader.load("test", 2, load_func),
            loader.load("test", 3, load_func),
        )

        # Wait for batch to process
        await asyncio.sleep(0.05)

        assert results == ["result_1", "result_2", "result_3"]
        # Should be batched into one call
        assert load_count == 1
        assert set(loaded_keys) == {1, 2, 3}

    @pytest.mark.asyncio
    async def test_load_error_handling(self):
        """Test error handling in batch loader."""
        loader = BatchLoader(max_batch_size=3, batch_delay_ms=10)

        async def failing_load(keys):
            """Execute failing_load operation.

            Args:
                keys: The keys parameter.

            Returns:
                The result of the operation.
            """
            raise ValueError("Database error")

        # Should propagate error
        with pytest.raises(ValueError, match="Database error"):
            await loader.load("test", 1, failing_load)

        # Wait for batch processing
        await asyncio.sleep(0.05)


class TestRelationshipPrefetch:
    """Tests for RelationshipPrefetch."""

    @pytest.mark.asyncio
    async def test_prefetch(self):
        """Test relationship prefetching."""
        prefetch = RelationshipPrefetch()

        # Create mock instances
        instances = [
            Mock(id=1),
            Mock(id=2),
            Mock(id=3),
        ]

        # Prefetch relationship
        await prefetch.load(instances, "orders")

        # Should not raise and should track prefetched keys
        assert "Mock.orders" in prefetch._prefetched
        assert {1, 2, 3}.issubset(prefetch._prefetched["Mock.orders"])

    @pytest.mark.asyncio
    async def test_prefetch_empty_list(self):
        """Test prefetching with empty list."""
        prefetch = RelationshipPrefetch()

        # Should not raise
        await prefetch.load([], "orders")

        assert len(prefetch._prefetched) == 0

    @pytest.mark.asyncio
    async def test_prefetch_idempotent(self):
        """Test that prefetching same items twice is idempotent."""
        prefetch = RelationshipPrefetch()

        instances = [Mock(id=1), Mock(id=2)]

        # Prefetch twice
        await prefetch.load(instances, "orders")
        await prefetch.load(instances, "orders")

        # Should only track once
        assert prefetch._prefetched["Mock.orders"] == {1, 2}


class TestDetectNPlus1Decorator:
    """Tests for the detect_nplus1 decorator."""

    @pytest.mark.asyncio
    async def test_async_function_decorator(self):
        """Test decorator on async function."""

        @detect_nplus1(warning_threshold=2)
        async def fetch_data():
            """Execute fetch_data operation.

            Returns:
                The result of the operation.
            """
            # Simulate some database queries
            detector.record_query("SELECT * FROM users", ())
            return "data"

        result = await fetch_data()
        assert result == "data"

    def test_sync_function_decorator(self):
        """Test decorator on sync function."""

        @detect_nplus1(warning_threshold=2)
        def fetch_data():
            """Execute fetch_data operation.

            Returns:
                The result of the operation.
            """
            detector.record_query("SELECT * FROM users", ())
            return "data"

        result = fetch_data()
        assert result == "data"


class TestIntegration:
    """Integration tests for N+1 detection."""

    def test_simulated_nplus1_detection(self):
        """Test detecting a simulated N+1 query pattern."""
        det = NPlus1Detector(
            warning_threshold=3,
            error_threshold=10,
        )

        with det.monitor("user_fetch") as ctx:
            # Simulate fetching users
            det.record_query("SELECT * FROM users LIMIT 10", ())

            # Simulate N+1: fetching orders for each user
            for i in range(5):
                det.record_query(f"SELECT * FROM orders WHERE user_id = {i}", (i,))

        stats = det.get_stats()
        assert stats["total_queries"] >= 6
        assert stats["patterns_detected"] >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
