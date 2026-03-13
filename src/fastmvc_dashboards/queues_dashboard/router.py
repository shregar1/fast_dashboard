"""
Queues & Jobs Dashboard Router.

Provides a visual dashboard at `/dashboard/queues` that surfaces basic
metrics and status information for message queues (RabbitMQ, SQS, NATS)
and background workers (Celery, RQ, Dramatiq).

The dashboard is intentionally read-only for destructive actions; it
exposes JSON endpoints that applications can extend for pause/resume or
replay semantics where needed.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter
from fastapi.responses import HTMLResponse, JSONResponse
from loguru import logger

from configurations.jobs import JobsConfiguration
from configurations.queues import QueuesConfiguration
from core.utils.optional_imports import optional_import

boto3, _ = optional_import("boto3")
_celery_mod, Celery = optional_import("celery", "Celery")
rq, _ = optional_import("rq")
_redis_mod, Redis = optional_import("redis", "Redis")
_rq_registry_mod, FailedJobRegistry = optional_import("rq.registry", "FailedJobRegistry")


router = APIRouter(prefix="/dashboard/queues", tags=["Queues Dashboard"])


def _inspect_rabbitmq(cfg) -> Optional[Dict[str, Any]]:
    if not (cfg.enabled and cfg.url):
        return None
    management_url = getattr(cfg, "management_url", None)
    if not management_url:
        # Management endpoint not configured; skip inspection but keep backend usable.
        return None
    try:
        auth = None
        username = getattr(cfg, "username", None)
        password = getattr(cfg, "password", None)
        if username and password:
            auth = (username, password)
        api_url = management_url.rstrip("/") + "/api/queues"
        resp = httpx.get(api_url, auth=auth, timeout=3.0)
        resp.raise_for_status()
        queues = resp.json()
        total_ready = 0
        total_unacked = 0
        for q in queues:
            try:
                total_ready += int(q.get("messages", 0))
                total_unacked += int(q.get("messages_unacknowledged", 0))
            except Exception:
                continue
        return {
            "backend": "rabbitmq",
            "name": management_url,
            "messages": total_ready,
            "inFlight": total_unacked,
            "delayed": 0,
        }
    except Exception as exc:  # pragma: no cover - best effort
        logger.warning(f"RabbitMQ inspection failed: {exc}")
        return {
            "backend": "rabbitmq",
            "name": management_url or cfg.url,
            "error": str(exc),
        }


def _inspect_sqs(cfg) -> Optional[Dict[str, Any]]:
    if not (cfg.enabled and cfg.queue_url and boto3 is not None):
        return None
    try:
        session_kwargs: Dict[str, Any] = {}
        if cfg.access_key_id and cfg.secret_access_key:
            session_kwargs.update(
                aws_access_key_id=cfg.access_key_id,
                aws_secret_access_key=cfg.secret_access_key,
            )
        sqs = boto3.client("sqs", region_name=cfg.region, **session_kwargs)
        attrs = sqs.get_queue_attributes(
            QueueUrl=cfg.queue_url,
            AttributeNames=[
                "ApproximateNumberOfMessages",
                "ApproximateNumberOfMessagesNotVisible",
                "ApproximateNumberOfMessagesDelayed",
            ],
        )["Attributes"]
        return {
            "backend": "sqs",
            "name": cfg.queue_url,
            "messages": int(attrs.get("ApproximateNumberOfMessages", "0")),
            "inFlight": int(attrs.get("ApproximateNumberOfMessagesNotVisible", "0")),
            "delayed": int(attrs.get("ApproximateNumberOfMessagesDelayed", "0")),
        }
    except Exception as exc:  # pragma: no cover - best effort
        logger.warning(f"SQS inspection failed: {exc}")
        return {
            "backend": "sqs",
            "name": cfg.queue_url,
            "error": str(exc),
        }


def _inspect_jobs() -> Dict[str, Any]:
    cfg = JobsConfiguration.instance().get_config()
    out: Dict[str, Any] = {
        "celery": {"enabled": cfg.celery.enabled, "workers": None, "active": None},
        "rq": {"enabled": cfg.rq.enabled, "queueSize": None, "failed": None},
        "dramatiq": {"enabled": cfg.dramatiq.enabled, "status": None},
    }

    if cfg.celery.enabled and Celery is not None:
        try:
            app = Celery(
                cfg.celery.namespace,
                broker=cfg.celery.broker_url,
                backend=cfg.celery.result_backend,
            )
            insp = app.control.inspect()
            active = insp.active() or {}
            out["celery"]["workers"] = len(active)
            out["celery"]["active"] = sum(len(tasks or []) for tasks in active.values())
        except Exception as exc:  # pragma: no cover
            logger.warning(f"Celery inspection failed: {exc}")
            out["celery"]["error"] = str(exc)

    if cfg.rq.enabled and rq is not None and Redis is not None and FailedJobRegistry is not None:
        try:
            redis_conn = Redis.from_url(cfg.rq.redis_url)
            queue = rq.Queue(cfg.rq.queue_name, connection=redis_conn)
            out["rq"]["queueSize"] = queue.count
            failed_registry = FailedJobRegistry(cfg.rq.queue_name, connection=redis_conn)
            out["rq"]["failed"] = len(failed_registry)
        except Exception as exc:  # pragma: no cover
            logger.warning(f"RQ inspection failed: {exc}")
            out["rq"]["error"] = str(exc)

    if cfg.dramatiq.enabled:
        # Dramatiq does not expose lightweight built-in inspection APIs;
        # we simply surface that it is configured.
        out["dramatiq"]["status"] = "configured"

    return out


@router.get("", response_class=HTMLResponse, summary="Queues & Jobs Dashboard")
async def queues_dashboard() -> HTMLResponse:
    """
    Render the queues & jobs dashboard page.
    """
    html = """
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <title>FastMVC Queues & Jobs Dashboard</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <style>
      :root {
        --bg: #020617;
        --bg-card: #020617;
        --bg-card-alt: #0b1120;
        --accent: #22c55e;
        --accent-soft: rgba(34, 197, 94, 0.12);
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
        background: linear-gradient(140deg, rgba(52, 211, 153, 0.4), rgba(15, 23, 42, 0.95));
        border-radius: 24px;
        padding: 1px;
        box-shadow: var(--shadow);
      }

      .content {
        border-radius: 24px;
        background: radial-gradient(circle at top left, rgba(16, 185, 129, 0.2), #020617 55%);
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
        border: 1px solid rgba(34, 197, 94, 0.45);
        color: var(--accent);
      }

      .grid {
        display: grid;
        grid-template-columns: minmax(0, 2.1fr) minmax(0, 2.5fr);
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

      .queue-row, .job-row {
        display: grid;
        grid-template-columns: auto 1fr auto;
        align-items: center;
        gap: 8px;
        padding: 7px 8px;
        border-radius: 999px;
        margin-bottom: 4px;
        background: rgba(15, 23, 42, 0.7);
        border: 1px solid rgba(31, 41, 55, 0.9);
      }

      .queue-meta, .job-meta {
        font-size: 0.76rem;
        color: var(--text-soft);
      }

      .metrics {
        display: flex;
        gap: 8px;
        font-size: 0.75rem;
      }

      .metric {
        padding: 2px 7px;
        border-radius: 999px;
        background: rgba(15, 23, 42, 0.9);
        border: 1px solid rgba(55, 65, 81, 0.9);
      }

      .status-dot {
        width: 7px;
        height: 7px;
        border-radius: 999px;
        margin-right: 6px;
        display: inline-block;
      }

      .status-ok {
        background: var(--accent);
      }

      .status-warn {
        background: #facc15;
      }

      .status-bad {
        background: var(--danger);
      }
    </style>
  </head>
  <body>
    <div class="shell">
      <div class="content">
        <div class="header">
          <div class="header-main">
            <div class="title">
              Queues & Jobs
              <span class="badge">Live system view</span>
            </div>
            <div class="subtitle">
              Inspect message backlogs and worker activity across RabbitMQ/SQS and Celery/RQ/Dramatiq.
            </div>
          </div>
        </div>
        <div class="grid">
          <div class="card">
            <div class="card-header">
              <div class="card-title">Queues</div>
              <div class="pill" id="queues-summary">Loading…</div>
            </div>
            <div class="list" id="queues-list"></div>
          </div>
          <div class="card">
            <div class="card-header">
              <div class="card-title">Workers & Jobs</div>
              <div class="pill" id="jobs-summary">Loading…</div>
            </div>
            <div class="list" id="jobs-list"></div>
          </div>
        </div>
      </div>
    </div>
    <script>
      async function loadState() {
        try {
          const res = await fetch(window.location.pathname + "/state");
          const data = await res.json();
          renderQueues(data.queues || []);
          renderJobs(data.jobs || {});
        } catch (e) {
          console.error(e);
        }
      }

      function renderQueues(queues) {
        const el = document.getElementById("queues-list");
        const summary = document.getElementById("queues-summary");
        el.innerHTML = "";
        if (!queues.length) {
          el.innerHTML = "<div class='queue-meta'>No queues configured.</div>";
          summary.textContent = "0 backends";
          return;
        }
        let totalMessages = 0;
        queues.forEach((q) => {
          totalMessages += q.messages || 0;
          const row = document.createElement("div");
          row.className = "queue-row";
          const name = document.createElement("div");
          name.innerHTML = "<span class='status-dot status-ok'></span>" + (q.backend || "queue");
          const meta = document.createElement("div");
          meta.className = "queue-meta";
          meta.textContent = q.name || "";
          const metrics = document.createElement("div");
          metrics.className = "metrics";
          metrics.innerHTML =
            "<span class='metric'>msg: " + (q.messages ?? "–") + "</span>" +
            "<span class='metric'>in-flight: " + (q.inFlight ?? "–") + "</span>" +
            "<span class='metric'>delayed: " + (q.delayed ?? "–") + "</span>";
          row.appendChild(name);
          row.appendChild(meta);
          row.appendChild(metrics);
          el.appendChild(row);
        });
        summary.textContent = queues.length + " backends · " + totalMessages + " messages";
      }

      function renderJobs(jobs) {
        const el = document.getElementById("jobs-list");
        const summary = document.getElementById("jobs-summary");
        el.innerHTML = "";
        const entries = Object.entries(jobs);
        if (!entries.length) {
          el.innerHTML = "<div class='job-meta'>No workers configured.</div>";
          summary.textContent = "0 workers";
          return;
        }
        let totalActive = 0;
        entries.forEach(([backend, info]) => {
          const row = document.createElement("div");
          row.className = "job-row";
          const name = document.createElement("div");
          name.innerHTML = "<span class='status-dot status-ok'></span>" + backend;
          const meta = document.createElement("div");
          meta.className = "job-meta";
          if (backend === "celery") {
            meta.textContent =
              (info.enabled ? "enabled" : "disabled") +
              " · workers: " +
              (info.workers ?? "–") +
              " · active: " +
              (info.active ?? "–");
            totalActive += info.active || 0;
          } else if (backend === "rq") {
            meta.textContent =
              (info.enabled ? "enabled" : "disabled") +
              " · queue: " +
              (info.queueSize ?? "–") +
              " · failed: " +
              (info.failed ?? "–");
          } else if (backend === "dramatiq") {
            meta.textContent =
              (info.enabled ? "enabled" : "disabled") + " · status: " + (info.status || "n/a");
          }
          const metrics = document.createElement("div");
          metrics.className = "metrics";
          row.appendChild(name);
          row.appendChild(meta);
          row.appendChild(metrics);
          el.appendChild(row);
        });
        summary.textContent = entries.length + " workers · " + totalActive + " active";
      }

      loadState();
      setInterval(loadState, 5000);
    </script>
  </body>
</html>
    """
    return HTMLResponse(content=html)


@router.get("/state", response_class=JSONResponse, summary="Queues & jobs state")
async def queues_state() -> JSONResponse:
    """
    Return JSON snapshot of queues and worker state for the dashboard UI.
    """
    q_cfg = QueuesConfiguration.instance().get_config()
    queues: List[Dict[str, Any]] = []

    rabbit_info = _inspect_rabbitmq(q_cfg.rabbitmq)
    if rabbit_info is not None:
        queues.append(rabbit_info)

    sqs_info = _inspect_sqs(q_cfg.sqs)
    if sqs_info is not None:
        queues.append(sqs_info)

    jobs = _inspect_jobs()
    return JSONResponse({"queues": queues, "jobs": jobs})


__all__ = [
    "router",
]

