# U-tec Local Gateway – Home Assistant Integration

Custom integration to expose U-tec locks via a local gateway.

## What this repo provides
- A **Dockerized FastAPI gateway** that proxies the U-tec open API and exposes
  Home Assistant–friendly endpoints (`/api/devices`, `/api/status`, `/lock`,
  `/unlock`). The gateway includes a lightweight UI for entering your API
  base URL, access key, secret key, and scope, plus buttons to clear/view logs.
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
1. Build the image (from the repo root). **If you only have the HACS download (which contains just `custom_components/` and `const.py`), you must clone the full repo first** so that `Dockerfile`, `gateway/`, and `scripts/build_gateway.sh` exist. Run `git pull` if you cloned earlier to ensure you have the latest files.
   ```bash
   git clone https://github.com/Wheresitat/uteclocal.git  # skip if already cloned
   cd uteclocal

   # quick sanity check that the needed files exist
   ls Dockerfile gateway scripts/build_gateway.sh

   # build from the repo root (uses the root-level Dockerfile)
   docker build -t uteclocal-gateway .

   # or run the helper, which checks that Dockerfile and gateway/ are present
   ./scripts/build_gateway.sh
   ```
   If you do not want to clone locally, you can also ask Docker to pull the
   repo as the build context directly:
   ```bash
   docker build -t uteclocal-gateway https://github.com/Wheresitat/uteclocal.git#main
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
   access key, secret key, and scope, and hit **Save**. Use the documented
   cloud host `https://openapi.ultraloq.com` (the previous placeholder
   `https://api.utec.com` can cause name-resolution errors). The settings are
   stored in `/data/config.json` inside the volume. Use **Clear Logs** to wipe
   the rotating log file.

If you prefer to pull an already-built image instead of building locally, tag
and push `utec-local-gateway` to your registry of choice, then run the same
`docker run` command above with that image reference.

**Troubleshooting build errors**
- If Docker cannot find `Dockerfile`, verify you are in the repo root by
  running `ls` and confirming you see `Dockerfile` and the `gateway/`
  directory. Re-clone the repo if those are missing.
- If you see build errors about missing files, run `git pull` to update to the
  latest commit, then retry `./scripts/build_gateway.sh`.
- If you only see `custom_components/` and `const.py`, you are looking at the
  HACS download. Either clone the repo (recommended) or use the git-URL build
  context command shown above so Docker fetches the missing files for you.
- If you are looking inside your Home Assistant `custom_components/` folder or
  a HACS download, you will not see `Dockerfile` or `gateway/`. Those files are
  only in the full repository—clone it to another folder (outside your HA
  config) and build the image there.

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
