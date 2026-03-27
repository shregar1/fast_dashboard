"""Power BI embed stub — embed tokens are minted via Azure / Power BI REST APIs.

See package README for a docs-only recipe.
"""


class PowerBIEmbedProvider:
    """Placeholder :class:`~fast_dashboards.providers.base.DashboardEmbedProvider` implementation.

    Power BI uses **GenerateToken** in the Power BI REST API; there is no static site secret
    analogous to Metabase's embedding secret in this package.
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
            "Power BI requires GenerateToken via REST API; see fast_dashboards README (Power BI)."
        )
