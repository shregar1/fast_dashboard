"""
Looker embed stub — full SSO requires the Looker API (signed embed URLs).

See package README for a high-level integration recipe.
"""


class LookerEmbedProvider:
    """
    Placeholder :class:`~fastmvc_dashboards.providers.base.DashboardEmbedProvider` implementation.

    Looker does not use a single static JWT like Metabase; use Looker's **Signed Embed** or
    **API** to obtain session URLs. Subclass or replace with your Looker client.
    """

    def build_embed_url(self, *, resource_id: str, ttl_seconds: int) -> str:
        raise NotImplementedError(
            "Looker embed requires Looker Signed Embed / API; see fastmvc_dashboards README (Looker)."
        )
