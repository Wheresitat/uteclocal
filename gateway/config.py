from __future__ import annotations

import json
from pathlib import Path
from typing import Any, TypedDict


class GatewayConfig(TypedDict, total=False):
    base_url: str
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
    # U-tec Open API per public docs: https://openapi.ultraloq.com
    "base_url": "https://openapi.ultraloq.com",
    "access_key": "",
    "secret_key": "",
    "auth_code": "",
    "access_token": "",
    "refresh_token": "",
    "token_type": "Bearer",
    "token_expires_in": 0,
    "log_level": "INFO",
    "scope": "",
    "redirect_url": "",
}


def ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def normalize_base_url(url: str) -> str:
    cleaned = (url or "").strip()
    if not cleaned:
        return DEFAULT_CONFIG["base_url"]
    if not cleaned.startswith("http://") and not cleaned.startswith("https://"):
        cleaned = "https://" + cleaned
    return cleaned


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
    # errors from the legacy "openapi.u-tec.com" host are avoided.
    normalized_base = normalize_base_url(config.get("base_url", ""))
    needs_save = False
    if not config.get("base_url") or config.get("base_url") != normalized_base:
        config["base_url"] = normalized_base
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
    "load_config",
    "save_config",
    "CONFIG_PATH",
    "DATA_DIR",
    "LOG_PATH",
    "ensure_data_dir",
]
