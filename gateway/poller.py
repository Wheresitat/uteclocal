from __future__ import annotations

import asyncio
import datetime as dt
import logging
import random
from typing import Callable

from .client import UtecCloudClient
from .config import GatewayConfig, save_config
from .state import STATE

logger = logging.getLogger(__name__)


class Poller:
    """Background poller that keeps device state in sync."""

    def __init__(self, config_loader: Callable[[], GatewayConfig]) -> None:
        self._config_loader = config_loader
        self._task: asyncio.Task | None = None
        self._stop_event = asyncio.Event()

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._stop_event.clear()
            self._task = asyncio.create_task(self._run())
            logger.info("Started background poller")
            STATE.set_poller_running(True)

    async def stop(self) -> None:
        if self._task:
            self._stop_event.set()
            await self._task
            logger.info("Stopped background poller")
            STATE.set_poller_running(False)

    async def _run(self) -> None:
        try:
            while not self._stop_event.is_set():
                config = self._config_loader()
                interval = max(int(config.get("polling_interval", 60)), 15)

                try:
                    await self._poll_once(config)
                except Exception as exc:  # pragma: no cover - background safety
                    logger.exception("Polling failed: %s", exc)
                    STATE.set_error(str(exc))

                try:
                    await asyncio.wait_for(self._stop_event.wait(), timeout=interval)
                except asyncio.TimeoutError:
                    continue
        finally:
            STATE.set_poller_running(False)

    async def _poll_once(self, config: GatewayConfig) -> None:
        if not (config.get("base_url") or "").strip():
            STATE.set_error("Base URL is not configured")
            return

        if not config.get("access_token"):
            STATE.set_error("No access token configured; OAuth flow not complete")
            return

        async with UtecCloudClient(config) as client:
            await self._ensure_token_valid(client, config)
            devices = await self._fetch_with_retry(lambda: client.fetch_devices())
            STATE.set_devices(devices)

            for device in devices:
                device_id = str(device.get("id"))
                if not device_id:
                    continue
                try:
                    details = await self._fetch_with_retry(lambda: client.fetch_status(device_id))
                    STATE.update_device(device_id, details, available=True, error=None)
                except Exception as exc:  # pragma: no cover - defensive
                    logger.warning("Failed to refresh device %s: %s", device_id, exc)
                    STATE.update_device(device_id, device, available=False, error=str(exc))

    async def _ensure_token_valid(self, client: UtecCloudClient, config: GatewayConfig) -> None:
        expiry_raw = config.get("token_expires_at")
        if expiry_raw:
            try:
                expiry = dt.datetime.fromisoformat(expiry_raw)
                STATE.set_token_expiry(expiry)
            except ValueError:
                expiry = None
        else:
            expiry = None

        if expiry and expiry > dt.datetime.utcnow() + dt.timedelta(seconds=30):
            return

        if not config.get("refresh_token"):
            logger.warning("Access token missing or expired and no refresh token present")
            STATE.set_error("Token expired; please re-run OAuth flow")
            return

        logger.info("Refreshing OAuth token before expiry")
        token = await client.refresh_token()
        if token:
            config.update(token)
            save_config(config)
            try:
                expires_in = int(token.get("expires_in", 0))
                new_expiry = dt.datetime.utcnow() + dt.timedelta(seconds=expires_in)
                STATE.set_token_expiry(new_expiry)
            except Exception:
                STATE.set_token_expiry(None)

    async def _fetch_with_retry(self, func: Callable[[], "asyncio.Future[Any]"] | Callable[[], Any], retries: int = 3) -> Any:
        delay = 1.0
        last_exc: Exception | None = None
        for attempt in range(1, retries + 1):
            try:
                result = func()
                if asyncio.iscoroutine(result):
                    return await result
                return result
            except Exception as exc:  # pragma: no cover - defensive
                last_exc = exc
                if attempt == retries:
                    break
                jitter = random.uniform(0, 0.5)
                logger.warning(
                    "Retrying after error (attempt %s/%s): %s", attempt, retries, exc
                )
                await asyncio.sleep(delay + jitter)
                delay = min(delay * 2, 30)
        if last_exc:
            raise last_exc


POLLING_MANAGER = Poller(lambda: client_config_loader())


def client_config_loader() -> GatewayConfig:
    from .config import load_config

    return load_config()

