"""API Activity Dashboard Router.

Provides a built-in dashboard similar in spirit to /docs and /redoc that
shows configured APIs along with sample payloads and lets you exercise
them from the UI to see whether they are active.
"""

from __future__ import annotations

import json
from typing import Any, Dict

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse

from ...core.seo import render_dashboard_inline_head

from .registry import EndpointSample, get_endpoint_sample, list_endpoint_samples


router = APIRouter(prefix="/dashboard/api", tags=["API Dashboard"])


def _serialize_sample(sample: EndpointSample) -> Dict[str, Any]:
    """Execute _serialize_sample operation.

    Args:
        sample: The sample parameter.

    Returns:
        The result of the operation.
    """
    return {
        "key": sample.key,
        "name": sample.name,
        "method": sample.method,
        "path": sample.path,
        "description": sample.description,
        "sampleRequest": sample.sample_request or {},
        "sampleQuery": sample.sample_query or {},
        "enabled": sample.enabled,
    }


@router.get("", response_class=HTMLResponse, summary="API Activity Dashboard")
async def api_dashboard() -> HTMLResponse:
    """Render the API dashboard page.

    The page fetches live data from the same router's JSON endpoints to
    keep the backend logic simple and avoid static assets.
    """
    _head_seo = render_dashboard_inline_head(
        page_title="FastMVC API Dashboard",
        description="Explore registered API endpoints, sample payloads, and live probes from the FastMVC API dashboard.",
        path="/dashboard/api",
    )
    html = (
        """
<!DOCTYPE html>
<html lang="en">
  <head>
    """
        + _head_seo
        + """
    <style>
      :root {
        --bg: #020617;
        --bg-card: #020617;
        --bg-card-alt: #0b1120;
        --accent: #6366f1;
        --accent-soft: rgba(99, 102, 241, 0.12);
        --success: #22c55e;
        --danger: #ef4444;
        --muted: #6b7280;
        --text: #e5e7eb;
        --text-soft: #9ca3af;
        --radius-xl: 16px;
        --shadow: 0 18px 45px rgba(15, 23, 42, 0.85);
      }

      * {
        box-sizing: border-box;
      }

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
        background: linear-gradient(140deg, rgba(148, 163, 184, 0.35), rgba(15, 23, 42, 0.95));
        border-radius: 24px;
        padding: 1px;
        box-shadow: var(--shadow);
      }

      .content {
        border-radius: 24px;
        background: radial-gradient(circle at top left, rgba(148, 163, 184, 0.2), #020617 55%);
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
        border: 1px solid rgba(129, 140, 248, 0.45);
        color: var(--accent);
      }

      .header-right {
        display: flex;
        align-items: center;
        gap: 10px;
        flex-wrap: wrap;
      }

      .pill {
        padding: 4px 9px;
        border-radius: 999px;
        font-size: 0.75rem;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        background: rgba(15, 23, 42, 0.85);
        border: 1px solid rgba(148, 163, 184, 0.5);
        color: var(--text-soft);
      }

      .grid {
        display: grid;
        grid-template-columns: minmax(0, 2.1fr) minmax(0, 2.5fr);
        gap: 16px;
      }

      .list-card,
      .detail-card {
        border-radius: var(--radius-xl);
        background: linear-gradient(165deg, var(--bg-card-alt), var(--bg-card));
        border: 1px solid rgba(148, 163, 184, 0.4);
        padding: 12px 12px 10px;
        box-shadow: 0 14px 28px rgba(15, 23, 42, 0.9);
        min-height: 220px;
      }

      .list-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 8px;
      }

      .list-title {
        font-size: 0.9rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.08em;
      }

      .list-body {
        max-height: 360px;
        overflow-y: auto;
        padding-right: 4px;
      }

      .endpoint-row {
        display: grid;
        grid-template-columns: auto 1fr auto;
        align-items: center;
        gap: 8px;
        padding: 7px 8px;
        border-radius: 999px;
        cursor: pointer;
        transition: background 120ms ease, transform 120ms ease;
        margin-bottom: 4px;
      }

      .endpoint-row:hover {
        background: rgba(15, 23, 42, 0.9);
        transform: translateY(-1px);
      }

      .endpoint-row.active {
        background: rgba(79, 70, 229, 0.25);
      }

      .method-pill {
        padding: 2px 7px;
        border-radius: 999px;
        font-size: 0.7rem;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        border: 1px solid rgba(148, 163, 184, 0.6);
      }

      .method-get { color: #22c55e; border-color: rgba(34, 197, 94, 0.6); }
      .method-post { color: #60a5fa; border-color: rgba(59, 130, 246, 0.7); }
      .method-put { color: #facc15; border-color: rgba(250, 204, 21, 0.7); }
      .method-patch { color: #f97316; border-color: rgba(249, 115, 22, 0.7); }
      .method-delete { color: #f87171; border-color: rgba(248, 113, 113, 0.8); }

      .endpoint-main {
        display: flex;
        flex-direction: column;
        gap: 2px;
      }

      .endpoint-name {
        font-size: 0.86rem;
        font-weight: 500;
      }

      .endpoint-path {
        font-size: 0.78rem;
        color: var(--text-soft);
        font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas,
          "Liberation Mono", "Courier New", monospace;
      }

      .status-dot {
        width: 8px;
        height: 8px;
        border-radius: 999px;
        background: rgba(148, 163, 184, 0.7);
      }

      .status-dot.ok {
        background: var(--success);
      }

      .status-dot.error {
        background: var(--danger);
      }

      .detail-title-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 4px;
      }

      .detail-title {
        font-size: 0.9rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.08em;
      }

      .badge-soft {
        padding: 2px 8px;
        font-size: 0.7rem;
        border-radius: 999px;
        background: rgba(15, 23, 42, 0.8);
        border: 1px solid rgba(148, 163, 184, 0.4);
        color: var(--text-soft);
      }

      .detail-body {
        display: grid;
        grid-template-rows: auto 1fr auto;
        gap: 8px;
      }

      .detail-meta {
        font-size: 0.8rem;
        color: var(--text-soft);
      }

      .code-block {
        position: relative;
        background: rgba(15, 23, 42, 0.95);
        border-radius: 10px;
        padding: 8px 8px 8px;
        font-size: 0.78rem;
        font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas,
          "Liberation Mono", "Courier New", monospace;
        color: #e5e7eb;
        border: 1px solid rgba(30, 64, 175, 0.6);
      }

      .code-block pre {
        margin: 0;
        white-space: pre-wrap;
        word-wrap: break-word;
      }

      .detail-footer {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 8px;
        margin-top: 4px;
      }

      .btn {
        border: none;
        outline: none;
        cursor: pointer;
        border-radius: 999px;
        padding: 6px 12px;
        font-size: 0.8rem;
        font-weight: 500;
        letter-spacing: 0.03em;
        text-transform: uppercase;
        background: linear-gradient(135deg, #4f46e5, #6366f1);
        color: white;
        box-shadow: 0 12px 25px rgba(79, 70, 229, 0.7);
        transition: transform 100ms ease, box-shadow 100ms ease, opacity 80ms ease;
      }

      .btn:disabled {
        opacity: 0.6;
        cursor: default;
        box-shadow: none;
      }

      .btn:hover:not(:disabled) {
        transform: translateY(-1px);
        box-shadow: 0 16px 32px rgba(79, 70, 229, 0.85);
      }

      .status-text {
        font-size: 0.78rem;
        color: var(--text-soft);
      }

      .status-text.ok {
        color: var(--success);
      }

      .status-text.error {
        color: var(--danger);
      }

      @media (max-width: 900px) {
        .grid {
          grid-template-columns: minmax(0, 1fr);
        }
      }
    </style>
  </head>
  <body>
    <div class="shell">
      <div class="content">
        <header class="header">
          <div class="header-main">
            <div class="title">
              API Activity
              <span class="badge">FastMVC dashboard</span>
            </div>
            <p class="subtitle">
              Configure sample requests for your endpoints and run live checks
              to see which APIs are active and healthy.
            </p>
          </div>
          <div class="header-right">
            <span class="pill">Mode: Dashboard</span>
            <span class="pill">Source: In-memory registry</span>
          </div>
        </header>

        <section class="grid">
          <article class="list-card">
            <div class="list-header">
              <div class="list-title">Endpoints</div>
              <div id="endpoint-count" class="badge-soft">Loading…</div>
            </div>
            <div class="list-body" id="endpoint-list"></div>
          </article>

          <article class="detail-card">
            <div class="detail-title-row">
              <div class="detail-title">Details</div>
              <div id="detail-method-pill" class="badge-soft" style="display:none;"></div>
            </div>
            <div class="detail-body">
              <div class="detail-meta" id="detail-meta">
                Select an endpoint on the left to see its sample payload
                and run a live health request.
              </div>
              <div class="code-block">
                <pre id="detail-sample">{}</pre>
              </div>
              <div class="detail-footer">
                <button class="btn" id="btn-run" disabled>Run sample</button>
                <div class="status-text" id="run-status"></div>
              </div>
            </div>
          </article>
        </section>
      </div>
    </div>

    <script>
      const endpointListEl = document.getElementById("endpoint-list");
      const endpointCountEl = document.getElementById("endpoint-count");
      const detailMetaEl = document.getElementById("detail-meta");
      const detailSampleEl = document.getElementById("detail-sample");
      const detailMethodPillEl = document.getElementById("detail-method-pill");
      const btnRunEl = document.getElementById("btn-run");
      const runStatusEl = document.getElementById("run-status");

      let endpoints = [];
      let activeKey = null;

      function methodClass(method) {
        switch (method) {
          case "GET": return "method-pill method-get";
          case "POST": return "method-pill method-post";
          case "PUT": return "method-pill method-put";
          case "PATCH": return "method-pill method-patch";
          case "DELETE": return "method-pill method-delete";
        }
        return "method-pill";
      }

      function renderList() {
        endpointListEl.innerHTML = "";
        if (!endpoints.length) {
          endpointCountEl.textContent = "0 endpoints";
          endpointListEl.innerHTML = '<div style="font-size:0.8rem;color:#9ca3af;">No endpoints registered yet. Import <code>register_endpoint_sample</code> in your controllers and register samples to see them here.</div>';
          return;
        }
        endpointCountEl.textContent = endpoints.length + " endpoints";

        for (const ep of endpoints) {
          const row = document.createElement("div");
          row.className = "endpoint-row" + (ep.key === activeKey ? " active" : "");
          row.dataset.key = ep.key;

          const method = document.createElement("span");
          method.className = methodClass(ep.method);
          method.textContent = ep.method;

          const main = document.createElement("div");
          main.className = "endpoint-main";
          const name = document.createElement("div");
          name.className = "endpoint-name";
          name.textContent = ep.name;
          const path = document.createElement("div");
          path.className = "endpoint-path";
          path.textContent = ep.path;
          main.appendChild(name);
          main.appendChild(path);

          const statusDot = document.createElement("div");
          statusDot.className = "status-dot";
          statusDot.id = "status-dot-" + ep.key;

          row.appendChild(method);
          row.appendChild(main);
          row.appendChild(statusDot);

          row.addEventListener("click", () => selectEndpoint(ep.key));
          endpointListEl.appendChild(row);
        }
      }

      function selectEndpoint(key) {
        activeKey = key;
        for (const row of endpointListEl.querySelectorAll(".endpoint-row")) {
          row.classList.toggle("active", row.dataset.key === key);
        }
        const ep = endpoints.find(e => e.key === key);
        if (!ep) return;

        detailMetaEl.textContent = ep.description || (ep.method + " " + ep.path);
        detailSampleEl.textContent = JSON.stringify(ep.sampleRequest || {}, null, 2);
        detailMethodPillEl.style.display = "inline-flex";
        detailMethodPillEl.textContent = ep.method + "  " + ep.path;
        btnRunEl.disabled = false;
        runStatusEl.textContent = "";
        runStatusEl.className = "status-text";
      }

      async function loadEndpoints() {
        try {
          const res = await fetch("/dashboard/api/endpoints");
          if (!res.ok) {
            throw new Error("Failed to load endpoints");
          }
          endpoints = await res.json();
          renderList();
        } catch (err) {
          console.error(err);
          endpointCountEl.textContent = "Error loading endpoints";
        }
      }

      async function runSample() {
        if (!activeKey) return;
        btnRunEl.disabled = true;
        runStatusEl.textContent = "Running…";
        runStatusEl.className = "status-text";
        try {
          const res = await fetch("/dashboard/api/test/" + encodeURIComponent(activeKey), {
            method: "POST"
          });
          const body = await res.json();
          const ok = body.ok === true;
          const label = (ok ? "OK " : "Error ") + "(" + body.status + ", " + body.latency_ms.toFixed(1) + " ms)";
          runStatusEl.textContent = label;
          runStatusEl.className = "status-text " + (ok ? "ok" : "error");
          const dot = document.getElementById("status-dot-" + activeKey);
          if (dot) {
            dot.classList.remove("ok", "error");
            dot.classList.add(ok ? "ok" : "error");
          }
        } catch (err) {
          console.error(err);
          runStatusEl.textContent = "Request failed";
          runStatusEl.className = "status-text error";
        } finally {
          btnRunEl.disabled = false;
        }
      }

      btnRunEl.addEventListener("click", runSample);
      loadEndpoints();
    </script>
  </body>
</html>
    """
    )
    return HTMLResponse(content=html)


@router.get(
    "/endpoints", response_class=JSONResponse, summary="List configured API samples"
)
async def list_endpoints() -> JSONResponse:
    """Return the list of registered endpoint samples as JSON."""
    samples = list_endpoint_samples()
    return JSONResponse(content=[_serialize_sample(s) for s in samples])


@router.post(
    "/test/{key}",
    response_class=JSONResponse,
    summary="Run sample request for an endpoint",
)
async def test_endpoint(key: str, request: Request) -> JSONResponse:
    """Execute the sample request for the given endpoint key against this API.

    This uses httpx to send a request back to the same FastAPI instance,
    so it respects middleware and routing exactly as a real client would.
    """
    sample = get_endpoint_sample(key)
    if not sample or not sample.enabled:
        raise HTTPException(status_code=404, detail="Endpoint sample not found.")

    base_url = str(request.base_url).rstrip("/")
    url = f"{base_url}{sample.path}"
    method = sample.method.upper()
    json_body = sample.sample_request or None
    params = sample.sample_query or None
    headers = sample.sample_headers or None

    import time as _time

    start = _time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.request(
                method=method,
                url=url,
                json=json_body,
                params=params,
                headers=headers,
            )
        elapsed_ms = (float(_time.perf_counter() - start)) * 1000.0
        truncated_body: Any
        try:
            data = response.json()
            serialized = json.dumps(data)
        except Exception:
            serialized = response.text or ""
        if len(serialized) > 400:
            truncated_body = serialized[:400] + "…"  # type: ignore
        else:
            truncated_body = serialized

        return JSONResponse(
            content={
                "ok": response.status_code < 500,
                "status": response.status_code,
                "latency_ms": elapsed_ms,
                "body": truncated_body,
            }
        )
    except Exception as exc:
        elapsed_ms = (float(_time.perf_counter() - start)) * 1000.0
        return JSONResponse(
            content={
                "ok": False,
                "status": 0,
                "latency_ms": elapsed_ms,
                "error": f"{exc}"[0:200],  # type: ignore
            },
            status_code=200,
        )
