from __future__ import annotations

from typing import Any

import aiohttp


class UtecLocalAPI:
    """Simple async HTTP client to the local U-tec gateway."""

    def __init__(self, host: str) -> None:
        self._host = host.rstrip("/")

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

    async def async_lock(self, device_id: str) -> None:
        """Send lock command to gateway."""
        url = f"{self._host}/lock"
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json={"id": device_id}) as resp:
                resp.raise_for_status()

    async def async_unlock(self, device_id: str) -> None:
        """Send unlock command to gateway."""
        url = f"{self._host}/unlock"
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json={"id": device_id}) as resp:
                resp.raise_for_status()

    async def async_get_status(self, device_id: str) -> dict[str, Any]:
        """Get raw status JSON for a device."""
        url = f"{self._host}/api/status"
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json={"id": device_id}) as resp:
                resp.raise_for_status()
                data = await resp.json(content_type=None)
        return data
