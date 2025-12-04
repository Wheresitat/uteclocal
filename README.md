# U-tec Local Gateway – Home Assistant Integration

Custom integration to expose U-tec locks via a local gateway.

## What this repo provides
- A **Dockerized FastAPI gateway** that proxies the U-tec open API and exposes
  Home Assistant–friendly endpoints (`/api/devices`, `/api/status`, `/lock`,
  `/unlock`). The gateway includes a lightweight UI for entering your API base
  URL, OAuth base URL, access key, secret key, scope, and redirect URL, plus
  buttons to trigger OAuth, list devices, and clear/view logs.
- A **HACS-compatible custom integration** that talks to the gateway and
  surfaces your locks as entities (lock/unlock, battery level, health).

## Install via HACS
1. Add custom repo: https://github.com/Wheresitat/uteclocal
2. Category: Integration
3. Install
4. Restart HA
5. Add Integration → 'U-tec Local Gateway'
6. Enter host of your gateway (default: http://localhost:8000 if you run the
   Docker container locally)

Your locks will appear as `lock.*` entities if `/api/devices` returns them.

## Run the Dockerized gateway
1. Clone the full repository (the HACS download alone does not include the
   gateway code or Docker assets):
   ```bash
   git clone https://github.com/Wheresitat/uteclocal.git
   cd uteclocal
   ```
2. Bring up the gateway with Docker Compose (builds the image on first run) and
   persist config/logs in the included volume. The explicit project name avoids
   picking up any unrelated Compose files or services on your system:
   ```bash
   docker compose -p uteclocal -f docker-compose.yml up -d --build
   ```
   The UI is reachable at `http://localhost:8000/` by default. To change the
   host port, edit `docker-compose.yml` (e.g., use `- "80:8000"` if you want to
   reach it on `http://<host>/`). If you previously launched an unrelated stack
   and want to ensure only the gateway is running, you can stop this project
   with `docker compose -p uteclocal down` before starting it again.
3. Open the UI and enter your U-tec API base URL, OAuth base URL, access key,
   secret key, scope (if your account uses one, e.g., `enterprise`), and the
   exact redirect URL you registered for the app, then hit **Save** or directly
   **Start OAuth** to launch the authorization URL in a new tab. Use the
   documented cloud host `https://openapi.u-tec.com` for API calls (the previous
   placeholder `https://api.utec.com` can cause name-resolution errors) and the
   documented OAuth host `https://oauth.u-tec.com/login` so the authorization
   link matches `https://oauth.u-tec.com/login/auth`. Existing configs that
   still reference the deprecated `openapi.ultraloq.com` hostname are
   automatically rewritten to `https://openapi.u-tec.com` on startup; refresh
   the UI to confirm the saved value. The settings are stored in
   `/data/config.json` inside the volume and can be managed entirely through the
   UI—no environment file is required. Use **List Devices** to confirm the API
   responds with your locks, and **Clear Logs** to wipe the rotating log file.
4. After approving the OAuth prompt, copy the full redirected URL from the
   browser, paste it into the **OAuth Callback** section, click **Extract Code**, and
   then **Exchange Code**. The gateway will store the resulting access/refresh
   tokens and use them for subsequent API calls (falling back to access/secret
   headers only if no bearer token is saved).

**Troubleshooting connectivity**
- Run `docker compose ps` and confirm the `gateway` service is `running`.
- Check logs with `docker compose logs gateway` to confirm Uvicorn started on
  the expected host/port and that no errors occurred.
- Verify network reachability with `curl http://<host>:<port>/health` from a
  machine on the same network. A JSON `{ "status": "ok" }` response confirms
  the gateway is running and reachable.

### Gateway endpoints
- `GET /api/devices` → returns `{ "payload": { "devices": [...] } }`
- `GET /api/status?id=<device_id>` → returns the raw status payload for the
  given device
- `POST /lock` / `POST /unlock` with JSON body `{ "id": "<device_id>" }`
- `GET /logs` (text), `POST /logs/clear`, `GET /health`

Point the Home Assistant integration at `http://<host>:8000` so it can fetch
devices and control them.

## Connect to Home Assistant

Follow these steps if you installed the custom integration via HACS:

1. In Home Assistant, go to **Settings → Devices & Services → Add Integration**.
2. Search for **U-tec Local Gateway** (the HACS-installed integration) and
   select it.
3. When prompted for the gateway host, enter `http://<host>:8000` (or whatever
   host/port you mapped in `docker-compose.yml`).
4. The integration will call the gateway’s `/api/devices` endpoint to discover
   locks and then expose entities such as `lock.<device>`, plus attributes like
   battery and status. You can control lock/unlock from the entity controls in
   Home Assistant.
