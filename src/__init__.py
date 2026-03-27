"""fast_dashboards – Dashboards extension for FastMVC.

This package provides dashboard routers for FastMVC applications. Dependencies
on host app modules (configurations, core.datastores, start_utils, etc.) are
resolved at runtime through a dependency registry pattern for loose coupling.

To configure dependencies in your host app::

    from fast_dashboards.core.registry import registry
    from myapp.config import JobsConfiguration
    registry.register_config("jobs", JobsConfiguration)

Layout follows the shared taxonomy: ``core/``, ``integrations/``, ``operations/``, ``sec/``.

Public attributes are loaded on first access so ``import fast_dashboards.core.layout``
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
    """Execute __getattr__ operation.

    Args:
        name: The name parameter.

    Returns:
        The result of the operation.
    """
    if name == "sign_embed_url":
        from .core.embed_signing import sign_embed_url

        return sign_embed_url
    if name == "verify_signed_embed_url":
        from .core.embed_signing import verify_signed_embed_url

        return verify_signed_embed_url
    if name == "EmbedRevocationChecker":
        from .core.embed_revocation import EmbedRevocationChecker

        return EmbedRevocationChecker
    if name == "InMemoryEmbedRevocationList":
        from .core.embed_revocation import InMemoryEmbedRevocationList

        return InMemoryEmbedRevocationList
    if name == "EmbedThemeParams":
        from .core.embed_theme import EmbedThemeParams

        return EmbedThemeParams
    if name == "theme_to_extra_params":
        from .core.embed_theme import theme_to_extra_params

        return theme_to_extra_params
    if name == "DashboardEmbedProvider":
        from .integrations.providers.base import DashboardEmbedProvider

        return DashboardEmbedProvider
    if name == "MetabaseEmbedProvider":
        from .integrations.providers.metabase import MetabaseEmbedProvider

        return MetabaseEmbedProvider
    if name == "GrafanaEmbedProvider":
        from .integrations.providers.grafana import GrafanaEmbedProvider

        return GrafanaEmbedProvider
    if name == "LookerEmbedProvider":
        from .integrations.providers.looker import LookerEmbedProvider

        return LookerEmbedProvider
    if name == "PowerBIEmbedProvider":
        from .integrations.providers.powerbi import PowerBIEmbedProvider

        return PowerBIEmbedProvider
    if name == "ApiDashboardRouter":
        from .operations.api_dashboard import ApiDashboardRouter

        return ApiDashboardRouter
    if name == "EndpointSample":
        from .operations.api_dashboard import EndpointSample

        return EndpointSample
    if name == "register_endpoint_sample":
        from .operations.api_dashboard import register_endpoint_sample

        return register_endpoint_sample
    if name == "DashboardRouter":
        from .core.router import router as DashboardRouter

        return DashboardRouter
    if name == "HealthDashboardRouter":
        from .operations.health import HealthDashboardRouter

        return HealthDashboardRouter
    if name == "QueuesDashboardRouter":
        from .operations.queues_dashboard import QueuesDashboardRouter

        return QueuesDashboardRouter
    if name == "SecretsDashboardRouter":
        from .operations.secrets_dashboard import SecretsDashboardRouter

        return SecretsDashboardRouter
    if name == "TenantsDashboardRouter":
        from .operations.tenants_dashboard import TenantsDashboardRouter

        return TenantsDashboardRouter
    if name == "WorkflowsDashboardRouter":
        from .operations.workflows_dashboard import WorkflowsDashboardRouter

        return WorkflowsDashboardRouter
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
