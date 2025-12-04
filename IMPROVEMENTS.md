# U-tec Local Bridge: Improvement Recommendations

This document summarizes actionable improvements to enhance functionality, stability, and operational practice based on the current codebase.

## Security & OAuth Hardening
- **Add OAuth state/PKCE validation.** The `/auth/start` handler builds the authorization URL without a `state` parameter or PKCE challenge, leaving the callback open to CSRF and code substitution attacks; the callback also trusts any inbound code. Generate a cryptographically random `state`, store it server-side, and verify it in `/auth/callback`, ideally with PKCE. 【F:gateway/app.py†L256-L299】
- **Restrict cross-origin and unauthenticated access.** The FastAPI app currently enables permissive CORS for all origins and exposes configuration and OAuth endpoints without authentication, which risks token exfiltration on a shared LAN. Add an authentication layer (API key/session auth) for config/OAuth routes and limit allowed origins/credentials. 【F:gateway/app.py†L16-L22】【F:gateway/app.py†L249-L339】
- **Harden secret storage.** Secrets and tokens are stored in plain JSON under `/data/config.json`, only protected by filesystem permissions. Consider encrypting secrets at rest (e.g., using a passphrase/env key) or supporting OS keyring storage, and avoid returning masked secrets in responses when not needed. 【F:gateway/config.py†L8-L45】【F:gateway/app.py†L377-L405】
- **Validate outbound base URLs.** The UI accepts arbitrary `base_url` strings, enabling SSRF-style misuse. Validate that the URL is HTTPS, uses an allowed host suffix, and reject loopback/private targets unless explicitly configured for testing. 【F:gateway/app.py†L311-L339】【F:gateway/client.py†L19-L47】

## Stability & Resilience
- **Introduce retries and backoff in the poller.** Polling currently runs on a fixed interval without retry/backoff; transient HTTP failures mark the bridge as errored but immediately continue. Add bounded retries with jitter, and surface retry state in `/api/status`. 【F:gateway/poller.py†L23-L70】
- **Timeout and error mapping per request.** The cloud client uses a single 15s timeout and raises raw exceptions; map failures to structured errors (auth vs. network vs. 5xx) so the UI/HA integration can present user-friendly messages and avoid noisy stack traces. 【F:gateway/client.py†L17-L93】【F:gateway/poller.py†L35-L102】
- **Preserve last-known-good device state.** When polling fails, `STATE.set_error` is set but device data is not refreshed; consider keeping the previous data and marking per-device availability to avoid oscillating entity availability in Home Assistant. 【F:gateway/poller.py†L51-L70】【F:gateway/state.py†L18-L63】

## Home Assistant Integration
- **Dynamic device discovery.** Entities are created only during initial setup; new locks added to the U-tec account won’t appear until the integration is reloaded. Add logic to add/remove entities on coordinator refresh to keep Home Assistant in sync. 【F:custom_components/uteclocal/lock.py†L16-L33】
- **Map device health to availability.** The coordinator exposes only global success; entities ignore per-device health/online states. Propagate the health/status capability to entity availability and expose diagnostics sensors to reflect bridge errors. 【F:custom_components/uteclocal/coordinator.py†L13-L36】【F:custom_components/uteclocal/lock.py†L57-L141】
- **Handle command failures gracefully.** `async_lock`/`async_unlock` fire commands then force-refresh without error handling; wrap calls to surface HTTP errors in HA logs and avoid marking the entity locked/unlocked until the bridge confirms success. 【F:custom_components/uteclocal/lock.py†L83-L141】

## Observability & Operations
- **Structured logging and correlation IDs.** Logging is plain text and not correlated to requests or devices. Emit JSON logs with request IDs/device IDs to simplify troubleshooting across the bridge and HA integration, and expose a bounded log buffer via `/api/logs`. 【F:gateway/logging_utils.py†L1-L31】【F:gateway/app.py†L342-L365】
- **Health and readiness signals.** `/health` always returns OK and `/api/status` only reports token validity. Add detailed readiness (dependency checks, poller running, OAuth freshness) and liveness endpoints for Docker healthchecks. 【F:gateway/app.py†L367-L398】【F:gateway/state.py†L35-L63】
- **Automated tests for HA flows.** Unit tests cover the poller and gateway endpoints, but HA entities and config/option flows lack coverage. Add tests that mock the bridge API to ensure entity creation, updates, and command execution stay compatible with Home Assistant releases. 【F:tests/test_gateway_api.py†L1-L114】【F:tests/test_poller.py†L1-L100】【F:custom_components/uteclocal/lock.py†L16-L141】

## Deployment & UX
- **Protect the UI/config endpoints.** There is no authentication or CSRF protection on the HTML form. Require a password/API token for the UI, add CSRF tokens, and consider serving the UI on a separate path with static assets instead of inline HTML for maintainability. 【F:gateway/app.py†L24-L232】【F:gateway/app.py†L311-L365】
- **Container healthchecks and graceful shutdown.** Docker artifacts expose the port but lack healthcheck commands and explicit shutdown hooks. Add a `HEALTHCHECK` in the Dockerfile/docker-compose pointing to `/health` and ensure the poller stops on SIGTERM. 【F:docker-compose.yml†L1-L15】【F:gateway/Dockerfile†L1-L17】【F:gateway/poller.py†L23-L50】
- **Surface OAuth expiry proactively.** The UI only shows expiry timestamps; add visual warnings, countdowns, and an automatic refresh trigger before expiry, along with manual token revocation/reset controls. 【F:gateway/app.py†L62-L118】【F:gateway/state.py†L41-L63】
