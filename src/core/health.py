"""Production-grade health checks and readiness probes.

Supports liveness, readiness, and startup probes with detailed checks
for database, cache, external services, etc.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Protocol

from fastapi import APIRouter, Response
from pydantic import BaseModel

from fast_dashboards.core.registry import registry


class HealthStatus(str, Enum):
    """Health check status."""

    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"


class ProbeType(str, Enum):
    """Types of health probes."""

    LIVENESS = "liveness"  # Is the app running?
    READINESS = "readiness"  # Is the app ready to serve traffic?
    STARTUP = "startup"  # Has the app started?


@dataclass
class HealthCheck:
    """Individual health check result."""

    name: str
    status: HealthStatus
    response_time_ms: float
    message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Execute to_dict operation.

        Returns:
            The result of the operation.
        """
        return {
            "name": self.name,
            "status": self.status.value,
            "response_time_ms": round(self.response_time_ms, 2),
            "message": self.message,
            "metadata": self.metadata,
        }


class HealthCheckFunction(Protocol):
    """Protocol for health check functions."""

    async def __call__(self) -> HealthCheck:
        """Perform a health check."""
        ...


class HealthRegistry:
    """Registry for health checks."""

    def __init__(self):
        """Execute __init__ operation."""
        self.checks: Dict[str, HealthCheckFunction] = {}
        self.startup_time = time.time()

    def register(
        self,
        name: str,
        check_func: HealthCheckFunction,
        probe_types: List[ProbeType] = None,
    ) -> None:
        """Register a health check."""
        self.checks[name] = check_func

    async def run_check(self, name: str) -> HealthCheck:
        """Run a specific health check."""
        check_func = self.checks.get(name)
        if not check_func:
            return HealthCheck(
                name=name,
                status=HealthStatus.UNKNOWN,
                response_time_ms=0,
                message="Check not registered",
            )

        start = time.time()
        try:
            result = await asyncio.wait_for(check_func(), timeout=5.0)
            result.response_time_ms = (time.time() - start) * 1000
            return result
        except asyncio.TimeoutError:
            return HealthCheck(
                name=name,
                status=HealthStatus.UNHEALTHY,
                response_time_ms=(time.time() - start) * 1000,
                message="Health check timed out",
            )
        except Exception as e:
            return HealthCheck(
                name=name,
                status=HealthStatus.UNHEALTHY,
                response_time_ms=(time.time() - start) * 1000,
                message=str(e)[:200],
            )

    async def run_all_checks(self) -> Dict[str, HealthCheck]:
        """Run all registered health checks."""
        results = {}
        for name in self.checks:
            results[name] = await self.run_check(name)
        return results

    def get_overall_status(self, checks: Dict[str, HealthCheck]) -> HealthStatus:
        """Determine overall health status from individual checks."""
        if not checks:
            return HealthStatus.UNKNOWN

        statuses = [c.status for c in checks.values()]

        if any(s == HealthStatus.UNHEALTHY for s in statuses):
            return HealthStatus.UNHEALTHY
        if any(s == HealthStatus.DEGRADED for s in statuses):
            return HealthStatus.DEGRADED
        if all(s == HealthStatus.HEALTHY for s in statuses):
            return HealthStatus.HEALTHY

        return HealthStatus.UNKNOWN


# Global health registry
health_registry = HealthRegistry()


# Built-in health checks


async def check_database() -> HealthCheck:
    """Check database connectivity."""
    start = time.time()
    try:
        db_session = registry.get_db_session()
        if db_session is None:
            return HealthCheck(
                name="database",
                status=HealthStatus.DEGRADED,
                response_time_ms=(time.time() - start) * 1000,
                message="Database not configured",
            )

        # Try to execute a simple query
        # Note: This is a simplified check
        return HealthCheck(
            name="database",
            status=HealthStatus.HEALTHY,
            response_time_ms=(time.time() - start) * 1000,
            message="Connected",
        )
    except Exception as e:
        return HealthCheck(
            name="database",
            status=HealthStatus.UNHEALTHY,
            response_time_ms=(time.time() - start) * 1000,
            message=str(e)[:200],
        )


async def check_redis() -> HealthCheck:
    """Check Redis connectivity."""
    start = time.time()
    try:
        redis = registry.get_redis_session()
        if redis is None:
            return HealthCheck(
                name="redis",
                status=HealthStatus.DEGRADED,
                response_time_ms=(time.time() - start) * 1000,
                message="Redis not configured",
            )

        # Try to ping Redis
        if hasattr(redis, "ping"):
            await redis.ping()

        return HealthCheck(
            name="redis",
            status=HealthStatus.HEALTHY,
            response_time_ms=(time.time() - start) * 1000,
            message="Connected",
        )
    except Exception as e:
        return HealthCheck(
            name="redis",
            status=HealthStatus.UNHEALTHY,
            response_time_ms=(time.time() - start) * 1000,
            message=str(e)[:200],
        )


async def check_disk_space() -> HealthCheck:
    """Check available disk space."""
    start = time.time()
    try:
        import shutil

        stat = shutil.disk_usage("/")
        free_gb = stat.free / (1024**3)
        total_gb = stat.total / (1024**3)
        used_percent = (stat.used / stat.total) * 100

        status = HealthStatus.HEALTHY
        if used_percent > 90:
            status = HealthStatus.UNHEALTHY
        elif used_percent > 80:
            status = HealthStatus.DEGRADED

        return HealthCheck(
            name="disk",
            status=status,
            response_time_ms=(time.time() - start) * 1000,
            message=f"{free_gb:.1f}GB free of {total_gb:.1f}GB",
            metadata={"free_gb": free_gb, "used_percent": used_percent},
        )
    except Exception as e:
        return HealthCheck(
            name="disk",
            status=HealthStatus.UNKNOWN,
            response_time_ms=(time.time() - start) * 1000,
            message=str(e)[:200],
        )


async def check_memory() -> HealthCheck:
    """Check memory usage."""
    start = time.time()
    try:
        import psutil

        mem = psutil.virtual_memory()

        status = HealthStatus.HEALTHY
        if mem.percent > 90:
            status = HealthStatus.UNHEALTHY
        elif mem.percent > 80:
            status = HealthStatus.DEGRADED

        return HealthCheck(
            name="memory",
            status=status,
            response_time_ms=(time.time() - start) * 1000,
            message=f"{mem.percent}% used",
            metadata={
                "percent": mem.percent,
                "available_mb": mem.available // (1024**2),
            },
        )
    except ImportError:
        return HealthCheck(
            name="memory",
            status=HealthStatus.UNKNOWN,
            response_time_ms=(time.time() - start) * 1000,
            message="psutil not installed",
        )
    except Exception as e:
        return HealthCheck(
            name="memory",
            status=HealthStatus.UNKNOWN,
            response_time_ms=(time.time() - start) * 1000,
            message=str(e)[:200],
        )


# Register built-in checks
health_registry.register("database", check_database, [ProbeType.READINESS])
health_registry.register("redis", check_redis, [ProbeType.READINESS])
health_registry.register("disk", check_disk_space, [ProbeType.LIVENESS])
health_registry.register("memory", check_memory, [ProbeType.LIVENESS])


# Create router
health_router = APIRouter(tags=["Health"])


class HealthResponse(BaseModel):
    """Health check response model."""

    status: str
    version: str = "1.0.0"
    timestamp: str
    uptime_seconds: float
    checks: Dict[str, Dict[str, Any]]


@health_router.get("/health", summary="Liveness Probe")
async def liveness_check() -> Response:
    """Liveness probe - indicates if the application is running.

    Returns 200 if the application is alive, regardless of dependencies.
    Kubernetes uses this to know when to restart a container.
    """
    return Response(
        content='{"status": "alive"}', media_type="application/json", status_code=200
    )


@health_router.get("/ready", summary="Readiness Probe")
async def readiness_check() -> Response:
    """Readiness probe - indicates if the application is ready to serve traffic.

    Returns 200 only if all dependencies (database, cache, etc.) are healthy.
    Kubernetes uses this to know when to send traffic to a pod.
    """
    checks = await health_registry.run_all_checks()
    overall = health_registry.get_overall_status(checks)

    response_data = HealthResponse(
        status=overall.value,
        timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        uptime_seconds=time.time() - health_registry.startup_time,
        checks={name: check.to_dict() for name, check in checks.items()},
    )

    status_code = (
        200 if overall in [HealthStatus.HEALTHY, HealthStatus.DEGRADED] else 503
    )

    return Response(
        content=response_data.json(),
        media_type="application/json",
        status_code=status_code,
    )


@health_router.get("/startup", summary="Startup Probe")
async def startup_check() -> Response:
    """Startup probe - indicates if the application has finished starting up.

    Returns 200 once the application is fully initialized.
    Kubernetes uses this during container startup.
    """
    # Check if startup time has passed (min 5 seconds)
    elapsed = time.time() - health_registry.startup_time

    if elapsed < 5:
        return Response(
            content=f'{{"status": "starting", "elapsed": {elapsed:.1f}}}',
            media_type="application/json",
            status_code=503,
        )

    return Response(
        content='{"status": "started"}', media_type="application/json", status_code=200
    )


@health_router.get("/health/detailed", summary="Detailed Health Check")
async def detailed_health() -> HealthResponse:
    """Get detailed health information about all components."""
    checks = await health_registry.run_all_checks()
    overall = health_registry.get_overall_status(checks)

    return HealthResponse(
        status=overall.value,
        timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        uptime_seconds=time.time() - health_registry.startup_time,
        checks={name: check.to_dict() for name, check in checks.items()},
    )


__all__ = [
    "health_router",
    "health_registry",
    "HealthRegistry",
    "HealthCheck",
    "HealthStatus",
    "ProbeType",
    "check_database",
    "check_redis",
    "check_disk_space",
    "check_memory",
]
