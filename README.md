# U-tec Local Gateway – Home Assistant Integration

Custom integration to expose U-tec locks via a local gateway.

## What this repo provides
- A **Dockerized FastAPI gateway** that proxies the U-tec open API and exposes
  Home Assistant–friendly endpoints (`/api/devices`, `/api/status`, `/lock`,
  `/unlock`). The gateway includes a lightweight UI for entering your API
  base URL, access key, and secret key, plus buttons to clear/view logs.
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
1. Build the image (from the repo root)
   ```bash
   git clone https://github.com/Wheresitat/uteclocal.git
   cd uteclocal
   # build from the repo root (uses the root-level Dockerfile)
   docker build -t uteclocal-gateway .
   ```
2. Run the container and persist its config/logs in `/data`:
   ```bash
   docker run -d \
     --name uteclocal-gateway \
     -p 8000:8000 \
     -v uteclocal-data:/data \
     uteclocal-gateway
   ```
3. Open the UI at `http://<host>:8000/`, enter your U-tec API base URL,
   access key, and secret key, and hit **Save**. The settings are stored in
   `/data/config.json` inside the volume. Use **Clear Logs** to wipe the
   rotating log file.

If you prefer to pull an already-built image instead of building locally, tag
and push `utec-local-gateway` to your registry of choice, then run the same
`docker run` command above with that image reference.

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
   host/port you mapped in the `docker run` command).
4. The integration will call the gateway’s `/api/devices` endpoint to discover
   locks and then expose entities such as `lock.<device>`, plus attributes like
   battery and status. You can control lock/unlock from the entity controls in
   Home Assistant.
