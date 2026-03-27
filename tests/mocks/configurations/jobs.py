"""Mock jobs configuration - registered with dependency registry."""

from dataclasses import dataclass
from typing import Any, Optional

# Register with registry on module load
try:
    from fast_dashboards.core.registry import registry

    _REGISTRY_AVAILABLE = True
except ImportError:
    _REGISTRY_AVAILABLE = False


@dataclass
class CeleryConfig:
    """Represents the CeleryConfig class."""

    enabled: bool = False
    namespace: str = "celery"
    broker_url: str = ""
    result_backend: str = ""


@dataclass
class RQConfig:
    """Represents the RQConfig class."""

    enabled: bool = False
    redis_url: str = ""
    queue_name: str = "default"


@dataclass
class DramatiqConfig:
    """Represents the DramatiqConfig class."""

    enabled: bool = False


@dataclass
class JobsConfig:
    """Represents the JobsConfig class."""

    celery: Optional[CeleryConfig] = None
    rq: Optional[RQConfig] = None
    dramatiq: Optional[DramatiqConfig] = None

    def __post_init__(self):
        """Execute __post_init__ operation.

        Returns:
            The result of the operation.
        """
        if self.celery is None:
            self.celery = CeleryConfig()
        if self.rq is None:
            self.rq = RQConfig()
        if self.dramatiq is None:
            self.dramatiq = DramatiqConfig()


class JobsConfiguration:
    """Represents the JobsConfiguration class."""

    _instance: Optional["JobsConfiguration"] = None

    @classmethod
    def instance(cls) -> "JobsConfiguration":
        """Execute instance operation.

        Returns:
            The result of the operation.
        """
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def get_config(self) -> JobsConfig:
        """Execute get_config operation.

        Returns:
            The result of the operation.
        """
        return JobsConfig()


# Auto-register with dependency registry
if _REGISTRY_AVAILABLE:
    registry.register_config("jobs", JobsConfiguration)
