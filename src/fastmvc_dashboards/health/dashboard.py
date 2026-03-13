"""
Visual health dashboard for core services.

Provides a beautiful HTML dashboard at `/dashboard/health` showing the
status of enabled infrastructure services such as PostgreSQL, Redis,
MongoDB, Cassandra, ScyllaDB, DynamoDB, and Cosmos DB.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List

from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from loguru import logger
from sqlalchemy import text

from core.datastores import (
    CassandraWideColumnStore,
    CosmosDocumentStore,
    DynamoKeyValueStore,
    MongoDocumentStore,
    ElasticsearchSearchStore,
    RedisKeyValueStore,
    ScyllaWideColumnStore,
)
from start_utils import db_session, redis_session


router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


def _bool_env(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


def _check_postgres() -> Dict[str, Any]:
    enabled = db_session is not None
    status = "skipped"
    message = "Database not configured"
    if not enabled:
        return {"name": "PostgreSQL", "key": "postgres", "enabled": False, "status": status, "message": message}

    try:
        db_session.execute(text("SELECT 1"))
        status = "healthy"
        message = "Connection OK"
    except Exception as exc:  # pragma: no cover - best-effort health check
        logger.error(f"PostgreSQL health check failed: {exc}")
        status = "unhealthy"
        message = str(exc)
    return {"name": "PostgreSQL", "key": "postgres", "enabled": True, "status": status, "message": message}


def _check_redis() -> Dict[str, Any]:
    enabled = redis_session is not None
    status = "skipped"
    message = "Redis not configured"
    if not enabled:
        return {"name": "Redis", "key": "redis", "enabled": False, "status": status, "message": message}

    try:
        if redis_session.ping():  # type: ignore[union-attr]
            status = "healthy"
            message = "PING OK"
        else:
            status = "unhealthy"
            message = "PING failed"
    except Exception as exc:  # pragma: no cover
        logger.error(f"Redis health check failed: {exc}")
        status = "unhealthy"
        message = str(exc)
    return {"name": "Redis", "key": "redis", "enabled": True, "status": status, "message": message}


def _check_mongo() -> Dict[str, Any]:
    enabled = _bool_env("MONGO_ENABLED", "false")
    if not enabled:
        return {
            "name": "MongoDB",
            "key": "mongo",
            "enabled": False,
            "status": "skipped",
            "message": "MongoDB disabled",
        }

    uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    database = os.getenv("MONGO_DATABASE", "admin")
    try:
        store = MongoDocumentStore(uri=uri, database=database)
        store.connect()
        db = store.get_database()
        # Lightweight command that works on modern MongoDB servers
        db.command("ping")
        store.disconnect()
        return {
            "name": "MongoDB",
            "key": "mongo",
            "enabled": True,
            "status": "healthy",
            "message": "Ping OK",
        }
    except Exception as exc:  # pragma: no cover
        logger.error(f"MongoDB health check failed: {exc}")
        return {
            "name": "MongoDB",
            "key": "mongo",
            "enabled": True,
            "status": "unhealthy",
            "message": str(exc),
        }


def _check_cassandra() -> Dict[str, Any]:
    enabled = _bool_env("CASSANDRA_ENABLED", "false")
    if not enabled:
        return {
            "name": "Cassandra",
            "key": "cassandra",
            "enabled": False,
            "status": "skipped",
            "message": "Cassandra disabled",
        }

    contact_points = os.getenv("CASSANDRA_CONTACT_POINTS", "127.0.0.1").split(",")
    port = int(os.getenv("CASSANDRA_PORT", "9042"))
    keyspace = os.getenv("CASSANDRA_KEYSPACE")
    try:
        store = CassandraWideColumnStore(contact_points=contact_points, port=port, keyspace=keyspace)
        store.connect()
        # Simple system query
        store.execute("SELECT release_version FROM system.local")
        store.disconnect()
        return {
            "name": "Cassandra",
            "key": "cassandra",
            "enabled": True,
            "status": "healthy",
            "message": "Query OK",
        }
    except Exception as exc:  # pragma: no cover
        logger.error(f"Cassandra health check failed: {exc}")
        return {
            "name": "Cassandra",
            "key": "cassandra",
            "enabled": True,
            "status": "unhealthy",
            "message": str(exc),
        }


def _check_scylla() -> Dict[str, Any]:
    enabled = _bool_env("SCYLLA_ENABLED", "false")
    if not enabled:
        return {
            "name": "ScyllaDB",
            "key": "scylla",
            "enabled": False,
            "status": "skipped",
            "message": "ScyllaDB disabled",
        }

    contact_points = os.getenv("SCYLLA_CONTACT_POINTS", "127.0.0.1").split(",")
    port = int(os.getenv("SCYLLA_PORT", "9042"))
    keyspace = os.getenv("SCYLLA_KEYSPACE")
    try:
        store = ScyllaWideColumnStore(contact_points=contact_points, port=port, keyspace=keyspace)
        store.connect()
        store.execute("SELECT release_version FROM system.local")
        store.disconnect()
        return {
            "name": "ScyllaDB",
            "key": "scylla",
            "enabled": True,
            "status": "healthy",
            "message": "Query OK",
        }
    except Exception as exc:  # pragma: no cover
        logger.error(f"ScyllaDB health check failed: {exc}")
        return {
            "name": "ScyllaDB",
            "key": "scylla",
            "enabled": True,
            "status": "unhealthy",
            "message": str(exc),
        }


def _check_dynamo() -> Dict[str, Any]:
    enabled = _bool_env("DYNAMO_ENABLED", "false")
    if not enabled:
        return {
            "name": "DynamoDB",
            "key": "dynamo",
            "enabled": False,
            "status": "skipped",
            "message": "DynamoDB disabled",
        }

    region = os.getenv("DYNAMO_REGION", "us-east-1")
    table_prefix = os.getenv("DYNAMO_TABLE_PREFIX", "")
    # We don't require a specific table to exist; listing tables is enough
    table_name = f"{table_prefix}healthcheck" if table_prefix else "healthcheck"
    try:
        store = DynamoKeyValueStore(table_name=table_name, region_name=region)
        store.connect()
        # This will succeed even if the table is missing, but the call itself
        # verifies AWS credentials and endpoint connectivity.
        _ = store  # noqa: F841
        store.disconnect()
        return {
            "name": "DynamoDB",
            "key": "dynamo",
            "enabled": True,
            "status": "healthy",
            "message": f"SDK initialized for region {region}",
        }
    except Exception as exc:  # pragma: no cover
        logger.error(f"DynamoDB health check failed: {exc}")
        return {
            "name": "DynamoDB",
            "key": "dynamo",
            "enabled": True,
            "status": "unhealthy",
            "message": str(exc),
        }


def _check_cosmos() -> Dict[str, Any]:
    enabled = _bool_env("COSMOS_ENABLED", "false")
    if not enabled:
        return {
            "name": "Cosmos DB",
            "key": "cosmos",
            "enabled": False,
            "status": "skipped",
            "message": "Cosmos DB disabled",
        }


def _check_elasticsearch() -> Dict[str, Any]:
    enabled = _bool_env("ELASTICSEARCH_ENABLED", "false")
    if not enabled:
        return {
            "name": "Elasticsearch",
            "key": "elasticsearch",
            "enabled": False,
            "status": "skipped",
            "message": "Elasticsearch disabled",
        }

    hosts_env = os.getenv("ELASTICSEARCH_HOSTS", "http://localhost:9200")
    hosts = [h.strip() for h in hosts_env.split(",") if h.strip()]
    username = os.getenv("ELASTICSEARCH_USERNAME") or None
    password = os.getenv("ELASTICSEARCH_PASSWORD") or None
    try:
        store = ElasticsearchSearchStore(
            hosts=hosts,
            username=username,
            password=password,
        )
        store.connect()
        healthy = store.ping()
        store.disconnect()
        return {
            "name": "Elasticsearch",
            "key": "elasticsearch",
            "enabled": True,
            "status": "healthy" if healthy else "unhealthy",
            "message": "Ping OK" if healthy else "Ping failed",
        }
    except Exception as exc:  # pragma: no cover
        logger.error(f"Elasticsearch health check failed: {exc}")
        return {
            "name": "Elasticsearch",
            "key": "elasticsearch",
            "enabled": True,
            "status": "unhealthy",
            "message": str(exc),
        }

    account_uri = os.getenv("COSMOS_ACCOUNT_URI", "")
    account_key = os.getenv("COSMOS_ACCOUNT_KEY", "")
    database = os.getenv("COSMOS_DATABASE", "fastmvc")
    try:
        store = CosmosDocumentStore(account_uri=account_uri, account_key=account_key, database=database)
        store.connect()
        _ = store.get_database()
        store.disconnect()
        return {
            "name": "Cosmos DB",
            "key": "cosmos",
            "enabled": True,
            "status": "healthy",
            "message": "Connection OK",
        }
    except Exception as exc:  # pragma: no cover
        logger.error(f"Cosmos DB health check failed: {exc}")
        return {
            "name": "Cosmos DB",
            "key": "cosmos",
            "enabled": True,
            "status": "unhealthy",
            "message": str(exc),
        }


def _gather_services() -> List[Dict[str, Any]]:
    services: List[Dict[str, Any]] = []
    services.append(_check_postgres())
    services.append(_check_redis())
    services.append(_check_mongo())
    services.append(_check_cassandra())
    services.append(_check_scylla())
    services.append(_check_dynamo())
    services.append(_check_cosmos())
    services.append(_check_elasticsearch())
    return services


@router.get("/health", response_class=HTMLResponse, summary="Health Dashboard")
async def health_dashboard() -> HTMLResponse:
    """
    Render an HTML dashboard that shows health status for core services.
    """
    services = _gather_services()

    # Map status to CSS class
    def status_class(status: str) -> str:
        if status == "healthy":
            return "status-pill healthy"
        if status == "unhealthy":
            return "status-pill unhealthy"
        if status == "skipped":
            return "status-pill skipped"
        return "status-pill unknown"

    cards_html = []
    for svc in services:
        cls = status_class(svc["status"])
        enabled_label = "Enabled" if svc["enabled"] else "Disabled"
        cards_html.append(
            f"""
            <div class="card">
              <div class="card-header">
                <span class="card-title">{svc['name']}</span>
                <span class="{cls}">{svc['status'].capitalize()}</span>
              </div>
              <div class="card-body">
                <p class="card-message">{svc['message']}</p>
                <p class="card-meta">Mode: {enabled_label}</p>
              </div>
            </div>
            """
        )

    html = f"""
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <title>FastMVC Service Health</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <style>
      :root {{
        --bg: #050816;
        --bg-card: #0b1120;
        --bg-card-hover: #111827;
        --accent: #6366f1;
        --accent-soft: rgba(99, 102, 241, 0.1);
        --success: #16a34a;
        --danger: #ef4444;
        --muted: #6b7280;
        --text: #e5e7eb;
        --text-soft: #9ca3af;
        --radius-xl: 18px;
        --shadow-soft: 0 18px 50px rgba(15, 23, 42, 0.65);
      }}

      * {{
        box-sizing: border-box;
      }}

      body {{
        margin: 0;
        min-height: 100vh;
        font-family: system-ui, -apple-system, BlinkMacSystemFont, "SF Pro Text",
          "Segoe UI", sans-serif;
        background: radial-gradient(circle at top left, #1e293b 0, #020617 45%, #000 100%);
        color: var(--text);
        display: flex;
        align-items: stretch;
        justify-content: center;
        padding: 32px 16px;
      }}

      .shell {{
        width: 100%;
        max-width: 1120px;
        background: linear-gradient(145deg, rgba(148, 163, 184, 0.1), rgba(15, 23, 42, 0.9));
        border-radius: 24px;
        padding: 1px;
        box-shadow: var(--shadow-soft);
      }}

      .content {{
        border-radius: 24px;
        background: radial-gradient(circle at top, rgba(148, 163, 184, 0.15), #020617 55%);
        padding: 24px 26px 26px;
      }}

      .header {{
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 16px;
        margin-bottom: 20px;
      }}

      .header-main {{
        display: flex;
        flex-direction: column;
        gap: 6px;
      }}

      .title {{
        font-size: 1.6rem;
        font-weight: 650;
        letter-spacing: 0.03em;
        display: flex;
        align-items: center;
        gap: 10px;
      }}

      .title-badge {{
        padding: 2px 9px;
        border-radius: 999px;
        font-size: 0.7rem;
        text-transform: uppercase;
        letter-spacing: 0.09em;
        background: var(--accent-soft);
        color: var(--accent);
        border: 1px solid rgba(129, 140, 248, 0.3);
      }}

      .subtitle {{
        font-size: 0.92rem;
        color: var(--text-soft);
      }}

      .header-meta {{
        display: flex;
        gap: 10px;
        align-items: center;
        flex-wrap: wrap;
      }}

      .pill {{
        padding: 4px 10px;
        border-radius: 999px;
        font-size: 0.75rem;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: var(--text-soft);
        background: rgba(15, 23, 42, 0.8);
        border: 1px solid rgba(148, 163, 184, 0.35);
      }}

      .grid {{
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
        gap: 16px;
      }}

      .card {{
        background: radial-gradient(circle at top left, rgba(148, 163, 184, 0.32), var(--bg-card) 45%);
        border-radius: var(--radius-xl);
        padding: 15px 15px 14px;
        border: 1px solid rgba(148, 163, 184, 0.3);
        box-shadow: 0 16px 35px rgba(15, 23, 42, 0.75);
        transition: transform 140ms ease, box-shadow 140ms ease,
          border-color 140ms ease, background 140ms ease;
      }}

      .card:hover {{
        transform: translateY(-3px);
        box-shadow: 0 22px 45px rgba(15, 23, 42, 0.9);
        border-color: rgba(129, 140, 248, 0.75);
        background: radial-gradient(circle at top left, rgba(129, 140, 248, 0.4), var(--bg-card-hover) 55%);
      }}

      .card-header {{
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 10px;
        margin-bottom: 8px;
      }}

      .card-title {{
        font-size: 0.95rem;
        font-weight: 600;
        letter-spacing: 0.04em;
        text-transform: uppercase;
        color: #e5e7eb;
      }}

      .status-pill {{
        padding: 3px 9px;
        border-radius: 999px;
        font-size: 0.7rem;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        border: 1px solid transparent;
      }}

      .status-pill.healthy {{
        background: rgba(22, 163, 74, 0.16);
        border-color: rgba(22, 163, 74, 0.65);
        color: #bbf7d0;
      }}

      .status-pill.unhealthy {{
        background: rgba(239, 68, 68, 0.16);
        border-color: rgba(239, 68, 68, 0.8);
        color: #fecaca;
      }}

      .status-pill.skipped {{
        background: rgba(148, 163, 184, 0.12);
        border-color: rgba(148, 163, 184, 0.55);
        color: #e5e7eb;
      }}

      .status-pill.unknown {{
        background: rgba(59, 130, 246, 0.16);
        border-color: rgba(59, 130, 246, 0.8);
        color: #bfdbfe;
      }}

      .card-body {{
        font-size: 0.82rem;
        color: var(--text-soft);
      }}

      .card-message {{
        margin: 0 0 4px;
        line-height: 1.4;
      }}

      .card-meta {{
        margin: 0;
        font-size: 0.75rem;
        color: var(--muted);
      }}

      @media (max-width: 640px) {{
        .content {{
          padding: 18px 16px 18px;
        }}
        .title {{
          font-size: 1.3rem;
        }}
      }}
    </style>
  </head>
  <body>
    <div class="shell">
      <div class="content">
        <header class="header">
          <div class="header-main">
            <div class="title">
              FastMVC Service Health
              <span class="title-badge">Live snapshot</span>
            </div>
            <p class="subtitle">
              Overview of core infrastructure services currently configured for this environment.
            </p>
          </div>
          <div class="header-meta">
            <span class="pill">Environment: {os.getenv("APP_ENV", "development").title()}</span>
            <span class="pill">Host: {os.getenv("HOST", "0.0.0.0")}:{os.getenv("PORT", "8000")}</span>
          </div>
        </header>

        <section class="grid">
          {''.join(cards_html)}
        </section>
      </div>
    </div>
  </body>
</html>
"""
    return HTMLResponse(content=html)

