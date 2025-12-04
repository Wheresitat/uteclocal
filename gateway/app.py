from __future__ import annotations

import logging
from string import Template
from typing import Any

from fastapi import Body, FastAPI, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse

from .client import UtecCloudClient
from .config import GatewayConfig, load_config, save_config
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
                .actions { margin-top: 1rem; }
            </style>
        </head>
        <body>
            <h1>U-tec Local Gateway</h1>
            <p>Configure your U-tec cloud credentials. Values are stored on disk in <code>/data/config.json</code> inside the container.</p>
            <form id="config-form">
                <label>API Base URL<br/><input type="text" name="base_url" value="$base_url" required /></label>
                <label>Access Key<br/><input type="text" name="access_key" value="$access_key" /></label>
                <label>Secret Key<br/><input type="password" name="secret_key" value="$secret_key" /></label>
                <label>Scope<br/><input type="text" name="scope" value="$scope" /></label>
                <label>Log Level<br/><input type="text" name="log_level" value="$log_level" /></label>
                <div class="actions">
                    <button type="submit">Save</button>
                    <button type="button" id="clear-logs">Clear Logs</button>
                </div>
            </form>
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
            </script>
        </body>
        </html>
        """
    )
    return template.substitute(
        base_url=config.get("base_url", ""),
        access_key=config.get("access_key", ""),
        secret_key=config.get("secret_key", ""),
        scope=config.get("scope", ""),
        log_level=config.get("log_level", "INFO"),
        logs_html=logs_html or "No logs yet.",
    )


@app.get("/", response_class=HTMLResponse)
async def index() -> HTMLResponse:
    config = load_config()
    logs = read_log_lines()
    return HTMLResponse(render_index(config, logs))


@app.post("/config")
async def update_config(
    base_url: str = Form(...),
    access_key: str = Form(""),
    secret_key: str = Form(""),
    scope: str = Form(""),
    log_level: str = Form("INFO"),
) -> JSONResponse:
    config: GatewayConfig = {
        "base_url": base_url,
        "access_key": access_key,
        "secret_key": secret_key,
        "scope": scope,
        "log_level": log_level,
    }
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
