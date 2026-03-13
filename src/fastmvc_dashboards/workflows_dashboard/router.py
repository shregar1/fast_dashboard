"""
Workflows Dashboard Router.

Provides a simple overview at `/dashboard/workflows` of the configured
workflow engine and an example "order lifecycle" workflow.
"""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, JSONResponse

from configurations.workflows import WorkflowsConfiguration
from services.workflows.order_lifecycle import OrderWorkflowService


router = APIRouter(prefix="/dashboard/workflows", tags=["Workflows Dashboard"])


@router.get("", response_class=HTMLResponse, summary="Workflows Dashboard")
async def workflows_dashboard() -> HTMLResponse:
    """
    Render the workflows dashboard page.
    """
    html = """
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <title>FastMVC Workflows Dashboard</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <style>
      :root {
        --bg: #020617;
        --bg-card: #020617;
        --bg-card-alt: #0b1120;
        --accent: #a855f7;
        --accent-soft: rgba(168, 85, 247, 0.14);
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
        max-width: 960px;
        background: linear-gradient(140deg, rgba(168, 85, 247, 0.4), rgba(15, 23, 42, 0.95));
        border-radius: 24px;
        padding: 1px;
        box-shadow: var(--shadow);
      }

      .content {
        border-radius: 24px;
        background: radial-gradient(circle at top left, rgba(147, 51, 234, 0.2), #020617 55%);
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
        border: 1px solid rgba(168, 85, 247, 0.5);
        color: var(--accent);
      }

      .card {
        border-radius: var(--radius-xl);
        background: linear-gradient(165deg, var(--bg-card-alt), var(--bg-card));
        border: 1px solid rgba(148, 163, 184, 0.4);
        padding: 14px 14px 12px;
        box-shadow: 0 14px 28px rgba(15, 23, 42, 0.9);
      }

      .card-title {
        font-size: 0.9rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        margin-bottom: 8px;
      }

      .row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 7px 8px;
        border-radius: 999px;
        background: rgba(15, 23, 42, 0.8);
        border: 1px solid rgba(31, 41, 55, 0.9);
        margin-bottom: 6px;
      }

      .row-main {
        display: flex;
        flex-direction: column;
        gap: 2px;
      }

      .row-title {
        font-size: 0.86rem;
        font-weight: 500;
      }

      .row-meta {
        font-size: 0.76rem;
        color: var(--text-soft);
      }

      .pill {
        padding: 3px 10px;
        border-radius: 999px;
        font-size: 0.7rem;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        background: rgba(15, 23, 42, 0.9);
        border: 1px solid rgba(148, 163, 184, 0.5);
        color: var(--text-soft);
      }
    </style>
  </head>
  <body>
    <div class="shell">
      <div class="content">
        <div class="header">
          <div class="header-main">
            <div class="title">
              Workflows
              <span class="badge">Order lifecycle</span>
            </div>
            <div class="subtitle">
              See which workflow engine is configured and inspect example order workflows.
            </div>
          </div>
        </div>
        <div class="card">
          <div class="card-title">Engine & Recent Runs</div>
          <div id="wf-list">
            <div class="row">
              <div class="row-main">
                <div class="row-title">Loading…</div>
                <div class="row-meta">Fetching workflow state</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
    <script>
      async function loadState() {
        try {
          const res = await fetch(window.location.pathname + "/state");
          const data = await res.json();
          renderWorkflows(data);
        } catch (e) {
          console.error(e);
        }
      }

      function renderWorkflows(data) {
        const el = document.getElementById("wf-list");
        el.innerHTML = "";
        const engine = data.engine || {};
        const runs = data.runs || [];

        const engineRow = document.createElement("div");
        engineRow.className = "row";
        const main = document.createElement("div");
        main.className = "row-main";
        const title = document.createElement("div");
        title.className = "row-title";
        title.textContent = engine.enabled ? (engine.engineName || "engine") + " (enabled)" : "Disabled";
        const meta = document.createElement("div");
        meta.className = "row-meta";
        meta.textContent =
          "Engine: " +
          (engine.engineName || "n/a") +
          " · Temporal: " +
          (engine.temporal || "n/a") +
          " · Prefect: " +
          (engine.prefect || "n/a") +
          " · Dagster: " +
          (engine.dagster || "n/a");
        main.appendChild(title);
        main.appendChild(meta);
        engineRow.appendChild(main);
        const pill = document.createElement("div");
        pill.className = "pill";
        pill.textContent = runs.length + " recent";
        engineRow.appendChild(pill);
        el.appendChild(engineRow);

        runs.forEach((r) => {
          const row = document.createElement("div");
          row.className = "row";
          const m = document.createElement("div");
          m.className = "row-main";
          const t = document.createElement("div");
          t.className = "row-title";
          t.textContent = "Order " + (r.orderId || "");
          const meta2 = document.createElement("div");
          meta2.className = "row-meta";
          meta2.textContent =
            "Workflow " +
            (r.workflowId || "") +
            " · status: " +
            (r.status || "unknown");
          m.appendChild(t);
          m.appendChild(meta2);
          row.appendChild(m);
          el.appendChild(row);
        });
      }

      loadState();
      setInterval(loadState, 8000);
    </script>
  </body>
</html>
    """
    return HTMLResponse(content=html)


@router.get("/state", response_class=JSONResponse, summary="Workflows state")
async def workflows_state() -> JSONResponse:
    """
    Return JSON snapshot of workflow engine configuration and sample runs.
    """
    cfg = WorkflowsConfiguration.instance().get_config()
    engine_info: Dict[str, Any] = {
        "enabled": cfg.enabled,
        "engineName": cfg.engine,
        "temporal": f"{cfg.temporal_address} / {cfg.temporal_namespace}" if cfg.engine == "temporal" else None,
        "prefect": cfg.prefect_api_url if cfg.engine == "prefect" else None,
        "dagster": cfg.dagster_grpc_endpoint if cfg.engine == "dagster" else None,
    }

    # For now, we do not query real backends for runs; this endpoint can be
    # extended by the application. We just surface an empty list.
    runs: list[Dict[str, Any]] = []

    return JSONResponse({"engine": engine_info, "runs": runs})


__all__ = ["router"]

