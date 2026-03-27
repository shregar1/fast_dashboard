"""Dependency registry for loose coupling with host application.

This module provides a registry pattern that allows the host application
to register dependencies (database sessions, configuration providers, etc.)
without requiring tight coupling to specific module paths.

Example:
    # In host app startup
    from fast_dashboards.core.registry import registry
    from myapp.config import JobsConfiguration
    registry.register_config("jobs", JobsConfiguration)

    # In dashboard (automatically resolved)
    cfg = registry.get_config("jobs")  # Returns host app's configuration

"""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional, Protocol, TypeVar, runtime_checkable

T = TypeVar("T")


@runtime_checkable
class ConfigProvider(Protocol):
    """Protocol for configuration providers."""

    def instance(self) -> Any: ...


@runtime_checkable
class TenantStore(Protocol):
    """Protocol for tenant store implementations."""

    def list_all(self) -> list[dict[str, Any]]: ...


@runtime_checkable
class DatabaseSession(Protocol):
    """Protocol for database session."""

    def execute(self, query: Any) -> Any: ...


@runtime_checkable
class RedisSession(Protocol):
    """Protocol for Redis session."""

    def ping(self) -> bool: ...
    def info(self) -> dict[str, Any]: ...


class DependencyRegistry:
    """Registry for host application dependencies.

    This allows dashboards to work without hard dependencies on
    specific host app modules like 'configurations', 'core.datastores',
    or 'start_utils'.
    """

    def __init__(self) -> None:
        self._configs: Dict[str, Any] = {}
        self._session_providers: Dict[str, Callable[[], Any]] = {}
        self._tenant_store: Optional[TenantStore] = None
        self._datastores: Dict[str, Any] = {}

    # Configuration providers
    def register_config(self, name: str, provider: Any) -> None:
        """Register a configuration provider (e.g., JobsConfiguration)."""
        self._configs[name] = provider

    def get_config(self, name: str) -> Optional[Any]:
        """Get a configuration provider by name."""
        provider = self._configs.get(name)
        if provider is None:
            # Try to auto-import from common patterns
            return self._try_auto_import_config(name)
        return provider

    def _try_auto_import_config(self, name: str) -> Optional[Any]:
        """Attempt to auto-import configuration from host app."""
        config_modules = {
            "jobs": "configurations.jobs",
            "queues": "configurations.queues",
            "workflows": "configurations.workflows",
            "secrets": "configurations.secrets",
            "feature_flags": "configurations.feature_flags",
            "identity": "configurations.identity",
            "rate_limit": "configurations.rate_limit",
        }
        module_path = config_modules.get(name)
        if not module_path:
            return None

        try:
            import importlib

            mod = importlib.import_module(module_path)
            # Try common class names
            class_name = f"{name.title().replace('_', '')}Configuration"
            if hasattr(mod, class_name):
                return getattr(mod, class_name)
            # Try without title case conversion for special cases
            alt_names = {
                "jobs": "JobsConfiguration",
                "queues": "QueuesConfiguration",
                "workflows": "WorkflowsConfiguration",
                "secrets": "SecretsConfiguration",
                "feature_flags": "FeatureFlagsConfiguration",
                "identity": "IdentityProvidersConfiguration",
                "rate_limit": "RateLimitConfiguration",
            }
            if name in alt_names and hasattr(mod, alt_names[name]):
                return getattr(mod, alt_names[name])
        except ImportError:
            pass
        return None

    # Session providers
    def register_db_session(self, provider: Callable[[], DatabaseSession]) -> None:
        """Register a database session provider."""
        self._session_providers["db"] = provider

    def register_redis_session(self, provider: Callable[[], RedisSession]) -> None:
        """Register a Redis session provider."""
        self._session_providers["redis"] = provider

    def get_db_session(self) -> Optional[DatabaseSession]:
        """Get the registered database session, or try to auto-import."""
        provider = self._session_providers.get("db")
        if provider:
            return provider()
        # Try to auto-import from start_utils
        try:
            import start_utils

            return getattr(start_utils, "db_session", None)
        except ImportError:
            return None

    def get_redis_session(self) -> Optional[RedisSession]:
        """Get the registered Redis session, or try to auto-import."""
        provider = self._session_providers.get("redis")
        if provider:
            return provider()
        # Try to auto-import from start_utils
        try:
            import start_utils

            return getattr(start_utils, "redis_session", None)
        except ImportError:
            return None

    # Tenant store
    def register_tenant_store(self, store: TenantStore) -> None:
        """Register a tenant store implementation."""
        self._tenant_store = store

    def get_tenant_store(self) -> Optional[TenantStore]:
        """Get the registered tenant store, or try to auto-import."""
        if self._tenant_store:
            return self._tenant_store
        # Try to auto-import from core.tenancy
        try:
            from core.tenancy.context import InMemoryTenantStore

            return InMemoryTenantStore()
        except ImportError:
            return None

    # Datastores
    def register_datastore(self, name: str, store_class: Any) -> None:
        """Register a datastore class."""
        self._datastores[name] = store_class

    def get_datastore(self, name: str) -> Optional[Any]:
        """Get a datastore class by name, or try to auto-import."""
        if name in self._datastores:
            return self._datastores[name]
        # Try to auto-import from core.datastores
        try:
            import core.datastores as datastores

            return getattr(datastores, name, None)
        except ImportError:
            return None

    def get_datastore_class(self, name: str) -> Optional[type]:
        """Get a datastore class by name (alias for get_datastore)."""
        return self.get_datastore(name)


# Global registry instance
registry = DependencyRegistry()


__all__ = [
    "registry",
    "DependencyRegistry",
    "ConfigProvider",
    "TenantStore",
    "DatabaseSession",
    "RedisSession",
]
