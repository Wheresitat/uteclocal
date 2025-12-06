from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import UtecLocalAPI
from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up U-tec Local sensors from a config entry."""
    host: str = hass.data[DOMAIN][entry.entry_id]["host"]
    api = UtecLocalAPI(host)

    devices = await api.async_get_devices()

    entities: list[SensorEntity] = []
    for dev in devices:
        dev_id = str(dev.get("id"))
        name = dev.get("name") or f"U-tec Lock {dev_id}"
        entities.append(
            UtecLocalBatterySensor(dev_id, name, api, entry.entry_id)
        )
        entities.append(
            UtecLocalHealthSensor(dev_id, name, api, entry.entry_id)
        )

    async_add_entities(entities, update_before_add=False)


class _BaseStatusSensor(SensorEntity):
    """Shared helpers for status-driven sensors."""

    _attr_should_poll = True

    def __init__(
        self,
        device_id: str,
        name: str,
        api: UtecLocalAPI,
        entry_id: str,
    ) -> None:
        self._device_id = device_id
        self._api = api
        self._attr_name = name
        self._entry_id = entry_id

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            name=self._attr_name,
            manufacturer="U-tec",
            via_device=(DOMAIN, "gateway"),
        )

    async def _fetch_states(self) -> list[dict[str, Any]]:
        """Fetch the state payload for this device via the gateway."""
        try:
            data = await self._api.async_get_status(self._device_id)
        except Exception:
            return []

        payload = data.get("payload") or {}
        devices = payload.get("devices") or []
        if not devices:
            return []

        states = devices[0].get("states") or devices[0].get("state") or []
        if isinstance(states, dict):
            return [states]
        return states


class UtecLocalBatterySensor(_BaseStatusSensor):
    """Battery level reported by the lock (scale 1-5)."""

    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self, device_id: str, name: str, api: UtecLocalAPI, entry_id: str
    ) -> None:
        super().__init__(device_id, f"{name} Battery", api, entry_id)
        self._attr_unique_id = f"{entry_id}_{device_id}_battery"

    async def async_update(self) -> None:
        states = await self._fetch_states()
        battery_level: int | None = None

        for state in states:
            cap = (state.get("capability") or "").lower()
            name = (state.get("name") or state.get("attribute") or "").lower()
            value = state.get("value")

            if cap == "st.batterylevel" and name == "level":
                try:
                    battery_level = int(value)
                except (TypeError, ValueError):
                    continue

        if battery_level is None:
            return

        # Convert documented 1-5 level into a percentage for HA battery UI.
        percentage = max(0, min(5, battery_level)) * 20
        self._attr_native_value = percentage


class UtecLocalHealthSensor(_BaseStatusSensor):
    """Health status string reported by the lock."""

    def __init__(
        self, device_id: str, name: str, api: UtecLocalAPI, entry_id: str
    ) -> None:
        super().__init__(device_id, f"{name} Health", api, entry_id)
        self._attr_unique_id = f"{entry_id}_{device_id}_health"

    async def async_update(self) -> None:
        states = await self._fetch_states()
        health_status: str | None = None

        for state in states:
            cap = (state.get("capability") or "").lower()
            name = (state.get("name") or state.get("attribute") or "").lower()
            value = state.get("value")

            if cap == "st.healthcheck" and name == "status" and isinstance(value, str):
                health_status = value
                break

        if health_status is None:
            return

        self._attr_native_value = health_status
