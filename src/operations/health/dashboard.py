"""Visual health dashboard for core services with beautiful UI.

Provides a stunning HTML dashboard at `/dashboard/health` showing the
status of enabled infrastructure services.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from loguru import logger
from sqlalchemy import text

from fast_dashboards.core.registry import registry
from fast_dashboards.core.seo import render_dashboard_inline_head

# Lazy imports for datastores - resolved at runtime via registry
_datastore_classes: Dict[str, Any] = {}


def _get_datastore_class(name: str) -> Optional[Any]:
    """Get datastore class lazily via registry."""
    if name not in _datastore_classes:
        klass = registry.get_datastore_class(name)
        _datastore_classes[name] = klass
    return _datastore_classes[name]


router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


def _bool_env(name: str, default: str = "false") -> bool:
    """Execute _bool_env operation.

    Args:
        name: The name parameter.
        default: The default parameter.

    Returns:
        The result of the operation.
    """
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


def _check_postgres() -> Dict[str, Any]:
    """Execute _check_postgres operation.

    Returns:
        The result of the operation.
    """
    db_session = registry.get_db_session()
    enabled = db_session is not None
    status = "skipped"
    message = "Database not configured"
    icon = "🐘"
    color = "#94a3b8"
    if not enabled:
        return {
            "name": "PostgreSQL",
            "key": "postgres",
            "enabled": False,
            "status": status,
            "message": message,
            "icon": icon,
            "color": color,
        }

    try:
        db_session.execute(text("SELECT 1"))
        status = "healthy"
        message = "Connected"
        color = "#10b981"
    except Exception as exc:
        logger.error(f"PostgreSQL health check failed: {exc}")
        status = "unhealthy"
        message = f"{exc}"[:50]
        color = "#ef4444"
    return {
        "name": "PostgreSQL",
        "key": "postgres",
        "enabled": True,
        "status": status,
        "message": message,
        "icon": icon,
        "color": color,
    }


def _check_redis() -> Dict[str, Any]:
    """Execute _check_redis operation.

    Returns:
        The result of the operation.
    """
    redis_session = registry.get_redis_session()
    enabled = redis_session is not None
    status = "skipped"
    message = "Redis not configured"
    icon = "⚡"
    color = "#94a3b8"
    if not enabled:
        return {
            "name": "Redis",
            "key": "redis",
            "enabled": False,
            "status": status,
            "message": message,
            "icon": icon,
            "color": color,
        }

    try:
        if redis_session.ping():
            status = "healthy"
            message = "Connected"
            color = "#10b981"
        else:
            status = "unhealthy"
            message = "Ping failed"
            color = "#ef4444"
    except Exception as exc:
        logger.error(f"Redis health check failed: {exc}")
        status = "unhealthy"
        message = str(exc)[:50]
        color = "#ef4444"
    return {
        "name": "Redis",
        "key": "redis",
        "enabled": True,
        "status": status,
        "message": message,
        "icon": icon,
        "color": color,
    }


def _check_mongo() -> Dict[str, Any]:
    """Execute _check_mongo operation.

    Returns:
        The result of the operation.
    """
    enabled = _bool_env("MONGO_ENABLED", "false")
    icon = "🍃"
    color = "#94a3b8"
    if not enabled:
        return {
            "name": "MongoDB",
            "key": "mongo",
            "enabled": False,
            "status": "skipped",
            "message": "Disabled",
            "icon": icon,
            "color": color,
        }

    try:
        MongoDocumentStore = _get_datastore_class("MongoDocumentStore")
        if MongoDocumentStore is None:
            return {
                "name": "MongoDB",
                "key": "mongo",
                "enabled": True,
                "status": "unhealthy",
                "message": "Store not available",
                "icon": icon,
                "color": "#ef4444",
            }
        store = MongoDocumentStore(
            uri=os.getenv("MONGO_URI", "mongodb://localhost:27017"),
            database=os.getenv("MONGO_DATABASE", "admin"),
        )
        store.connect()
        db = store.get_database()
        db.command("ping")
        store.disconnect()
        return {
            "name": "MongoDB",
            "key": "mongo",
            "enabled": True,
            "status": "healthy",
            "message": "Connected",
            "icon": icon,
            "color": "#10b981",
        }
    except Exception as exc:
        logger.error(f"MongoDB health check failed: {exc}")
        return {
            "name": "MongoDB",
            "key": "mongo",
            "enabled": True,
            "status": "unhealthy",
            "message": str(exc)[:50],
            "icon": icon,
            "color": "#ef4444",
        }


def _check_cassandra() -> Dict[str, Any]:
    """Execute _check_cassandra operation.

    Returns:
        The result of the operation.
    """
    enabled = _bool_env("CASSANDRA_ENABLED", "false")
    icon = "🔱"
    color = "#94a3b8"
    if not enabled:
        return {
            "name": "Cassandra",
            "key": "cassandra",
            "enabled": False,
            "status": "skipped",
            "message": "Disabled",
            "icon": icon,
            "color": color,
        }

    try:
        CassandraWideColumnStore = _get_datastore_class("CassandraWideColumnStore")
        if CassandraWideColumnStore is None:
            return {
                "name": "Cassandra",
                "key": "cassandra",
                "enabled": True,
                "status": "unhealthy",
                "message": "Store not available",
                "icon": icon,
                "color": "#ef4444",
            }
        store = CassandraWideColumnStore(
            contact_points=os.getenv("CASSANDRA_CONTACT_POINTS", "127.0.0.1").split(
                ","
            ),
            port=int(os.getenv("CASSANDRA_PORT", "9042")),
            keyspace=os.getenv("CASSANDRA_KEYSPACE"),
        )
        store.connect()
        store.execute("SELECT release_version FROM system.local")
        store.disconnect()
        return {
            "name": "Cassandra",
            "key": "cassandra",
            "enabled": True,
            "status": "healthy",
            "message": "Connected",
            "icon": icon,
            "color": "#10b981",
        }
    except Exception as exc:
        logger.error(f"Cassandra health check failed: {exc}")
        return {
            "name": "Cassandra",
            "key": "cassandra",
            "enabled": True,
            "status": "unhealthy",
            "message": str(exc)[:50],
            "icon": icon,
            "color": "#ef4444",
        }


def _check_scylla() -> Dict[str, Any]:
    """Execute _check_scylla operation.

    Returns:
        The result of the operation.
    """
    enabled = _bool_env("SCYLLA_ENABLED", "false")
    icon = "🌊"
    color = "#94a3b8"
    if not enabled:
        return {
            "name": "ScyllaDB",
            "key": "scylla",
            "enabled": False,
            "status": "skipped",
            "message": "Disabled",
            "icon": icon,
            "color": color,
        }

    try:
        ScyllaWideColumnStore = _get_datastore_class("ScyllaWideColumnStore")
        if ScyllaWideColumnStore is None:
            return {
                "name": "ScyllaDB",
                "key": "scylla",
                "enabled": True,
                "status": "unhealthy",
                "message": "Store not available",
                "icon": icon,
                "color": "#ef4444",
            }
        store = ScyllaWideColumnStore(
            contact_points=os.getenv("SCYLLA_CONTACT_POINTS", "127.0.0.1").split(","),
            port=int(os.getenv("SCYLLA_PORT", "9042")),
            keyspace=os.getenv("SCYLLA_KEYSPACE"),
        )
        store.connect()
        store.execute("SELECT release_version FROM system.local")
        store.disconnect()
        return {
            "name": "ScyllaDB",
            "key": "scylla",
            "enabled": True,
            "status": "healthy",
            "message": "Connected",
            "icon": icon,
            "color": "#10b981",
        }
    except Exception as exc:
        logger.error(f"ScyllaDB health check failed: {exc}")
        return {
            "name": "ScyllaDB",
            "key": "scylla",
            "enabled": True,
            "status": "unhealthy",
            "message": str(exc)[:50],
            "icon": icon,
            "color": "#ef4444",
        }


def _check_dynamo() -> Dict[str, Any]:
    """Execute _check_dynamo operation.

    Returns:
        The result of the operation.
    """
    enabled = _bool_env("DYNAMO_ENABLED", "false")
    icon = "📦"
    color = "#94a3b8"
    if not enabled:
        return {
            "name": "DynamoDB",
            "key": "dynamo",
            "enabled": False,
            "status": "skipped",
            "message": "Disabled",
            "icon": icon,
            "color": color,
        }

    try:
        DynamoKeyValueStore = _get_datastore_class("DynamoKeyValueStore")
        if DynamoKeyValueStore is None:
            return {
                "name": "DynamoDB",
                "key": "dynamo",
                "enabled": True,
                "status": "unhealthy",
                "message": "Store not available",
                "icon": icon,
                "color": "#ef4444",
            }
        store = DynamoKeyValueStore(
            table_name="healthcheck",
            region_name=os.getenv("DYNAMO_REGION", "us-east-1"),
        )
        store.connect()
        store.disconnect()
        return {
            "name": "DynamoDB",
            "key": "dynamo",
            "enabled": True,
            "status": "healthy",
            "message": f"Region: {os.getenv('DYNAMO_REGION', 'us-east-1')}",
            "icon": icon,
            "color": "#10b981",
        }
    except Exception as exc:
        logger.error(f"DynamoDB health check failed: {exc}")
        return {
            "name": "DynamoDB",
            "key": "dynamo",
            "enabled": True,
            "status": "unhealthy",
            "message": str(exc)[:50],
            "icon": icon,
            "color": "#ef4444",
        }


def _check_cosmos() -> Dict[str, Any]:
    """Execute _check_cosmos operation.

    Returns:
        The result of the operation.
    """
    enabled = _bool_env("COSMOS_ENABLED", "false")
    icon = "🌌"
    color = "#94a3b8"
    if not enabled:
        return {
            "name": "Cosmos DB",
            "key": "cosmos",
            "enabled": False,
            "status": "skipped",
            "message": "Disabled",
            "icon": icon,
            "color": color,
        }

    try:
        CosmosDocumentStore = _get_datastore_class("CosmosDocumentStore")
        if CosmosDocumentStore is None:
            return {
                "name": "Cosmos DB",
                "key": "cosmos",
                "enabled": True,
                "status": "unhealthy",
                "message": "Store not available",
                "icon": icon,
                "color": "#ef4444",
            }
        store = CosmosDocumentStore(
            account_uri=os.getenv("COSMOS_ACCOUNT_URI", ""),
            account_key=os.getenv("COSMOS_ACCOUNT_KEY", ""),
            database=os.getenv("COSMOS_DATABASE", "fastmvc"),
        )
        store.connect()
        _ = store.get_database()
        store.disconnect()
        return {
            "name": "Cosmos DB",
            "key": "cosmos",
            "enabled": True,
            "status": "healthy",
            "message": "Connected",
            "icon": icon,
            "color": "#10b981",
        }
    except Exception as exc:
        logger.error(f"Cosmos DB health check failed: {exc}")
        return {
            "name": "Cosmos DB",
            "key": "cosmos",
            "enabled": True,
            "status": "unhealthy",
            "message": str(exc)[:50],
            "icon": icon,
            "color": "#ef4444",
        }


def _check_elasticsearch() -> Dict[str, Any]:
    """Execute _check_elasticsearch operation.

    Returns:
        The result of the operation.
    """
    enabled = _bool_env("ELASTICSEARCH_ENABLED", "false")
    icon = "🔍"
    color = "#94a3b8"
    if not enabled:
        return {
            "name": "Elasticsearch",
            "key": "elasticsearch",
            "enabled": False,
            "status": "skipped",
            "message": "Disabled",
            "icon": icon,
            "color": color,
        }

    try:
        ElasticsearchSearchStore = _get_datastore_class("ElasticsearchSearchStore")
        if ElasticsearchSearchStore is None:
            return {
                "name": "Elasticsearch",
                "key": "elasticsearch",
                "enabled": True,
                "status": "unhealthy",
                "message": "Store not available",
                "icon": icon,
                "color": "#ef4444",
            }
        hosts = [
            h.strip()
            for h in os.getenv("ELASTICSEARCH_HOSTS", "http://localhost:9200").split(
                ","
            )
            if h.strip()
        ]
        store = ElasticsearchSearchStore(
            hosts=hosts,
            username=os.getenv("ELASTICSEARCH_USERNAME"),
            password=os.getenv("ELASTICSEARCH_PASSWORD"),
        )
        store.connect()
        healthy = store.ping()
        store.disconnect()
        status = "healthy" if healthy else "unhealthy"
        message = "Connected" if healthy else "Ping failed"
        color = "#10b981" if healthy else "#ef4444"
        return {
            "name": "Elasticsearch",
            "key": "elasticsearch",
            "enabled": True,
            "status": status,
            "message": message,
            "icon": icon,
            "color": color,
        }
    except Exception as exc:
        logger.error(f"Elasticsearch health check failed: {exc}")
        return {
            "name": "Elasticsearch",
            "key": "elasticsearch",
            "enabled": True,
            "status": "unhealthy",
            "message": str(exc)[:50],
            "icon": icon,
            "color": "#ef4444",
        }


def _gather_services() -> List[Dict[str, Any]]:
    """Execute _gather_services operation.

    Returns:
        The result of the operation.
    """
    return [
        _check_postgres(),
        _check_redis(),
        _check_mongo(),
        _check_cassandra(),
        _check_scylla(),
        _check_dynamo(),
        _check_cosmos(),
        _check_elasticsearch(),
    ]


def _get_status_summary(services: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Generate status summary for visualization."""
    total = len(services)
    healthy = sum(1 for s in services if s["status"] == "healthy")
    unhealthy = sum(1 for s in services if s["status"] == "unhealthy")
    skipped = sum(1 for s in services if s["status"] == "skipped")
    enabled = sum(1 for s in services if s["enabled"])

    overall_status = (
        "healthy"
        if unhealthy == 0 and healthy > 0
        else "warning"
        if unhealthy == 0
        else "critical"
    )

    return {
        "total": total,
        "healthy": healthy,
        "unhealthy": unhealthy,
        "skipped": skipped,
        "enabled": enabled,
        "overall_status": overall_status,
        "health_percent": round((healthy / enabled * 100) if enabled > 0 else 0.0, 1),
    }


@router.get("/health", response_class=HTMLResponse, summary="Health Dashboard")
async def health_dashboard() -> HTMLResponse:
    """Render a beautiful HTML dashboard showing health status."""
    services = _gather_services()
    summary = _get_status_summary(services)

    _head_seo = render_dashboard_inline_head(
        page_title="FastMVC Service Health",
        description="Live health checks for PostgreSQL, Redis, MongoDB, Elasticsearch, Cassandra, Scylla, DynamoDB, and Cosmos DB.",
        path="/dashboard/health",
    )

    # Build service cards
    service_cards = []
    for svc in services:
        pulse_animation = "pulse-animation" if svc["status"] == "healthy" else ""
        status_dot = f'<span class="status-dot {pulse_animation}" style="background: {svc["color"]}; box-shadow: 0 0 12px {svc["color"]};"></span>'
        card_html = f"""
        <div class="service-card" data-status="{svc["status"]}">
            <div class="service-header">
                <div class="service-icon">{svc["icon"]}</div>
                <div class="service-info">
                    <h3>{svc["name"]}</h3>
                    <span class="service-key">{svc["key"]}</span>
                </div>
                {status_dot}
            </div>
            <div class="service-body">
                <div class="status-badge" style="background: {svc["color"]}20; color: {svc["color"]}; border-color: {svc["color"]}40;">
                    {svc["status"].upper()}
                </div>
                <p class="service-message">{svc["message"]}</p>
            </div>
            <div class="service-footer">
                <span class="mode-badge">{"Enabled" if svc["enabled"] else "Disabled"}</span>
            </div>
        </div>
        """
        service_cards.append(card_html)

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
            --accent-primary: #6366f1;
            --accent-secondary: #8b5cf6;
            --accent-gradient: linear-gradient(135deg, #6366f1 0%, #8b5cf6 50%, #a855f7 100%);
            --success: #10b981;
            --warning: #f59e0b;
            --error: #ef4444;
            --border-color: rgba(148, 163, 184, 0.1);
            --shadow-sm: 0 1px 2px 0 rgba(0, 0, 0, 0.3);
            --shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.4), 0 2px 4px -1px rgba(0, 0, 0, 0.2);
            --shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.5), 0 4px 6px -2px rgba(0, 0, 0, 0.3);
            --shadow-glow: 0 0 40px rgba(99, 102, 241, 0.15);
        }}
        
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            min-height: 100vh;
            line-height: 1.6;
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
            background: radial-gradient(ellipse at top, rgba(99, 102, 241, 0.15) 0%, transparent 70%);
            pointer-events: none;
            z-index: 0;
        }}
        
        .header-content {{
            position: relative;
            z-index: 1;
        }}
        
        .header-title {{
            font-size: 2.5rem;
            font-weight: 700;
            background: var(--accent-gradient);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            margin-bottom: 0.5rem;
            display: flex;
            align-items: center;
            gap: 1rem;
        }}
        
        .header-title::before {{
            content: '◆';
            font-size: 1.5rem;
            -webkit-text-fill-color: #6366f1;
        }}
        
        .header-subtitle {{
            color: var(--text-secondary);
            font-size: 1.1rem;
            max-width: 600px;
        }}
        
        /* Summary Cards */
        .summary-section {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1rem;
            margin-bottom: 2rem;
        }}
        
        .summary-card {{
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 16px;
            padding: 1.5rem;
            position: relative;
            overflow: hidden;
            transition: all 0.3s ease;
        }}
        
        .summary-card:hover {{
            transform: translateY(-2px);
            box-shadow: var(--shadow-lg);
        }}
        
        .summary-card::before {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 3px;
            background: var(--accent-gradient);
        }}
        
        .summary-card.critical::before {{ background: var(--error); }}
        .summary-card.warning::before {{ background: var(--warning); }}
        .summary-card.healthy::before {{ background: var(--success); }}
        
        .summary-value {{
            font-size: 2.5rem;
            font-weight: 700;
            margin-bottom: 0.25rem;
        }}
        
        .summary-label {{
            color: var(--text-secondary);
            font-size: 0.875rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}
        
        .summary-card.healthy .summary-value {{ color: var(--success); }}
        .summary-card.warning .summary-value {{ color: var(--warning); }}
        .summary-card.critical .summary-value {{ color: var(--error); }}
        
        /* Services Grid */
        .services-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 1.5rem;
        }}
        
        .service-card {{
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 16px;
            padding: 1.5rem;
            transition: all 0.3s ease;
            position: relative;
            overflow: hidden;
        }}
        
        .service-card::before {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            width: 4px;
            height: 100%;
            background: var(--text-muted);
            transition: all 0.3s ease;
        }}
        
        .service-card[data-status="healthy"]::before {{ background: var(--success); }}
        .service-card[data-status="unhealthy"]::before {{ background: var(--error); }}
        .service-card[data-status="skipped"]::before {{ background: var(--text-muted); }}
        
        .service-card:hover {{
            transform: translateY(-4px);
            box-shadow: var(--shadow-lg), var(--shadow-glow);
            border-color: rgba(99, 102, 241, 0.3);
        }}
        
        .service-header {{
            display: flex;
            align-items: center;
            gap: 1rem;
            margin-bottom: 1rem;
        }}
        
        .service-icon {{
            font-size: 2rem;
            width: 48px;
            height: 48px;
            display: flex;
            align-items: center;
            justify-content: center;
            background: var(--bg-secondary);
            border-radius: 12px;
            border: 1px solid var(--border-color);
        }}
        
        .service-info {{
            flex: 1;
        }}
        
        .service-info h3 {{
            font-size: 1.1rem;
            font-weight: 600;
            margin-bottom: 0.25rem;
        }}
        
        .service-key {{
            font-size: 0.75rem;
            color: var(--text-muted);
            font-family: 'Monaco', 'Consolas', monospace;
            text-transform: lowercase;
        }}
        
        .status-dot {{
            width: 12px;
            height: 12px;
            border-radius: 50%;
            display: inline-block;
        }}
        
        .pulse-animation {{
            animation: pulse 2s infinite;
        }}
        
        @keyframes pulse {{
            0%, 100% {{ opacity: 1; }}
            50% {{ opacity: 0.5; }}
        }}
        
        .service-body {{
            margin-bottom: 1rem;
        }}
        
        .status-badge {{
            display: inline-block;
            padding: 0.375rem 0.75rem;
            border-radius: 20px;
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            border: 1px solid;
            margin-bottom: 0.75rem;
        }}
        
        .service-message {{
            color: var(--text-secondary);
            font-size: 0.875rem;
            line-height: 1.5;
        }}
        
        .service-footer {{
            display: flex;
            justify-content: flex-end;
        }}
        
        .mode-badge {{
            font-size: 0.75rem;
            color: var(--text-muted);
            padding: 0.25rem 0.5rem;
            background: var(--bg-secondary);
            border-radius: 4px;
        }}
        
        /* Refresh Indicator */
        .refresh-indicator {{
            position: fixed;
            bottom: 2rem;
            right: 2rem;
            display: flex;
            align-items: center;
            gap: 0.75rem;
            padding: 0.75rem 1.25rem;
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 50px;
            font-size: 0.875rem;
            color: var(--text-secondary);
            box-shadow: var(--shadow-lg);
        }}
        
        .refresh-spinner {{
            width: 16px;
            height: 16px;
            border: 2px solid var(--border-color);
            border-top-color: var(--accent-primary);
            border-radius: 50%;
            animation: spin 1s linear infinite;
        }}
        
        @keyframes spin {{
            to {{ transform: rotate(360deg); }}
        }}
        
        /* Responsive */
        @media (max-width: 768px) {{
            .dashboard-container {{
                padding: 1rem;
            }}
            
            .header-title {{
                font-size: 1.75rem;
            }}
            
            .services-grid {{
                grid-template-columns: 1fr;
            }}
        }}
    </style>
</head>
<body>
    <div class="dashboard-container">
        <header class="header">
            <div class="header-content">
                <h1 class="header-title">Service Health</h1>
                <p class="header-subtitle">Real-time monitoring of your infrastructure services and datastores</p>
            </div>
        </header>
        
        <section class="summary-section">
            <div class="summary-card {summary["overall_status"]}">
                <div class="summary-value">{summary["health_percent"]}%</div>
                <div class="summary-label">Health Score</div>
            </div>
            <div class="summary-card healthy">
                <div class="summary-value">{summary["healthy"]}</div>
                <div class="summary-label">Healthy</div>
            </div>
            <div class="summary-card critical">
                <div class="summary-value">{summary["unhealthy"]}</div>
                <div class="summary-label">Unhealthy</div>
            </div>
            <div class="summary-card">
                <div class="summary-value">{summary["skipped"]}</div>
                <div class="summary-label">Disabled</div>
            </div>
        </section>
        
        <div class="services-grid">
            {"".join(service_cards)}
        </div>
    </div>
    
    <div class="refresh-indicator">
        <div class="refresh-spinner"></div>
        <span>Auto-refreshing...</span>
    </div>
    
    <script>
        // Auto-refresh every 10 seconds
        setInterval(() => {{
            fetch(window.location.pathname)
                .then(response => response.text())
                .then(html => {{
                    const parser = new DOMParser();
                    const doc = parser.parseFromString(html, 'text/html');
                    const newGrid = doc.querySelector('.services-grid');
                    if (newGrid) {{
                        document.querySelector('.services-grid').innerHTML = newGrid.innerHTML;
                    }}
                    const newSummary = doc.querySelector('.summary-section');
                    if (newSummary) {{
                        document.querySelector('.summary-section').innerHTML = newSummary.innerHTML;
                    }}
                }})
                .catch(err => console.error('Refresh failed:', err));
        }}, 10000);
    </script>
</body>
</html>"""
    return HTMLResponse(content=html)
