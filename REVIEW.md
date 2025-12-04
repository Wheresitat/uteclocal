# U-tec Local Bridge – Requirement Verification

This document re-evaluates the current repository against the original project requirements and notes any remaining gaps.

## Gateway service

### Configuration & secrets
* ✅ UI exposes API base URL, client ID/secret, access key/secret, polling interval, and log level fields with validation for required base URL and persistence to `/data/config.json` via `gateway.config` and `gateway.app`. Secrets are masked in API responses and best-effort file permissions (0700 dir, 0600 file) are applied on save.
* ⚠️ Stored secrets remain in plain JSON on disk; no additional encryption/keyring layer is provided.

### OAuth2 flow
* ✅ `/auth/start`, `/auth/callback`, and `/auth/status` implement authorization URL generation, code exchange, token refresh persistence, and token status exposure. The UI includes “Start OAuth Flow” and manual code submission controls.
* ⚠️ No explicit CSRF/state parameter handling is present during authorization URL generation.

### Polling & device sync
* ✅ `gateway.poller.Poller` runs as a background task on startup/save/config change, refreshes tokens ahead of expiry, and syncs device lists plus per-device status into the shared `gateway.state` cache. Polling interval is configurable (min 15s) and errors surface through `STATE.status()`.
* ✅ Token expiry and refresh outcomes are tracked so HA/UI can see validity; polling stops gracefully when base URL or tokens are missing.

### Local API for Home Assistant
* ✅ Endpoints: `/api/status`, `/api/devices`, `/api/devices/{id}`, `/api/devices/{id}/lock`, `/api/devices/{id}/unlock`, `/api/logs` (GET/DELETE), `/logs` (plaintext), and legacy `/lock`/`/unlock` payload-based routes. Proper 4xx responses are returned for missing/unknown device IDs or misconfiguration.
* ⚠️ REST API currently returns cached device payloads without normalization; capability/state mapping is left to clients.

### Web UI
* ✅ Single-page HTML served at `/` with sections for configuration, OAuth, logs, bridge status, and device table (lock/battery/online fields with raw JSON viewer).
* ⚠️ UI does not yet provide modal-based JSON pretty rendering or log level filtering; styling is basic and there is no websocket-based live refresh.

### Logging
* ✅ Central logging to `/data/gateway.log` with read/clear support, exposure via UI and API, and log level configuration in UI. Log output is timestamped via Python logging defaults.
* ⚠️ In-memory size limits for `/api/logs` are not enforced beyond filesystem rotation, and log entries are returned as plain strings rather than structured JSON with levels/timestamps.

### Docker & runtime
* ✅ Gateway Dockerfile exposes port 8124, installs runtime deps only, and mounts `/data`. `docker-compose.yml` provides the uteclocal service with volume, restart policy, and environment placeholders for port/log level.
* ⚠️ No explicit healthcheck or startup retry loop beyond Docker’s restart policy.

## Home Assistant (HACS) integration

### Repository structure & manifest
* ✅ HACS-compatible structure under `custom_components/uteclocal` with manifest declaring `local_polling`, config flow enabled, and integration type `hub`.
* ⚠️ Manifest version remains `1.0.0` rather than the requested `0.1.0`, though this is cosmetic.

### Config flow & options
* ✅ UI config flow accepts bridge host (default http://localhost:8124) and validates via `/api/status`; options flow allows adjusting host and scan interval with re-validation.

### Entities & polling
* ✅ Uses a shared `DataUpdateCoordinator` to poll `/api/devices` at configurable intervals and expose locks plus battery and online sensors per device. Entities surface device attributes and mark unavailable on coordinator errors.
* ⚠️ Additional optional sensors (last operation/user, door sensor) are not yet implemented; scan interval defaults align with consts but are not user-documented in README.

### Commands
* ✅ Lock entities call `/api/devices/{id}/lock` and `/api/devices/{id}/unlock`, with payload-based fallbacks, updating state from responses.

## Documentation
* ✅ README covers OAuth-enabled setup, Docker usage, API endpoints, and Home Assistant integration steps, including offline push guidance and local branch publishing notes.
* ⚠️ No screenshots or UX walkthroughs are provided; security guidance is limited to permission tightening without encryption.

## Overall status
The latest deliverables implement the core functional requirements: configurable gateway with OAuth, background polling and caching, REST endpoints for HA/UI, basic UI with device/log views, Docker artifacts on port 8124, and a HACS integration with config/option flows plus lock and sensor entities. Remaining items are primarily hardening and UX polish (state parameter in OAuth, structured logs, optional sensors, manifest version alignment, and richer UI/healthchecks).
