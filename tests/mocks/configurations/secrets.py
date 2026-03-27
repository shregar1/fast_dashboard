"""Mock secrets configuration - registered with dependency registry."""

from dataclasses import dataclass, field
from typing import Optional

# Register with registry on module load
try:
    from fast_dashboards.core.registry import registry

    _REGISTRY_AVAILABLE = True
except ImportError:
    _REGISTRY_AVAILABLE = False


@dataclass
class VaultConfig:
    """Represents the VaultConfig class."""

    enabled: bool = False
    url: str = ""
    mount_point: str = ""


@dataclass
class AWSConfig:
    """Represents the AWSConfig class."""

    enabled: bool = False
    region: str = ""
    prefix: str = ""


@dataclass
class GCPConfig:
    """Represents the GCPConfig class."""

    enabled: bool = False
    project_id: str = ""


@dataclass
class AzureConfig:
    """Represents the AzureConfig class."""

    enabled: bool = False
    vault_url: str = ""


@dataclass
class SecretsConfig:
    """Represents the SecretsConfig class."""

    vault: VaultConfig = field(default_factory=VaultConfig)
    aws: AWSConfig = field(default_factory=AWSConfig)
    gcp: GCPConfig = field(default_factory=GCPConfig)
    azure: AzureConfig = field(default_factory=AzureConfig)


class SecretsConfiguration:
    """Represents the SecretsConfiguration class."""

    _instance: Optional["SecretsConfiguration"] = None

    @classmethod
    def instance(cls) -> "SecretsConfiguration":
        """Execute instance operation.

        Returns:
            The result of the operation.
        """
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def get_config(self) -> SecretsConfig:
        """Execute get_config operation.

        Returns:
            The result of the operation.
        """
        return SecretsConfig()


# Auto-register with dependency registry
if _REGISTRY_AVAILABLE:
    registry.register_config("secrets", SecretsConfiguration)
