from __future__ import annotations

import logging
import base64
import hashlib
import os
import secrets
from datetime import datetime, timedelta
from string import Template
from typing import Any
from urllib.parse import urlencode, urlparse
import ipaddress

from fastapi import Body, FastAPI, Form, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse

from .client import UtecCloudClient
from .config import GatewayConfig, load_config, save_config
from .logging_utils import clear_logs, read_log_lines, setup_logging
from .poller import POLLING_MANAGER
from .state import STATE

app = FastAPI(title="U-tec Local Gateway", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost",
        "http://127.0.0.1",
        "http://0.0.0.0",
        "http://localhost:8124",
        "http://127.0.0.1:8124",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def _startup() -> None:
    config = load_config()
    setup_logging(config.get("log_level", "INFO"))
    logging.getLogger(__name__).info("Gateway starting with base URL %s", config.get("base_url"))
    POLLING_MANAGER.start()


@app.on_event("shutdown")
async def _shutdown() -> None:
    await POLLING_MANAGER.stop()


def _validate_base_url(raw_url: str) -> str:
    parsed = urlparse(raw_url)
    if parsed.scheme not in {"https", "http"}:
        raise HTTPException(status_code=400, detail="Base URL must be http or https")
    if not parsed.hostname:
        raise HTTPException(status_code=400, detail="Base URL hostname is required")

    allow_insecure = os.getenv("ALLOW_INSECURE_UTEC", "").lower() in {"1", "true", "yes"}
    if parsed.scheme != "https" and not allow_insecure:
        raise HTTPException(status_code=400, detail="HTTPS is required unless ALLOW_INSECURE_UTEC=1")

    try:
        ip_obj = ipaddress.ip_address(parsed.hostname)
        is_private = ip_obj.is_private or ip_obj.is_loopback
    except ValueError:
        # hostname
        is_private = parsed.hostname.endswith(".local") or parsed.hostname in {"localhost"}
    if is_private and not allow_insecure:
        raise HTTPException(status_code=400, detail="Private/loopback base URLs require ALLOW_INSECURE_UTEC=1")

    return raw_url.rstrip("/")


def _render_index(config: GatewayConfig, log_lines: list[str]) -> str:
    logs_html = "<br>".join(line.replace("<", "&lt;").replace(">", "&gt;") for line in log_lines)
    template = Template(
        """
        <!doctype html>
        <html lang='en'>
        <head>
            <meta charset='utf-8' />
            <title>U-tec Local Gateway</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 2rem; }
                label { display: block; margin-top: 0.5rem; }
                input[type=text], input[type=password], input[type=number] { width: 26rem; }
                section { border: 1px solid #ccc; padding: 1rem; margin-bottom: 1rem; background: #fafafa; }
                .logs { max-height: 220px; overflow-y: auto; font-family: monospace; font-size: 0.9rem; }
                .actions { margin-top: 0.75rem; }
                .pill { display: inline-block; padding: 0.25rem 0.5rem; border-radius: 8px; background: #eef; margin-left: 0.5rem; }
            </style>
        </head>
        <body>
            <h1>U-tec Local Gateway</h1>
            <p>Configure U-tec cloud access and monitor polling/OAuth status. Config is stored at <code>/data/config.json</code>.</p>

            <section>
                <h2>Configuration</h2>
                <form id="config-form">
                    <label>API Base URL<br/><input type="text" name="base_url" value="$base_url" required /></label>
                    <label>Client ID<br/><input type="text" name="client_id" value="$client_id" /></label>
                    <label>Client Secret<br/><input type="password" name="client_secret" value="$client_secret" /></label>
                    <label>Access Key (optional)<br/><input type="text" name="access_key" value="$access_key" /></label>
                    <label>Secret Key (optional)<br/><input type="password" name="secret_key" value="$secret_key" /></label>
                    <label>Polling Interval (seconds)<br/><input type="number" min="15" step="5" name="polling_interval" value="$polling_interval" /></label>
                    <label>Log Level<br/><input type="text" name="log_level" value="$log_level" /></label>
                    <div class="actions">
                        <button type="submit">Save</button>
                        <button type="button" id="clear-logs">Clear Logs</button>
                    </div>
                </form>
            </section>

            <section>
                <h2>OAuth 2.0</h2>
                <p>Click start to launch the authorization flow. After U-tec redirects back, tokens are saved locally.</p>
                <button id="start-oauth">Start OAuth Flow</button>
                <div class="pill">Access token: $access_token_status</div>
                <div class="pill">Expires: $token_expiry</div>
                <div class="pill">Refresh token: $refresh_token_status</div>
                <div class="actions">
                    <label>Paste Authorization Code<br/><input type="text" id="manual-code" placeholder="code from redirect" /></label>
                    <button id="submit-code">Submit Code</button>
                </div>
            </section>

            <section>
                <h2>Recent Logs</h2>
                <div class="logs">$logs_html</div>
            </section>

            <section>
                <h2>Bridge & Devices</h2>
                <div id="status">Loading status…</div>
                <div class="actions" style="margin-top: 0.5rem;">
                    <button type="button" id="refresh-devices">Refresh Devices</button>
                </div>
                <table id="devices" border="1" cellspacing="0" cellpadding="6" style="margin-top: 0.75rem; border-collapse: collapse; min-width: 60%;">
                    <thead>
                        <tr>
                            <th>Name</th>
                            <th>ID</th>
                            <th>Type</th>
                            <th>Locked</th>
                            <th>Battery</th>
                            <th>Online</th>
                            <th>Last Updated</th>
                            <th>Raw</th>
                        </tr>
                    </thead>
                    <tbody id="device-rows">
                        <tr><td colspan="8">Loading…</td></tr>
                    </tbody>
                </table>
            </section>

            <script>
                const form = document.getElementById('config-form');
                form.addEventListener('submit', async (e) => {
                    e.preventDefault();
                    const data = new FormData(form);
                    const resp = await fetch('/config', { method: 'POST', body: data });
                    if (resp.ok) { alert('Saved configuration.'); window.location.reload(); }
                    else { alert('Failed to save config'); }
                });

                document.getElementById('clear-logs').addEventListener('click', async () => {
                    await fetch('/logs/clear', { method: 'POST' });
                    window.location.reload();
                });

                document.getElementById('start-oauth').addEventListener('click', async () => {
                    const resp = await fetch('/auth/start');
                    const data = await resp.json();
                    if (data.url) {
                        window.location.href = data.url;
                    }
                });

                document.getElementById('submit-code').addEventListener('click', async () => {
                    const code = document.getElementById('manual-code').value;
                    if (!code) return alert('Enter a code first');
                    const resp = await fetch('/auth/callback?code=' + encodeURIComponent(code));
                    if (resp.ok) { alert('Tokens saved'); window.location.reload(); }
                    else { alert('Failed to save tokens'); }
                });

                const formatState = (device, attribute) => {
                    const payload = device.data || device;
                    const inner = (payload.payload && payload.payload.devices && payload.payload.devices[0]) || payload;
                    const states = inner.states || inner.state || [];
                    const list = Array.isArray(states) ? states : [states];
                    for (const state of list) {
                        const cap = (state.capability || '').toLowerCase();
                        const name = (state.name || state.attribute || '').toLowerCase();
                        if (attribute === 'lock' && cap === 'st.lock' && name === 'lockstate') {
                            const v = String(state.value || '').toLowerCase();
                            if (v === 'locked') return 'Locked';
                            if (v === 'unlocked') return 'Unlocked';
                        }
                        if (attribute === 'battery' && cap === 'st.batterylevel' && name === 'level') {
                            return state.value + '%';
                        }
                        if (attribute === 'online' && cap === 'st.healthcheck' && name === 'status') {
                            return String(state.value || '').toLowerCase();
                        }
                    }
                    return '';
                };

                async function loadStatus() {
                    try {
                        const resp = await fetch('/api/status');
                        const data = await resp.json();
                        const bridge = data.bridge || {};
                        const parts = [];
                        parts.push(`Last poll: ${bridge.last_poll || 'never'}`);
                        parts.push(`Token valid: ${bridge.token_valid ? 'yes' : 'no'}`);
                        if (bridge.error) parts.push(`Error: ${bridge.error}`);
                        document.getElementById('status').textContent = parts.join(' | ');
                    } catch (err) {
                        document.getElementById('status').textContent = 'Failed to load status: ' + err;
                    }
                }

                async function loadDevices() {
                    const tbody = document.getElementById('device-rows');
                    tbody.innerHTML = '<tr><td colspan="8">Loading…</td></tr>';
                    try {
                        const resp = await fetch('/api/devices');
                        const data = await resp.json();
                        const devices = (data.payload && data.payload.devices) || [];
                        if (!devices.length) {
                            tbody.innerHTML = '<tr><td colspan="8">No devices</td></tr>';
                            return;
                        }
                        tbody.innerHTML = '';
                        for (const dev of devices) {
                            const row = document.createElement('tr');
                            row.innerHTML = `
                                <td>${dev.name || ''}</td>
                                <td><code>${dev.id || ''}</code></td>
                                <td>${dev.type || ''}</td>
                                <td>${formatState(dev, 'lock') || ''}</td>
                                <td>${formatState(dev, 'battery') || ''}</td>
                                <td>${formatState(dev, 'online') || ''}</td>
                                <td>${dev.last_updated || ''}</td>
                                <td><button data-id="${dev.id}">View</button></td>
                            `;
                            row.querySelector('button')?.addEventListener('click', () => {
                                alert(JSON.stringify(dev, null, 2));
                            });
                            tbody.appendChild(row);
                        }
                    } catch (err) {
                        tbody.innerHTML = `<tr><td colspan="8">Failed to load devices: ${err}</td></tr>`;
                    }
                }

                document.getElementById('refresh-devices').addEventListener('click', () => {
                    loadStatus();
                    loadDevices();
                });

                loadStatus();
                loadDevices();
            </script>
        </body>
        </html>
        """
    )
    return template.substitute(
        base_url=config.get("base_url", ""),
        client_id=config.get("client_id", ""),
        client_secret=config.get("client_secret", ""),
        access_key=config.get("access_key", ""),
        secret_key=config.get("secret_key", ""),
        log_level=config.get("log_level", "INFO"),
        polling_interval=config.get("polling_interval", 60),
        logs_html=logs_html or "No logs yet.",
        access_token_status="set" if config.get("access_token") else "missing",
        refresh_token_status="set" if config.get("refresh_token") else "missing",
        token_expiry=config.get("token_expires_at", "unknown"),
    )


@app.get("/", response_class=HTMLResponse)
async def index() -> HTMLResponse:
    config = load_config()
    logs = read_log_lines()
    return HTMLResponse(_render_index(config, logs))


@app.get("/auth/start")
async def auth_start(request: Request) -> JSONResponse:
    config = load_config()
    base_url = _validate_base_url((config.get("base_url") or "").strip())
    redirect_uri = str(request.url_for("auth_callback"))
    state = secrets.token_urlsafe(32)
    code_verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest()).rstrip(b"=").decode()
    STATE.set_oauth_challenge(
        {
            "state": state,
            "code_verifier": code_verifier,
            "expires_at": datetime.utcnow() + timedelta(minutes=10),
        }
    )
    authorize_url = f"{base_url}/oauth/authorize"
    params = urlencode(
        {
            "client_id": config.get("client_id", ""),
            "response_type": "code",
            "redirect_uri": redirect_uri,
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
    )
    url = f"{authorize_url}?{params}"
    logging.getLogger(__name__).info("Generated authorization URL: %s", url)
    return JSONResponse({"url": url, "redirect_uri": redirect_uri})


@app.get("/auth/callback")
async def auth_callback(request: Request, code: str, state: str | None = None) -> JSONResponse:
    config = load_config()
    redirect_uri = str(request.url_for("auth_callback"))
    challenge = STATE.get_oauth_challenge()
    if not challenge or challenge["expires_at"] <= datetime.utcnow():
        raise HTTPException(status_code=400, detail="OAuth state has expired; restart flow")
    if state and state != challenge["state"]:
        raise HTTPException(status_code=400, detail="OAuth state mismatch")
    try:
        async with UtecCloudClient(config) as client:
            token = await client.exchange_code(code, redirect_uri, code_verifier=challenge["code_verifier"])
    except Exception as exc:
        logging.getLogger(__name__).exception("OAuth callback failed: %s", exc)
        raise HTTPException(status_code=400, detail="Failed to exchange authorization code") from exc
    STATE.set_oauth_challenge(None)
    if token:
        config.update(token)  # type: ignore[arg-type]
        if "expires_in" in token:
            try:
                config["token_expires_at"] = (datetime.utcnow() + timedelta(seconds=int(token["expires_in"]))).isoformat()
            except Exception:
                pass
        save_config(config)
        logging.getLogger(__name__).info("OAuth tokens stored and polling refreshed")
        POLLING_MANAGER.start()
    return JSONResponse({"status": "ok", "token": _public_config(config)})


@app.get("/auth/status")
async def auth_status() -> dict[str, Any]:
    config = load_config()
    return {
        "has_access_token": bool(config.get("access_token")),
        "has_refresh_token": bool(config.get("refresh_token")),
        "token_expires_at": config.get("token_expires_at"),
    }


@app.post("/config")
async def update_config(
    base_url: str = Form(...),
    client_id: str = Form(""),
    client_secret: str = Form(""),
    access_key: str = Form(""),
    secret_key: str = Form(""),
    log_level: str = Form("INFO"),
    polling_interval: int = Form(60),
) -> JSONResponse:
    config: GatewayConfig = load_config()
    if not (base_url or "").strip():
        raise HTTPException(status_code=400, detail="Base URL is required")
    base_url = _validate_base_url(base_url.strip())
    config.update(
        {
            "base_url": base_url,
            "client_id": client_id,
            "client_secret": client_secret,
            "access_key": access_key,
            "secret_key": secret_key,
            "log_level": log_level,
            "polling_interval": polling_interval,
        }
    )
    save_config(config)
    setup_logging(log_level)
    logging.getLogger(__name__).info("Configuration updated")
    POLLING_MANAGER.start()
    return JSONResponse({"status": "ok"})


@app.get("/logs", response_class=PlainTextResponse)
async def get_logs() -> PlainTextResponse:
    return PlainTextResponse("\n".join(read_log_lines(limit=None)))


@app.post("/logs/clear")
async def clear_log_file() -> JSONResponse:
    clear_logs()
    logging.getLogger(__name__).info("Logs cleared via UI")
    return JSONResponse({"status": "cleared"})


@app.get("/api/logs")
async def api_logs() -> dict[str, Any]:
    logs = read_log_lines(limit=None)
    return {"logs": logs}


@app.delete("/api/logs")
async def api_logs_clear() -> JSONResponse:
    clear_logs()
    logging.getLogger(__name__).info("Logs cleared via API")
    return JSONResponse({"status": "cleared"})


def _health_payload() -> dict[str, Any]:
    status = STATE.status()
    healthy = status.get("token_valid", False) and not status.get("error") and status.get("poller_running", False)
    return {"status": "ok" if healthy else "error", "bridge": status}


@app.get("/health")
async def health() -> JSONResponse:
    payload = _health_payload()
    return JSONResponse(payload, status_code=200 if payload["status"] == "ok" else 503)


@app.get("/health/ready")
async def readiness() -> JSONResponse:
    return await health()


async def _with_client() -> UtecCloudClient:
    config = load_config()
    return UtecCloudClient(config)


def _public_config(config: GatewayConfig) -> GatewayConfig:
    sanitized = config.copy()
    for field in ("client_secret", "secret_key", "access_token", "refresh_token"):
        if sanitized.get(field):
            sanitized[field] = "***"
    return sanitized


@app.get("/api/devices")
async def api_devices() -> dict[str, Any]:
    devices = STATE.devices()
    return {"payload": {"devices": devices}}


@app.get("/api/status")
async def api_status() -> dict[str, Any]:
    config = load_config()
    return {
        "config": _public_config(config),
        "bridge": STATE.status(),
    }


@app.get("/api/devices/{device_id}")
async def api_device_detail(device_id: str) -> dict[str, Any]:
    device = STATE.device(device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    return device


async def _send_device_command(device_id: str, action: str) -> dict[str, Any]:
    if not device_id:
        raise HTTPException(status_code=400, detail="Missing 'id'")
    try:
        client = await _with_client()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    try:
        result = await client.send_lock(device_id, action)
        logging.getLogger(__name__).info("%s request sent to %s", action.title(), device_id)
        return result or {"status": "ok"}
    finally:
        await client.aclose()


@app.post("/lock")
async def api_lock(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    device_id = str(payload.get("id")) if payload.get("id") is not None else None
    return await _send_device_command(device_id or "", "lock")


@app.post("/unlock")
async def api_unlock(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    device_id = str(payload.get("id")) if payload.get("id") is not None else None
    return await _send_device_command(device_id or "", "unlock")


@app.post("/api/devices/{device_id}/lock")
async def api_device_lock(device_id: str) -> dict[str, Any]:
    return await _send_device_command(device_id, "lock")


@app.post("/api/devices/{device_id}/unlock")
async def api_device_unlock(device_id: str) -> dict[str, Any]:
    return await _send_device_command(device_id, "unlock")
