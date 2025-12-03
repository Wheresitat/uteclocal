from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


def _extract_online(device: dict[str, Any]) -> bool | None:
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
        val = s.get("value")
        if cap == "st.healthcheck" and name == "status" and isinstance(val, str):
            return val.lower() == "online"
    return None


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]

    entities: list[UtecOnlineBinarySensor] = []
    for dev in coordinator.data:
        dev_id = str(dev.get("id"))
        name = dev.get("name") or f"U-tec Device {dev_id}"
        entities.append(UtecOnlineBinarySensor(dev_id, name, entry.entry_id, coordinator))

    async_add_entities(entities)


class UtecOnlineBinarySensor(CoordinatorEntity, BinarySensorEntity):
    _attr_has_entity_name = True
    _attr_icon = "mdi:lan-connect"

    def __init__(self, device_id: str, name: str, entry_id: str, coordinator) -> None:
        super().__init__(coordinator)
        self._device_id = device_id
        self._attr_unique_id = f"{entry_id}_{device_id}_online"
        self._attr_name = f"{name} Online"

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
        online = None
        for dev in self.coordinator.data:
            if str(dev.get("id")) == self._device_id:
                online = _extract_online(dev)
                break
        self._attr_is_on = online
        self.async_write_ha_state()

