from __future__ import annotations

import logging
from string import Template
from typing import Any
from urllib.parse import urlencode, urlparse, parse_qs

import httpx

from fastapi import Body, FastAPI, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse

from .client import UtecCloudClient
from .config import (
    GatewayConfig,
    load_config,
    normalize_action_path,
    normalize_base_url,
    normalize_devices_path,
    normalize_oauth_base_url,
    save_config,
)
from .logging_utils import clear_logs, read_log_lines, setup_logging

app = FastAPI(title="U-tec Local Gateway", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def _startup() -> None:
    config = load_config()
    setup_logging(config.get("log_level", "INFO"))
    logging.getLogger(__name__).info("Gateway starting with base URL %s", config.get("base_url"))


def render_index(config: GatewayConfig, log_lines: list[str]) -> str:
    logs_html = "<br>".join(line.replace("<", "&lt;").replace(">", "&gt;") for line in log_lines)
    token_status = ""
    if config.get("access_token"):
        token_status = f"Stored token ({config.get('token_type', 'Bearer')}) ready; expires in {config.get('token_expires_in', 0)}s"
    elif config.get("auth_code"):
        token_status = "Authorization code saved; exchange it for a token below."
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
                input[type=text], input[type=password] { width: 24rem; }
                .logs { margin-top: 1.5rem; padding: 1rem; border: 1px solid #ccc; background: #f9f9f9; max-height: 300px; overflow-y: auto; }
                .actions { margin-top: 1rem; display: flex; gap: 0.5rem; flex-wrap: wrap; }
                .section { margin-top: 1.5rem; padding: 1rem; border: 1px solid #ddd; background: #fcfcfc; }
                .muted { color: #555; font-size: 0.9rem; }
                ul.devices { padding-left: 1.25rem; }
            </style>
        </head>
        <body>
            <h1>U-tec Local Gateway</h1>
            <p>Configure your U-tec cloud credentials. Values are stored on disk in <code>/data/config.json</code> inside the container.</p>
            <form id="config-form">
                <label>API Base URL<br/><input type="text" name="base_url" value="$base_url" required /></label>
                <label>OAuth Base URL<br/><input type="text" name="oauth_base_url" value="$oauth_base_url" required /></label>
                <label>Action Endpoint Path<br/><input type="text" name="action_path" value="$action_path" placeholder="/action" /></label>
                <label>Devices Endpoint Path<br/><input type="text" name="devices_path" value="$devices_path" placeholder="/openapi/v1/devices" /></label>
                <label>Access Key<br/><input type="text" name="access_key" value="$access_key" /></label>
                <label>Secret Key<br/><input type="password" name="secret_key" value="$secret_key" /></label>
                <label>Scope<br/>
                    <input type="text" name="scope" value="$scope" placeholder="openapi" />
                    <small>Per U-tec docs use <code>openapi</code>; enterprise tenants may require a specific scope.</small>
                </label>
                <label>Redirect URL<br/><input type="text" name="redirect_url" value="$redirect_url" placeholder="https://your-app/callback" /></label>
                <p class="muted">Redirect URL must exactly match what you registered for the app in the U-tec console.</p>
                <label>Log Level<br/><input type="text" name="log_level" value="$log_level" /></label>
                <div class="actions">
                    <button type="submit">Save</button>
                    <button type="button" id="start-oauth">Start OAuth</button>
                    <button type="button" id="fetch-devices">List Devices</button>
                    <button type="button" id="clear-logs">Clear Logs</button>
                </div>
            </form>
            <div class="section">
                <strong>OAuth Callback</strong>
                <p class="muted">After approving access, paste the final redirected URL below to extract the <code>code</code> and exchange it for tokens.</p>
                <label>Redirected URL<br/><input type="text" id="callback-url" placeholder="https://your-app/callback?code=..." style="width: 36rem;" /></label>
                <label>Authorization Code<br/><input type="text" id="auth-code" value="$auth_code" style="width: 18rem;" /></label>
                <div class="actions" style="margin-top: 0.5rem;">
                    <button type="button" id="extract-code">Extract Code</button>
                    <button type="button" id="exchange-code">Exchange Code</button>
                </div>
                <div class="muted" id="token-status">$token_status</div>
            </div>
            <div class="section">
                <strong>Devices</strong>
                <div id="devices" class="muted">No devices fetched yet.</div>
            </div>
            <div class="logs">
                <strong>Recent Logs</strong><br/>
                <div id="logs">$logs_html</div>
            </div>
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
                    const data = new FormData(form);
                    const base_url = data.get('base_url');
                    const oauth_base_url = data.get('oauth_base_url');
                    const access_key = data.get('access_key');
                    const secret_key = data.get('secret_key');
                    const redirect_url = data.get('redirect_url');
                    const scope = data.get('scope');
                    if (!base_url || !oauth_base_url || !access_key || !secret_key || !redirect_url) {
                        alert('Base URL, OAuth Base URL, Access Key, Secret Key, and Redirect URL are required to build the OAuth link.');
                        return;
                    }
                    const resp = await fetch('/oauth/start', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ base_url, oauth_base_url, access_key, secret_key, redirect_url, scope })
                    });
                    const payload = await resp.json();
                    if (resp.ok && payload.authorize_url) {
                        window.open(payload.authorize_url, '_blank');
                    } else {
                        alert(payload.detail || 'Unable to start OAuth flow');
                    }
                });

                function parseAuthCode(urlStr) {
                    try {
                        const parsed = new URL(urlStr);
                        return parsed.searchParams.get('authorization_code') || parsed.searchParams.get('code');
                    } catch (err) {
                        return '';
                    }
                }

                document.getElementById('extract-code').addEventListener('click', () => {
                    const urlStr = document.getElementById('callback-url').value;
                    const code = parseAuthCode(urlStr);
                    if (!code) {
                        alert('No "authorization_code" or "code" parameter found in the provided URL.');
                        return;
                    }
                    document.getElementById('auth-code').value = code;
                });

                document.getElementById('exchange-code').addEventListener('click', async () => {
                    const data = new FormData(form);
                    const base_url = data.get('base_url');
                    const oauth_base_url = data.get('oauth_base_url');
                    const access_key = data.get('access_key');
                    const secret_key = data.get('secret_key');
                    const redirect_url = data.get('redirect_url');
                    const code = document.getElementById('auth-code').value;
                    const status = document.getElementById('token-status');
                    status.textContent = 'Requesting token...';
                    const resp = await fetch('/oauth/exchange', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ base_url, oauth_base_url, access_key, secret_key, redirect_url, code })
                    });
                    const payload = await resp.json();
                    if (resp.ok) {
                        const tokenLabel = payload.token_type || 'token';
                        const expires = payload.expires_in || '?';
                        status.textContent = 'Received ' + tokenLabel + ' (expires in ' + expires + 's)';
                        alert('Token saved. You can now use the UI to test the API.');
                        window.location.reload();
                    } else {
                        status.textContent = payload.detail || 'Token exchange failed';
                        alert(payload.detail || 'Token exchange failed');
                    }
                });

                document.getElementById('fetch-devices').addEventListener('click', async () => {
                    const devicesDiv = document.getElementById('devices');
                    devicesDiv.textContent = 'Loading devices...';
                    try {
                        const resp = await fetch('/api/devices');
                        const payload = await resp.json();
                        if (!resp.ok) {
                            devicesDiv.textContent = payload.detail || 'Failed to load devices';
                            return;
                        }
                        const devices = (payload.payload && payload.payload.devices) || [];
                        if (!devices.length) {
                            devicesDiv.textContent = 'No devices returned by the API.';
                            return;
                        }
                        const list = document.createElement('ul');
                        list.className = 'devices';
                        devices.forEach((dev) => {
                            const li = document.createElement('li');
                            const name = dev.name || dev.device_name || dev.device_id || 'Unknown device';
                            const id = dev.id || dev.device_id || dev.serial_no || '';
                            li.textContent = id ? name + ' (' + id + ')' : name;
                            list.appendChild(li);
                        });
                        devicesDiv.replaceChildren(list);
                    } catch (err) {
                        devicesDiv.textContent = 'Error loading devices: ' + err;
                    }
                });
            </script>
        </body>
        </html>
        """
    )
    return template.safe_substitute(
        base_url=config.get("base_url", ""),
        access_key=config.get("access_key", ""),
        secret_key=config.get("secret_key", ""),
        scope=config.get("scope", ""),
        oauth_base_url=config.get("oauth_base_url", ""),
        devices_path=config.get("devices_path", ""),
        action_path=config.get("action_path", ""),
        redirect_url=config.get("redirect_url", ""),
        log_level=config.get("log_level", "INFO"),
        logs_html=logs_html or "No logs yet.",
        auth_code=config.get("auth_code", ""),
        token_status=token_status,
    )


@app.get("/", response_class=HTMLResponse)
async def index() -> HTMLResponse:
    config = load_config()
    logs = read_log_lines()
    return HTMLResponse(render_index(config, logs))


@app.post("/config")
async def update_config(
    base_url: str = Form(...),
    oauth_base_url: str = Form(""),
    devices_path: str = Form(""),
    action_path: str = Form("/action"),
    access_key: str = Form(""),
    secret_key: str = Form(""),
    scope: str = Form(""),
    redirect_url: str = Form(""),
    log_level: str = Form("INFO"),
) -> JSONResponse:
    existing = load_config()
    config: GatewayConfig = existing.copy()
    config.update(
        {
            "base_url": normalize_base_url(base_url),
            "oauth_base_url": normalize_oauth_base_url(oauth_base_url),
            "action_path": normalize_action_path(action_path),
            "devices_path": normalize_devices_path(devices_path),
            "access_key": access_key,
            "secret_key": secret_key,
            "scope": scope,
            "redirect_url": redirect_url,
            "log_level": log_level,
        }
    )
    save_config(config)
    setup_logging(log_level)
    logging.getLogger(__name__).info("Configuration updated")
    return JSONResponse({"status": "ok"})


@app.get("/logs", response_class=PlainTextResponse)
async def get_logs() -> PlainTextResponse:
    return PlainTextResponse("\n".join(read_log_lines(limit=None)))


@app.post("/logs/clear")
async def clear_log_file() -> JSONResponse:
    clear_logs()
    logging.getLogger(__name__).info("Logs cleared via UI")
    return JSONResponse({"status": "cleared"})


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


async def _with_client() -> UtecCloudClient:
    config = load_config()
    return UtecCloudClient(config)


@app.get("/api/devices")
async def api_devices() -> dict[str, Any]:
    client = await _with_client()
    log = logging.getLogger(__name__)
    try:
        devices = await client.fetch_devices()
        log.info("Fetched %d devices", len(devices))
        return {"payload": {"devices": devices}}
    except httpx.HTTPStatusError as exc:
        body = exc.response.text
        log.warning("Device fetch failed (%s): %s", exc.response.status_code, body[:500])
        return JSONResponse(
            status_code=exc.response.status_code,
            content={"detail": body or exc.response.reason_phrase},
        )
    except httpx.RequestError as exc:
        host = getattr(exc.request.url, "host", None) if exc.request else None
        log.warning("Device fetch could not reach cloud host %s: %s", host, exc)
        return JSONResponse(
            status_code=502,
            content={"detail": f"Unable to reach cloud host {host or 'unknown'}: {exc}"},
        )
    except ValueError as exc:
        log.warning("Device fetch returned non-JSON response")
        return JSONResponse(status_code=502, content={"detail": "Cloud response was not JSON"})
    except Exception as exc:  # pragma: no cover - defensive logging
        log.exception("Unexpected error fetching devices")
        return JSONResponse(status_code=500, content={"detail": str(exc)})
    finally:
        await client.aclose()


@app.get("/api/status")
async def api_status(id: str) -> dict[str, Any]:
    client = await _with_client()
    log = logging.getLogger(__name__)
    try:
        status = await client.fetch_status(id)
        log.info("Fetched status for %s", id)
        return status
    finally:
        await client.aclose()


@app.post("/lock")
async def api_lock(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    device_id = str(payload.get("id")) if payload.get("id") is not None else None
    if not device_id:
        raise HTTPException(status_code=400, detail="Missing 'id'")
    client = await _with_client()
    try:
        result = await client.send_lock(device_id, "lock")
        logging.getLogger(__name__).info("Lock request sent to %s", device_id)
        return result or {"status": "ok"}
    finally:
        await client.aclose()


@app.post("/unlock")
async def api_unlock(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    device_id = str(payload.get("id")) if payload.get("id") is not None else None
    if not device_id:
        raise HTTPException(status_code=400, detail="Missing 'id'")
    client = await _with_client()
    try:
        result = await client.send_lock(device_id, "unlock")
        logging.getLogger(__name__).info("Unlock request sent to %s", device_id)
        return result or {"status": "ok"}
    finally:
        await client.aclose()


@app.post("/oauth/start")
async def oauth_start(payload: dict[str, Any] = Body(...)) -> JSONResponse:
    oauth_base_url = normalize_oauth_base_url(payload.get("oauth_base_url") or "")
    access_key = (payload.get("access_key") or "").strip()
    secret_key = (payload.get("secret_key") or "").strip()
    redirect_url = (payload.get("redirect_url") or "").strip()
    scope = (payload.get("scope") or "").strip() or "openapi"

    if not oauth_base_url or not access_key or not secret_key or not redirect_url:
        raise HTTPException(
            status_code=400, detail="oauth_base_url, access_key, secret_key, and redirect_url are required"
        )

    params = urlencode(
        {
            "response_type": "code",
            "client_id": access_key,
            "client_secret": secret_key,
            "redirect_uri": redirect_url,
            "scope": scope,
            "state": "uteclocal",
        }
    )
    authorize_url = f"{oauth_base_url.rstrip('/')}/authorize?{params}"
    logging.getLogger(__name__).info("Generated OAuth authorize URL for redirect %s", redirect_url)
    return JSONResponse({"authorize_url": authorize_url})


def _extract_code(code: str | None, callback_url: str | None) -> str:
    if code and code.strip():
        return code.strip()
    if not callback_url:
        return ""
    parsed = urlparse(callback_url)
    params = parse_qs(parsed.query)
    return params.get("authorization_code", params.get("code", [""]))[0]


@app.post("/oauth/exchange")
async def oauth_exchange(payload: dict[str, Any] = Body(...)) -> JSONResponse:
    base_url = normalize_base_url(payload.get("base_url") or "")
    oauth_base_url = normalize_oauth_base_url(payload.get("oauth_base_url") or "")
    access_key = (payload.get("access_key") or "").strip()
    secret_key = (payload.get("secret_key") or "").strip()
    redirect_url = (payload.get("redirect_url") or "").strip()
    code = _extract_code(payload.get("code"), payload.get("callback_url"))

    if not all([base_url, oauth_base_url, access_key, secret_key, redirect_url, code]):
        raise HTTPException(
            status_code=400,
            detail="base_url, oauth_base_url, access_key, secret_key, redirect_url, and code are required",
        )

    data = {
        "grant_type": "authorization_code",
        "code": code,
        "client_id": access_key,
        "client_secret": secret_key,
    }
    if redirect_url:
        data["redirect_uri"] = redirect_url
    token_url = f"{oauth_base_url.rstrip('/')}/token"
    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.post(token_url, data=data)

    if resp.status_code >= 400:
        detail = resp.text or resp.reason_phrase
        logging.getLogger(__name__).warning("OAuth exchange failed: %s", detail)
        raise HTTPException(status_code=resp.status_code, detail=detail)

    tokens = resp.json()
    config = load_config()
    config.update(
        {
            "base_url": base_url,
            "oauth_base_url": oauth_base_url,
            "access_key": access_key,
            "secret_key": secret_key,
            "redirect_url": redirect_url,
            "auth_code": code,
            "access_token": tokens.get("access_token", ""),
            "refresh_token": tokens.get("refresh_token", ""),
            "token_type": tokens.get("token_type", "Bearer"),
            "token_expires_in": int(tokens.get("expires_in", 0)),
        }
    )
    save_config(config)
    logging.getLogger(__name__).info("OAuth code exchanged; access token stored")

    return JSONResponse(
        {
            "access_token": tokens.get("access_token"),
            "refresh_token": tokens.get("refresh_token"),
            "token_type": tokens.get("token_type", "Bearer"),
            "expires_in": tokens.get("expires_in", 0),
        }
    )
