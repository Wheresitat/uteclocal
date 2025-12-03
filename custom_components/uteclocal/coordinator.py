from __future__ import annotations

from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import UtecLocalAPI
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN


class UtecDataUpdateCoordinator(DataUpdateCoordinator[list[dict[str, Any]]]):
    """Coordinator that polls the local gateway for device state."""

    def __init__(self, hass: HomeAssistant, api: UtecLocalAPI, scan_interval: int) -> None:
        super().__init__(
            hass,
            hass.logger,
            name=f"{DOMAIN} data",
            update_interval=timedelta(seconds=max(scan_interval, 10)),
        )
        self.api = api

    async def _async_update_data(self) -> list[dict[str, Any]]:
        try:
            return await self.api.async_get_devices()
        except Exception as exc:
            raise UpdateFailed(f"Failed to fetch devices: {exc}") from exc


async def async_setup_coordinator(hass: HomeAssistant, host: str, scan_interval: int | None) -> UtecDataUpdateCoordinator:
    api = UtecLocalAPI(host)
    coordinator = UtecDataUpdateCoordinator(hass, api, scan_interval or DEFAULT_SCAN_INTERVAL)
    await coordinator.async_config_entry_first_refresh()
    return coordinator

