"""Tests for mock configuration and datastore modules."""

from __future__ import annotations

import pytest
from typing import Any


class TestMockConfigurations:
    """Tests for mock configuration classes."""

    def test_jobs_configuration(self):
        """Test JobsConfiguration mock."""
        from tests.mocks.configurations.jobs import JobsConfiguration, JobsConfig

        # Test singleton pattern
        inst1 = JobsConfiguration.instance()
        inst2 = JobsConfiguration.instance()
        assert inst1 is inst2

        # Test config structure
        cfg = inst1.get_config()
        assert isinstance(cfg, JobsConfig)
        assert hasattr(cfg, "celery")
        assert hasattr(cfg, "rq")
        assert hasattr(cfg, "dramatiq")

        # Test defaults
        assert cfg.celery.enabled is False
        assert cfg.rq.enabled is False
        assert cfg.dramatiq.enabled is False

    def test_queues_configuration(self):
        """Test QueuesConfiguration mock."""
        from tests.mocks.configurations.queues import QueuesConfiguration, QueuesConfig

        inst = QueuesConfiguration.instance()
        cfg = inst.get_config()

        assert isinstance(cfg, QueuesConfig)
        assert hasattr(cfg, "rabbitmq")
        assert hasattr(cfg, "sqs")
        assert hasattr(cfg, "nats")

        assert cfg.rabbitmq.enabled is False
        assert cfg.sqs.enabled is False
        assert cfg.nats.enabled is False

    def test_workflows_configuration(self):
        """Test WorkflowsConfiguration mock."""
        from tests.mocks.configurations.workflows import (
            WorkflowsConfiguration,
            WorkflowsConfig,
        )

        inst = WorkflowsConfiguration.instance()
        cfg = inst.get_config()

        assert isinstance(cfg, WorkflowsConfig)
        assert cfg.enabled is False
        assert cfg.engine == ""

    def test_secrets_configuration(self):
        """Test SecretsConfiguration mock."""
        from tests.mocks.configurations.secrets import (
            SecretsConfiguration,
            SecretsConfig,
        )

        inst = SecretsConfiguration.instance()
        cfg = inst.get_config()

        assert isinstance(cfg, SecretsConfig)
        assert hasattr(cfg, "vault")
        assert hasattr(cfg, "aws")
        assert hasattr(cfg, "gcp")
        assert hasattr(cfg, "azure")

        assert cfg.vault.enabled is False
        assert cfg.aws.enabled is False

    def test_feature_flags_configuration(self):
        """Test FeatureFlagsConfiguration mock."""
        from tests.mocks.configurations.feature_flags import (
            FeatureFlagsConfiguration,
            FeatureFlagsConfig,
        )

        inst = FeatureFlagsConfiguration.instance()
        cfg = inst.get_config()

        assert isinstance(cfg, FeatureFlagsConfig)
        assert hasattr(cfg, "launchdarkly")
        assert hasattr(cfg, "unleash")

        assert cfg.launchdarkly.enabled is False
        assert cfg.unleash.enabled is False

    def test_identity_configuration(self):
        """Test IdentityProvidersConfiguration mock."""
        from tests.mocks.configurations.identity import (
            IdentityProvidersConfiguration,
            IdentityProvidersConfig,
        )

        inst = IdentityProvidersConfiguration.instance()
        cfg = inst.get_config()

        assert isinstance(cfg, IdentityProvidersConfig)
        assert hasattr(cfg, "google")
        assert hasattr(cfg, "github")
        assert hasattr(cfg, "azure_ad")
        assert hasattr(cfg, "okta")
        assert hasattr(cfg, "auth0")
        assert hasattr(cfg, "saml")

    def test_rate_limit_configuration(self):
        """Test RateLimitConfiguration mock."""
        from tests.mocks.configurations.rate_limit import (
            RateLimitConfiguration,
            RateLimitConfig,
        )

        inst = RateLimitConfiguration.instance()
        cfg = inst.get_config()

        assert isinstance(cfg, RateLimitConfig)
        assert cfg.enabled is False
        assert cfg.default_per_minute == 60
        assert cfg.default_burst == 10
        assert cfg.per_tenant_overrides == {}


class TestMockDatastores:
    """Tests for mock datastore classes."""

    def test_mongo_document_store(self):
        """Test MongoDocumentStore mock."""
        from tests.mocks.core.datastores import MongoDocumentStore

        store = MongoDocumentStore(uri="mongodb://test:27017", database="testdb")

        assert store.uri == "mongodb://test:27017"
        assert store.database == "testdb"

        # Test connect/disconnect don't raise
        store.connect()
        db = store.get_database()
        assert db is not None
        store.disconnect()

    def test_cassandra_store(self):
        """Test CassandraWideColumnStore mock."""
        from tests.mocks.core.datastores import CassandraWideColumnStore

        store = CassandraWideColumnStore(
            contact_points=["127.0.0.1", "127.0.0.2"], port=9042, keyspace="test"
        )

        assert store.contact_points == ["127.0.0.1", "127.0.0.2"]
        assert store.port == 9042
        assert store.keyspace == "test"

        # Test methods don't raise
        store.connect()
        result = store.execute("SELECT 1")
        assert result == []
        store.disconnect()

    def test_cosmos_document_store(self):
        """Test CosmosDocumentStore mock."""
        from tests.mocks.core.datastores import CosmosDocumentStore

        store = CosmosDocumentStore(
            account_uri="https://test.documents.azure.com",
            account_key="test-key",
            database="testdb",
        )

        assert store.account_uri == "https://test.documents.azure.com"
        assert store.account_key == "test-key"

        store.connect()
        db = store.get_database()
        store.disconnect()

    def test_dynamo_key_value_store(self):
        """Test DynamoKeyValueStore mock."""
        from tests.mocks.core.datastores import DynamoKeyValueStore

        store = DynamoKeyValueStore(table_name="test-table", region_name="us-west-2")

        assert store.table_name == "test-table"
        assert store.region_name == "us-west-2"

        store.connect()
        store.disconnect()

    def test_elasticsearch_search_store(self):
        """Test ElasticsearchSearchStore mock."""
        from tests.mocks.core.datastores import ElasticsearchSearchStore

        store = ElasticsearchSearchStore(
            hosts=["http://localhost:9200"], username="elastic", password="test"
        )

        assert store.hosts == ["http://localhost:9200"]
        assert store.username == "elastic"

        store.connect()
        assert store.ping() is True
        store.disconnect()

    def test_redis_key_value_store(self):
        """Test RedisKeyValueStore mock."""
        from tests.mocks.core.datastores import RedisKeyValueStore

        health = RedisKeyValueStore.check_health()
        assert health == {"status": "disabled"}

    def test_scylla_wide_column_store(self):
        """Test ScyllaWideColumnStore mock."""
        from tests.mocks.core.datastores import ScyllaWideColumnStore

        store = ScyllaWideColumnStore(
            contact_points=["127.0.0.1"], port=9042, keyspace="test"
        )

        store.connect()
        result = store.execute("SELECT 1")
        assert result == []
        store.disconnect()


class TestMockCoreUtils:
    """Tests for mock core utilities."""

    def test_optional_imports(self):
        """Test OptionalImports utility."""
        from tests.mocks.core.utils.optional_imports import OptionalImports

        # Test importing existing module
        mod, attr = OptionalImports.optional_import("os")
        assert mod is not None
        assert attr is None

        # Test importing existing module with attribute
        mod, path = OptionalImports.optional_import("os", "path")
        assert mod is not None
        assert path is not None

        # Test importing non-existent module
        mod, attr = OptionalImports.optional_import("nonexistent_module_xyz")
        assert mod is None
        assert attr is None

        # Test importing non-existent attribute
        mod, attr = OptionalImports.optional_import("os", "nonexistent_attr_xyz")
        assert mod is not None  # Module exists
        assert attr is None  # Attribute doesn't


class TestMockStartUtils:
    """Tests for mock start_utils."""

    @pytest.mark.asyncio
    async def test_mock_db_session(self):
        """Test MockDBSession context manager."""
        from tests.mocks.start_utils import db_session, MockDBSession

        async with db_session() as session:
            assert isinstance(session, MockDBSession)
            result = await session.execute("SELECT 1")
            assert result is None

    @pytest.mark.asyncio
    async def test_mock_redis_session(self):
        """Test MockRedisSession context manager."""
        from tests.mocks.start_utils import redis_session, MockRedisSession

        async with redis_session() as redis:
            assert isinstance(redis, MockRedisSession)
            assert await redis.ping() is False
            assert await redis.info() == {}


class TestMockTenancy:
    """Tests for mock tenancy module."""

    def test_tenant_dataclass(self):
        """Test Tenant dataclass."""
        from tests.mocks.core.tenancy.context import Tenant

        tenant = Tenant(
            id="test-123", name="Test Tenant", slug="test-tenant", org_id="org-456"
        )

        assert tenant.id == "test-123"
        assert tenant.name == "Test Tenant"
        assert tenant.slug == "test-tenant"
        assert tenant.org_id == "org-456"

    def test_in_memory_tenant_store(self):
        """Test InMemoryTenantStore."""
        from tests.mocks.core.tenancy.context import InMemoryTenantStore

        store = InMemoryTenantStore()
        tenants = store.list_all()

        assert isinstance(tenants, list)
        assert len(tenants) == 0


class TestMockConfigRegistration:
    """Tests that mocks auto-register with registry."""

    def test_all_configs_registered(self):
        """Test that all config mocks are registered."""
        from fast_dashboards.core.registry import registry

        configs = [
            "jobs",
            "queues",
            "workflows",
            "secrets",
            "feature_flags",
            "identity",
            "rate_limit",
        ]

        for name in configs:
            cfg = registry.get_config(name)
            assert cfg is not None, f"Config '{name}' should be registered"
            assert hasattr(cfg, "instance"), (
                f"Config '{name}' should have instance method"
            )

    def test_all_datastores_registered(self):
        """Test that all datastore mocks are registered."""
        from fast_dashboards.core.registry import registry

        datastores = [
            "MongoDocumentStore",
            "CassandraWideColumnStore",
            "CosmosDocumentStore",
            "DynamoKeyValueStore",
            "ElasticsearchSearchStore",
            "RedisKeyValueStore",
            "ScyllaWideColumnStore",
            "PostgresDocumentStore",
        ]

        for name in datastores:
            store = registry.get_datastore(name)
            assert store is not None, f"Datastore '{name}' should be registered"

    def test_config_instances_work(self):
        """Test that registered config instances return valid configs."""
        from fast_dashboards.core.registry import registry

        configs = ["jobs", "queues", "workflows", "secrets"]

        for name in configs:
            cfg_class = registry.get_config(name)
            instance = cfg_class.instance()
            config = instance.get_config()
            assert config is not None, f"Config '{name}' should return valid config"
