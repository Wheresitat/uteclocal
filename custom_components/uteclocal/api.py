from __future__ import annotations

from typing import Any

import aiohttp


class UtecLocalAPI:
    """Simple async HTTP client to the local U-tec gateway."""

    def __init__(self, host: str) -> None:
        self._host = host.rstrip("/")

    async def _post(self, url: str, payload: dict[str, Any]) -> None:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as resp:
                resp.raise_for_status()

    async def async_get_devices(self) -> list[dict[str, Any]]:
        """Return a list of devices from the gateway."""
        url = f"{self._host}/api/devices"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                resp.raise_for_status()
                data = await resp.json(content_type=None)
        payload = data.get("payload") or {}
        devices = payload.get("devices") or []
        if isinstance(data, list):
            return data
        return devices

    async def async_get_bridge_status(self) -> dict[str, Any]:
        url = f"{self._host}/api/status"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                resp.raise_for_status()
                return await resp.json(content_type=None)

    async def async_lock(self, device_id: str) -> None:
        """Send lock command to gateway."""
        url = f"{self._host}/api/devices/{device_id}/lock"
        try:
            await self._post(url, {})
        except aiohttp.ClientResponseError as exc:
            if exc.status == 404:
                await self._post(f"{self._host}/lock", {"id": device_id})
            else:
                raise

    async def async_unlock(self, device_id: str) -> None:
        """Send unlock command to gateway."""
        url = f"{self._host}/api/devices/{device_id}/unlock"
        try:
            await self._post(url, {})
        except aiohttp.ClientResponseError as exc:
            if exc.status == 404:
                await self._post(f"{self._host}/unlock", {"id": device_id})
            else:
                raise

    async def async_get_status(self, device_id: str) -> dict[str, Any]:
        """Get raw status JSON for a device."""
        url = f"{self._host}/api/devices/{device_id}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                resp.raise_for_status()
                data = await resp.json(content_type=None)
        return data
