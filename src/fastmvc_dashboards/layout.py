"""
Shared layout helpers for FastMVC HTML dashboards.

Provides a common shell (HTML, body, base CSS) so individual dashboards
only define their inner grid/cards and page-specific JavaScript.
"""

from __future__ import annotations

from typing import Optional


BASE_CSS = """
      :root {
        --bg: #020617;
        --bg-card: #020617;
        --bg-card-alt: #0b1120;
        --accent: ACCENT_COLOR;
        --accent-soft: ACCENT_SOFT;
        --danger: #ef4444;
        --muted: #6b7280;
        --text: #e5e7eb;
        --text-soft: #9ca3af;
        --radius-xl: 16px;
        --shadow: 0 18px 45px rgba(15, 23, 42, 0.85);
      }

      * { box-sizing: border-box; }

      body {
        margin: 0;
        min-height: 100vh;
        font-family: system-ui, -apple-system, BlinkMacSystemFont, "SF Pro Text",
          "Segoe UI", sans-serif;
        background: radial-gradient(circle at top, #1f2937 0, #020617 45%, #000 100%);
        color: var(--text);
        display: flex;
        align-items: stretch;
        justify-content: center;
        padding: 32px 16px;
      }

      .shell {
        width: 100%;
        max-width: 1160px;
        background: linear-gradient(140deg, ACCENT_GRADIENT, rgba(15, 23, 42, 0.95));
        border-radius: 24px;
        padding: 1px;
        box-shadow: var(--shadow);
      }

      .content {
        border-radius: 24px;
        background: radial-gradient(circle at top left, ACCENT_BG_GRADIENT, #020617 55%);
        padding: 22px 24px 24px;
      }

      .header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 16px;
        margin-bottom: 18px;
      }

      .header-main {
        display: flex;
        flex-direction: column;
        gap: 6px;
      }

      .title {
        font-size: 1.5rem;
        font-weight: 650;
        letter-spacing: 0.03em;
        display: flex;
        align-items: center;
        gap: 10px;
      }

      .subtitle {
        font-size: 0.9rem;
        color: var(--text-soft);
      }

      .badge {
        padding: 2px 9px;
        border-radius: 999px;
        font-size: 0.7rem;
        text-transform: uppercase;
        letter-spacing: 0.09em;
        background: var(--accent-soft);
        border: 1px solid ACCENT_BORDER;
        color: var(--accent);
      }

      .card {
        border-radius: var(--radius-xl);
        background: linear-gradient(165deg, var(--bg-card-alt), var(--bg-card));
        border: 1px solid rgba(148, 163, 184, 0.4);
        padding: 12px 12px 10px;
        box-shadow: 0 14px 28px rgba(15, 23, 42, 0.9);
        min-height: 220px;
      }

      .card-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 8px;
      }

      .card-title {
        font-size: 0.9rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.08em;
      }

      .pill {
        padding: 3px 10px;
        border-radius: 999px;
        font-size: 0.7rem;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        background: rgba(15, 23, 42, 0.85);
        border: 1px solid rgba(148, 163, 184, 0.5);
        color: var(--text-soft);
      }

      .list {
        max-height: 360px;
        overflow-y: auto;
        padding-right: 4px;
      }
"""


def render_dashboard_page(
    *,
    title: str,
    subtitle: str,
    body_html: str,
    accent_color: str,
    accent_gradient: Optional[str] = None,
    accent_bg_gradient: Optional[str] = None,
    accent_border: Optional[str] = None,
) -> str:
    """
    Compose a full HTML page for a dashboard using the shared layout.
    """

    accent_gradient = accent_gradient or "rgba(ACCENT_R, ACCENT_G, ACCENT_B, 0.4)"
    accent_bg_gradient = accent_bg_gradient or "rgba(ACCENT_R, ACCENT_G, ACCENT_B, 0.24)"
    accent_border = accent_border or "rgba(ACCENT_R, ACCENT_G, ACCENT_B, 0.5)"

    # Convert hex accent (e.g. #22c55e) to RGB for gradients; fallback to a generic teal.
    accent_hex = accent_color.lstrip("#")
    try:
        r = int(accent_hex[0:2], 16)
        g = int(accent_hex[2:4], 16)
        b = int(accent_hex[4:6], 16)
    except Exception:
        r, g, b = 45, 212, 191

    css = (
        BASE_CSS.replace("ACCENT_COLOR", accent_color)
        .replace("ACCENT_SOFT", f"rgba({r}, {g}, {b}, 0.12)")
        .replace("ACCENT_GRADIENT", accent_gradient.replace("ACCENT_R", str(r)).replace("ACCENT_G", str(g)).replace("ACCENT_B", str(b)))
        .replace("ACCENT_BG_GRADIENT", accent_bg_gradient.replace("ACCENT_R", str(r)).replace("ACCENT_G", str(g)).replace("ACCENT_B", str(b)))
        .replace("ACCENT_BORDER", accent_border.replace("ACCENT_R", str(r)).replace("ACCENT_G", str(g)).replace("ACCENT_B", str(b)))
    )

    html = f"""
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <title>{title}</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <style>
{css}
    </style>
  </head>
  <body>
    <div class="shell">
      <div class="content">
        <div class="header">
          <div class="header-main">
            <div class="title">
              {title}
            </div>
            <div class="subtitle">
              {subtitle}
            </div>
          </div>
        </div>
        {body_html}
      </div>
    </div>
  </body>
</html>
"""
    return html


__all__ = ["render_dashboard_page"]

