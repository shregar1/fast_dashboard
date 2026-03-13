"""
Tenants, Auth & Feature Flags Dashboard Router.

Provides a dashboard at `/dashboard/tenants` that surfaces:
- Tenants & orgs (from in-memory tenant store as a reference)
- Feature flag provider configuration (LaunchDarkly / Unleash)
- Identity provider configuration (Google, GitHub, Azure AD, Okta, Auth0, SAML)

Metrics like per-tenant traffic or login counts can be wired in later
via analytics/event tracking; this dashboard focuses on configuration
and basic status visibility.
"""

from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, JSONResponse

from configurations.feature_flags import FeatureFlagsConfiguration
from configurations.identity import IdentityProvidersConfiguration
from configurations.rate_limit import RateLimitConfiguration
from core.tenancy.context import InMemoryTenantStore, Tenant


router = APIRouter(prefix="/dashboard/tenants", tags=["Tenants Dashboard"])


async def _load_tenants() -> List[Dict[str, Any]]:
    """
    Load tenants from the in-memory store.

    In production, replace this with a concrete TenantStore that reads
    from your database.
    """

    store = InMemoryTenantStore()
    tenants = await store.list_all(active_only=False)
    return [t.to_dict() for t in tenants]


def _load_feature_flags() -> Dict[str, Any]:
    cfg = FeatureFlagsConfiguration.instance().get_config()
    return {
        "launchdarkly": {
            "enabled": cfg.launchdarkly.enabled,
            "defaultUserKey": cfg.launchdarkly.default_user_key,
            "hasSdkKey": bool(cfg.launchdarkly.sdk_key),
        },
        "unleash": {
            "enabled": cfg.unleash.enabled,
            "url": cfg.unleash.url,
            "appName": cfg.unleash.app_name,
            "instanceId": cfg.unleash.instance_id,
            "hasApiKey": bool(cfg.unleash.api_key),
        },
    }


def _load_identity_providers() -> Dict[str, Any]:
    cfg = IdentityProvidersConfiguration.instance().get_config()
    providers: Dict[str, Any] = {}
    providers["google"] = {
        "enabled": cfg.google.enabled,
        "redirectUri": cfg.google.redirect_uri,
        "hasClient": bool(cfg.google.client_id and cfg.google.client_secret),
    }
    providers["github"] = {
        "enabled": cfg.github.enabled,
        "redirectUri": cfg.github.redirect_uri,
        "hasClient": bool(cfg.github.client_id and cfg.github.client_secret),
    }
    providers["azure_ad"] = {
        "enabled": cfg.azure_ad.enabled,
        "redirectUri": cfg.azure_ad.redirect_uri,
        "hasClient": bool(cfg.azure_ad.client_id and cfg.azure_ad.client_secret),
    }
    providers["okta"] = {
        "enabled": cfg.okta.enabled,
        "redirectUri": cfg.okta.redirect_uri,
        "hasClient": bool(cfg.okta.client_id and cfg.okta.client_secret),
    }
    providers["auth0"] = {
        "enabled": cfg.auth0.enabled,
        "redirectUri": cfg.auth0.redirect_uri,
        "hasClient": bool(cfg.auth0.client_id and cfg.auth0.client_secret),
    }
    providers["saml"] = {
        "enabled": cfg.saml.enabled,
        "idpMetadataUrl": cfg.saml.idp_metadata_url,
        "acsUrl": cfg.saml.acs_url,
    }
    return providers


def _load_quotas() -> Dict[str, Any]:
    cfg = RateLimitConfiguration.instance().get_config()
    return {
        "enabled": cfg.enabled,
        "defaultPerMinute": cfg.default_per_minute,
        "defaultBurst": cfg.default_burst,
        "overrides": cfg.per_tenant_overrides,
    }


@router.get("", response_class=HTMLResponse, summary="Tenants & Auth Dashboard")
async def tenants_dashboard() -> HTMLResponse:
    """
    Render the tenants/auth/feature-flags dashboard page.
    """
    html = """
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <title>FastMVC Tenants & Auth Dashboard</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <style>
      :root {
        --bg: #020617;
        --bg-card: #020617;
        --bg-card-alt: #0b1120;
        --accent: #38bdf8;
        --accent-soft: rgba(56, 189, 248, 0.12);
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
        background: radial-gradient(circle at top, #1e293b 0, #020617 45%, #000 100%);
        color: var(--text);
        display: flex;
        align-items: stretch;
        justify-content: center;
        padding: 32px 16px;
      }

      .shell {
        width: 100%;
        max-width: 1160px;
        background: linear-gradient(140deg, rgba(56, 189, 248, 0.4), rgba(15, 23, 42, 0.95));
        border-radius: 24px;
        padding: 1px;
        box-shadow: var(--shadow);
      }

      .content {
        border-radius: 24px;
        background: radial-gradient(circle at top left, rgba(37, 99, 235, 0.24), #020617 55%);
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
        font-size: 0.92rem;
        color: var(--text-soft);
      }

      .badge {
        padding: 2px 9px;
        border-radius: 999px;
        font-size: 0.7rem;
        text-transform: uppercase;
        letter-spacing: 0.09em;
        background: var(--accent-soft);
        border: 1px solid rgba(56, 189, 248, 0.5);
        color: var(--accent);
      }

      .grid {
        display: grid;
        grid-template-columns: minmax(0, 2.2fr) minmax(0, 2.2fr) minmax(0, 2.2fr);
        gap: 16px;
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

      .row {
        padding: 7px 8px;
        border-radius: 14px;
        margin-bottom: 4px;
        background: rgba(15, 23, 42, 0.7);
        border: 1px solid rgba(31, 41, 55, 0.9);
        font-size: 0.8rem;
      }

      .row-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 4px;
      }

      .row-title {
        font-weight: 500;
      }

      .row-meta {
        font-size: 0.74rem;
        color: var(--text-soft);
      }

      .chips {
        display: flex;
        flex-wrap: wrap;
        gap: 4px;
        margin-top: 4px;
      }

      .chip {
        padding: 2px 7px;
        border-radius: 999px;
        background: rgba(15, 23, 42, 0.9);
        border: 1px solid rgba(55, 65, 81, 0.9);
        font-size: 0.7rem;
      }

      .status-dot {
        width: 7px;
        height: 7px;
        border-radius: 999px;
        margin-right: 6px;
        display: inline-block;
        background: #22c55e;
      }
    </style>
  </head>
  <body>
    <div class="shell">
      <div class="content">
        <div class="header">
          <div class="header-main">
            <div class="title">
              Tenants & Auth
              <span class="badge">Configuration overview</span>
            </div>
            <div class="subtitle">
              See tenants, feature flag providers, and identity providers configured for this FastMVC instance.
            </div>
          </div>
        </div>
        <div class="grid">
          <div class="card">
            <div class="card-header">
              <div class="card-title">Tenants</div>
              <div class="pill" id="tenants-summary">Loading…</div>
            </div>
            <div class="list" id="tenants-list"></div>
          </div>
          <div class="card">
            <div class="card-header">
              <div class="card-title">Feature Flags</div>
              <div class="pill" id="flags-summary">Loading…</div>
            </div>
            <div class="list" id="flags-list"></div>
          </div>
          <div class="card">
            <div class="card-header">
              <div class="card-title">Identity Providers</div>
              <div class="pill" id="idp-summary">Loading…</div>
            </div>
            <div class="list" id="idp-list"></div>
          </div>
        </div>
      </div>
    </div>
    <script>
      async function loadState() {
        try {
          const res = await fetch(window.location.pathname + "/state");
          const data = await res.json();
          renderTenants(data.tenants || []);
          renderFlags(data.flags || {});
          renderIdps(data.idps || {});
        } catch (e) {
          console.error(e);
        }
      }

      function renderTenants(tenants) {
        const el = document.getElementById("tenants-list");
        const summary = document.getElementById("tenants-summary");
        el.innerHTML = "";
        if (!tenants.length) {
          el.innerHTML = "<div class='row-meta'>No tenants in the in-memory store. Wire your own TenantStore for production.</div>";
          summary.textContent = "0 tenants";
          return;
        }
        tenants.forEach((t) => {
          const row = document.createElement("div");
          row.className = "row";
          const header = document.createElement("div");
          header.className = "row-header";
          header.innerHTML =
            "<div class='row-title'><span class='status-dot'></span>" +
            (t.name || t.id) +
            "</div><div class='row-meta'>" +
            (t.slug || "") +
            "</div>";
          const meta = document.createElement("div");
          meta.className = "row-meta";
          meta.textContent =
            "Active: " + (t.is_active ? "yes" : "no") + " · Features: " + (t.config?.features?.length || 0);
          const chips = document.createElement("div");
          chips.className = "chips";
          (t.config?.features || []).forEach((f) => {
            const chip = document.createElement("span");
            chip.className = "chip";
            chip.textContent = f;
            chips.appendChild(chip);
          });
          row.appendChild(header);
          row.appendChild(meta);
          row.appendChild(chips);
          el.appendChild(row);
        });
        summary.textContent = tenants.length + " tenants";
      }

      function renderFlags(flags) {
        const el = document.getElementById("flags-list");
        const summary = document.getElementById("flags-summary");
        el.innerHTML = "";
        const providers = Object.entries(flags);
        if (!providers.length) {
          el.innerHTML = "<div class='row-meta'>No feature flag providers configured.</div>";
          summary.textContent = "0 providers";
          return;
        }
        let enabledCount = 0;
        providers.forEach(([name, info]) => {
          if (info.enabled) enabledCount++;
          const row = document.createElement("div");
          row.className = "row";
          const header = document.createElement("div");
          header.className = "row-header";
          header.innerHTML =
            "<div class='row-title'>" +
            name +
            "</div><div class='row-meta'>" +
            (info.enabled ? "enabled" : "disabled") +
            "</div>";
          const meta = document.createElement("div");
          meta.className = "row-meta";
          if (name === "launchdarkly") {
            meta.textContent =
              "Default user key: " + (info.defaultUserKey || "n/a") + " · SDK key: " + (info.hasSdkKey ? "set" : "not set");
          } else if (name === "unleash") {
            meta.textContent =
              (info.url || "") +
              " · app=" +
              (info.appName || "") +
              " · instance=" +
              (info.instanceId || "") +
              " · API key: " +
              (info.hasApiKey ? "set" : "not set");
          }
          row.appendChild(header);
          row.appendChild(meta);
          el.appendChild(row);
        });
        summary.textContent = providers.length + " providers · " + enabledCount + " enabled";
      }

      function renderIdps(idps) {
        const el = document.getElementById("idp-list");
        const summary = document.getElementById("idp-summary");
        el.innerHTML = "";
        const providers = Object.entries(idps);
        if (!providers.length) {
          el.innerHTML = "<div class='row-meta'>No identity providers configured.</div>";
          summary.textContent = "0 providers";
          return;
        }
        let enabledCount = 0;
        providers.forEach(([name, info]) => {
          if (info.enabled) enabledCount++;
          const row = document.createElement("div");
          row.className = "row";
          const header = document.createElement("div");
          header.className = "row-header";
          header.innerHTML =
            "<div class='row-title'>" +
            name +
            "</div><div class='row-meta'>" +
            (info.enabled ? "enabled" : "disabled") +
            "</div>";
          const meta = document.createElement("div");
          meta.className = "row-meta";
          meta.textContent =
            "Redirect URI: " +
            (info.redirectUri || info.acsUrl || "n/a") +
            (info.hasClient !== undefined ? " · client: " + (info.hasClient ? "configured" : "not configured") : "");
          row.appendChild(header);
          row.appendChild(meta);
          el.appendChild(row);
        });
        summary.textContent = providers.length + " providers · " + enabledCount + " enabled";
      }

      loadState();
      setInterval(loadState, 8000);
    </script>
  </body>
</html>
    """
    return HTMLResponse(content=html)


@router.get("/state", response_class=JSONResponse, summary="Tenants/auth state")
async def tenants_state() -> JSONResponse:
    tenants = await _load_tenants()
    flags = _load_feature_flags()
    idps = _load_identity_providers()
    quotas = _load_quotas()
    return JSONResponse({"tenants": tenants, "flags": flags, "idps": idps, "quotas": quotas})


__all__ = [
    "router",
]

