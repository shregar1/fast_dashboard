"""Mock core.tenancy.context module."""

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class Tenant:
    """Mock Tenant."""

    id: str = ""
    name: str = ""
    slug: str = ""
    org_id: str = ""


class InMemoryTenantStore:
    """Mock in-memory tenant store."""

    def list_all(self) -> List[Dict[str, Any]]:
        """Execute list_all operation.

        Returns:
            The result of the operation.
        """
        return []
