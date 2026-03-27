"""Mock feature flags configuration - registered with dependency registry."""

from dataclasses import dataclass, field
from typing import Optional

# Register with registry on module load
try:
    from fast_dashboards.core.registry import registry

    _REGISTRY_AVAILABLE = True
except ImportError:
    _REGISTRY_AVAILABLE = False


@dataclass
class LaunchDarklyConfig:
    """Represents the LaunchDarklyConfig class."""

    enabled: bool = False
    sdk_key: str = ""
    default_user_key: str = ""


@dataclass
class UnleashConfig:
    """Represents the UnleashConfig class."""

    enabled: bool = False
    url: str = ""
    app_name: str = ""
    instance_id: str = ""
    api_key: str = ""


@dataclass
class FeatureFlagsConfig:
    """Represents the FeatureFlagsConfig class."""

    launchdarkly: LaunchDarklyConfig = field(default_factory=LaunchDarklyConfig)
    unleash: UnleashConfig = field(default_factory=UnleashConfig)


class FeatureFlagsConfiguration:
    """Represents the FeatureFlagsConfiguration class."""

    _instance: Optional["FeatureFlagsConfiguration"] = None

    @classmethod
    def instance(cls) -> "FeatureFlagsConfiguration":
        """Execute instance operation.

        Returns:
            The result of the operation.
        """
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def get_config(self) -> FeatureFlagsConfig:
        """Execute get_config operation.

        Returns:
            The result of the operation.
        """
        return FeatureFlagsConfig()


# Auto-register with dependency registry
if _REGISTRY_AVAILABLE:
    registry.register_config("feature_flags", FeatureFlagsConfiguration)
