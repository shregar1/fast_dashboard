"""Tests for dashboard router and layout."""


def test_layout_base_css():
    """Execute test_layout_base_css operation.

    Returns:
        The result of the operation.
    """
    from fast_dashboards.core.layout import BASE_CSS

    assert "--bg:" in BASE_CSS
    assert "var(--text)" in BASE_CSS


def test_render_dashboard_page():
    """Execute test_render_dashboard_page operation.

    Returns:
        The result of the operation.
    """
    from fast_dashboards.core.layout import render_dashboard_page

    html = render_dashboard_page(
        title="Test",
        subtitle="Sub",
        body_html="<p>Hi</p>",
        accent_color="#22c55e",
    )
    assert "Test" in html
    assert "Sub" in html
    assert "<p>Hi</p>" in html
    assert 'property="og:title"' in html
    assert "noindex" in html
    assert "application/ld+json" in html


def test_render_dashboard_page_invalid_accent_hex():
    """Execute test_render_dashboard_page_invalid_accent_hex operation.

    Returns:
        The result of the operation.
    """
    from fast_dashboards.core.layout import render_dashboard_page

    html = render_dashboard_page(
        title="T",
        subtitle="S",
        body_html="",
        accent_color="#gggggg",
    )
    assert "T" in html
