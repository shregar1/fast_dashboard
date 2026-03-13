"""
Composite dashboard router.

Nests all dashboard routers (health, API, queues, tenants, secrets, workflows)
under a single router for inclusion in the app.
"""

from __future__ import annotations

from fastapi import APIRouter

from .api_dashboard import ApiDashboardRouter
from .health import HealthDashboardRouter
from .queues_dashboard import QueuesDashboardRouter
from .secrets_dashboard import SecretsDashboardRouter
from .tenants_dashboard import TenantsDashboardRouter
from .workflows_dashboard import WorkflowsDashboardRouter


router = APIRouter()

router.include_router(HealthDashboardRouter)
router.include_router(ApiDashboardRouter)
router.include_router(QueuesDashboardRouter)
router.include_router(TenantsDashboardRouter)
router.include_router(SecretsDashboardRouter)
router.include_router(WorkflowsDashboardRouter)

__all__ = ["router"]
