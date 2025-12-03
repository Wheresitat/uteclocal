# U-tec Local Gateway – Home Assistant Integration

Custom integration to expose U-tec locks via a local gateway.

## What this repo provides
- A **Dockerized FastAPI gateway** that proxies the U-tec OpenAPI, manages the
  OAuth2 flow (start/callback/status), and polls the cloud for devices on a
  configurable interval. The gateway exposes Home Assistant–friendly endpoints
  (`/api/status`, `/api/devices`, `/api/devices/{id}`,
  `/api/devices/{id}/lock`, `/api/devices/{id}/unlock`, `/lock`, `/unlock`),
  ships with a web UI for configuration + OAuth + device viewer, and streams
  logs via `/api/logs`.
- A **HACS-compatible custom integration** that talks to the gateway and
  surfaces your locks plus battery and online status as entities.

## Install via HACS
1. Add custom repo: https://github.com/Wheresitat/uteclocal
2. Category: Integration
3. Install
4. Restart HA
5. Add Integration → 'U-tec Local Gateway'
6. Enter host of your gateway (default: http://localhost:8124 if you run the
   Docker container locally)

Your locks will appear as `lock.*` entities if `/api/devices` returns them.

## Run the Dockerized gateway
1. Build the image
   ```bash
   git clone https://github.com/Wheresitat/uteclocal.git
   cd uteclocal
   docker build -t uteclocal-gateway ./gateway
   ```
2. Run the container and persist its config/logs in `/data`:
   ```bash
   docker run -d \
     --name uteclocal-gateway \
     -p 8124:8124 \
     -v uteclocal-data:/data \
     uteclocal-gateway
   ```
3. Open the UI at `http://<host>:8124/`, enter your U-tec API base URL,
   OAuth client ID/secret, optional access/secret keys, and hit **Save**.
   Click **Start OAuth Flow** to complete authorization, then the background
   poller will keep devices in sync. Settings live in `/data/config.json` and
   logs rotate in `/data/gateway.log`.

If you prefer to pull an already-built image instead of building locally, tag
and push `utec-local-gateway` to your registry of choice, then run the same
`docker run` command above with that image reference.

### Gateway endpoints
- `GET /api/status` → bridge health + OAuth token info
- `GET /api/devices` → cached devices and latest state from the poller
- `GET /api/devices/<device_id>` → single device payload
- `POST /api/devices/<device_id>/lock` and `/api/devices/<device_id>/unlock`
  (compatibility endpoints `/lock` and `/unlock` remain, expecting
  `{ "id": "<device_id>" }` in the body)
- `GET /api/logs` / `DELETE /api/logs` → structured log access
- OAuth helpers: `GET /auth/start`, `GET /auth/callback`, `GET /auth/status`

Point the Home Assistant integration at `http://<host>:8124` so it can fetch
devices and control them.

## Connect to Home Assistant

Follow these steps if you installed the custom integration via HACS:

1. In Home Assistant, go to **Settings → Devices & Services → Add Integration**.
2. Search for **U-tec Local Gateway** (the HACS-installed integration) and
   select it.
3. When prompted for the gateway host, enter `http://<host>:8124` (or whatever
   host/port you mapped in the `docker run` command).
4. The integration calls `/api/devices` on the gateway, exposes
   `lock.<device>` entities, plus sensors for battery and online status. You
   can control lock/unlock directly from Home Assistant and adjust the scan
   interval in the integration options.

## Development & testing

- Install the gateway dependencies locally if you want to run the API or unit
  tests outside Docker:
  ```bash
  pip install -r requirements.txt
  ```
- If you are behind a proxy or working in a restricted environment, configure
  your pip proxy settings or pre-download the required wheels; otherwise the
  FastAPI-dependent API tests will be skipped because the library cannot be
  installed.
- Run the lightweight unit tests that exercise the poller/token refresh logic:
  ```bash
  python -m unittest discover -s tests -p 'test_*.py'
  ```

## Contributing and pushing to GitHub

If you need to publish your changes from this environment, add a remote and push a branch explicitly:

```bash
# create a feature branch if you are still on 'work'
git checkout -b feature/my-change

# add your GitHub remote once per repository
git remote add origin https://github.com/<your-username>/uteclocal.git

# push the branch upstream
git push -u origin feature/my-change
```

If a remote already exists, verify it with `git remote -v` and adjust the URL if necessary using `git remote set-url origin <url>` before pushing. Make sure your GitHub credentials and network access are available in the environment where you run these commands.

> Why branches may look stale on GitHub: branches in the GitHub UI only update after you push your local commits to a configured remote. This environment starts without any remotes, so `git remote -v` shows nothing and no branches are published until you add your GitHub remote and run `git push -u origin <branch>`.

### Local-only “remote” when GitHub isn’t reachable

If you simply need a branch push to succeed for testing or CI without Internet access, you can create a local bare repository and push to it:

```bash
# create a bare repository that will act like a remote
git init --bare /workspace/uteclocal-remote.git

# register it as a remote
git remote add offline /workspace/uteclocal-remote.git

# create and push a branch to the local remote
git checkout -b feature/offline-push
git push -u offline feature/offline-push
```

The push above updates `/workspace/uteclocal-remote.git` so other local clones can fetch it, and it lets you verify the repository pushes cleanly even when GitHub is temporarily unavailable.

Once the bare remote exists, you can reuse it for new branches without recreating it:

```bash
# assuming you're on the work branch with fresh commits
git switch -c feature/offline-push-2
git push -u offline feature/offline-push-2

# confirm the branch exists on the offline remote
git ls-remote --heads offline
```
