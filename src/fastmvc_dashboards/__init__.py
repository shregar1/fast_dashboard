"""
fastmvc_dashboards – Dashboards extension for FastMVC.

Requires the host app to provide: configurations.*, core.datastores,
start_utils (db_session, redis_session), core.tenancy, services.secrets,
services.workflows, and related modules. Use within a FastMVC application.
"""

from __future__ import annotations

from .api_dashboard import ApiDashboardRouter, EndpointSample, register_endpoint_sample
from .router import router as DashboardRouter
from .health import HealthDashboardRouter
from .queues_dashboard import QueuesDashboardRouter
from .secrets_dashboard import SecretsDashboardRouter
from .tenants_dashboard import TenantsDashboardRouter
from .workflows_dashboard import WorkflowsDashboardRouter

__all__ = [
    "ApiDashboardRouter",
    "DashboardRouter",
    "EndpointSample",
    "HealthDashboardRouter",
    "QueuesDashboardRouter",
    "register_endpoint_sample",
    "SecretsDashboardRouter",
    "TenantsDashboardRouter",
    "WorkflowsDashboardRouter",
]
