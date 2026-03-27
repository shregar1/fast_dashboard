"""Mock workflows configuration - registered with dependency registry."""

from dataclasses import dataclass
from typing import Optional

# Register with registry on module load
try:
    from fast_dashboards.core.registry import registry

    _REGISTRY_AVAILABLE = True
except ImportError:
    _REGISTRY_AVAILABLE = False


@dataclass
class WorkflowsConfig:
    """Represents the WorkflowsConfig class."""

    enabled: bool = False
    engine: str = ""
    temporal_address: str = ""
    temporal_namespace: str = ""
    prefect_api_url: str = ""
    dagster_grpc_endpoint: str = ""


class WorkflowsConfiguration:
    """Represents the WorkflowsConfiguration class."""

    _instance: Optional["WorkflowsConfiguration"] = None

    @classmethod
    def instance(cls) -> "WorkflowsConfiguration":
        """Execute instance operation.

        Returns:
            The result of the operation.
        """
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def get_config(self) -> WorkflowsConfig:
        """Execute get_config operation.

        Returns:
            The result of the operation.
        """
        return WorkflowsConfig()


# Auto-register with dependency registry
if _REGISTRY_AVAILABLE:
    registry.register_config("workflows", WorkflowsConfiguration)
