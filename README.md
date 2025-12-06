# U-tec Local Gateway – Home Assistant Integration

**Version: 1.3.5**
Increment this version string in the README whenever new functionality ships so users can confirm they are on the latest documented baseline.

Custom integration to expose U-tec locks via a local gateway.

## What this repo provides
- A **Dockerized FastAPI gateway** that proxies the U-tec open API and exposes
  Home Assistant–friendly endpoints (`/api/devices`, `/api/status`, `/lock`,
  `/unlock`). The gateway includes a lightweight UI for entering your API base
  URL, OAuth base URL, **action endpoint path** from the docs, access key,
  secret key, scope, and redirect URL, plus buttons to trigger OAuth, list
  devices, and clear/view logs.
- A **HACS-compatible custom integration** that talks to the gateway and
  surfaces your locks as entities (lock/unlock) plus separate sensor entities
  for battery level and health status.

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
3. Open the UI and enter your U-tec API base URL, OAuth base URL,
   **action endpoint path** (`/action` per the device discovery docs at
   https://doc.api.u-tec.com/#db817fe1-0bfe-47f1-877d-ac02df4d2b0e), access key,
   secret key, scope (`openapi` per the docs), and the exact redirect URL you
   registered for the app, then hit **Save** or directly **Start OAuth** to
   launch the authorization URL in a new tab. Use the documented cloud host
   `https://api.u-tec.com` for API calls (the gateway defaults to this and logs
   the final URL it calls) and the documented OAuth host `https://oauth.u-tec.com`
   so the authorization link matches `https://oauth.u-tec.com/authorize`.
   Existing configs that still reference the deprecated `openapi.ultraloq.com`
   hostname (or the old `/login` OAuth suffix) are automatically rewritten on
   startup; refresh the UI to confirm the saved values. The settings are stored
  in `/data/config.json` inside the volume and can be managed entirely through
  the UI—no environment file is required. Use **List Devices** to confirm the
  API responds with your locks. **Status poll interval** controls how often the
  gateway auto-refreshes device status in the background (default 60s). **Query
  Status** lets you fetch a specific lock on-demand, and **Clear Logs** wipes
  the rotating log file.
4. After approving the OAuth prompt, copy the full redirected URL from the
   browser, paste it into the **OAuth Callback** section, click **Extract Code**, and
   then **Exchange Code**. The gateway will store the resulting access/refresh
  tokens and use them for subsequent API calls (the gateway now includes your
  access/secret headers alongside the bearer token to satisfy endpoints that
  require both). The UI also exposes **Manual Lock /
   Unlock** controls; paste a device MAC address and click **Lock** or **Unlock**
   to send the documented action payloads to the `/action` endpoint and view the
   raw cloud response inline.

**Troubleshooting connectivity**
- Run `docker compose ps` and confirm the `gateway` service is `running`.
- Check logs with `docker compose logs gateway` to confirm Uvicorn started on
  the expected host/port and that no errors occurred.
- Verify network reachability with `curl http://<host>:<port>/health` from a
  machine on the same network. A JSON `{ "status": "ok" }` response confirms
  the gateway is running and reachable.

### Gateway endpoints
- `GET /api/devices` → returns `{ "payload": { "devices": [...] } }` by posting
  the documented discovery payload to `<base_url><action_path>` (defaults to
  `https://api.u-tec.com/action`)
- `POST /api/status` → body `{ "devices": [{ "id": "<device_id>" }] }` posts
  the documented `Uhome.Device/Query` payload to the same action endpoint and
  returns the raw cloud status response.
- `GET /api/status/latest` → returns the most recent status payload collected
  by the background poller plus a `last_updated` timestamp (epoch seconds).
- `POST /api/status/refresh` → triggers a fresh discovery + status poll and
  returns the resulting payload with a timestamp.
- `POST /lock` / `POST /unlock` (aliases at `/api/lock` and `/api/unlock`) with
  JSON body `{ "id": "<device_id>" }` first post the documented
  `Uhome.Device/Command` payload from the U-tec docs (with `capability`
  `st.lock` and `name` set to `lock`/`unlock`). If the cloud rejects that, the
  gateway automatically cycles through the older `Control` payload variants
  (`LockState`/`Lock` shapes) before returning an error. Requests are sent to
  the configured action endpoint (defaults to `https://api.u-tec.com/action`).
- `GET /devices` mirrors `/api/devices` for clients that expect the non-`/api`
  path.
- `GET /logs` (text), `POST /logs/clear`, `GET /health`

Point the Home Assistant integration at `http://<host>:8000` so it can fetch
devices and control them.

#### Curl smoke tests
With the gateway running you can sanity-check the endpoints using `curl` (or
run the helper script at `scripts/curl-smoke.sh`). Replace `<host>` and
`<device_id>` with your values:

```bash
# Basic reachability
curl http://<host>:8000/health

# Device discovery (requires saved OAuth token or access/secret key)
curl --fail-with-body http://<host>:8000/api/devices

# Status query for a specific lock
curl --fail-with-body -X POST http://<host>:8000/api/status \
  -H "Content-Type: application/json" \
  -d '{"id":"<device_id>"}'

# Lock / unlock actions using the documented Control payload
curl --fail-with-body -X POST http://<host>:8000/api/lock \
  -H "Content-Type: application/json" \
  -d '{"id":"<device_id>"}'

curl --fail-with-body -X POST http://<host>:8000/api/unlock \
  -H "Content-Type: application/json" \
  -d '{"id":"<device_id>"}'
```

To exercise all of the above in one go, set `HOST=http://<host>:8000` and
`DEVICE_ID=<device_id>` (MAC) and run `./scripts/curl-smoke.sh`. Use
`SKIP_DEVICES=1` if you only want to hit health/status/control.

## Connect to Home Assistant

Follow these steps if you installed the custom integration via HACS:

1. In Home Assistant, go to **Settings → Devices & Services → Add Integration**.
2. Search for **U-tec Local Gateway** (the HACS-installed integration) and
   select it.
3. When prompted for the gateway host, enter `http://<host>:8000` (or whatever
   host/port you mapped in `docker-compose.yml`). If you see a port field (for
   example, a form that defaults to `8100`), change it to `8000` to match the
   gateway’s published port. Leave the **API key** field empty—the gateway
   endpoints are already authenticated through the cloud tokens you configure in
   the UI and do not require an extra per-request key. If your Home Assistant is
   running over HTTPS but the gateway is HTTP-only, uncheck **Verify SSL
   certificates** for this connection so HA will accept the plain HTTP endpoint.
4. The integration will call the gateway’s `/api/devices` endpoint to discover
   locks and then expose entities such as `lock.<device>`, plus attributes like
   battery and status. You can control lock/unlock from the entity controls in
   Home Assistant.
