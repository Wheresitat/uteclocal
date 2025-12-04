from __future__ import annotations

import json
from pathlib import Path
from typing import Any, TypedDict


class GatewayConfig(TypedDict, total=False):
    base_url: str
    oauth_base_url: str
    devices_path: str
    access_key: str
    secret_key: str
    auth_code: str
    access_token: str
    refresh_token: str
    token_type: str
    token_expires_in: int
    log_level: str
    scope: str
    redirect_url: str


DATA_DIR = Path("/data")
CONFIG_PATH = DATA_DIR / "config.json"
LOG_PATH = DATA_DIR / "gateway.log"

DEFAULT_CONFIG: GatewayConfig = {
    # U-tec Open API per public docs: https://openapi.u-tec.com
    "base_url": "https://openapi.u-tec.com",
    # Documented device listing path: https://doc.api.u-tec.com/#db817fe1-0bfe-47f1-877d-ac02df4d2b0e
    "devices_path": "/openapi/v1/devices",
    # OAuth host documented for auth/token flow: https://oauth.u-tec.com
    "oauth_base_url": "https://oauth.u-tec.com",
    "access_key": "",
    "secret_key": "",
    "auth_code": "",
    "access_token": "",
    "refresh_token": "",
    "token_type": "Bearer",
    "token_expires_in": 0,
    "log_level": "INFO",
    # Per docs the OAuth scope should be "openapi"
    "scope": "openapi",
    "redirect_url": "",
}


def ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def normalize_base_url(url: str) -> str:
    cleaned = (url or "").strip()
    if not cleaned:
        return DEFAULT_CONFIG["base_url"]
    if "openapi.ultraloq.com" in cleaned:
        # Migrate the legacy hostname that fails DNS resolution to the
        # documented endpoint used by the OAuth/auth flows.
        cleaned = cleaned.replace("openapi.ultraloq.com", "openapi.u-tec.com")
    if not cleaned.startswith("http://") and not cleaned.startswith("https://"):
        cleaned = "https://" + cleaned
    return cleaned


def normalize_devices_path(path: str) -> str:
    cleaned = (path or "").strip() or DEFAULT_CONFIG["devices_path"]
    if not cleaned.startswith("/"):
        cleaned = "/" + cleaned
    return cleaned.rstrip("/") or DEFAULT_CONFIG["devices_path"]


def normalize_oauth_base_url(url: str) -> str:
    cleaned = (url or "").strip()
    if not cleaned:
        return DEFAULT_CONFIG["oauth_base_url"]
    if not cleaned.startswith("http://") and not cleaned.startswith("https://"):
        cleaned = "https://" + cleaned
    # Previous builds saved the /login suffix; strip it to match the documented host
    # used by /authorize and /token endpoints.
    if cleaned.rstrip("/").endswith("/login"):
        cleaned = cleaned.rstrip("/")[:- len("/login")]
    return cleaned.rstrip("/")


def load_config() -> GatewayConfig:
    ensure_data_dir()
    config: GatewayConfig = DEFAULT_CONFIG.copy()
    loaded: GatewayConfig | None = None
    if CONFIG_PATH.exists():
        try:
            loaded = GatewayConfig(**json.loads(CONFIG_PATH.read_text()))
        except Exception:
            pass
    if loaded:
        config.update(loaded)

    # Auto-migrate old/blank hosts to the documented endpoint so name resolution
    # errors from the deprecated "openapi.ultraloq.com" host are avoided.
    normalized_base = normalize_base_url(config.get("base_url", ""))
    normalized_oauth_base = normalize_oauth_base_url(config.get("oauth_base_url", ""))
    normalized_devices_path = normalize_devices_path(config.get("devices_path", ""))
    needs_save = False
    if not config.get("base_url") or config.get("base_url") != normalized_base:
        config["base_url"] = normalized_base
        needs_save = True
    if not config.get("oauth_base_url") or config.get("oauth_base_url") != normalized_oauth_base:
        config["oauth_base_url"] = normalized_oauth_base
        needs_save = True
    if not config.get("devices_path") or config.get("devices_path") != normalized_devices_path:
        config["devices_path"] = normalized_devices_path
        needs_save = True

    if needs_save:
        CONFIG_PATH.write_text(json.dumps(config, indent=2))

    return config


def save_config(config: GatewayConfig) -> None:
    ensure_data_dir()
    CONFIG_PATH.write_text(json.dumps(config, indent=2))


__all__ = [
    "GatewayConfig",
    "DEFAULT_CONFIG",
    "normalize_base_url",
    "normalize_oauth_base_url",
    "normalize_devices_path",
    "load_config",
    "save_config",
    "CONFIG_PATH",
    "DATA_DIR",
    "LOG_PATH",
    "ensure_data_dir",
]
