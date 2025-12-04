from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Iterable

from .config import LOG_PATH, ensure_data_dir


def setup_logging(log_level: str = "INFO") -> None:
    ensure_data_dir()
    logger = logging.getLogger()
    logger.handlers.clear()
    logger.setLevel(log_level)
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

    file_handler = RotatingFileHandler(LOG_PATH, maxBytes=1_000_000, backupCount=3)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)


def read_log_lines(limit: int | None = 200) -> list[str]:
    if not LOG_PATH.exists():
        return []
    lines: Iterable[str] = LOG_PATH.read_text().splitlines()
    if limit is not None:
        return list(lines)[-limit:]
    return list(lines)


def clear_logs() -> None:
    if LOG_PATH.exists():
        LOG_PATH.unlink()
