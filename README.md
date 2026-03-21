# fastmvc_dashboards

**HTML dashboards for FastMVC:** FastAPI routers and shared layout/CSS for operational UIs—health, API activity, queues, tenants, secrets, workflows—and a reusable **`render_dashboard_page`** layout helper. Also **signed embed URLs** (time-limited HMAC) and **Metabase / Grafana** embed helpers behind one protocol.

**Python:** 3.10+ · **Dependencies:** `fastapi`, `httpx`, `loguru`, `pydantic>=2`, `sqlalchemy>=2` · **Optional:** `PyJWT` for Metabase (`pip install 'fastmvc_dashboards[metabase]'`).

## What you get

- **`sign_embed_url`**, **`verify_signed_embed_url`** — append `exp` + `sig` (HMAC-SHA256) for iframe-safe dashboard URLs; optional signed **`tid`** (revocation id), **`theme`**, **`locale`** query params.
- **`EmbedRevocationChecker`**, **`InMemoryEmbedRevocationList`** — block leaked embeds by revoking **`tid`** before expiry.
- **`EmbedThemeParams`**, **`theme_to_extra_params`** — bundle dark/light + locale for **`sign_embed_url`** / Grafana.
- **`DashboardEmbedProvider`**, **`MetabaseEmbedProvider`**, **`GrafanaEmbedProvider`** — unified `build_embed_url(resource_id=..., ttl_seconds=...)`; Grafana supports **`theme`** / **`locale`** / **`token_id`**; Metabase supports **`theme`** (URL fragment) and **`locale`** (JWT params).
- **`LookerEmbedProvider`**, **`PowerBIEmbedProvider`** — stubs; use Looker Signed Embed / Power BI **GenerateToken** (see below).
- **Composite `DashboardRouter`** — nested routers (health, API, queues, tenants, secrets, workflows); **lazy-imported** from the package root so `fastmvc_dashboards.layout` works without the full host app on `PYTHONPATH`.
- **`layout.render_dashboard_page`**, **`BASE_CSS`** — shared HTML shell for dashboards.
- **Per-area routers** — e.g. `HealthDashboardRouter`, `ApiDashboardRouter`, … (see `src/fastmvc_dashboards/`).

> **Note:** Many sub-routers expect host app modules (`core.datastores`, `start_utils`, configurations, …). Run inside a full FastMVC app or only import submodules you need (e.g. `layout`, `embed_signing`, `providers`).

## Looker (recipe)

Looker **Signed embed** uses a server-generated SSO URL per session. Implement a small service that calls Looker’s API with your embed secret, then pass the returned URL to the iframe. Do **not** expect a static `build_embed_url` from this package — **`LookerEmbedProvider`** is a deliberate stub.

## Power BI (recipe)

Use the Power BI REST API **GenerateToken** for reports/dashboards (Azure AD app registration). Return the embed URL + token to the client per Microsoft’s embed flow. **`PowerBIEmbedProvider`** is a stub pointing you to that flow.

## Revocation example

```python
from fastmvc_dashboards import InMemoryEmbedRevocationList, sign_embed_url, verify_signed_embed_url

secret = b"your-32-byte-secret-here!!!!"
block = InMemoryEmbedRevocationList()
url = sign_embed_url("https://dash.example.com/view", secret, 3600, token_id="session-abc")
# Later: leak detected
block.revoke("session-abc")
assert verify_signed_embed_url(url, secret, revocation=block) is None
```

## Install

```bash
pip install -e ./fastmvc_dashboards
```

## Optional dev extras

```bash
pip install -e ".[dev]"
```

## Related packages

- **`fastmvc_db`** — when dashboards query SQLAlchemy.
- Monorepo: [../README.md](../README.md).

## Tooling

See [CONTRIBUTING.md](CONTRIBUTING.md), [Makefile](Makefile), and [PUBLISHING.md](PUBLISHING.md).
