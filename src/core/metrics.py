"""Production-grade metrics collection for Prometheus.

Supports counters, gauges, histograms, and summaries with automatic
HTTP request tracking.
"""

from __future__ import annotations

import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Union

from fastapi import APIRouter, Request, Response

# Try to import prometheus_client, fallback to stubs if not available
try:
    from prometheus_client import (
        Counter,
        Gauge,
        Histogram,
        Info,
        generate_latest,
        CONTENT_TYPE_LATEST,
        CollectorRegistry,
    )

    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False

    # Stub classes
    class CollectorRegistry:
        pass

    class Counter:
        def __init__(self, *args, **kwargs):
            pass

        def labels(self, **kwargs):
            return self

        def inc(self, *args, **kwargs):
            pass

        def observe(self, *args, **kwargs):
            pass

    class Gauge:
        def __init__(self, *args, **kwargs):
            pass

        def labels(self, **kwargs):
            return self

        def set(self, *args, **kwargs):
            pass

        def inc(self, *args, **kwargs):
            pass

        def dec(self, *args, **kwargs):
            pass

    class Histogram:
        def __init__(self, *args, **kwargs):
            pass

        def labels(self, **kwargs):
            return self

        def observe(self, *args, **kwargs):
            pass

    class Info:
        def __init__(self, *args, **kwargs):
            pass

        def info(self, *args, **kwargs):
            pass

    def generate_latest(*args, **kwargs):
        return b"# prometheus_client not installed"

    CONTENT_TYPE_LATEST = "text/plain"


# Custom registry for our metrics
metrics_registry = CollectorRegistry()

# Application info
app_info = Info("fastmvc_app", "Application information", registry=metrics_registry)

# HTTP request metrics
http_requests_total = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status_code"],
    registry=metrics_registry,
)

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint"],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
    registry=metrics_registry,
)

http_request_size_bytes = Histogram(
    "http_request_size_bytes",
    "HTTP request size in bytes",
    ["method", "endpoint"],
    buckets=[100, 1000, 10000, 100000, 1000000],
    registry=metrics_registry,
)

http_response_size_bytes = Histogram(
    "http_response_size_bytes",
    "HTTP response size in bytes",
    ["method", "endpoint"],
    buckets=[100, 1000, 10000, 100000, 1000000],
    registry=metrics_registry,
)

# Active connections
active_connections = Gauge(
    "http_active_connections",
    "Number of active HTTP connections",
    registry=metrics_registry,
)

# Database metrics
db_connections_active = Gauge(
    "db_connections_active",
    "Number of active database connections",
    registry=metrics_registry,
)

db_connections_idle = Gauge(
    "db_connections_idle",
    "Number of idle database connections",
    registry=metrics_registry,
)

db_query_duration_seconds = Histogram(
    "db_query_duration_seconds",
    "Database query duration in seconds",
    ["operation", "table"],
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0],
    registry=metrics_registry,
)

# Cache metrics
cache_operations_total = Counter(
    "cache_operations_total",
    "Total cache operations",
    ["operation", "result"],
    registry=metrics_registry,
)

cache_duration_seconds = Histogram(
    "cache_duration_seconds",
    "Cache operation duration in seconds",
    ["operation"],
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05],
    registry=metrics_registry,
)

# Business metrics
users_active = Gauge(
    "users_active", "Number of active users", ["tenant"], registry=metrics_registry
)

jobs_queued = Gauge(
    "jobs_queued", "Number of queued jobs", ["queue"], registry=metrics_registry
)

jobs_processing = Gauge(
    "jobs_processing", "Number of processing jobs", ["queue"], registry=metrics_registry
)


@dataclass
class MetricTimer:
    """Helper for timing operations."""

    histogram: Histogram
    labels: Dict[str, str] = field(default_factory=dict)
    start_time: Optional[float] = None

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time is not None:
            duration = time.time() - self.start_time
            self.histogram.labels(**self.labels).observe(duration)

    def observe(self, value: float):
        """Manually observe a value."""
        self.histogram.labels(**self.labels).observe(value)


class MetricsCollector:
    """Centralized metrics collector."""

    def __init__(self):
        self.custom_counters: Dict[str, Counter] = {}
        self.custom_gauges: Dict[str, Gauge] = {}
        self.custom_histograms: Dict[str, Histogram] = {}

    def set_app_info(self, version: str, app_name: str = "fastmvc") -> None:
        """Set application information."""
        app_info.info({"version": version, "name": app_name})

    def counter(
        self, name: str, description: str, labels: Optional[List[str]] = None
    ) -> Counter:
        """Get or create a counter."""
        if name not in self.custom_counters:
            self.custom_counters[name] = Counter(
                name, description, labels or [], registry=metrics_registry
            )
        return self.custom_counters[name]

    def gauge(
        self, name: str, description: str, labels: Optional[List[str]] = None
    ) -> Gauge:
        """Get or create a gauge."""
        if name not in self.custom_gauges:
            self.custom_gauges[name] = Gauge(
                name, description, labels or [], registry=metrics_registry
            )
        return self.custom_gauges[name]

    def histogram(
        self,
        name: str,
        description: str,
        labels: Optional[List[str]] = None,
        buckets: Optional[List[float]] = None,
    ) -> Histogram:
        """Get or create a histogram."""
        if name not in self.custom_histograms:
            self.custom_histograms[name] = Histogram(
                name,
                description,
                labels or [],
                buckets=buckets
                or [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
                registry=metrics_registry,
            )
        return self.custom_histograms[name]

    def time(self, histogram: Histogram, **labels) -> MetricTimer:
        """Time an operation."""
        return MetricTimer(histogram, labels)

    def track_db_query(self, operation: str, table: str, duration: float):
        """Track database query duration."""
        db_query_duration_seconds.labels(operation=operation, table=table).observe(
            duration
        )

    def track_cache_hit(self, operation: str = "get"):
        """Track cache hit."""
        cache_operations_total.labels(operation=operation, result="hit").inc()

    def track_cache_miss(self, operation: str = "get"):
        """Track cache miss."""
        cache_operations_total.labels(operation=operation, result="miss").inc()

    def set_active_users(self, count: int, tenant: str = "default"):
        """Set active users gauge."""
        users_active.labels(tenant=tenant).set(count)

    def set_jobs_queued(self, count: int, queue: str = "default"):
        """Set jobs queued gauge."""
        jobs_queued.labels(queue=queue).set(count)

    def set_jobs_processing(self, count: int, queue: str = "default"):
        """Set jobs processing gauge."""
        jobs_processing.labels(queue=queue).set(count)


# Global metrics collector
metrics = MetricsCollector()


# Create metrics router
metrics_router = APIRouter(tags=["Metrics"])


@metrics_router.get("/metrics", summary="Prometheus Metrics")
async def prometheus_metrics() -> Response:
    """Prometheus metrics endpoint.

    Returns metrics in Prometheus exposition format for scraping.
    """
    return Response(
        content=generate_latest(metrics_registry), media_type=CONTENT_TYPE_LATEST
    )


class MetricsMiddleware:
    """FastAPI middleware for automatic metrics collection."""

    def __init__(self, app, skip_paths: Optional[List[str]] = None):
        self.app = app
        self.skip_paths = set(
            skip_paths or ["/metrics", "/health", "/ready", "/startup"]
        )

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive)

        if request.url.path in self.skip_paths:
            await self.app(scope, receive, send)
            return

        active_connections.inc()
        start_time = time.time()

        # Capture response info
        status_code = 200
        response_body = []

        async def wrapped_send(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message.get("status", 200)
            elif message["type"] == "http.response.body":
                body = message.get("body", b"")
                response_body.append(body)
            await send(message)

        try:
            await self.app(scope, receive, wrapped_send)
        finally:
            active_connections.dec()

            duration = time.time() - start_time
            method = request.method
            path = request.url.path

            # Normalize path for metrics (replace IDs with placeholders)
            metric_path = self._normalize_path(path)

            # Record metrics
            http_requests_total.labels(
                method=method, endpoint=metric_path, status_code=str(status_code)
            ).inc()

            http_request_duration_seconds.labels(
                method=method, endpoint=metric_path
            ).observe(duration)

            # Request/response sizes
            request_size = int(request.headers.get("content-length", 0))
            if request_size > 0:
                http_request_size_bytes.labels(
                    method=method, endpoint=metric_path
                ).observe(request_size)

            response_size = sum(len(chunk) for chunk in response_body)
            if response_size > 0:
                http_response_size_bytes.labels(
                    method=method, endpoint=metric_path
                ).observe(response_size)

    def _normalize_path(self, path: str) -> str:
        """Normalize path for metrics by replacing dynamic segments."""
        # Simple normalization - replace UUIDs and numbers
        import re

        # Replace UUIDs
        path = re.sub(
            r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
            "{uuid}",
            path,
            flags=re.IGNORECASE,
        )

        # Replace numeric IDs (but keep common numeric paths like /v1/)
        parts = path.split("/")
        normalized = []
        for part in parts:
            if part.isdigit():
                normalized.append("{id}")
            else:
                normalized.append(part)

        return "/".join(normalized)


__all__ = [
    "metrics_router",
    "metrics",
    "MetricsCollector",
    "MetricsMiddleware",
    "MetricTimer",
    "metrics_registry",
    # Prometheus metrics
    "http_requests_total",
    "http_request_duration_seconds",
    "http_request_size_bytes",
    "http_response_size_bytes",
    "active_connections",
    "db_connections_active",
    "db_connections_idle",
    "db_query_duration_seconds",
    "cache_operations_total",
    "cache_duration_seconds",
    "users_active",
    "jobs_queued",
    "jobs_processing",
]
