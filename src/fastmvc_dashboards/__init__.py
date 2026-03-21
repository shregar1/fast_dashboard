"""
fastmvc_dashboards – Dashboards extension for FastMVC.

Requires the host app to provide: configurations.*, core.datastores,
start_utils (db_session, redis_session), core.tenancy, services.secrets,
services.workflows, and related modules. Use within a FastMVC application.

Public attributes are loaded on first access so ``import fastmvc_dashboards.layout``
(and tests of layout helpers) work without the full app stack.
"""

from __future__ import annotations

__version__ = "0.3.0"

__all__ = [
    "ApiDashboardRouter",
    "DashboardEmbedProvider",
    "DashboardRouter",
    "EmbedRevocationChecker",
    "EmbedThemeParams",
    "EndpointSample",
    "GrafanaEmbedProvider",
    "HealthDashboardRouter",
    "InMemoryEmbedRevocationList",
    "LookerEmbedProvider",
    "MetabaseEmbedProvider",
    "PowerBIEmbedProvider",
    "QueuesDashboardRouter",
    "register_endpoint_sample",
    "SecretsDashboardRouter",
    "sign_embed_url",
    "TenantsDashboardRouter",
    "theme_to_extra_params",
    "verify_signed_embed_url",
    "WorkflowsDashboardRouter",
]


def __getattr__(name: str):
    if name == "sign_embed_url":
        from .embed_signing import sign_embed_url

        return sign_embed_url
    if name == "verify_signed_embed_url":
        from .embed_signing import verify_signed_embed_url

        return verify_signed_embed_url
    if name == "EmbedRevocationChecker":
        from .embed_revocation import EmbedRevocationChecker

        return EmbedRevocationChecker
    if name == "InMemoryEmbedRevocationList":
        from .embed_revocation import InMemoryEmbedRevocationList

        return InMemoryEmbedRevocationList
    if name == "EmbedThemeParams":
        from .embed_theme import EmbedThemeParams

        return EmbedThemeParams
    if name == "theme_to_extra_params":
        from .embed_theme import theme_to_extra_params

        return theme_to_extra_params
    if name == "DashboardEmbedProvider":
        from .providers.base import DashboardEmbedProvider

        return DashboardEmbedProvider
    if name == "MetabaseEmbedProvider":
        from .providers.metabase import MetabaseEmbedProvider

        return MetabaseEmbedProvider
    if name == "GrafanaEmbedProvider":
        from .providers.grafana import GrafanaEmbedProvider

        return GrafanaEmbedProvider
    if name == "LookerEmbedProvider":
        from .providers.looker import LookerEmbedProvider

        return LookerEmbedProvider
    if name == "PowerBIEmbedProvider":
        from .providers.powerbi import PowerBIEmbedProvider

        return PowerBIEmbedProvider
    if name == "ApiDashboardRouter":
        from .api_dashboard import ApiDashboardRouter

        return ApiDashboardRouter
    if name == "EndpointSample":
        from .api_dashboard import EndpointSample

        return EndpointSample
    if name == "register_endpoint_sample":
        from .api_dashboard import register_endpoint_sample

        return register_endpoint_sample
    if name == "DashboardRouter":
        from .router import router as DashboardRouter

        return DashboardRouter
    if name == "HealthDashboardRouter":
        from .health import HealthDashboardRouter

        return HealthDashboardRouter
    if name == "QueuesDashboardRouter":
        from .queues_dashboard import QueuesDashboardRouter

        return QueuesDashboardRouter
    if name == "SecretsDashboardRouter":
        from .secrets_dashboard import SecretsDashboardRouter

        return SecretsDashboardRouter
    if name == "TenantsDashboardRouter":
        from .tenants_dashboard import TenantsDashboardRouter

        return TenantsDashboardRouter
    if name == "WorkflowsDashboardRouter":
        from .workflows_dashboard import WorkflowsDashboardRouter

        return WorkflowsDashboardRouter
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
