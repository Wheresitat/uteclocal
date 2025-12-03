# U-tec Local Gateway – Specification Review

This document compares the current repository against the requested project goals and highlights gaps.

## High-level coverage

* The repository includes a FastAPI gateway (`gateway/app.py`) with minimal UI for entering base URL, access key, secret key, and log level.
* A HACS integration exists under `custom_components/uteclocal` with a config flow and lock entity.
* Many required features from the project overview are not yet implemented.

## Requirements assessment

### Configuration & Secrets (Gateway)
* ✅ Basic config storage in `/data/config.json` with fields for base URL, access key, secret key, and log level (`gateway/config.py`, `gateway/app.py`).
* ❌ No support for client ID/secret, polling interval, or API base URL override via UI with validation. Secrets are written in plain JSON without explicit permissions or masking in logs.
* ❌ Startup does not validate required fields or surface errors in the UI.

### OAuth2 Flow Management
* ❌ No OAuth flow endpoints (`/auth/start`, `/auth/callback`, `/auth/status`), token exchange, refresh handling, or UI elements for authorization.

### Polling & Device Sync
* ❌ No background polling loop to fetch devices or states. Gateway only proxies single-shot requests to a configured base URL.
* ❌ No handling for invalid tokens, paused polling, or cached device state.

### Local API for Home Assistant
* ✅ Provides `/api/devices` and `/api/status` proxies plus `/lock` and `/unlock` commands (`gateway/app.py`).
* ❌ Missing REST conventions from the spec (e.g., `/api/devices/<id>` routes, structured status, proper 4xx/5xx handling). Logs endpoint returns plain text but lacks pagination or JSON format.

### Web UI (Frontend)
* ✅ Minimal HTML form served at `/` for config and log viewing (`gateway/app.py`).
* ❌ No sections for OAuth initiation, token status, device viewer, or rich log viewer with timestamps and levels. Secrets are not masked in the form display.

### Logging
* ✅ Centralized rotating file logger (`gateway/logging_utils.py`).
* ❌ Logs are not exposed as JSON, do not show levels/timestamps in UI, and no max entry controls beyond rotation. Clearing logs simply deletes the file.

### Docker Requirements
* ✅ Basic Dockerfile builds the gateway and exposes port 8000 with `/data` volume (`gateway/Dockerfile`).
* ❌ No docker-compose example, environment variable support for port/log level, startup retries, or graceful shutdown handling beyond uvicorn defaults. Default port differs from required 8124.

### Home Assistant HACS Custom Integration
* ✅ HACS files present with config flow and lock platform (`custom_components/uteclocal`).
* ❌ Integration does not poll the bridge on an interval, lacks sensors/binary_sensors for battery/online status, and does not expose options flow. Error handling for unreachable gateway is minimal. `manifest.json` marks `iot_class` as `cloud_polling` instead of `local_polling` and version is 1.0.0 vs requested 0.1.0.

### Documentation
* ❌ README lacks required setup guidance for OAuth, docker-compose, scan intervals, and entity mapping. No mention of security or log redaction.

## Summary of major gaps
1. OAuth2 flow (UI + endpoints) is entirely missing.
2. Background polling/cache layer and richer local API endpoints are absent.
3. UI lacks configuration breadth, device viewer, and token/log status views.
4. Docker-compose example and env-based configuration are not provided; default port differs from spec.
5. HACS integration is minimal—no sensors, options flow, or robust status polling/error handling.

These areas need implementation to satisfy the project requirements.
