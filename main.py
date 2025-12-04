"""Entry point for running the gateway with environment-driven settings."""
from __future__ import annotations

import os
import uvicorn


def main() -> None:
    port = int(os.getenv("UTECLocal_PORT", "8124"))
    log_level = os.getenv("UTECLocal_LOG_LEVEL", "info").lower()
    uvicorn.run(
        "gateway.app:app",
        host="0.0.0.0",
        port=port,
        log_level=log_level,
    )


if __name__ == "__main__":
    main()
