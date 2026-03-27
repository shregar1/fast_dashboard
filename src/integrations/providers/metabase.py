"""`Metabase static embedding <https://www.metabase.com/docs/latest/embedding/static-embedding>`_.

Requires ``PyJWT`` (``pip install PyJWT`` or ``fast_dashboards[metabase]``).
"""

from __future__ import annotations

import time
from typing import Any, Literal, Optional


class MetabaseEmbedProvider:
    """JWT-based embed URLs for Metabase dashboards or questions.

    ``embedding_secret`` is the **Embedding secret** from Metabase Admin → Settings → Embedding.
    """

    def __init__(
        self,
        site_url: str,
        embedding_secret: str,
        *,
        resource_key: str = "dashboard",
    ) -> None:
        """Execute __init__ operation.

        Args:
            site_url: The site_url parameter.
            embedding_secret: The embedding_secret parameter.
            resource_key: The resource_key parameter.
        """
        self._site = site_url.rstrip("/")
        self._secret = embedding_secret
        self._resource_key = resource_key

    def build_embed_url(
        self,
        *,
        resource_id: str,
        ttl_seconds: int,
        params: Optional[dict[str, Any]] = None,
        theme: Optional[Literal["light", "dark"]] = None,
        locale: Optional[str] = None,
    ) -> str:
        """Execute build_embed_url operation.

        Args:
            resource_id: The resource_id parameter.
            ttl_seconds: The ttl_seconds parameter.
            params: The params parameter.
            theme: The theme parameter.
            locale: The locale parameter.

        Returns:
            The result of the operation.
        """
        try:
            import jwt
        except ImportError as exc:  # pragma: no cover - exercised when PyJWT missing
            raise RuntimeError(
                "MetabaseEmbedProvider requires PyJWT. Install: pip install PyJWT"
            ) from exc

        try:
            rid = int(resource_id)
        except ValueError as exc:
            raise ValueError(
                "Metabase resource_id must be a numeric id string"
            ) from exc

        now = int(time.time())
        merged_params: dict[str, Any] = dict(params or {})
        if locale:
            merged_params.setdefault("_locale", locale)
        payload: dict[str, Any] = {
            "resource": {self._resource_key: rid},
            "params": merged_params,
            "exp": now + int(ttl_seconds),
        }
        token = jwt.encode(payload, self._secret, algorithm="HS256")
        if isinstance(token, bytes):
            token = token.decode("utf-8")
        url = f"{self._site}/embed/{self._resource_key}/{token}"
        if theme == "dark":
            url += "#theme=night"
        elif theme == "light":
            url += "#theme=day"
        return url
