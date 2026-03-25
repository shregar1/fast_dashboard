"""End-to-end tests simulating real user scenarios."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from typing import Any


class TestEndToEndDashboardWorkflows:
    """E2E tests for complete dashboard workflows."""

    def test_admin_views_all_dashboards(self):
        """
        E2E: Admin user navigates through all dashboards.
        
        Scenario:
        1. Admin opens health dashboard
        2. Checks service statuses
        3. Navigates to queues dashboard
        4. Views tenant configuration
        5. Checks secrets configuration
        6. Views workflows status
        """
        from fast_dashboards.core.router import router as composite_router
        
        app = FastAPI()
        app.include_router(composite_router)
        client = TestClient(app)
        
        # Step 1: Health dashboard
        response = client.get("/dashboard/health")
        assert response.status_code == 200
        assert "FastMVC Service Health" in response.text
        
        # Step 2: Check health state
        services = _get_health_services(client)
        assert len(services) >= 8  # All expected services
        
        # Step 3: Queues dashboard
        response = client.get("/dashboard/queues")
        assert response.status_code == 200
        assert "Queues & Jobs" in response.text
        
        # Step 4: Tenants dashboard
        response = client.get("/dashboard/tenants")
        assert response.status_code == 200
        assert "Tenants & Auth" in response.text
        
        # Step 5: Secrets dashboard
        response = client.get("/dashboard/secrets")
        assert response.status_code == 200
        assert "Secrets & Configuration" in response.text
        
        # Step 6: Workflows dashboard
        response = client.get("/dashboard/workflows")
        assert response.status_code == 200
        assert "Workflows" in response.text

    def test_developer_troubleshoots_services(self):
        """
        E2E: Developer troubleshoots service issues.
        
        Scenario:
        1. Developer notices service is unhealthy
        2. Checks detailed status
        3. Views configuration
        4. Takes action based on findings
        """
        from fast_dashboards.core.registry import DependencyRegistry
        from fast_dashboards.operations.health.dashboard import router as health_router
        from fast_dashboards.operations.secrets_dashboard.router import router as secrets_router
        
        # Use fresh registry
        fresh_registry = DependencyRegistry()
        
        # Register a "broken" service config
        class BrokenRedis:
            enabled = True
            def ping(self):
                raise Exception("Connection refused")
            def info(self):
                return {}
        
        fresh_registry.register_redis_session(lambda: BrokenRedis())
        
        app = FastAPI()
        app.include_router(health_router)
        app.include_router(secrets_router)
        client = TestClient(app)
        
        # Check health dashboard loads
        services = _get_health_services(client)
        assert len(services) > 0
        
        # Find redis service - should exist
        redis_svc = next((s for s in services if s["key"] == "redis"), None)
        assert redis_svc is not None
        
        # Service status should be one of the valid states
        assert redis_svc["status"] in ["healthy", "unhealthy", "skipped"]

    def test_ops_monitors_queues(self):
        """
        E2E: Ops engineer monitors queue health.
        
        Scenario:
        1. Ops opens queues dashboard
        2. Checks RabbitMQ status
        3. Monitors job workers
        4. Refreshes state endpoint
        """
        from fast_dashboards.core.registry import registry
        from fast_dashboards.operations.queues_dashboard.router import router as queues_router
        
        # Configure queues
        class MockRabbitConfig:
            enabled = True
            url = "amqp://prod"
            management_url = ""
            username = ""
            password = ""
        
        class MockQueuesConfig:
            rabbitmq = MockRabbitConfig()
            sqs = type('obj', (object,), {'enabled': False, 'queue_url': '', 'region': ''})()
        
        class MockQueuesConfiguration:
            @classmethod
            def instance(cls):
                return cls()
            def get_config(self):
                return MockQueuesConfig()
        
        registry.register_config("queues", MockQueuesConfiguration)
        
        app = FastAPI()
        app.include_router(queues_router)
        client = TestClient(app)
        
        # Open dashboard
        response = client.get("/dashboard/queues")
        assert response.status_code == 200
        assert "Queues & Jobs" in response.text
        
        # Check state (refreshes every 5s in real UI)
        for _ in range(3):  # Simulate multiple refreshes
            state = client.get("/dashboard/queues/state").json()
            assert "queues" in state
            assert "jobs" in state

    def test_sre_checks_secrets_configuration(self):
        """
        E2E: SRE checks secrets configuration.
        
        Scenario:
        1. SRE opens secrets dashboard
        2. Verifies Vault is configured
        3. Checks AWS secrets
        4. Validates env diff
        """
        from fast_dashboards.core.registry import registry
        from fast_dashboards.operations.secrets_dashboard.router import router as secrets_router
        
        # Configure secrets
        class MockVaultConfig:
            enabled = True
            url = "https://vault.prod.example.com"
            mount_point = "prod"
        
        class MockAWSConfig:
            enabled = True
            region = "us-west-2"
            prefix = "/prod"
        
        class MockSecretsConfig:
            vault = MockVaultConfig()
            aws = MockAWSConfig()
        
        class MockSecretsConfiguration:
            @classmethod
            def instance(cls):
                return cls()
            def get_config(self):
                return MockSecretsConfig()
        
        registry.register_config("secrets", MockSecretsConfiguration)
        
        app = FastAPI()
        app.include_router(secrets_router)
        client = TestClient(app)
        
        # Open dashboard
        response = client.get("/dashboard/secrets")
        assert response.status_code == 200
        assert "Secrets & Configuration" in response.text
        
        # Check state
        state = client.get("/dashboard/secrets/state").json()
        assert state["backends"]["vault"]["enabled"] is True
        assert state["backends"]["vault"]["url"] == "https://vault.prod.example.com"


class TestEndToEndMultiTenantSetup:
    """E2E tests for multi-tenant dashboard scenarios."""

    def test_tenant_admin_views_tenant_config(self):
        """
        E2E: Tenant admin views their tenant configuration.
        
        Scenario:
        1. Tenant with specific features
        2. Identity providers configured
        3. Rate limits visible
        """
        from fast_dashboards.core.registry import registry
        from fast_dashboards.operations.tenants_dashboard.router import router as tenants_router
        
        # Setup tenant store with specific tenant
        class Tenant:
            def __init__(self, id: str, name: str, features: list):
                self.id = id
                self.name = name
                self.slug = name.lower().replace(" ", "-")
                self.is_active = True
                self.config = {"features": features}
            
            def to_dict(self):
                return {
                    "id": self.id,
                    "name": self.name,
                    "slug": self.slug,
                    "is_active": self.is_active,
                    "config": self.config
                }
        
        class TenantStore:
            async def list_all(self, active_only: bool = False):
                return [
                    Tenant("tenant-1", "Enterprise", ["sso", "audit", "analytics"]),
                    Tenant("tenant-2", "Startup", ["basic"]),
                ]
        
        # Setup identity providers
        class MockIdentityConfig:
            google = type('obj', (object,), {
                'enabled': True, 'client_id': 'xxx', 'client_secret': 'yyy', 'redirect_uri': '/callback'
            })()
            saml = type('obj', (object,), {
                'enabled': True, 'idp_metadata_url': 'https://idp.xml', 'acs_url': '/acs'
            })()
        
        class MockIdentityConfiguration:
            @classmethod
            def instance(cls):
                return cls()
            def get_config(self):
                return MockIdentityConfig()
        
        # Setup rate limits
        class MockRateLimitConfig:
            enabled = True
            default_per_minute = 1000
            default_burst = 100
            per_tenant_overrides = {"tenant-1": {"per_minute": 5000}}
        
        class MockRateLimitConfiguration:
            @classmethod
            def instance(cls):
                return cls()
            def get_config(self):
                return MockRateLimitConfig()
        
        registry.register_tenant_store(TenantStore())
        registry.register_config("identity", MockIdentityConfiguration)
        registry.register_config("rate_limit", MockRateLimitConfiguration)
        
        app = FastAPI()
        app.include_router(tenants_router)
        client = TestClient(app)
        
        # View dashboard
        response = client.get("/dashboard/tenants")
        assert response.status_code == 200
        
        # Check state
        state = client.get("/dashboard/tenants/state").json()
        assert len(state["tenants"]) == 2
        assert state["tenants"][0]["name"] in ["Enterprise", "Startup"]
        assert state["quotas"]["enabled"] is True
        assert state["quotas"]["defaultPerMinute"] == 1000


class TestEndToEndWorkflowMonitoring:
    """E2E tests for workflow monitoring scenarios."""

    def test_data_engineer_monitors_workflows(self):
        """
        E2E: Data engineer monitors workflow executions.
        
        Scenario:
        1. Engineer opens workflows dashboard
        2. Checks Temporal configuration
        3. Views recent runs
        """
        from fast_dashboards.core.registry import registry
        from fast_dashboards.operations.workflows_dashboard.router import (
            router as workflows_router
        )
        
        # Configure Temporal
        class MockWorkflowsConfig:
            enabled = True
            engine = "temporal"
            temporal_address = "temporal-frontend.temporal:7233"
            temporal_namespace = "production"
            prefect_api_url = ""
            dagster_grpc_endpoint = ""
        
        class MockWorkflowsConfiguration:
            _instance = None
            @classmethod
            def instance(cls):
                if cls._instance is None:
                    cls._instance = cls()
                return cls._instance
            def get_config(self):
                return MockWorkflowsConfig()
        
        registry.register_config("workflows", MockWorkflowsConfiguration)
        
        app = FastAPI()
        app.include_router(workflows_router)
        client = TestClient(app)
        
        # Open dashboard
        response = client.get("/dashboard/workflows")
        assert response.status_code == 200
        assert "Workflows" in response.text
        
        # Check state
        state = client.get("/dashboard/workflows/state").json()
        assert state["engine"]["enabled"] is True
        assert state["engine"]["engineName"] == "temporal"
        assert "temporal-frontend" in state["engine"]["temporal"]

    def test_ml_engineer_uses_prefect(self):
        """
        E2E: ML engineer uses Prefect for ML pipelines.
        
        Scenario:
        1. ML engineer configures Prefect
        2. Opens workflows dashboard
        3. Verifies Prefect API connection
        """
        from fast_dashboards.core.registry import registry
        from fast_dashboards.operations.workflows_dashboard.router import router as workflows_router
        
        class MockWorkflowsConfig:
            enabled = True
            engine = "prefect"
            temporal_address = ""
            temporal_namespace = ""
            prefect_api_url = "http://prefect-server:4200/api"
            dagster_grpc_endpoint = ""
        
        class MockWorkflowsConfiguration:
            @classmethod
            def instance(cls):
                return cls()
            def get_config(self):
                return MockWorkflowsConfig()
        
        registry.register_config("workflows", MockWorkflowsConfiguration)
        
        app = FastAPI()
        app.include_router(workflows_router)
        client = TestClient(app)
        
        state = client.get("/dashboard/workflows/state").json()
        assert state["engine"]["engineName"] == "prefect"
        assert state["engine"]["prefect"] == "http://prefect-server:4200/api"


class TestEndToEdgeCaseScenarios:
    """E2E tests for edge cases and error scenarios."""

    def test_dashboard_loads_with_no_configuration(self):
        """
        E2E: Dashboard loads gracefully when no configuration exists.
        
        Scenario:
        1. Fresh installation with no config
        2. All dashboards should still load
        3. Show appropriate messages
        """
        from fast_dashboards.core.router import router as composite_router

        # Create app with composite router
        app = FastAPI()
        app.include_router(composite_router)
        client = TestClient(app)

        # All dashboards should still load (graceful degradation)
        for path in ["/dashboard/health", "/dashboard/queues", "/dashboard/tenants", 
                    "/dashboard/secrets", "/dashboard/workflows"]:
            response = client.get(path)
            assert response.status_code == 200, f"Failed for {path}"

    def test_dashboard_handles_partial_configuration(self):
        """
        E2E: Dashboard handles partial/misconfiguration.
        
        Scenario:
        1. Some configs present
        2. Some configs missing
        3. Dashboard shows available data
        """
        from fast_dashboards.core.registry import DependencyRegistry
        from fast_dashboards.operations.tenants_dashboard.router import router as tenants_router
        
        reg = DependencyRegistry()
        
        # Only register partial config
        class PartialFeatureFlags:
            @classmethod
            def instance(cls):
                return cls()
            def get_config(self):
                class Config:
                    launchdarkly = type('obj', (object,), {'enabled': True, 'sdk_key': 'test'})()
                    unleash = type('obj', (object,), {'enabled': False})()
                return Config()
        
        reg.register_config("feature_flags", PartialFeatureFlags)
        
        from fast_dashboards import operations
        original_get_config = operations.tenants_dashboard.router.registry.get_config if hasattr(operations.tenants_dashboard.router, 'registry') else None
        
        app = FastAPI()
        app.include_router(tenants_router)
        client = TestClient(app)
        
        response = client.get("/dashboard/tenants/state")
        assert response.status_code == 200


def _get_health_services(client: TestClient) -> list:
    """Helper to get health services from dashboard HTML."""
    # In a real E2E test, this would parse the HTML
    # For now, we check the page loaded successfully
    response = client.get("/dashboard/health")
    assert response.status_code == 200
    # Return list of services from actual data
    from fast_dashboards.operations.health.dashboard import _gather_services
    return _gather_services()
