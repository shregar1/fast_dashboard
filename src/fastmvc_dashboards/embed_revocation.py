"""
Server-side revocation for signed embed URLs that include a ``tid`` (token id) query parameter.

Pair with :func:`fastmvc_dashboards.embed_signing.sign_embed_url` when ``token_id`` is set.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class EmbedRevocationChecker(Protocol):
    """Return ``True`` if *token_id* must no longer be accepted (leaked URL, logout, etc.)."""

    def is_revoked(self, token_id: str) -> bool:
        ...


class InMemoryEmbedRevocationList:
    """Process-local blocklist of ``tid`` values (not shared across workers)."""

    def __init__(self) -> None:
        self._revoked: set[str] = set()

    def revoke(self, token_id: str) -> None:
        """Block future verification for this ``tid``."""
        self._revoked.add(token_id)

    def is_revoked(self, token_id: str) -> bool:
        return token_id in self._revoked
