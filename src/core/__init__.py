"""
Fast Dashboards Core - Production-grade utilities.

This module provides enterprise-ready features for:
- Authentication & Authorization
- Audit Logging
- Rate Limiting
- Health Checks
- Metrics (Prometheus)
- Webhooks
- Database Management
"""

from fast_dashboards.core.auth import (
    AuthManager,
    CurrentUser,
    Permission,
    RequireAdmin,
    RequireExecute,
    RequireRead,
    RequireWrite,
    Role,
    TenantMiddleware,
    User,
    auth_manager,
)
from fast_dashboards.core.audit import (
    AuditAction,
    AuditBackend,
    AuditEvent,
    AuditLevel,
    AuditMiddleware,
    AuditLogger,
    ConsoleAuditBackend,
    FileAuditBackend,
    InMemoryAuditBackend,
    audit_logger,
)
from fast_dashboards.core.database import (
    CircuitBreaker,
    CircuitBreakerState,
    RetryConfig,
    TransactionIsolationLevel,
    db_circuit_breaker,
    db_manager,
    read_only_transaction,
    transaction,
    transactional,
    with_retry,
)
from fast_dashboards.core.health import (
    HealthCheck,
    HealthRegistry,
    HealthStatus,
    ProbeType,
    check_database,
    check_disk_space,
    check_memory,
    check_redis,
    health_registry,
    health_router,
)
from fast_dashboards.core.metrics import (
    MetricTimer,
    MetricsCollector,
    MetricsMiddleware,
    active_connections,
    cache_duration_seconds,
    cache_operations_total,
    db_connections_active,
    db_connections_idle,
    db_query_duration_seconds,
    http_request_duration_seconds,
    http_request_size_bytes,
    http_requests_total,
    http_response_size_bytes,
    jobs_processing,
    jobs_queued,
    metrics,
    metrics_registry,
    metrics_router,
    users_active,
)
from fast_dashboards.core.rate_limit import (
    RateLimitAlgorithm,
    RateLimitConfig,
    RateLimitMiddleware,
    RateLimitResult,
    RateLimiter,
    rate_limiter,
)
from fast_dashboards.core.registry import (
    ConfigProvider,
    DatabaseSession,
    DependencyRegistry,
    RedisSession,
    TenantStore,
    registry,
)
from fast_dashboards.core.webhooks import (
    InMemoryWebhookStore,
    WebhookAuthType,
    WebhookDelivery,
    WebhookEventType,
    WebhookManager,
    WebhookStatus,
    WebhookStore,
    WebhookSubscription,
    register_webhook,
    trigger_event,
    webhook_manager,
)

__all__ = [
    # Auth
    "AuthManager",
    "auth_manager",
    "User",
    "Role",
    "Permission",
    "CurrentUser",
    "RequireRead",
    "RequireWrite",
    "RequireAdmin",
    "RequireExecute",
    "TenantMiddleware",
    # Audit
    "AuditLogger",
    "audit_logger",
    "AuditEvent",
    "AuditLevel",
    "AuditAction",
    "AuditBackend",
    "ConsoleAuditBackend",
    "FileAuditBackend",
    "InMemoryAuditBackend",
    "AuditMiddleware",
    # Rate Limit
    "RateLimiter",
    "rate_limiter",
    "RateLimitConfig",
    "RateLimitResult",
    "RateLimitAlgorithm",
    "RateLimitMiddleware",
    # Health
    "health_router",
    "HealthRegistry",
    "health_registry",
    "HealthCheck",
    "HealthStatus",
    "ProbeType",
    "check_database",
    "check_redis",
    "check_disk_space",
    "check_memory",
    # Metrics
    "metrics_router",
    "MetricsCollector",
    "metrics",
    "MetricsMiddleware",
    "MetricTimer",
    "metrics_registry",
    # Webhooks
    "WebhookManager",
    "webhook_manager",
    "WebhookSubscription",
    "WebhookDelivery",
    "WebhookEventType",
    "WebhookStatus",
    "WebhookAuthType",
    "WebhookStore",
    "InMemoryWebhookStore",
    "register_webhook",
    "trigger_event",
    # Database
    "transaction",
    "read_only_transaction",
    "transactional",
    "with_retry",
    "CircuitBreaker",
    "CircuitBreakerState",
    "RetryConfig",
    "TransactionIsolationLevel",
    "db_manager",
    "db_circuit_breaker",
    # Registry
    "registry",
    "DependencyRegistry",
    "ConfigProvider",
    "TenantStore",
    "DatabaseSession",
    "RedisSession",
]

__version__ = "0.4.0"
