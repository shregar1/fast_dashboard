"""
API Dashboard Registry.

Holds metadata and sample payloads for APIs so that the
API dashboard can show and exercise them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional


HttpMethod = Literal["GET", "POST", "PUT", "PATCH", "DELETE"]


@dataclass
class EndpointSample:
    """
    Describes a single API endpoint and a sample request.
    """

    key: str
    name: str
    method: HttpMethod
    path: str
    description: str = ""
    sample_request: Optional[Dict[str, Any]] = None
    sample_query: Dict[str, str] = field(default_factory=dict)
    sample_headers: Dict[str, str] = field(default_factory=dict)
    enabled: bool = True


_registry: Dict[str, EndpointSample] = {}


def register_endpoint_sample(
    key: str,
    name: str,
    method: HttpMethod,
    path: str,
    description: str = "",
    sample_request: Optional[Dict[str, Any]] = None,
    sample_query: Optional[Dict[str, str]] = None,
    sample_headers: Optional[Dict[str, str]] = None,
    enabled: bool = True,
) -> None:
    """
    Register (or update) an endpoint sample in the in-memory registry.

    Typical usage in a controller module:

        from core.api_dashboard import register_endpoint_sample

        register_endpoint_sample(
            key="user_login",
            name="User Login",
            method="POST",
            path="/user/login",
            description="Authenticate a user and issue JWT.",
            sample_request={"username": "demo@example.com", "password": "secret"},
        )
    """
    _registry[key] = EndpointSample(
        key=key,
        name=name,
        method=method,
        path=path,
        description=description,
        sample_request=sample_request,
        sample_query=sample_query or {},
        sample_headers=sample_headers or {},
        enabled=enabled,
    )


def list_endpoint_samples() -> List[EndpointSample]:
    """Return all registered endpoint samples."""
    return list(_registry.values())


def get_endpoint_sample(key: str) -> Optional[EndpointSample]:
    """Return a single endpoint sample by key, if present."""
    return _registry.get(key)

