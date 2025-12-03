from __future__ import annotations

from typing import Any

from homeassistant.components.lock import LockEntity
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .api import UtecLocalAPI


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up U-tec Local lock entities from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    api = UtecLocalAPI(data["host"])

    entities: list[UtecLocalLock] = []
    for dev in coordinator.data:
        dev_id = str(dev.get("id"))
        name = dev.get("name") or f"U-tec Lock {dev_id}"
        entities.append(UtecLocalLock(dev_id, name, api, entry.entry_id, coordinator))

    async_add_entities(entities)


class UtecLocalLock(CoordinatorEntity, LockEntity):
    """Representation of a U-tec lock exposed via the local gateway."""

    _attr_has_entity_name = True

    def __init__(
        self,
        device_id: str,
        name: str,
        api: UtecLocalAPI,
        entry_id: str,
        coordinator,
    ) -> None:
        super().__init__(coordinator)
        self._device_id = device_id
        self._attr_unique_id = f"{entry_id}_{device_id}"
        self._attr_name = name
        self._api = api
        self._is_locked: bool | None = None
        self._battery_level: int | None = None
        self._health_status: str | None = None

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success

    @property
    def is_locked(self) -> bool | None:
        return self._is_locked

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        attrs: dict[str, Any] = {}
        if self._battery_level is not None:
            attrs["battery_level"] = self._battery_level
        if self._health_status is not None:
            attrs["health_status"] = self._health_status
        return attrs

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            name=self._attr_name,
            manufacturer="U-tec",
            via_device=(DOMAIN, "gateway"),
        )

    async def async_lock(self, **kwargs: Any) -> None:
        await self._api.async_lock(self._device_id)
        await self.coordinator.async_request_refresh()

    async def async_unlock(self, **kwargs: Any) -> None:
        await self._api.async_unlock(self._device_id)
        await self.coordinator.async_request_refresh()

    @property
    def _device_payload(self) -> dict[str, Any] | None:
        for dev in self.coordinator.data:
            if str(dev.get("id")) == self._device_id:
                return dev.get("data") or dev
        return None

    @property
    def _states(self) -> list[dict[str, Any]]:
        data = self._device_payload or {}
        payload = data.get("payload") or {}
        devices = payload.get("devices") or []
        if devices:
            data = devices[0]
        states = data.get("states") or data.get("state") or []
        if isinstance(states, dict):
            return [states]
        return states

    def _handle_coordinator_update(self) -> None:
        lock_state: bool | None = None
        battery_level: int | None = None
        health_status: str | None = None

        for s in self._states:
            cap = (s.get("capability") or "").lower()
            name = (s.get("name") or s.get("attribute") or "").lower()
            value = s.get("value")

            if cap == "st.healthcheck" and name == "status" and isinstance(value, str):
                health_status = value
            if cap == "st.lock" and name == "lockstate" and isinstance(value, str):
                v = value.lower()
                if v == "locked":
                    lock_state = True
                elif v == "unlocked":
                    lock_state = False
            if cap == "st.batterylevel" and name == "level":
                try:
                    battery_level = int(value)
                except (TypeError, ValueError):
                    pass

        if lock_state is not None:
            self._is_locked = lock_state
        if battery_level is not None:
            self._battery_level = battery_level
        if health_status is not None:
            self._health_status = health_status

        self.async_write_ha_state()
