"""Mock configurations package - auto-registers with registry on import."""

# Import all mock modules to trigger their registration
from . import jobs, queues, workflows, secrets, feature_flags, identity, rate_limit

__all__ = [
    "jobs",
    "queues",
    "workflows",
    "secrets",
    "feature_flags",
    "identity",
    "rate_limit",
]
