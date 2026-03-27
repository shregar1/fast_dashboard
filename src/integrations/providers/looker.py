"""Looker embed stub — full SSO requires the Looker API (signed embed URLs).

See package README for a high-level integration recipe.
"""


class LookerEmbedProvider:
    """Placeholder :class:`~fast_dashboards.providers.base.DashboardEmbedProvider` implementation.

    Looker does not use a single static JWT like Metabase; use Looker's **Signed Embed** or
    **API** to obtain session URLs. Subclass or replace with your Looker client.
    """

    def build_embed_url(self, *, resource_id: str, ttl_seconds: int) -> str:
        """Execute build_embed_url operation.

        Args:
            resource_id: The resource_id parameter.
            ttl_seconds: The ttl_seconds parameter.

        Returns:
            The result of the operation.
        """
        raise NotImplementedError(
            "Looker embed requires Looker Signed Embed / API; see fast_dashboards README (Looker)."
        )
