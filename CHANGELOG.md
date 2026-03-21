# Changelog

All notable changes to **fastmvc_dashboards** will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.3.0] - 2026-03-21

### Added

- **`sign_embed_url`**: optional ``tid`` (token id), ``theme``, ``locale`` query params (signed).
- **`verify_signed_embed_url`**: optional ``revocation`` (:class:`EmbedRevocationChecker`); **`InMemoryEmbedRevocationList`** (`embed_revocation.py`).
- **`EmbedThemeParams`**, **`theme_to_extra_params`** (`embed_theme.py`).
- **`GrafanaEmbedProvider`**: optional ``theme``, ``locale``, ``token_id`` passed into signing.
- **`MetabaseEmbedProvider`**: optional ``theme`` (``#theme=night`` / ``#theme=day``) and ``locale`` (JWT ``params._locale``).
- **`LookerEmbedProvider`**, **`PowerBIEmbedProvider`** — stubs raising ``NotImplementedError`` with README recipes.

## [0.2.0] - 2026-03-21

### Added

- **`embed_signing`**: `sign_embed_url`, `verify_signed_embed_url` (time-limited HMAC query params).
- **`providers`**: `DashboardEmbedProvider`, `MetabaseEmbedProvider` (JWT; optional `PyJWT`), `GrafanaEmbedProvider` (signed `/d/{uid}/{slug}` URLs).
- **`__version__`** = `0.2.0`; lazy exports on the package root for the above.
- **Coverage config**: `omit` for large integration-only dashboard routers so `pytest --cov` reflects unit-tested modules (`embed_signing`, `providers`, `layout`, `api_dashboard/__init__`).

