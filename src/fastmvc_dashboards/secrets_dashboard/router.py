"""
Secrets & Configuration Dashboard Router.

Provides a read-only dashboard at `/dashboard/secrets` that shows:
- Which secrets backends are configured/enabled (Vault, AWS, GCP, Azure)
- A simple "can we fetch a test secret" health check
- A diff-style view comparing `.env.example` vs `.env` configuration
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Tuple

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, JSONResponse

from configurations.secrets import SecretsConfiguration
from services.secrets import build_secrets_backend


router = APIRouter(prefix="/dashboard/secrets", tags=["Secrets Dashboard"])


def _load_backends_state() -> Dict[str, Any]:
    cfg = SecretsConfiguration.instance().get_config()
    return {
        "vault": {
            "enabled": cfg.vault.enabled,
            "url": cfg.vault.url,
            "mountPoint": cfg.vault.mount_point,
        },
        "aws": {
            "enabled": cfg.aws.enabled,
            "region": cfg.aws.region,
            "prefix": cfg.aws.prefix,
        },
        "gcp": {
            "enabled": cfg.gcp.enabled,
            "projectId": cfg.gcp.project_id,
        },
        "azure": {
            "enabled": cfg.azure.enabled,
            "vaultUrl": cfg.azure.vault_url,
        },
    }


async def _check_secret_health() -> Dict[str, Any]:
    backend = build_secrets_backend()
    if backend is None:
        return {"hasBackend": False, "ok": False, "message": "No secrets backend enabled."}

    test_name = os.getenv("SECRETS_HEALTH_CHECK_NAME", "fastmvc/health")
    try:
        value = await backend.get_secret(test_name)
        return {
            "hasBackend": True,
            "ok": value is not None,
            "secretName": test_name,
            "message": "Secret retrieved" if value is not None else "Secret not found / not accessible",
        }
    except Exception as exc:  # pragma: no cover - defensive
        return {
            "hasBackend": True,
            "ok": False,
            "secretName": test_name,
            "message": str(exc),
        }


def _parse_env_file(path: Path) -> Dict[str, str]:
    if not path.exists():
        return {}
    data: Dict[str, str] = {}
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        data[key] = value
    return data


def _diff_envs(base: Dict[str, str], current: Dict[str, str]) -> Dict[str, Any]:
    added = {k: current[k] for k in current.keys() - base.keys()}
    removed = {k: base[k] for k in base.keys() - current.keys()}
    changed = {
        k: {"from": base[k], "to": current[k]}
        for k in base.keys() & current.keys()
        if base[k] != current[k]
    }
    return {"added": added, "removed": removed, "changed": changed}


def _load_env_diff() -> Dict[str, Any]:
    root = Path(".")
    example = _parse_env_file(root / ".env.example")
    current = _parse_env_file(root / ".env")
    if not example and not current:
        return {"hasEnv": False, "diff": {"added": {}, "removed": {}, "changed": {}}}
    return {
        "hasEnv": True,
        "diff": _diff_envs(example, current),
    }


@router.get("", response_class=HTMLResponse, summary="Secrets & Config Dashboard")
async def secrets_dashboard() -> HTMLResponse:
    html = """
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <title>FastMVC Secrets & Config Dashboard</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <style>
      :root {
        --bg: #020617;
        --bg-card: #020617;
        --bg-card-alt: #0b1120;
        --accent: #f97316;
        --accent-soft: rgba(249, 115, 22, 0.12);
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
        background: linear-gradient(140deg, rgba(249, 115, 22, 0.4), rgba(15, 23, 42, 0.95));
        border-radius: 24px;
        padding: 1px;
        box-shadow: var(--shadow);
      }

      .content {
        border-radius: 24px;
        background: radial-gradient(circle at top left, rgba(249, 115, 22, 0.24), #020617 55%);
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
        border: 1px solid rgba(249, 115, 22, 0.5);
        color: var(--accent);
      }

      .grid {
        display: grid;
        grid-template-columns: minmax(0, 2.2fr) minmax(0, 2.8fr);
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

      pre {
        font-family: ui-monospace, Menlo, Monaco, "SF Mono", monospace;
        font-size: 0.74rem;
        background: rgba(15, 23, 42, 0.85);
        border-radius: 10px;
        padding: 8px 10px;
        white-space: pre-wrap;
        word-break: break-all;
        border: 1px solid rgba(31, 41, 55, 0.9);
      }
    </style>
  </head>
  <body>
    <div class="shell">
      <div class="content">
        <div class="header">
          <div class="header-main">
            <div class="title">
              Secrets & Configuration
              <span class="badge">Read-only overview</span>
            </div>
            <div class="subtitle">
              See which secrets backends are active, run a test secret fetch, and inspect differences between .env.example and .env.
            </div>
          </div>
        </div>
        <div class="grid">
          <div class="card">
            <div class="card-header">
              <div class="card-title">Secrets Backends</div>
              <div class="pill" id="backends-summary">Loading…</div>
            </div>
            <div class="list" id="backends-list"></div>
          </div>
          <div class="card">
            <div class="card-header">
              <div class="card-title">Env Config Diff</div>
              <div class="pill" id="env-summary">Loading…</div>
            </div>
            <div class="list" id="env-list"></div>
          </div>
        </div>
      </div>
    </div>
    <script>
      async function loadState() {
        try {
          const res = await fetch(window.location.pathname + "/state");
          const data = await res.json();
          renderBackends(data.backends || {}, data.health || {});
          renderEnvDiff(data.envDiff || {});
        } catch (e) {
          console.error(e);
        }
      }

      function renderBackends(backends, health) {
        const el = document.getElementById("backends-list");
        const summary = document.getElementById("backends-summary");
        el.innerHTML = "";
        const entries = Object.entries(backends);
        if (!entries.length) {
          el.innerHTML = "<div class='row-meta'>No secrets configuration found.</div>";
          summary.textContent = "0 backends";
          return;
        }
        let enabledCount = 0;
        entries.forEach(([name, info]) => {
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
          if (name === "vault") {
            meta.textContent = (info.url || "") + " · mount=" + (info.mountPoint || "");
          } else if (name === "aws") {
            meta.textContent = (info.region || "") + " · prefix=" + (info.prefix || "");
          } else if (name === "gcp") {
            meta.textContent = "project=" + (info.projectId || "");
          } else if (name === "azure") {
            meta.textContent = info.vaultUrl || "";
          }
          row.appendChild(header);
          row.appendChild(meta);
          el.appendChild(row);
        });
        const healthText = health.ok
          ? "test secret OK (" + (health.secretName || "") + ")"
          : "test secret failed (" + (health.message || "n/a") + ")";
        summary.textContent = enabledCount + " enabled · " + healthText;
      }

      function renderEnvDiff(envDiff) {
        const el = document.getElementById("env-list");
        const summary = document.getElementById("env-summary");
        el.innerHTML = "";
        if (!envDiff.hasEnv) {
          el.innerHTML = "<div class='row-meta'>No .env or .env.example files found.</div>";
          summary.textContent = "no env files";
          return;
        }
        const diff = envDiff.diff || { added: {}, removed: {}, changed: {} };
        const added = Object.keys(diff.added || {}).length;
        const removed = Object.keys(diff.removed || {}).length;
        const changed = Object.keys(diff.changed || {}).length;
        summary.textContent =
          "added: " + added + " · removed: " + removed + " · changed: " + changed;

        const pre = document.createElement("pre");
        pre.textContent = JSON.stringify(diff, null, 2);
        el.appendChild(pre);
      }

      loadState();
      setInterval(loadState, 10000);
    </script>
  </body>
</html>
    """
    return HTMLResponse(content=html)


@router.get("/state", response_class=JSONResponse, summary="Secrets/config state")
async def secrets_state() -> JSONResponse:
    backends = _load_backends_state()
    health = await _check_secret_health()
    env_diff = _load_env_diff()
    return JSONResponse({"backends": backends, "health": health, "envDiff": env_diff})


__all__ = [
    "router",
]

