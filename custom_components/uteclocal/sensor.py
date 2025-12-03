from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


def _extract_battery(device: dict[str, Any]) -> int | None:
    payload = device.get("data") or device
    inner = payload.get("payload") or {}
    devices = inner.get("devices") or []
    if devices:
        payload = devices[0]
    states = payload.get("states") or payload.get("state") or []
    if isinstance(states, dict):
        states = [states]
    for s in states:
        cap = (s.get("capability") or "").lower()
        name = (s.get("name") or s.get("attribute") or "").lower()
        if cap == "st.batterylevel" and name == "level":
            try:
                return int(s.get("value"))
            except (TypeError, ValueError):
                return None
    return None


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]

    entities: list[UtecBatterySensor] = []
    for dev in coordinator.data:
        dev_id = str(dev.get("id"))
        name = dev.get("name") or f"U-tec Battery {dev_id}"
        entities.append(UtecBatterySensor(dev_id, name, entry.entry_id, coordinator))

    async_add_entities(entities)


class UtecBatterySensor(CoordinatorEntity, SensorEntity):
    _attr_icon = "mdi:battery"
    _attr_has_entity_name = True
    _attr_native_unit_of_measurement = "%"

    def __init__(self, device_id: str, name: str, entry_id: str, coordinator) -> None:
        super().__init__(coordinator)
        self._device_id = device_id
        self._attr_unique_id = f"{entry_id}_{device_id}_battery"
        self._attr_name = f"{name} Battery"

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            name=self._attr_name,
            manufacturer="U-tec",
            via_device=(DOMAIN, "gateway"),
        )

    def _handle_coordinator_update(self) -> None:
        battery = None
        for dev in self.coordinator.data:
            if str(dev.get("id")) == self._device_id:
                battery = _extract_battery(dev)
                break
        self._attr_native_value = battery
        self.async_write_ha_state()

