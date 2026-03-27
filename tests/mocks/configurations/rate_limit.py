"""Mock rate limit configuration - registered with dependency registry."""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional

# Register with registry on module load
try:
    from fast_dashboards.core.registry import registry

    _REGISTRY_AVAILABLE = True
except ImportError:
    _REGISTRY_AVAILABLE = False


@dataclass
class RateLimitConfig:
    """Represents the RateLimitConfig class."""

    enabled: bool = False
    default_per_minute: int = 60
    default_burst: int = 10
    per_tenant_overrides: Dict[str, Any] = field(default_factory=dict)


class RateLimitConfiguration:
    """Represents the RateLimitConfiguration class."""

    _instance: Optional["RateLimitConfiguration"] = None

    @classmethod
    def instance(cls) -> "RateLimitConfiguration":
        """Execute instance operation.

        Returns:
            The result of the operation.
        """
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def get_config(self) -> RateLimitConfig:
        """Execute get_config operation.

        Returns:
            The result of the operation.
        """
        return RateLimitConfig()


# Auto-register with dependency registry
if _REGISTRY_AVAILABLE:
    registry.register_config("rate_limit", RateLimitConfiguration)
