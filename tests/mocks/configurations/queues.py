"""Mock queues configuration - registered with dependency registry."""

from dataclasses import dataclass
from typing import Optional

# Register with registry on module load
try:
    from fast_dashboards.core.registry import registry

    _REGISTRY_AVAILABLE = True
except ImportError:
    _REGISTRY_AVAILABLE = False


@dataclass
class RabbitMQConfig:
    """Represents the RabbitMQConfig class."""

    enabled: bool = False
    url: str = ""
    management_url: str = ""
    username: str = ""
    password: str = ""


@dataclass
class SQSConfig:
    """Represents the SQSConfig class."""

    enabled: bool = False
    queue_url: str = ""
    region: str = ""
    access_key_id: str = ""
    secret_access_key: str = ""


@dataclass
class NATSConfig:
    """Represents the NATSConfig class."""

    enabled: bool = False
    url: str = ""


@dataclass
class QueuesConfig:
    """Represents the QueuesConfig class."""

    rabbitmq: Optional[RabbitMQConfig] = None
    sqs: Optional[SQSConfig] = None
    nats: Optional[NATSConfig] = None

    def __post_init__(self):
        """Execute __post_init__ operation.

        Returns:
            The result of the operation.
        """
        if self.rabbitmq is None:
            self.rabbitmq = RabbitMQConfig()
        if self.sqs is None:
            self.sqs = SQSConfig()
        if self.nats is None:
            self.nats = NATSConfig()


class QueuesConfiguration:
    """Represents the QueuesConfiguration class."""

    _instance: Optional["QueuesConfiguration"] = None

    @classmethod
    def instance(cls) -> "QueuesConfiguration":
        """Execute instance operation.

        Returns:
            The result of the operation.
        """
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def get_config(self) -> QueuesConfig:
        """Execute get_config operation.

        Returns:
            The result of the operation.
        """
        return QueuesConfig()


# Auto-register with dependency registry
if _REGISTRY_AVAILABLE:
    registry.register_config("queues", QueuesConfiguration)
