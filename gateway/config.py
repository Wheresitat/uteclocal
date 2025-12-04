from __future__ import annotations

import json
from pathlib import Path
from typing import Any, TypedDict


class GatewayConfig(TypedDict, total=False):
    base_url: str
    access_key: str
    secret_key: str
    log_level: str
    scope: str


DATA_DIR = Path("/data")
CONFIG_PATH = DATA_DIR / "config.json"
LOG_PATH = DATA_DIR / "gateway.log"

DEFAULT_CONFIG: GatewayConfig = {
    # U-tec Open API per public docs: https://openapi.ultraloq.com
    "base_url": "https://openapi.ultraloq.com",
    "access_key": "",
    "secret_key": "",
    "log_level": "INFO",
    "scope": "",
}


def ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


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
