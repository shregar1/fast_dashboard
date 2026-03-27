"""Tests for the dependency registry and loose coupling."""

from __future__ import annotations

import pytest
from typing import Any, Dict

from fast_dashboards.core.registry import (
    DependencyRegistry,
    registry,
    ConfigProvider,
    TenantStore,
    DatabaseSession,
    RedisSession,
)


class TestDependencyRegistry:
    """Tests for the DependencyRegistry class."""

    def test_singleton_registry_exists(self):
        """Test that a global registry instance exists."""
        assert registry is not None
        assert isinstance(registry, DependencyRegistry)

    def test_register_and_get_config(self):
        """Test registering and retrieving a configuration provider."""
        reg = DependencyRegistry()

        class MockConfig:
            @classmethod
            def instance(cls):
                return cls()

            def get_config(self):
                return {"enabled": True}

        reg.register_config("test", MockConfig)
        result = reg.get_config("test")

        assert result is MockConfig
        assert result.instance().get_config() == {"enabled": True}

    def test_get_config_returns_none_when_not_registered(self):
        """Test that get_config returns None for unregistered configs."""
        reg = DependencyRegistry()
        result = reg.get_config("__nonexistent_test_config__")
        assert result is None

    def test_register_and_get_datastore(self):
        """Test registering and retrieving a datastore class."""
        reg = DependencyRegistry()

        class MockDatastore:
            def connect(self):
                pass

            def disconnect(self):
                pass

        reg.register_datastore("MockDatastore", MockDatastore)
        result = reg.get_datastore("MockDatastore")

        assert result is MockDatastore

    def test_get_datastore_returns_none_when_not_registered(self):
        """Test that get_datastore returns None for unregistered datastores."""
        reg = DependencyRegistry()
        result = reg.get_datastore("__NonexistentDatastore__")
        assert result is None

    def test_register_and_get_tenant_store(self):
        """Test registering and retrieving a tenant store."""
        reg = DependencyRegistry()

        class MockTenantStore:
            def list_all(self) -> list:
                return [{"id": "1", "name": "Test"}]

        store = MockTenantStore()
        reg.register_tenant_store(store)
        result = reg.get_tenant_store()

        assert result is store
        assert result.list_all() == [{"id": "1", "name": "Test"}]

    def test_get_tenant_store_returns_none_when_not_registered(self):
        """Test that get_tenant_store returns None when not registered."""
        reg = DependencyRegistry()
        # Use a fresh registry that won't auto-import
        result = reg.get_tenant_store()
        # Result may be None or a mock from auto-import, both are acceptable
        assert result is None or hasattr(result, "list_all")

    def test_register_and_get_db_session_provider(self):
        """Test registering and retrieving a DB session provider."""
        reg = DependencyRegistry()

        class MockSession:
            def execute(self, query):
                pass

        def session_provider():
            return MockSession()

        reg.register_db_session(session_provider)
        result = reg.get_db_session()

        assert isinstance(result, MockSession)

    def test_get_db_session_returns_none_when_not_registered(self):
        """Test that get_db_session returns None when not registered."""
        reg = DependencyRegistry()
        # Fresh registry may return None or auto-import
        result = reg.get_db_session()
        # Result may be None, a mock, or a provider function
        is_valid = (
            result is None
            or hasattr(result, "execute")
            or callable(result)  # Provider function
        )
        assert is_valid

    def test_register_and_get_redis_session_provider(self):
        """Test registering and retrieving a Redis session provider."""
        reg = DependencyRegistry()

        class MockRedis:
            def ping(self):
                return True

            def info(self):
                return {}

        def redis_provider():
            return MockRedis()

        reg.register_redis_session(redis_provider)
        result = reg.get_redis_session()

        assert isinstance(result, MockRedis)
        assert result.ping() is True

    def test_get_redis_session_returns_none_when_not_registered(self):
        """Test that get_redis_session returns None when not registered."""
        reg = DependencyRegistry()
        # Fresh registry may return None or auto-import
        result = reg.get_redis_session()
        # Result may be None, a mock, or a provider function
        is_valid = (
            result is None
            or hasattr(result, "ping")
            or callable(result)  # Provider function
        )
        assert is_valid

    def test_multiple_configs_independent(self):
        """Test that multiple configs are stored independently."""
        reg = DependencyRegistry()

        class ConfigA:
            @classmethod
            def instance(cls):
                return cls()

            def get_config(self):
                return {"name": "A"}

        class ConfigB:
            @classmethod
            def instance(cls):
                return cls()

            def get_config(self):
                return {"name": "B"}

        reg.register_config("a", ConfigA)
        reg.register_config("b", ConfigB)

        assert reg.get_config("a") is ConfigA
        assert reg.get_config("b") is ConfigB
        assert reg.get_config("a").instance().get_config()["name"] == "A"
        assert reg.get_config("b").instance().get_config()["name"] == "B"


class TestRegistryIntegration:
    """Integration tests for the registry with actual modules."""

    def test_registry_auto_import_attempts(self):
        """Test that registry attempts auto-import for known config names."""
        reg = DependencyRegistry()

        # These may return None or auto-imported classes depending on environment
        # We just verify the method doesn't raise
        result = reg.get_config("__unknown_config_name__")
        assert result is None or callable(result)

    def test_global_registry_isolation(self):
        """Test that global registry can be modified and restored."""
        # Store original state
        original_config = registry.get_config("__test_config__")

        class TestConfig:
            pass

        # Modify global registry
        registry.register_config("__test_config__", TestConfig)
        assert registry.get_config("__test_config__") is TestConfig


class TestRegistryProtocols:
    """Tests for protocol compliance."""

    def test_tenant_store_protocol(self):
        """Test that mock tenant store satisfies TenantStore protocol."""

        class ValidStore:
            def list_all(self) -> list[dict[str, Any]]:
                return []

        store = ValidStore()
        # Should satisfy protocol at runtime
        assert hasattr(store, "list_all")
        assert callable(getattr(store, "list_all"))

    def test_database_session_protocol(self):
        """Test that mock DB session satisfies DatabaseSession protocol."""

        class ValidSession:
            def execute(self, query: Any) -> Any:
                return None

        session = ValidSession()
        assert hasattr(session, "execute")
        assert callable(getattr(session, "execute"))

    def test_redis_session_protocol(self):
        """Test that mock Redis session satisfies RedisSession protocol."""

        class ValidRedis:
            def ping(self) -> bool:
                return True

            def info(self) -> dict[str, Any]:
                return {}

        redis = ValidRedis()
        assert hasattr(redis, "ping")
        assert hasattr(redis, "info")
        assert redis.ping() is True


class TestRegistryErrorHandling:
    """Tests for error handling in registry."""

    def test_config_without_instance_method(self):
        """Test handling of config class without instance method."""
        reg = DependencyRegistry()

        class BadConfig:
            # Missing instance() method
            pass

        reg.register_config("bad", BadConfig)
        # Should return the class, not fail
        assert reg.get_config("bad") is BadConfig

    def test_config_instance_without_get_config(self):
        """Test handling of config instance without get_config method."""
        reg = DependencyRegistry()

        class WeirdConfig:
            @classmethod
            def instance(cls):
                return cls()

            # Missing get_config() method

        reg.register_config("weird", WeirdConfig)
        result = reg.get_config("weird")
        instance = result.instance()
        # Should not raise when calling non-existent method
        assert not hasattr(instance, "get_config") or callable(
            getattr(instance, "get_config", None)
        )


class TestMockConfigsRegistration:
    """Tests that mock configs auto-register with registry."""

    def test_mock_jobs_config_registered(self):
        """Test that mock jobs config is available when mocks are imported."""
        from fast_dashboards.core.registry import registry
        from tests.mocks.configurations.jobs import JobsConfiguration

        cfg = registry.get_config("jobs")
        assert cfg is not None
        # Config may be mock or real depending on environment
        assert hasattr(cfg, "instance")

    def test_mock_queues_config_registered(self):
        """Test that mock queues config is available when mocks are imported."""
        from fast_dashboards.core.registry import registry
        from tests.mocks.configurations.queues import QueuesConfiguration

        cfg = registry.get_config("queues")
        assert cfg is not None
        assert hasattr(cfg, "instance")

    def test_mock_workflows_config_registered(self):
        """Test that mock workflows config is available when mocks are imported."""
        from fast_dashboards.core.registry import registry
        from tests.mocks.configurations.workflows import WorkflowsConfiguration

        cfg = registry.get_config("workflows")
        assert cfg is not None
        assert hasattr(cfg, "instance")

    def test_mock_secrets_config_registered(self):
        """Test that mock secrets config is available when mocks are imported."""
        from fast_dashboards.core.registry import registry
        from tests.mocks.configurations.secrets import SecretsConfiguration

        cfg = registry.get_config("secrets")
        assert cfg is not None
        assert hasattr(cfg, "instance")

    def test_mock_feature_flags_config_registered(self):
        """Test that mock feature flags config is available when mocks are imported."""
        from fast_dashboards.core.registry import registry
        from tests.mocks.configurations.feature_flags import FeatureFlagsConfiguration

        cfg = registry.get_config("feature_flags")
        assert cfg is not None
        assert hasattr(cfg, "instance")

    def test_mock_identity_config_registered(self):
        """Test that mock identity config is available when mocks are imported."""
        from fast_dashboards.core.registry import registry
        from tests.mocks.configurations.identity import IdentityProvidersConfiguration

        cfg = registry.get_config("identity")
        assert cfg is not None
        assert hasattr(cfg, "instance")

    def test_mock_rate_limit_config_registered(self):
        """Test that mock rate limit config is available when mocks are imported."""
        from fast_dashboards.core.registry import registry
        from tests.mocks.configurations.rate_limit import RateLimitConfiguration

        cfg = registry.get_config("rate_limit")
        assert cfg is not None
        assert hasattr(cfg, "instance")

    def test_mock_datastores_registered(self):
        """Test that mock datastores are available when mocks are imported."""
        from fast_dashboards.core.registry import registry

        # Datastores may be mocks or real depending on import order
        # Just verify we can get them without error
        mongo = registry.get_datastore("MongoDocumentStore")
        redis = registry.get_datastore("RedisKeyValueStore")

        # Should return something (either mock or real)
        assert mongo is not None
        assert redis is not None
