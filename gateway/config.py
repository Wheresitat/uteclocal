from __future__ import annotations

import json
import os
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
    "base_url": os.getenv("GATEWAY_BASE_URL", "https://openapi.ultraloq.com"),
    "access_key": os.getenv("GATEWAY_ACCESS_KEY", ""),
    "secret_key": os.getenv("GATEWAY_SECRET_KEY", ""),
    "log_level": os.getenv("GATEWAY_LOG_LEVEL", "INFO"),
    "scope": os.getenv("GATEWAY_SCOPE", ""),
}


def ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


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

    # Environment variables always take precedence over saved values so the
    # container can be configured via docker compose without manually editing
    # /data/config.json.
    for key, env_var in (
        ("base_url", "GATEWAY_BASE_URL"),
        ("access_key", "GATEWAY_ACCESS_KEY"),
        ("secret_key", "GATEWAY_SECRET_KEY"),
        ("log_level", "GATEWAY_LOG_LEVEL"),
        ("scope", "GATEWAY_SCOPE"),
    ):
        env_value = os.getenv(env_var)
        if env_value is not None and env_value != "":
            config[key] = env_value

    # Auto-migrate old/blank hosts to the documented endpoint so name resolution
    # errors from the legacy "openapi.u-tec.com" host are avoided.
    normalized_base = (config.get("base_url") or "").strip()
    needs_save = False
    if not normalized_base:
        config["base_url"] = DEFAULT_CONFIG["base_url"]
        needs_save = True
    elif "openapi.u-tec.com" in normalized_base:
        config["base_url"] = DEFAULT_CONFIG["base_url"]
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
    "load_config",
    "save_config",
    "CONFIG_PATH",
    "DATA_DIR",
    "LOG_PATH",
    "ensure_data_dir",
]
