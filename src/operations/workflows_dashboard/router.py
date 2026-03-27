"""Workflows Dashboard Router with beautiful UI."""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, JSONResponse

from fast_dashboards.core.registry import registry
from fast_dashboards.core.seo import render_dashboard_inline_head

router = APIRouter(prefix="/dashboard/workflows", tags=["Workflows Dashboard"])


def _get_workflows_config() -> Optional[Any]:
    """Get workflows configuration via registry."""
    cfg_class = registry.get_config("workflows")
    if cfg_class and hasattr(cfg_class, "instance"):
        return cfg_class.instance().get_config()
    return None


@router.get("", response_class=HTMLResponse, summary="Workflows Dashboard")
async def workflows_dashboard() -> HTMLResponse:
    """Render the workflows dashboard page."""
    _head_seo = render_dashboard_inline_head(
        page_title="FastMVC Workflows Dashboard",
        description="Workflow engine status, configuration, and example order lifecycle for FastMVC.",
        path="/dashboard/workflows",
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
            --accent-primary: #a855f7;
            --accent-secondary: #c084fc;
            --accent-gradient: linear-gradient(135deg, #a855f7 0%, #c084fc 100%);
            --success: #10b981;
            --warning: #f59e0b;
            --error: #ef4444;
            --info: #3b82f6;
            --border-color: rgba(148, 163, 184, 0.1);
            --shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.5);
            --shadow-glow: 0 0 40px rgba(168, 85, 247, 0.15);
        }}
        
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        
        body {{
            font-family: 'Inter', sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            min-height: 100vh;
        }}
        
        .dashboard-container {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 2rem;
        }}
        
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
            background: radial-gradient(ellipse at top, rgba(168, 85, 247, 0.15) 0%, transparent 70%);
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
        
        .dashboard-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 1.5rem;
        }}
        
        @media (max-width: 900px) {{
            .dashboard-grid {{ grid-template-columns: 1fr; }}
        }}
        
        .section-card {{
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 20px;
            overflow: hidden;
        }}
        
        .section-card.wide {{
            grid-column: span 2;
        }}
        
        @media (max-width: 900px) {{
            .section-card.wide {{ grid-column: span 1; }}
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
            background: rgba(168, 85, 247, 0.2);
            color: var(--accent-primary);
        }}
        
        .section-content {{ padding: 1.5rem; }}
        
        /* Engine Card */
        .engine-card {{
            background: var(--bg-secondary);
            border: 1px solid var(--border-color);
            border-radius: 16px;
            padding: 2rem;
            text-align: center;
            transition: all 0.3s ease;
        }}
        
        .engine-card:hover {{
            transform: translateY(-4px);
            border-color: rgba(168, 85, 247, 0.3);
            box-shadow: var(--shadow-glow);
        }}
        
        .engine-icon {{
            font-size: 4rem;
            margin-bottom: 1rem;
        }}
        
        .engine-name {{
            font-size: 1.5rem;
            font-weight: 700;
            margin-bottom: 0.5rem;
        }}
        
        .engine-status {{
            display: inline-block;
            padding: 0.5rem 1rem;
            border-radius: 20px;
            font-size: 0.875rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 1.5rem;
        }}
        
        .engine-status.enabled {{
            background: rgba(16, 185, 129, 0.2);
            color: var(--success);
        }}
        
        .engine-status.disabled {{
            background: rgba(148, 163, 184, 0.2);
            color: var(--text-muted);
        }}
        
        .engine-config {{
            background: var(--bg-card);
            border-radius: 12px;
            padding: 1rem;
            text-align: left;
        }}
        
        .config-row {{
            display: flex;
            justify-content: space-between;
            padding: 0.5rem 0;
            border-bottom: 1px solid var(--border-color);
        }}
        
        .config-row:last-child {{
            border-bottom: none;
        }}
        
        .config-label {{
            color: var(--text-muted);
            font-size: 0.875rem;
        }}
        
        .config-value {{
            font-family: 'Monaco', monospace;
            font-size: 0.875rem;
            color: var(--accent-secondary);
        }}
        
        /* Engine Options */
        .engine-options {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 1rem;
        }}
        
        .engine-option {{
            background: var(--bg-secondary);
            border: 2px solid var(--border-color);
            border-radius: 12px;
            padding: 1.25rem;
            text-align: center;
            transition: all 0.3s ease;
            opacity: 0.5;
        }}
        
        .engine-option:hover {{
            opacity: 0.8;
        }}
        
        .engine-option.active {{
            border-color: var(--accent-primary);
            opacity: 1;
        }}
        
        .engine-option-icon {{
            font-size: 2rem;
            margin-bottom: 0.5rem;
        }}
        
        .engine-option-name {{
            font-weight: 600;
            font-size: 0.875rem;
        }}
        
        /* Stats Grid */
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 1rem;
        }}
        
        .stat-card {{
            background: var(--bg-secondary);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 1.25rem;
            text-align: center;
        }}
        
        .stat-value {{
            font-size: 2rem;
            font-weight: 700;
            color: var(--accent-primary);
            margin-bottom: 0.25rem;
        }}
        
        .stat-label {{
            font-size: 0.75rem;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}
        
        /* Workflow Runs */
        .runs-list {{
            display: flex;
            flex-direction: column;
            gap: 0.75rem;
        }}
        
        .run-item {{
            background: var(--bg-secondary);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 1rem;
            display: flex;
            align-items: center;
            gap: 1rem;
            transition: all 0.3s ease;
        }}
        
        .run-item:hover {{
            border-color: rgba(168, 85, 247, 0.3);
        }}
        
        .run-status {{
            width: 12px;
            height: 12px;
            border-radius: 50%;
            flex-shrink: 0;
        }}
        
        .run-status.success {{ background: var(--success); box-shadow: 0 0 8px var(--success); }}
        .run-status.running {{ background: var(--info); animation: pulse 2s infinite; }}
        .run-status.failed {{ background: var(--error); }}
        
        @keyframes pulse {{
            0%, 100% {{ opacity: 1; }}
            50% {{ opacity: 0.5; }}
        }}
        
        .run-info {{ flex: 1; }}
        
        .run-name {{
            font-weight: 600;
            margin-bottom: 0.25rem;
        }}
        
        .run-meta {{
            font-size: 0.75rem;
            color: var(--text-muted);
        }}
        
        .run-time {{
            font-size: 0.875rem;
            color: var(--text-secondary);
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
        
        /* Skeleton */
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
                <h1 class="header-title">⚡ Workflows</h1>
                <p class="header-subtitle">Orchestrate and monitor your background workflows</p>
            </div>
        </header>
        
        <div class="dashboard-grid">
            <!-- Engine Status -->
            <div class="section-card wide">
                <div class="section-header">
                    <div class="section-title">
                        <div class="section-icon">⚙️</div>
                        Workflow Engine
                    </div>
                    <span class="badge" id="engine-badge">Loading...</span>
                </div>
                <div class="section-content">
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem;">
                        <div id="engine-details">
                            <div class="skeleton" style="height: 250px;"></div>
                        </div>
                        <div>
                            <h3 style="font-size: 1rem; font-weight: 600; margin-bottom: 1rem; color: var(--text-secondary);">Available Engines</h3>
                            <div class="engine-options">
                                <div class="engine-option" id="opt-temporal">
                                    <div class="engine-option-icon">⏳</div>
                                    <div class="engine-option-name">Temporal</div>
                                </div>
                                <div class="engine-option" id="opt-prefect">
                                    <div class="engine-option-icon">🐦</div>
                                    <div class="engine-option-name">Prefect</div>
                                </div>
                                <div class="engine-option" id="opt-dagster">
                                    <div class="engine-option-icon">🎯</div>
                                    <div class="engine-option-name">Dagster</div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Stats -->
            <div class="section-card">
                <div class="section-header">
                    <div class="section-title">
                        <div class="section-icon">📊</div>
                        Statistics
                    </div>
                </div>
                <div class="section-content">
                    <div class="stats-grid" id="stats-grid">
                        <div class="stat-card">
                            <div class="stat-value">-</div>
                            <div class="stat-label">Total Runs</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-value">-</div>
                            <div class="stat-label">Success</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-value">-</div>
                            <div class="stat-label">Failed</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-value">-</div>
                            <div class="stat-label">Running</div>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Recent Runs -->
            <div class="section-card">
                <div class="section-header">
                    <div class="section-title">
                        <div class="section-icon">📝</div>
                        Recent Runs
                    </div>
                </div>
                <div class="section-content">
                    <div class="runs-list" id="runs-list">
                        <div class="empty-state">
                            <div class="empty-icon">📝</div>
                            <p>No recent workflow runs</p>
                        </div>
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
                renderEngine(data.engine || {{}});
                renderRuns(data.runs || []);
            }} catch (e) {{
                console.error('Failed to load state:', e);
            }}
        }}
        
        function renderEngine(engine) {{
            document.getElementById('engine-badge').textContent = engine.enabled ? 'Active' : 'Inactive';
            
            // Update engine options
            document.querySelectorAll('.engine-option').forEach(opt => opt.classList.remove('active'));
            if (engine.engineName === 'temporal') document.getElementById('opt-temporal').classList.add('active');
            if (engine.engineName === 'prefect') document.getElementById('opt-prefect').classList.add('active');
            if (engine.engineName === 'dagster') document.getElementById('opt-dagster').classList.add('active');
            
            const container = document.getElementById('engine-details');
            
            const engineIcons = {{
                temporal: '⏳',
                prefect: '🐦',
                dagster: '🎯'
            }};
            
            container.innerHTML = `
                <div class="engine-card">
                    <div class="engine-icon">${{engineIcons[engine.engineName] || '⚙️'}}</div>
                    <div class="engine-name">${{engine.engineName ? engine.engineName.charAt(0).toUpperCase() + engine.engineName.slice(1) : 'Not Configured'}}</div>
                    <div class="engine-status ${{engine.enabled ? 'enabled' : 'disabled'}}">
                        ${{engine.enabled ? '✓ Enabled' : '✗ Disabled'}}
                    </div>
                    ${{engine.enabled ? `
                    <div class="engine-config">
                        ${{engine.temporal ? `
                            <div class="config-row">
                                <span class="config-label">Address</span>
                                <span class="config-value">${{engine.temporal}}</span>
                            </div>
                        ` : ''}}
                        ${{engine.prefect ? `
                            <div class="config-row">
                                <span class="config-label">API URL</span>
                                <span class="config-value">${{engine.prefect}}</span>
                            </div>
                        ` : ''}}
                        ${{engine.dagster ? `
                            <div class="config-row">
                                <span class="config-label">gRPC Endpoint</span>
                                <span class="config-value">${{engine.dagster}}</span>
                            </div>
                        ` : ''}}
                    </div>
                    ` : '<p style="color: var(--text-muted); margin-top: 1rem;">Configure a workflow engine to get started</p>'}}
                </div>
            `;
        }}
        
        function renderRuns(runs) {{
            const container = document.getElementById('runs-list');
            
            if (!runs.length) {{
                container.innerHTML = `
                    <div class="empty-state">
                        <div class="empty-icon">📝</div>
                        <p>No recent workflow runs</p>
                    </div>
                `;
                return;
            }}
            
            container.innerHTML = runs.map(run => `
                <div class="run-item">
                    <div class="run-status ${{run.status}}"></div>
                    <div class="run-info">
                        <div class="run-name">${{run.name || 'Workflow Run'}}</div>
                        <div class="run-meta">${{run.id || 'Unknown ID'}}</div>
                    </div>
                    <div class="run-time">${{run.time || 'Just now'}}</div>
                </div>
            `).join('');
        }}
        
        loadState();
        setInterval(loadState, 8000);
    </script>
</body>
</html>"""
    return HTMLResponse(content=html)


@router.get("/state", response_class=JSONResponse, summary="Workflows state")
async def workflows_state() -> JSONResponse:
    """Return JSON snapshot of workflow engine configuration and sample runs."""
    cfg = _get_workflows_config()

    if cfg is None:
        engine_info: Dict[str, Any] = {
            "enabled": False,
            "engineName": None,
            "status": "Not configured",
        }
    else:
        engine_info = {
            "enabled": getattr(cfg, "enabled", False),
            "engineName": getattr(cfg, "engine", None),
            "temporal": f"{getattr(cfg, 'temporal_address', '')} / {getattr(cfg, 'temporal_namespace', '')}"
            if getattr(cfg, "engine", None) == "temporal"
            else None,
            "prefect": getattr(cfg, "prefect_api_url", "")
            if getattr(cfg, "engine", None) == "prefect"
            else None,
            "dagster": getattr(cfg, "dagster_grpc_endpoint", "")
            if getattr(cfg, "engine", None) == "dagster"
            else None,
        }

    runs: list[Dict[str, Any]] = []
    return JSONResponse({"engine": engine_info, "runs": runs})


__all__ = ["router"]
