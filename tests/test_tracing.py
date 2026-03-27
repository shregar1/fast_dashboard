"""Tests for Distributed Tracing with Cost Attribution."""

import asyncio
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, Mock

from fast_dashboards.core.tracing import (
    Tracer,
    TracingConfig,
    Span,
    SpanKind,
    SpanStatus,
    SpanEvent,
    CostBreakdown,
    ConsoleSpanExporter,
    InMemorySpanExporter,
    APICostTracker,
    DatabaseCostTracker,
)


class TestCostBreakdown:
    """Tests for CostBreakdown."""

    def test_empty_cost(self):
        """Test empty cost breakdown."""
        cost = CostBreakdown()
        assert cost.total_cost_usd == Decimal("0")

    def test_add_costs(self):
        """Test adding different cost categories."""
        cost = CostBreakdown()
        cost.compute_cost_usd = Decimal("0.01")
        cost.database_cost_usd = Decimal("0.02")
        cost.api_cost_usd = Decimal("0.03")

        assert cost.total_cost_usd == Decimal("0.06")

    def test_to_dict(self):
        """Test conversion to dictionary."""
        cost = CostBreakdown()
        cost.compute_cost_usd = Decimal("0.01")
        cost.database_cost_usd = Decimal("0.02")

        result = cost.to_dict()

        assert result["compute_usd"] == 0.01
        assert result["database_usd"] == 0.02
        assert result["total_usd"] == 0.03


class TestSpan:
    """Tests for Span."""

    def test_span_creation(self):
        """Test creating a span."""
        import time

        span = Span(
            trace_id="abc123",
            span_id="def456",
            parent_id=None,
            name="test_span",
            kind=SpanKind.INTERNAL,
            start_time=time.time(),
        )

        assert span.trace_id == "abc123"
        assert span.span_id == "def456"
        assert span.name == "test_span"
        assert span.status == SpanStatus.UNSET

    def test_span_attributes(self):
        """Test setting span attributes."""
        import time

        span = Span(
            trace_id="abc123",
            span_id="def456",
            parent_id=None,
            name="test_span",
            kind=SpanKind.INTERNAL,
            start_time=time.time(),
        )

        span.set_attribute("user.id", "123")
        span.set_attribute("http.status_code", 200)

        assert span.attributes["user.id"] == "123"
        assert span.attributes["http.status_code"] == 200

    def test_span_events(self):
        """Test adding span events."""
        import time

        span = Span(
            trace_id="abc123",
            span_id="def456",
            parent_id=None,
            name="test_span",
            kind=SpanKind.INTERNAL,
            start_time=time.time(),
        )

        span.add_event("cache_miss", {"key": "user:123"})

        assert len(span.events) == 1
        assert span.events[0].name == "cache_miss"
        assert span.events[0].attributes["key"] == "user:123"

    def test_record_exception(self):
        """Test recording exceptions."""
        import time

        span = Span(
            trace_id="abc123",
            span_id="def456",
            parent_id=None,
            name="test_span",
            kind=SpanKind.INTERNAL,
            start_time=time.time(),
        )

        try:
            raise ValueError("Something went wrong")
        except Exception as e:
            span.record_exception(e)

        assert span.status == SpanStatus.ERROR
        assert span.attributes["error"] is True
        assert span.attributes["error.type"] == "ValueError"

    def test_add_cost(self):
        """Test adding costs to span."""
        import time

        span = Span(
            trace_id="abc123",
            span_id="def456",
            parent_id=None,
            name="test_span",
            kind=SpanKind.INTERNAL,
            start_time=time.time(),
        )

        span.add_cost("compute", Decimal("0.001"))
        span.add_cost("database", Decimal("0.002"))

        assert span.cost.compute_cost_usd == Decimal("0.001")
        assert span.cost.database_cost_usd == Decimal("0.002")

    def test_finish_span(self):
        """Test finishing a span."""
        import time

        span = Span(
            trace_id="abc123",
            span_id="def456",
            parent_id=None,
            name="test_span",
            kind=SpanKind.INTERNAL,
            start_time=time.time(),
        )

        span.finish(SpanStatus.OK)

        assert span.end_time is not None
        assert span.status == SpanStatus.OK
        assert span.duration_ms >= 0


class TestTracer:
    """Tests for Tracer."""

    @pytest.fixture
    def tracer(self):
        """Create a tracer with in-memory exporter."""
        config = TracingConfig(
            service_name="test-service",
            sample_rate=1.0,
            enable_cost_tracking=True,
        )
        t = Tracer(config)
        t._exporters = [InMemorySpanExporter()]  # Replace console exporter
        return t

    def test_start_span(self, tracer):
        """Test starting a span."""
        span = tracer.start_span("test_operation", SpanKind.SERVER)

        assert span.name == "test_operation"
        assert span.kind == SpanKind.SERVER
        assert span.trace_id is not None
        assert span.span_id is not None

    def test_start_span_with_parent(self, tracer):
        """Test starting a span with parent."""
        parent = tracer.start_span("parent", SpanKind.SERVER)

        child = tracer.start_span("child", SpanKind.INTERNAL, parent=parent)

        assert child.parent_id == parent.span_id
        assert child.trace_id == parent.trace_id

    def test_finish_span(self, tracer):
        """Test finishing a span."""
        span = tracer.start_span("test_operation")
        tracer.finish_span(span, SpanStatus.OK)

        assert span.end_time is not None
        assert span.status == SpanStatus.OK

    def test_context_manager(self, tracer):
        """Test the span context manager."""
        with tracer.span("test_operation") as span:
            span.set_attribute("test", True)

        assert span.end_time is not None
        assert span.status == SpanStatus.OK

    def test_context_manager_exception(self, tracer):
        """Test that exceptions are recorded."""
        with pytest.raises(ValueError):
            with tracer.span("test_operation") as span:
                raise ValueError("Test error")

        # Span should have error status
        current = tracer.get_current_span()
        if current:
            assert current.status == SpanStatus.ERROR

    @pytest.mark.asyncio
    async def test_async_trace(self, tracer):
        """Test async trace context manager."""
        async with tracer.trace("async_operation") as span:
            span.set_attribute("async", True)
            await asyncio.sleep(0.01)

        assert span.end_time is not None

    def test_trace_method_decorator(self, tracer):
        """Test the trace_method decorator."""

        @tracer.trace_method("test_function")
        def test_function(x):
            """Execute test_function operation.

            Args:
                x: The x parameter.

            Returns:
                The result of the operation.
            """
            return x * 2

        result = test_function(5)
        assert result == 10

    @pytest.mark.asyncio
    async def test_async_trace_method_decorator(self, tracer):
        """Test async trace_method decorator."""

        @tracer.trace_method("async_test_function")
        async def async_test_function(x):
            """Execute async_test_function operation.

            Args:
                x: The x parameter.

            Returns:
                The result of the operation.
            """
            await asyncio.sleep(0.01)
            return x * 2

        result = await async_test_function(5)
        assert result == 10

    def test_cost_tracking(self, tracer):
        """Test cost attribution."""
        span = tracer.start_span("test_operation")
        span.add_cost("compute", Decimal("0.01"))
        span.add_cost("database", Decimal("0.02"))

        tracer.finish_span(span)

        assert span.cost.total_cost_usd == Decimal("0.03")

    def test_cost_by_tenant(self, tracer):
        """Test cost tracking by tenant."""
        span = tracer.start_span("test_operation")
        span.set_attribute("tenant.id", "tenant1")
        span.add_cost("compute", Decimal("0.01"))
        tracer.finish_span(span)

        cost = tracer.get_cost_by_tenant("tenant1")
        assert cost.compute_cost_usd == Decimal("0.01")


class TestConsoleSpanExporter:
    """Tests for ConsoleSpanExporter."""

    @pytest.mark.asyncio
    async def test_export(self, capsys):
        """Test exporting spans to console."""
        exporter = ConsoleSpanExporter()

        import time

        span = Span(
            trace_id="abc123",
            span_id="def456",
            parent_id=None,
            name="test_span",
            kind=SpanKind.INTERNAL,
            start_time=time.time(),
        )
        span.finish(SpanStatus.OK)

        result = await exporter.export([span])
        assert result is True

        # Check output
        captured = capsys.readouterr()
        assert "test_span" in captured.out or "test_span" in captured.err


class TestInMemorySpanExporter:
    """Tests for InMemorySpanExporter."""

    @pytest.mark.asyncio
    async def test_export_and_retrieve(self):
        """Test exporting and retrieving spans."""
        exporter = InMemorySpanExporter()

        import time

        span = Span(
            trace_id="abc123",
            span_id="def456",
            parent_id=None,
            name="test_span",
            kind=SpanKind.INTERNAL,
            start_time=time.time(),
        )
        span.finish(SpanStatus.OK)

        await exporter.export([span])

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].name == "test_span"

    def test_clear(self):
        """Test clearing spans."""
        exporter = InMemorySpanExporter()

        import time

        span = Span(
            trace_id="abc123",
            span_id="def456",
            parent_id=None,
            name="test_span",
            kind=SpanKind.INTERNAL,
            start_time=time.time(),
        )
        span.finish(SpanStatus.OK)

        # Export synchronously for this test
        import asyncio

        asyncio.run(exporter.export([span]))

        exporter.clear()
        assert len(exporter.spans) == 0


class TestAPICostTracker:
    """Tests for APICostTracker."""

    def test_track_api_call(self):
        """Test tracking API call costs."""
        tracker = APICostTracker()

        import time

        span = Span(
            trace_id="abc123",
            span_id="def456",
            parent_id=None,
            name="api_call",
            kind=SpanKind.CLIENT,
            start_time=time.time(),
        )

        tracker.track_api_call("openai_gpt4", span, units=1000)

        assert span.cost.api_cost_usd > 0
        assert "api.openai_gpt4.units" in span.attributes

    def test_custom_costs(self):
        """Test custom API costs."""
        custom_costs = {"custom_api": Decimal("0.05")}
        tracker = APICostTracker(custom_costs=custom_costs)

        import time

        span = Span(
            trace_id="abc123",
            span_id="def456",
            parent_id=None,
            name="api_call",
            kind=SpanKind.CLIENT,
            start_time=time.time(),
        )

        tracker.track_api_call("custom_api", span, units=10)

        assert span.cost.api_cost_usd == Decimal("0.5")


class TestDatabaseCostTracker:
    """Tests for DatabaseCostTracker."""

    def test_track_query(self):
        """Test tracking database query costs."""
        tracker = DatabaseCostTracker()

        import time

        span = Span(
            trace_id="abc123",
            span_id="def456",
            parent_id=None,
            name="db_query",
            kind=SpanKind.INTERNAL,
            start_time=time.time(),
        )

        tracker.track_query("read", span, rows_affected=100)

        assert span.cost.database_cost_usd > 0
        assert span.attributes["db.query_type"] == "read"
        assert span.attributes["db.rows_affected"] == 100


class TestIntegration:
    """Integration tests for tracing."""

    def test_full_workflow(self):
        """Test a complete tracing workflow."""
        config = TracingConfig(
            service_name="integration-test",
            sample_rate=1.0,
            enable_cost_tracking=True,
        )
        tracer = Tracer(config)
        exporter = InMemorySpanExporter()
        tracer.add_exporter(exporter)

        # Simulate a request
        with tracer.span("http_request", SpanKind.SERVER) as request_span:
            request_span.set_attribute("http.method", "GET")
            request_span.set_attribute("http.url", "/api/users")
            request_span.set_attribute("tenant.id", "tenant1")
            request_span.set_attribute("user.id", "user123")

            # Simulate database query
            with tracer.span("db_query", SpanKind.INTERNAL) as db_span:
                db_span.add_cost("database", Decimal("0.001"))

            # Simulate API call
            with tracer.span("api_call", SpanKind.CLIENT) as api_span:
                api_span.add_cost("api", Decimal("0.01"))

            # Add compute cost
            request_span.add_cost("compute", Decimal("0.0001"))

        # Verify spans were exported
        spans = exporter.get_finished_spans()
        assert len(spans) >= 3

        # Verify cost tracking
        tenant_cost = tracer.get_cost_by_tenant("tenant1")
        assert tenant_cost.total_cost_usd > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
