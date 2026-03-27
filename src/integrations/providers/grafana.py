"""Grafana dashboard URL helper with :mod:`fast_dashboards.embed_signing` for optional signed query params.

Typical pattern: ``/d/{uid}/{slug}`` — ``dashboard_uid`` is the Grafana dashboard UID; ``resource_id``
is the URL slug segment (often short name).

Grafana honors ``theme=dark|light`` (and ``locale`` in some builds) on the query string; these are
signed together with ``exp`` / ``sig`` when passed to :func:`~fast_dashboards.embed_signing.sign_embed_url`.
"""

from __future__ import annotations

from typing import Optional

from fast_dashboards.core.embed_signing import sign_embed_url


class GrafanaEmbedProvider:
    """Build a signed Grafana ``/d/{uid}/{slug}`` URL (``sig`` + ``exp`` query params)."""

    def __init__(
        self, site_url: str, signing_secret: bytes, dashboard_uid: str
    ) -> None:
        """Execute __init__ operation.

        Args:
            site_url: The site_url parameter.
            signing_secret: The signing_secret parameter.
            dashboard_uid: The dashboard_uid parameter.
        """
        self._site = site_url.rstrip("/")
        self._secret = signing_secret
        self._uid = dashboard_uid

    def build_embed_url(
        self,
        *,
        resource_id: str,
        ttl_seconds: int,
        theme: Optional[str] = None,
        locale: Optional[str] = None,
        token_id: Optional[str] = None,
    ) -> str:
        """Execute build_embed_url operation.

        Args:
            resource_id: The resource_id parameter.
            ttl_seconds: The ttl_seconds parameter.
            theme: The theme parameter.
            locale: The locale parameter.
            token_id: The token_id parameter.

        Returns:
            The result of the operation.
        """
        base = f"{self._site}/d/{self._uid}/{resource_id.lstrip('/')}"
        return sign_embed_url(
            base,
            self._secret,
            int(ttl_seconds),
            theme=theme,
            locale=locale,
            token_id=token_id,
        )
