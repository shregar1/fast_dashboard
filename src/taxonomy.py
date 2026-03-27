"""Section layout for :mod:`fast_dashboards` (aligned with ``fast_platform.taxonomy``).

- **core** — embed signing/revocation/theme, layout, composite router
- **integrations** — BI embed providers (Metabase, Grafana, …)
- **operations** — dashboard routers (API, health, queues, tenants, secrets UI, workflows)
- **sec** — secrets backend helpers for the secrets dashboard
"""

from __future__ import annotations

from enum import Enum
from typing import Final

__all__ = ["DashboardSection", "SECTION_SUBPACKAGES"]


class DashboardSection(str, Enum):
    """Represents the DashboardSection class."""

    CORE = "core"
    INTEGRATIONS = "integrations"
    OPERATIONS = "operations"
    SECURITY = "sec"


SECTION_SUBPACKAGES: Final[dict[DashboardSection, tuple[str, ...]]] = {
    DashboardSection.CORE: (),
    DashboardSection.INTEGRATIONS: ("providers",),
    DashboardSection.OPERATIONS: (
        "api_dashboard",
        "health",
        "queues_dashboard",
        "secrets_dashboard",
        "tenants_dashboard",
        "workflows",
        "workflows_dashboard",
    ),
    DashboardSection.SECURITY: ("secrets",),
}
