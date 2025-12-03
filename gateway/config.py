from __future__ import annotations

import json
from pathlib import Path
from typing import Any, TypedDict


class GatewayConfig(TypedDict, total=False):
    base_url: str
    client_id: str
    client_secret: str
    access_key: str
    secret_key: str
    log_level: str
    polling_interval: int
    access_token: str
    refresh_token: str
    token_expires_at: str


DATA_DIR = Path("/data")
CONFIG_PATH = DATA_DIR / "config.json"
LOG_PATH = DATA_DIR / "gateway.log"

DEFAULT_CONFIG: GatewayConfig = {
    "base_url": "https://api.utec.com",
    "client_id": "",
    "client_secret": "",
    "access_key": "",
    "secret_key": "",
    "log_level": "INFO",
    "polling_interval": 60,
}


def ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    try:
        DATA_DIR.chmod(0o700)
    except PermissionError:
        # Best-effort; containerized environments may ignore chmod.
        pass


def load_config() -> GatewayConfig:
    ensure_data_dir()
    if CONFIG_PATH.exists():
        try:
            return GatewayConfig(**json.loads(CONFIG_PATH.read_text()))
        except Exception:
            pass
    return DEFAULT_CONFIG.copy()


def save_config(config: GatewayConfig) -> None:
    ensure_data_dir()
    CONFIG_PATH.write_text(json.dumps(config, indent=2))
    try:
        CONFIG_PATH.chmod(0o600)
    except PermissionError:
        # Ignore if the filesystem does not allow changing permissions.
        pass


__all__ = [
    "GatewayConfig",
    "DEFAULT_CONFIG",
    "load_config",
    "save_config",
    "CONFIG_PATH",
    "DATA_DIR",
    "LOG_PATH",
    "ensure_data_dir",
]
