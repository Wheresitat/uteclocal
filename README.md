# U-tec Local Gateway – Home Assistant Integration

Custom integration to expose U-tec locks via a local gateway.

## What this repo provides
- A **FastAPI gateway** that proxies the U-tec OpenAPI, manages OAuth2
  (start/callback/status), and polls the cloud for devices on a configurable
  interval. It exposes Home Assistant–friendly endpoints (`/api/status`,
  `/api/devices`, `/api/devices/{id}`, `/api/devices/{id}/lock`,
  `/api/devices/{id}/unlock`), serves a configuration/OAuth/device UI, and
  streams logs via `/api/logs`.
- A **HACS-compatible custom integration** (`custom_components/uteclocal`) that
  connects to the gateway and surfaces locks plus battery and online status as
  Home Assistant entities.

## Run the gateway with docker compose (no Dockerfile required)
1. Clone the repository, create a data folder for persisted config/tokens/logs,
   and review the provided `.env` defaults (edit as needed):
   ```bash
   git clone https://github.com/Wheresitat/uteclocal.git
   cd uteclocal
   mkdir -p data
   # edit .env if you want to change the port/log level
   ```
2. Start the container (the compose file uses the official `python:3.12-slim`
   runtime, mounts the source code into `/app`, installs requirements on boot,
   and stores persistent data under `./data`):
   ```bash
   docker compose up -d
   ```
3. Open the UI at `http://<host>:8124/`, enter your API base URL, OAuth
   client ID/secret, optional access/secret keys, and click **Save**. Hit
   **Start OAuth Flow** to authorize; tokens are stored under `/data/config.json`.

### Environment variables (.env)
- `UTECLocal_PORT` (default `8124`) controls the container port and the
  uvicorn port.
- `UTECLocal_LOG_LEVEL` (default `INFO`) sets the gateway log level.
- `ALLOW_INSECURE_UTEC=1` allows non-HTTPS or private base URLs for testing.

The included healthcheck probes `http://localhost:<port>/health` and reports an
error status if the poller or token is unhealthy.

## Run the gateway without Docker
```bash
pip install -r requirements.txt
UTECLocal_PORT=8124 UTECLocal_LOG_LEVEL=DEBUG python main.py
```

## Gateway endpoints
- `GET /api/status` → bridge health + OAuth token info
- `GET /api/devices` → cached devices and latest state from the poller
- `GET /api/devices/<device_id>` → single device payload
- `POST /api/devices/<device_id>/lock` and `/api/devices/<device_id>/unlock`
  (compatibility endpoints `/lock` and `/unlock` remain, expecting
  `{ "id": "<device_id>" }` in the body)
- `GET /api/logs` / `DELETE /api/logs` → structured log access
- OAuth helpers: `GET /auth/start`, `GET /auth/callback`, `GET /auth/status`
- Health: `GET /health` / `GET /health/ready` → returns 200 only when the poller
  is running with a valid token and no bridge error

Point the Home Assistant integration at `http://<host>:8124` so it can fetch
devices and control them.

## Connect via Home Assistant (HACS)
1. Add custom repo: https://github.com/Wheresitat/uteclocal (Category:
   Integration).
2. Install, restart HA, then **Add Integration → "U-tec Local Gateway"**.
3. Enter the gateway host/port (default `http://localhost:8124`).
4. The integration pulls `/api/devices`, exposes `lock.<device>` entities plus
   sensors for battery/online status, discovers new devices dynamically, and
   marks entities unavailable if the bridge or device goes unhealthy. You can
   adjust the scan interval in the integration options and send lock/unlock
   commands directly from Home Assistant.

## Development & testing
- Install dependencies: `pip install -r requirements.txt`.
- Run unit tests: `python -m unittest discover -s tests -p 'test_*.py'`.
- Byte-compile check: `python -m compileall gateway custom_components`.

## Pushing your work
To publish changes, add a GitHub remote and push a branch:
```bash
git remote add origin https://github.com/<your-username>/uteclocal.git
git checkout -b feature/my-change
git push -u origin feature/my-change
```

If GitHub is unreachable, you can push to a local bare remote for verification:
```bash
git init --bare /workspace/uteclocal-remote.git
git remote add offline /workspace/uteclocal-remote.git
git checkout -b feature/offline-push
git push -u offline feature/offline-push
```
