"""Tests for production SEO head generation."""

import os


def test_render_seo_head_includes_og_and_robots():
    """Execute test_render_seo_head_includes_og_and_robots operation.

    Returns:
        The result of the operation.
    """
    from fast_dashboards.core.seo import PageSEO, render_seo_head

    seo = PageSEO(
        title="T",
        description="D" * 20,
        path="/x",
        robots="index, follow",
    )
    html = render_seo_head(seo)
    assert 'property="og:title"' in html
    assert 'property="og:description"' in html
    assert 'name="twitter:card"' in html
    assert "index, follow" in html
    assert "application/ld+json" in html


def test_canonical_from_env(monkeypatch):
    """Execute test_canonical_from_env operation.

    Args:
        monkeypatch: The monkeypatch parameter.

    Returns:
        The result of the operation.
    """
    from fast_dashboards.core.seo import default_dashboard_seo, render_seo_head

    monkeypatch.setenv("FASTMVC_PUBLIC_BASE_URL", "https://app.example.com")
    seo = default_dashboard_seo("Page", "Desc", path="/dashboard/queues")
    out = render_seo_head(seo)
    assert "https://app.example.com/dashboard/queues" in out
    assert 'rel="canonical"' in out


def test_robots_txt_helpers():
    """Execute test_robots_txt_helpers operation.

    Returns:
        The result of the operation.
    """
    from fast_dashboards.core.seo import (
        robots_txt_private_dashboards,
        robots_txt_public_site,
    )

    assert "Disallow: /" in robots_txt_private_dashboards()
    assert "Allow: /" in robots_txt_public_site()
    assert "Sitemap: https://x/sitemap.xml" in robots_txt_public_site(
        sitemap_url="https://x/sitemap.xml"
    )
