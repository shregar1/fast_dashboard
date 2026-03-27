"""Queues & Jobs Dashboard Router with beautiful visualizations."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple

import httpx
from fastapi import APIRouter
from fastapi.responses import HTMLResponse, JSONResponse
from loguru import logger

from fast_dashboards.core.registry import registry
from fast_dashboards.core.seo import render_dashboard_inline_head
from fast_dashboards.core._optional_import import optional_import

boto3, _ = optional_import("boto3")
_celery_mod, Celery = optional_import("celery", "Celery")
rq, _ = optional_import("rq")
_redis_mod, Redis = optional_import("redis", "Redis")
_rq_registry_mod, FailedJobRegistry = optional_import(
    "rq.registry", "FailedJobRegistry"
)


def _get_jobs_config() -> Optional[Any]:
    """Get jobs configuration via registry."""
    cfg_class = registry.get_config("jobs")
    if cfg_class and hasattr(cfg_class, "instance"):
        return cfg_class.instance().get_config()
    return None


def _get_queues_config() -> Optional[Any]:
    """Get queues configuration via registry."""
    cfg_class = registry.get_config("queues")
    if cfg_class and hasattr(cfg_class, "instance"):
        return cfg_class.instance().get_config()
    return None


router = APIRouter(prefix="/dashboard/queues", tags=["Queues Dashboard"])


def _inspect_rabbitmq(cfg) -> Optional[Dict[str, Any]]:
    """Execute _inspect_rabbitmq operation.

    Args:
        cfg: The cfg parameter.

    Returns:
        The result of the operation.
    """
    if not (cfg.enabled and cfg.url):
        return None
    management_url = getattr(cfg, "management_url", None)
    if not management_url:
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
            "icon": "🐰",
            "color": "#ff6b6b",
        }
    except Exception as exc:
        logger.warning(f"RabbitMQ inspection failed: {exc}")
        return {
            "backend": "rabbitmq",
            "name": management_url or cfg.url,
            "error": str(exc)[:50],
            "icon": "🐰",
            "color": "#ff6b6b",
        }


def _inspect_sqs(cfg) -> Optional[Dict[str, Any]]:
    """Execute _inspect_sqs operation.

    Args:
        cfg: The cfg parameter.

    Returns:
        The result of the operation.
    """
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
            "name": cfg.queue_url.split("/")[-1],
            "messages": int(attrs.get("ApproximateNumberOfMessages", "0")),
            "inFlight": int(attrs.get("ApproximateNumberOfMessagesNotVisible", "0")),
            "delayed": int(attrs.get("ApproximateNumberOfMessagesDelayed", "0")),
            "icon": "📦",
            "color": "#f59e0b",
        }
    except Exception as exc:
        logger.warning(f"SQS inspection failed: {exc}")
        return {
            "backend": "sqs",
            "name": cfg.queue_url.split("/")[-1] if cfg.queue_url else "SQS",
            "error": str(exc)[:50],
            "icon": "📦",
            "color": "#f59e0b",
        }


def _inspect_jobs() -> Dict[str, Any]:
    """Execute _inspect_jobs operation.

    Returns:
        The result of the operation.
    """
    cfg = _get_jobs_config()
    if cfg is None:
        return {
            "celery": {
                "enabled": False,
                "workers": 0,
                "active": 0,
                "icon": "🌿",
                "color": "#22c55e",
                "status": "disabled",
            },
            "rq": {
                "enabled": False,
                "queueSize": 0,
                "failed": 0,
                "icon": "🔴",
                "color": "#ef4444",
                "status": "disabled",
            },
            "dramatiq": {
                "enabled": False,
                "status": "n/a",
                "icon": "🎭",
                "color": "#8b5cf6",
                "status": "disabled",
            },
        }

    out: Dict[str, Any] = {
        "celery": {
            "enabled": cfg.celery.enabled,
            "workers": 0,
            "active": 0,
            "icon": "🌿",
            "color": "#22c55e",
            "status": "idle",
        },
        "rq": {
            "enabled": cfg.rq.enabled,
            "queueSize": 0,
            "failed": 0,
            "icon": "🔴",
            "color": "#ef4444",
            "status": "idle",
        },
        "dramatiq": {
            "enabled": cfg.dramatiq.enabled,
            "status": "configured" if cfg.dramatiq.enabled else "n/a",
            "icon": "🎭",
            "color": "#8b5cf6",
            "status": "idle",
        },
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
            out["celery"]["status"] = "active" if len(active) > 0 else "idle"
        except Exception as exc:
            logger.warning(f"Celery inspection failed: {exc}")
            out["celery"]["error"] = str(exc)[:30]
            out["celery"]["status"] = "error"

    if (
        cfg.rq.enabled
        and rq is not None
        and Redis is not None
        and FailedJobRegistry is not None
    ):
        try:
            redis_conn = Redis.from_url(cfg.rq.redis_url)
            queue = rq.Queue(cfg.rq.queue_name, connection=redis_conn)
            out["rq"]["queueSize"] = queue.count
            failed_registry = FailedJobRegistry(
                cfg.rq.queue_name, connection=redis_conn
            )
            out["rq"]["failed"] = len(failed_registry)
            out["rq"]["status"] = "active" if queue.count > 0 else "idle"
        except Exception as exc:
            logger.warning(f"RQ inspection failed: {exc}")
            out["rq"]["error"] = str(exc)[:30]
            out["rq"]["status"] = "error"

    if cfg.dramatiq.enabled:
        out["dramatiq"]["status"] = "configured"

    return out


@router.get("", response_class=HTMLResponse, summary="Queues & Jobs Dashboard")
async def queues_dashboard() -> HTMLResponse:
    """Render the queues & jobs dashboard page."""
    _head_seo = render_dashboard_inline_head(
        page_title="FastMVC Queues & Jobs Dashboard",
        description="Queue backends, workers, and job runner status for RabbitMQ, SQS, NATS, Celery, RQ, and Dramatiq.",
        path="/dashboard/queues",
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
            --accent-primary: #f59e0b;
            --accent-secondary: #fbbf24;
            --accent-gradient: linear-gradient(135deg, #f59e0b 0%, #fbbf24 100%);
            --success: #10b981;
            --warning: #f59e0b;
            --error: #ef4444;
            --border-color: rgba(148, 163, 184, 0.1);
            --shadow-sm: 0 1px 2px 0 rgba(0, 0, 0, 0.3);
            --shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.4);
            --shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.5);
            --shadow-glow: 0 0 40px rgba(245, 158, 11, 0.15);
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
            background: radial-gradient(ellipse at top, rgba(245, 158, 11, 0.15) 0%, transparent 70%);
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
            grid-template-columns: 1fr 1fr;
            gap: 1.5rem;
        }}
        
        @media (max-width: 1024px) {{
            .dashboard-grid {{ grid-template-columns: 1fr; }}
        }}
        
        /* Section Cards */
        .section-card {{
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 20px;
            overflow: hidden;
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
            font-size: 1.25rem;
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
        
        .live-indicator {{
            display: flex;
            align-items: center;
            gap: 0.5rem;
            font-size: 0.75rem;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}
        
        .live-dot {{
            width: 8px;
            height: 8px;
            background: var(--success);
            border-radius: 50%;
            animation: pulse 2s infinite;
        }}
        
        @keyframes pulse {{
            0%, 100% {{ opacity: 1; box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.4); }}
            50% {{ opacity: 0.8; box-shadow: 0 0 0 8px rgba(16, 185, 129, 0); }}
        }}
        
        .section-content {{ padding: 1.5rem; }}
        
        /* Queue Items */
        .queue-list {{
            display: flex;
            flex-direction: column;
            gap: 1rem;
        }}
        
        .queue-item {{
            background: var(--bg-secondary);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 1.25rem;
            transition: all 0.3s ease;
        }}
        
        .queue-item:hover {{
            transform: translateX(4px);
            border-color: rgba(245, 158, 11, 0.3);
        }}
        
        .queue-header {{
            display: flex;
            align-items: center;
            gap: 1rem;
            margin-bottom: 1rem;
        }}
        
        .queue-icon {{
            font-size: 1.75rem;
            width: 48px;
            height: 48px;
            display: flex;
            align-items: center;
            justify-content: center;
            background: var(--bg-card);
            border-radius: 12px;
            border: 1px solid var(--border-color);
        }}
        
        .queue-info {{ flex: 1; }}
        
        .queue-name {{
            font-weight: 600;
            font-size: 1rem;
            margin-bottom: 0.25rem;
        }}
        
        .queue-backend {{
            font-size: 0.75rem;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}
        
        .queue-status {{
            padding: 0.375rem 0.75rem;
            border-radius: 20px;
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
        }}
        
        .queue-status.active {{ background: rgba(16, 185, 129, 0.2); color: var(--success); }}
        .queue-status.error {{ background: rgba(239, 68, 68, 0.2); color: var(--error); }}
        .queue-status.idle {{ background: rgba(148, 163, 184, 0.2); color: var(--text-secondary); }}
        
        /* Metrics Grid */
        .metrics-grid {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 0.75rem;
        }}
        
        .metric-box {{
            background: var(--bg-card);
            border-radius: 8px;
            padding: 0.75rem;
            text-align: center;
        }}
        
        .metric-value {{
            font-size: 1.5rem;
            font-weight: 700;
            color: var(--accent-primary);
        }}
        
        .metric-label {{
            font-size: 0.7rem;
            color: var(--text-muted);
            text-transform: uppercase;
        }}
        
        /* Worker Cards */
        .worker-list {{
            display: flex;
            flex-direction: column;
            gap: 1rem;
        }}
        
        .worker-card {{
            background: var(--bg-secondary);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 1.25rem;
        }}
        
        .worker-header {{
            display: flex;
            align-items: center;
            gap: 1rem;
            margin-bottom: 1rem;
        }}
        
        .worker-icon {{
            font-size: 1.5rem;
            width: 44px;
            height: 44px;
            display: flex;
            align-items: center;
            justify-content: center;
            background: var(--bg-card);
            border-radius: 10px;
            border: 1px solid var(--border-color);
        }}
        
        .worker-info {{ flex: 1; }}
        
        .worker-name {{
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }}
        
        .status-indicator {{
            width: 8px;
            height: 8px;
            border-radius: 50%;
        }}
        
        .worker-stats {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 0.5rem;
        }}
        
        .stat-item {{
            text-align: center;
            padding: 0.5rem;
            background: var(--bg-card);
            border-radius: 6px;
        }}
        
        .stat-value {{
            font-size: 1.25rem;
            font-weight: 700;
        }}
        
        .stat-label {{
            font-size: 0.65rem;
            color: var(--text-muted);
            text-transform: uppercase;
        }}
        
        /* Empty State */
        .empty-state {{
            text-align: center;
            padding: 3rem;
            color: var(--text-muted);
        }}
        
        .empty-icon {{
            font-size: 3rem;
            margin-bottom: 1rem;
            opacity: 0.5;
        }}
        
        /* Loading Animation */
        .loading-skeleton {{
            background: linear-gradient(90deg, var(--bg-secondary) 25%, var(--bg-hover) 50%, var(--bg-secondary) 75%);
            background-size: 200% 100%;
            animation: shimmer 1.5s infinite;
            border-radius: 8px;
            height: 80px;
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
                <h1 class="header-title">⚡ Queues & Jobs</h1>
                <p class="header-subtitle">Real-time monitoring of message queues and background workers</p>
            </div>
        </header>
        
        <div class="dashboard-grid">
            <!-- Queues Section -->
            <div class="section-card">
                <div class="section-header">
                    <div class="section-title">
                        <div class="section-icon">📬</div>
                        Message Queues
                    </div>
                    <div class="live-indicator">
                        <div class="live-dot"></div>
                        Live
                    </div>
                </div>
                <div class="section-content">
                    <div class="queue-list" id="queues-list">
                        <div class="loading-skeleton"></div>
                        <div class="loading-skeleton"></div>
                    </div>
                </div>
            </div>
            
            <!-- Workers Section -->
            <div class="section-card">
                <div class="section-header">
                    <div class="section-title">
                        <div class="section-icon">👷</div>
                        Job Workers
                    </div>
                    <div class="live-indicator">
                        <div class="live-dot"></div>
                        Live
                    </div>
                </div>
                <div class="section-content">
                    <div class="worker-list" id="workers-list">
                        <div class="loading-skeleton"></div>
                        <div class="loading-skeleton"></div>
                        <div class="loading-skeleton"></div>
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
                renderQueues(data.queues || []);
                renderWorkers(data.jobs || {{}});
            }} catch (e) {{
                console.error('Failed to load state:', e);
            }}
        }}
        
        function renderQueues(queues) {{
            const container = document.getElementById('queues-list');
            if (!queues.length) {{
                container.innerHTML = `
                    <div class="empty-state">
                        <div class="empty-icon">📭</div>
                        <p>No queues configured</p>
                    </div>
                `;
                return;
            }}
            
            container.innerHTML = queues.map(q => {{
                const hasError = q.error;
                const statusClass = hasError ? 'error' : q.messages > 0 ? 'active' : 'idle';
                const statusText = hasError ? 'Error' : q.messages > 0 ? 'Active' : 'Idle';
                
                return `
                    <div class="queue-item">
                        <div class="queue-header">
                            <div class="queue-icon">${{q.icon || '📦'}}</div>
                            <div class="queue-info">
                                <div class="queue-name">${{q.name}}</div>
                                <div class="queue-backend">${{q.backend}}</div>
                            </div>
                            <span class="queue-status ${{statusClass}}">${{statusText}}</span>
                        </div>
                        ${{hasError ? `<p style="color: var(--error); font-size: 0.875rem;">${{q.error}}</p>` : `
                        <div class="metrics-grid">
                            <div class="metric-box">
                                <div class="metric-value">${{q.messages || 0}}</div>
                                <div class="metric-label">Messages</div>
                            </div>
                            <div class="metric-box">
                                <div class="metric-value">${{q.inFlight || 0}}</div>
                                <div class="metric-label">In Flight</div>
                            </div>
                            <div class="metric-box">
                                <div class="metric-value">${{q.delayed || 0}}</div>
                                <div class="metric-label">Delayed</div>
                            </div>
                        </div>
                        `}}
                    </div>
                `;
            }}).join('');
        }}
        
        function renderWorkers(jobs) {{
            const container = document.getElementById('workers-list');
            const workers = Object.entries(jobs);
            
            if (!workers.length) {{
                container.innerHTML = `
                    <div class="empty-state">
                        <div class="empty-icon">😴</div>
                        <p>No workers configured</p>
                    </div>
                `;
                return;
            }}
            
            container.innerHTML = workers.map(([name, info]) => {{
                const statusColor = info.status === 'active' ? 'var(--success)' : info.status === 'error' ? 'var(--error)' : 'var(--text-muted)';
                
                let statsHtml = '';
                if (name === 'celery') {{
                    statsHtml = `
                        <div class="stat-item"><div class="stat-value">${{info.workers || 0}}</div><div class="stat-label">Workers</div></div>
                        <div class="stat-item"><div class="stat-value">${{info.active || 0}}</div><div class="stat-label">Active</div></div>
                        <div class="stat-item"><div class="stat-value">${{info.enabled ? 'On' : 'Off'}}</div><div class="stat-label">Status</div></div>
                    `;
                }} else if (name === 'rq') {{
                    statsHtml = `
                        <div class="stat-item"><div class="stat-value">${{info.queueSize || 0}}</div><div class="stat-label">Queue</div></div>
                        <div class="stat-item"><div class="stat-value">${{info.failed || 0}}</div><div class="stat-label">Failed</div></div>
                        <div class="stat-item"><div class="stat-value">${{info.enabled ? 'On' : 'Off'}}</div><div class="stat-label">Status</div></div>
                    `;
                }} else {{
                    statsHtml = `
                        <div class="stat-item"><div class="stat-value">-</div><div class="stat-label">Queue</div></div>
                        <div class="stat-item"><div class="stat-value">-</div><div class="stat-label">Failed</div></div>
                        <div class="stat-item"><div class="stat-value">${{info.enabled ? 'On' : 'Off'}}</div><div class="stat-label">Status</div></div>
                    `;
                }}
                
                return `
                    <div class="worker-card">
                        <div class="worker-header">
                            <div class="worker-icon">${{info.icon || '⚙️'}}</div>
                            <div class="worker-info">
                                <div class="worker-name">
                                    <span class="status-indicator" style="background: ${{statusColor}};"></span>
                                    ${{name.charAt(0).toUpperCase() + name.slice(1)}}
                                </div>
                            </div>
                        </div>
                        <div class="worker-stats">${{statsHtml}}</div>
                    </div>
                `;
            }}).join('');
        }}
        
        loadState();
        setInterval(loadState, 5000);
    </script>
</body>
</html>"""
    return HTMLResponse(content=html)


@router.get("/state", response_class=JSONResponse, summary="Queues & jobs state")
async def queues_state() -> JSONResponse:
    """Return JSON snapshot of queues and worker state."""
    q_cfg = _get_queues_config()
    queues: List[Dict[str, Any]] = []

    if q_cfg is not None:
        rabbit_info = _inspect_rabbitmq(q_cfg.rabbitmq)
        if rabbit_info is not None:
            queues.append(rabbit_info)
        sqs_info = _inspect_sqs(q_cfg.sqs)
        if sqs_info is not None:
            queues.append(sqs_info)

    jobs = _inspect_jobs()
    return JSONResponse({"queues": queues, "jobs": jobs})


__all__ = ["router"]
