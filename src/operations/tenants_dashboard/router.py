"""Tenants, Auth & Feature Flags Dashboard Router with beautiful UI."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, JSONResponse

from fast_dashboards.core.registry import registry
from fast_dashboards.core.seo import render_dashboard_inline_head

router = APIRouter(prefix="/dashboard/tenants", tags=["Tenants Dashboard"])


async def _load_tenants() -> List[Dict[str, Any]]:
    """Load tenants from the registered tenant store."""
    store = registry.get_tenant_store()
    if store is None:
        return []

    try:
        tenants = await store.list_all(active_only=False)
        return [t.to_dict() if hasattr(t, "to_dict") else dict(t) for t in tenants]
    except Exception:
        try:
            tenants = store.list_all()
            return [t.to_dict() if hasattr(t, "to_dict") else dict(t) for t in tenants]
        except Exception:
            return []


def _load_feature_flags() -> Dict[str, Any]:
    """Load feature flags configuration via registry."""
    cfg_class = registry.get_config("feature_flags")
    if cfg_class is None or not hasattr(cfg_class, "instance"):
        return {
            "launchdarkly": {"enabled": False, "mode": "Not configured"},
            "unleash": {"enabled": False, "mode": "Not configured"},
        }

    try:
        cfg = cfg_class.instance().get_config()
        return {
            "launchdarkly": {
                "enabled": getattr(cfg.launchdarkly, "enabled", False),
                "mode": "SDK Active"
                if getattr(cfg.launchdarkly, "sdk_key", None)
                else "SDK Key Missing",
                "userKey": getattr(cfg.launchdarkly, "default_user_key", ""),
                "icon": "🚀",
                "color": "#3b82f6",
            },
            "unleash": {
                "enabled": getattr(cfg.unleash, "enabled", False),
                "mode": "Connected"
                if getattr(cfg.unleash, "api_key", None)
                else "API Key Missing",
                "url": getattr(cfg.unleash, "url", ""),
                "appName": getattr(cfg.unleash, "app_name", ""),
                "icon": "🐆",
                "color": "#8b5cf6",
            },
        }
    except Exception as e:
        return {
            "launchdarkly": {
                "enabled": False,
                "mode": f"Error: {str(e)[:30]}",
                "icon": "🚀",
                "color": "#3b82f6",
            },
            "unleash": {
                "enabled": False,
                "mode": "Error",
                "icon": "🐆",
                "color": "#8b5cf6",
            },
        }


def _load_identity_providers() -> Dict[str, Any]:
    """Load identity providers configuration via registry."""
    cfg_class = registry.get_config("identity")
    if cfg_class is None or not hasattr(cfg_class, "instance"):
        return {}

    try:
        cfg = cfg_class.instance().get_config()
        providers = {}

        idp_configs = {
            "google": ("Google", "🔵", "#ea4335"),
            "github": ("GitHub", "⚫", "#333"),
            "azure_ad": ("Azure AD", "🔷", "#0078d4"),
            "okta": ("Okta", "🟣", "#007dc1"),
            "auth0": ("Auth0", "🟠", "#eb5424"),
            "saml": ("SAML", "🛡️", "#10b981"),
        }

        for key, (name, icon, color) in idp_configs.items():
            provider = getattr(cfg, key, None)
            if provider:
                is_configured = bool(
                    getattr(provider, "client_id", None)
                    or getattr(provider, "idp_metadata_url", None)
                )
                providers[key] = {
                    "name": name,
                    "enabled": getattr(provider, "enabled", False),
                    "configured": is_configured,
                    "redirectUri": getattr(
                        provider, "redirect_uri", getattr(provider, "acs_url", "")
                    ),
                    "icon": icon,
                    "color": color,
                }

        return providers
    except Exception:
        return {}


def _load_quotas() -> Dict[str, Any]:
    """Load rate limit configuration via registry."""
    cfg_class = registry.get_config("rate_limit")
    if cfg_class is None or not hasattr(cfg_class, "instance"):
        return {"enabled": False, "mode": "Not configured"}

    try:
        cfg = cfg_class.instance().get_config()
        return {
            "enabled": getattr(cfg, "enabled", False),
            "defaultPerMinute": getattr(cfg, "default_per_minute", 60),
            "defaultBurst": getattr(cfg, "default_burst", 10),
            "overrides": len(getattr(cfg, "per_tenant_overrides", {})),
        }
    except Exception as e:
        return {"enabled": False, "mode": f"Error: {str(e)[:30]}"}


@router.get("", response_class=HTMLResponse, summary="Tenants & Auth Dashboard")
async def tenants_dashboard() -> HTMLResponse:
    """Render the tenants/auth/feature-flags dashboard page."""
    _head_seo = render_dashboard_inline_head(
        page_title="FastMVC Tenants & Auth Dashboard",
        description="Tenants, identity providers, feature flags, and rate-limit configuration overview.",
        path="/dashboard/tenants",
    )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    {_head_seo}
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg-primary: #0a0a0f;
            --bg-secondary: #12121a;
            --bg-card: #1a1a25;
            --bg-hover: #222230;
            --text-primary: #f8fafc;
            --text-secondary: #94a3b8;
            --text-muted: #64748b;
            --accent-primary: #8b5cf6;
            --accent-secondary: #a855f7;
            --accent-gradient: linear-gradient(135deg, #8b5cf6 0%, #a855f7 100%);
            --success: #10b981;
            --warning: #f59e0b;
            --error: #ef4444;
            --info: #3b82f6;
            --border-color: rgba(148, 163, 184, 0.1);
            --shadow-sm: 0 1px 2px 0 rgba(0, 0, 0, 0.3);
            --shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.4);
            --shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.5);
            --shadow-glow: 0 0 40px rgba(139, 92, 246, 0.15);
        }}
        
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        
        body {{
            font-family: 'Inter', sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            min-height: 100vh;
        }}
        
        .dashboard-container {{
            max-width: 1400px;
            margin: 0 auto;
            padding: 2rem;
        }}
        
        /* Header */
        .header {{
            margin-bottom: 2.5rem;
            position: relative;
        }}
        
        .header::before {{
            content: '';
            position: absolute;
            top: -2rem;
            left: -2rem;
            right: -2rem;
            height: 400px;
            background: radial-gradient(ellipse at top, rgba(139, 92, 246, 0.15) 0%, transparent 70%);
            pointer-events: none;
        }}
        
        .header-content {{ position: relative; z-index: 1; }}
        
        .header-title {{
            font-size: 2.5rem;
            font-weight: 700;
            background: var(--accent-gradient);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 0.5rem;
            display: flex;
            align-items: center;
            gap: 1rem;
        }}
        
        .header-subtitle {{
            color: var(--text-secondary);
            font-size: 1.1rem;
        }}
        
        /* Grid Layout */
        .dashboard-grid {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 1.5rem;
        }}
        
        @media (max-width: 1200px) {{
            .dashboard-grid {{ grid-template-columns: repeat(2, 1fr); }}
        }}
        
        @media (max-width: 768px) {{
            .dashboard-grid {{ grid-template-columns: 1fr; }}
        }}
        
        /* Section Cards */
        .section-card {{
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 20px;
            overflow: hidden;
            display: flex;
            flex-direction: column;
        }}
        
        .section-card.large {{
            grid-column: span 2;
        }}
        
        @media (max-width: 1200px) {{
            .section-card.large {{ grid-column: span 1; }}
        }}
        
        .section-header {{
            padding: 1.5rem;
            border-bottom: 1px solid var(--border-color);
            display: flex;
            align-items: center;
            justify-content: space-between;
        }}
        
        .section-title {{
            display: flex;
            align-items: center;
            gap: 0.75rem;
            font-size: 1.1rem;
            font-weight: 600;
        }}
        
        .section-icon {{
            width: 40px;
            height: 40px;
            border-radius: 12px;
            background: var(--accent-gradient);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.25rem;
        }}
        
        .badge {{
            padding: 0.375rem 0.75rem;
            border-radius: 20px;
            font-size: 0.75rem;
            font-weight: 600;
            background: rgba(139, 92, 246, 0.2);
            color: var(--accent-primary);
        }}
        
        .section-content {{
            padding: 1.5rem;
            flex: 1;
        }}
        
        /* Tenant Cards */
        .tenant-list {{
            display: flex;
            flex-direction: column;
            gap: 1rem;
        }}
        
        .tenant-card {{
            background: var(--bg-secondary);
            border: 1px solid var(--border-color);
            border-radius: 16px;
            padding: 1.25rem;
            transition: all 0.3s ease;
            cursor: pointer;
        }}
        
        .tenant-card:hover {{
            transform: translateY(-2px);
            border-color: rgba(139, 92, 246, 0.3);
            box-shadow: var(--shadow-glow);
        }}
        
        .tenant-header {{
            display: flex;
            align-items: center;
            gap: 1rem;
            margin-bottom: 0.75rem;
        }}
        
        .tenant-avatar {{
            width: 48px;
            height: 48px;
            border-radius: 12px;
            background: var(--accent-gradient);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.25rem;
            font-weight: 700;
        }}
        
        .tenant-info {{ flex: 1; }}
        
        .tenant-name {{
            font-weight: 600;
            font-size: 1rem;
            margin-bottom: 0.25rem;
        }}
        
        .tenant-slug {{
            font-size: 0.75rem;
            color: var(--text-muted);
            font-family: 'Monaco', monospace;
        }}
        
        .tenant-status {{
            width: 10px;
            height: 10px;
            border-radius: 50%;
            background: var(--success);
            box-shadow: 0 0 8px var(--success);
        }}
        
        .tenant-status.inactive {{ background: var(--text-muted); box-shadow: none; }}
        
        .tenant-features {{
            display: flex;
            flex-wrap: wrap;
            gap: 0.5rem;
        }}
        
        .feature-tag {{
            padding: 0.25rem 0.625rem;
            background: var(--bg-card);
            border-radius: 6px;
            font-size: 0.75rem;
            color: var(--text-secondary);
        }}
        
        /* Provider Cards */
        .provider-grid {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 1rem;
        }}
        
        .provider-card {{
            background: var(--bg-secondary);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 1rem;
            transition: all 0.3s ease;
        }}
        
        .provider-card:hover {{
            border-color: rgba(255, 255, 255, 0.1);
        }}
        
        .provider-header {{
            display: flex;
            align-items: center;
            gap: 0.75rem;
            margin-bottom: 0.75rem;
        }}
        
        .provider-icon {{
            font-size: 1.5rem;
        }}
        
        .provider-name {{
            font-weight: 600;
            flex: 1;
        }}
        
        .provider-status {{
            width: 8px;
            height: 8px;
            border-radius: 50%;
        }}
        
        .provider-status.enabled {{ background: var(--success); box-shadow: 0 0 8px var(--success); }}
        .provider-status.disabled {{ background: var(--text-muted); }}
        
        .provider-config {{
            font-size: 0.75rem;
            color: var(--text-muted);
            display: flex;
            align-items: center;
            gap: 0.25rem;
        }}
        
        /* Feature Flag Cards */
        .ff-list {{
            display: flex;
            flex-direction: column;
            gap: 1rem;
        }}
        
        .ff-card {{
            background: var(--bg-secondary);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 1.25rem;
            transition: all 0.3s ease;
        }}
        
        .ff-card:hover {{
            border-color: rgba(59, 130, 246, 0.3);
        }}
        
        .ff-header {{
            display: flex;
            align-items: center;
            gap: 1rem;
            margin-bottom: 0.75rem;
        }}
        
        .ff-icon {{
            font-size: 1.75rem;
        }}
        
        .ff-info {{ flex: 1; }}
        
        .ff-name {{
            font-weight: 600;
            margin-bottom: 0.25rem;
        }}
        
        .ff-mode {{
            font-size: 0.75rem;
            color: var(--text-muted);
        }}
        
        .ff-toggle {{
            width: 48px;
            height: 26px;
            background: var(--bg-card);
            border-radius: 13px;
            position: relative;
            cursor: pointer;
            transition: all 0.3s ease;
        }}
        
        .ff-toggle.active {{ background: var(--success); }}
        
        .ff-toggle::after {{
            content: '';
            position: absolute;
            top: 3px;
            left: 3px;
            width: 20px;
            height: 20px;
            background: white;
            border-radius: 50%;
            transition: transform 0.3s ease;
        }}
        
        .ff-toggle.active::after {{
            transform: translateX(22px);
        }}
        
        /* Rate Limit Card */
        .rl-stats {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 1rem;
            margin-bottom: 1.5rem;
        }}
        
        .rl-stat {{
            background: var(--bg-secondary);
            border-radius: 12px;
            padding: 1rem;
            text-align: center;
        }}
        
        .rl-value {{
            font-size: 2rem;
            font-weight: 700;
            color: var(--accent-primary);
        }}
        
        .rl-label {{
            font-size: 0.75rem;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}
        
        .rl-visual {{
            height: 8px;
            background: var(--bg-secondary);
            border-radius: 4px;
            overflow: hidden;
            margin-top: 1rem;
        }}
        
        .rl-bar {{
            height: 100%;
            background: var(--accent-gradient);
            border-radius: 4px;
            transition: width 0.5s ease;
        }}
        
        /* Empty State */
        .empty-state {{
            text-align: center;
            padding: 3rem 1rem;
            color: var(--text-muted);
        }}
        
        .empty-icon {{
            font-size: 3rem;
            margin-bottom: 1rem;
            opacity: 0.5;
        }}
        
        /* Loading */
        .skeleton {{
            background: linear-gradient(90deg, var(--bg-secondary) 25%, var(--bg-hover) 50%, var(--bg-secondary) 75%);
            background-size: 200% 100%;
            animation: shimmer 1.5s infinite;
            border-radius: 8px;
        }}
        
        @keyframes shimmer {{
            0% {{ background-position: -200% 0; }}
            100% {{ background-position: 200% 0; }}
        }}
    </style>
</head>
<body>
    <div class="dashboard-container">
        <header class="header">
            <div class="header-content">
                <h1 class="header-title">🏢 Tenants & Auth</h1>
                <p class="header-subtitle">Multi-tenant configuration, identity providers, and feature flags</p>
            </div>
        </header>
        
        <div class="dashboard-grid">
            <!-- Tenants Section -->
            <div class="section-card large">
                <div class="section-header">
                    <div class="section-title">
                        <div class="section-icon">🏢</div>
                        Tenants
                    </div>
                    <span class="badge" id="tenant-count">Loading...</span>
                </div>
                <div class="section-content">
                    <div class="tenant-list" id="tenant-list">
                        <div class="skeleton" style="height: 80px; margin-bottom: 1rem;"></div>
                        <div class="skeleton" style="height: 80px;"></div>
                    </div>
                </div>
            </div>
            
            <!-- Identity Providers Section -->
            <div class="section-card">
                <div class="section-header">
                    <div class="section-title">
                        <div class="section-icon">🔐</div>
                        Identity Providers
                    </div>
                </div>
                <div class="section-content">
                    <div class="provider-grid" id="provider-list">
                        <div class="skeleton" style="height: 60px;"></div>
                        <div class="skeleton" style="height: 60px;"></div>
                        <div class="skeleton" style="height: 60px;"></div>
                        <div class="skeleton" style="height: 60px;"></div>
                    </div>
                </div>
            </div>
            
            <!-- Feature Flags Section -->
            <div class="section-card">
                <div class="section-header">
                    <div class="section-title">
                        <div class="section-icon">🚩</div>
                        Feature Flags
                    </div>
                </div>
                <div class="section-content">
                    <div class="ff-list" id="ff-list">
                        <div class="skeleton" style="height: 80px; margin-bottom: 1rem;"></div>
                        <div class="skeleton" style="height: 80px;"></div>
                    </div>
                </div>
            </div>
            
            <!-- Rate Limits Section -->
            <div class="section-card">
                <div class="section-header">
                    <div class="section-title">
                        <div class="section-icon">⏱️</div>
                        Rate Limits
                    </div>
                    <span class="badge" id="rl-status">Loading...</span>
                </div>
                <div class="section-content">
                    <div id="rl-content">
                        <div class="skeleton" style="height: 120px;"></div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <script>
        async function loadState() {{
            try {{
                const res = await fetch(window.location.pathname + '/state');
                const data = await res.json();
                renderTenants(data.tenants || []);
                renderProviders(data.idps || {{}});
                renderFeatureFlags(data.flags || {{}});
                renderRateLimits(data.quotas || {{}});
            }} catch (e) {{
                console.error('Failed to load state:', e);
            }}
        }}
        
        function renderTenants(tenants) {{
            document.getElementById('tenant-count').textContent = `${{tenants.length}} tenants`;
            const container = document.getElementById('tenant-list');
            
            if (!tenants.length) {{
                container.innerHTML = `
                    <div class="empty-state">
                        <div class="empty-icon">🏢</div>
                        <p>No tenants configured</p>
                    </div>
                `;
                return;
            }}
            
            container.innerHTML = tenants.map(t => `
                <div class="tenant-card">
                    <div class="tenant-header">
                        <div class="tenant-avatar">${{t.name?.[0] || 'T'}}</div>
                        <div class="tenant-info">
                            <div class="tenant-name">${{t.name || 'Unknown'}}</div>
                            <div class="tenant-slug">@${{t.slug || t.id}}</div>
                        </div>
                        <div class="tenant-status ${{t.is_active ? '' : 'inactive'}}"></div>
                    </div>
                    <div class="tenant-features">
                        ${{t.config?.features?.map(f => `<span class="feature-tag">${{f}}</span>`).join('') || '<span class="feature-tag">No features</span>'}}
                    </div>
                </div>
            `).join('');
        }}
        
        function renderProviders(providers) {{
            const container = document.getElementById('provider-list');
            const entries = Object.entries(providers);
            
            if (!entries.length) {{
                container.innerHTML = `
                    <div class="empty-state" style="grid-column: span 2;">
                        <div class="empty-icon">🔐</div>
                        <p>No providers configured</p>
                    </div>
                `;
                return;
            }}
            
            container.innerHTML = entries.map(([key, p]) => `
                <div class="provider-card">
                    <div class="provider-header">
                        <span class="provider-icon">${{p.icon}}</span>
                        <span class="provider-name">${{p.name}}</span>
                        <div class="provider-status ${{p.enabled ? 'enabled' : 'disabled'}}"></div>
                    </div>
                    <div class="provider-config">
                        ${{p.configured ? '✓ Configured' : '⚠ Not configured'}}
                    </div>
                </div>
            `).join('');
        }}
        
        function renderFeatureFlags(flags) {{
            const container = document.getElementById('ff-list');
            const entries = Object.entries(flags);
            
            container.innerHTML = entries.map(([key, f]) => `
                <div class="ff-card">
                    <div class="ff-header">
                        <span class="ff-icon">${{f.icon}}</span>
                        <div class="ff-info">
                            <div class="ff-name">${{key.charAt(0).toUpperCase() + key.slice(1)}}</div>
                            <div class="ff-mode">${{f.mode}}</div>
                        </div>
                        <div class="ff-toggle ${{f.enabled ? 'active' : ''}}"></div>
                    </div>
                </div>
            `).join('');
        }}
        
        function renderRateLimits(quotas) {{
            const container = document.getElementById('rl-content');
            document.getElementById('rl-status').textContent = quotas.enabled ? 'Enabled' : 'Disabled';
            
            if (!quotas.enabled) {{
                container.innerHTML = `
                    <div class="empty-state">
                        <div class="empty-icon">⏱️</div>
                        <p>Rate limiting not enabled</p>
                    </div>
                `;
                return;
            }}
            
            container.innerHTML = `
                <div class="rl-stats">
                    <div class="rl-stat">
                        <div class="rl-value">${{quotas.defaultPerMinute}}</div>
                        <div class="rl-label">Requests/min</div>
                    </div>
                    <div class="rl-stat">
                        <div class="rl-value">${{quotas.defaultBurst}}</div>
                        <div class="rl-label">Burst</div>
                    </div>
                </div>
                <div style="display: flex; justify-content: space-between; font-size: 0.75rem; color: var(--text-muted); margin-bottom: 0.5rem;">
                    <span>Custom overrides</span>
                    <span>${{quotas.overrides}} tenants</span>
                </div>
                <div class="rl-visual">
                    <div class="rl-bar" style="width: ${{Math.min((quotas.overrides / 10) * 100, 100)}}%;"></div>
                </div>
            `;
        }}
        
        loadState();
        setInterval(loadState, 8000);
    </script>
</body>
</html>"""
    return HTMLResponse(content=html)


@router.get("/state", response_class=JSONResponse, summary="Tenants/auth state")
async def tenants_state() -> JSONResponse:
    """Execute tenants_state operation.

    Returns:
        The result of the operation.
    """
    tenants = await _load_tenants()
    flags = _load_feature_flags()
    idps = _load_identity_providers()
    quotas = _load_quotas()
    return JSONResponse(
        {"tenants": tenants, "flags": flags, "idps": idps, "quotas": quotas}
    )


__all__ = ["router"]
