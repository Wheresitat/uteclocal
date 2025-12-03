from __future__ import annotations

from typing import Any

from homeassistant.components.lock import LockEntity
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .api import UtecLocalAPI


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up U-tec Local lock entities from a config entry."""
    host: str = hass.data[DOMAIN][entry.entry_id]["host"]
    api = UtecLocalAPI(host)

    devices = await api.async_get_devices()

    entities: list[UtecLocalLock] = []
    for dev in devices:
        dev_id = str(dev.get("id"))
        name = dev.get("name") or f"U-tec Lock {dev_id}"
        entities.append(UtecLocalLock(dev_id, name, api, entry.entry_id))

    # We don't need update_before_add because entities will poll
    async_add_entities(entities, update_before_add=False)


class UtecLocalLock(LockEntity):
    """Representation of a U-tec lock exposed via the local gateway."""

    _attr_has_entity_name = True

    def __init__(
        self,
        device_id: str,
        name: str,
        api: UtecLocalAPI,
        entry_id: str,
    ) -> None:
        self._device_id = device_id
        self._attr_unique_id = f"{entry_id}_{device_id}"
        self._attr_name = name
        self._api = api
        self._is_locked: bool | None = None
        self._battery_level: int | None = None  # 1–5
        self._health_status: str | None = None

    # ---------- HA metadata ----------

    @property
    def should_poll(self) -> bool:
        """Tell Home Assistant to call async_update periodically."""
        return True

    @property
    def is_locked(self) -> bool | None:
        return self._is_locked

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose battery level and health as attributes."""
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

    # ---------- Commands ----------

    async def async_lock(self, **kwargs: Any) -> None:
        await self._api.async_lock(self._device_id)
        self._is_locked = True
        self.async_write_ha_state()

    async def async_unlock(self, **kwargs: Any) -> None:
        await self._api.async_unlock(self._device_id)
        self._is_locked = False
        self.async_write_ha_state()

    # ---------- Polling / status ----------

    async def async_update(self) -> None:
        """Query status from the gateway (lock state + battery + health)."""
        try:
            data = await self._api.async_get_status(self._device_id)
        except Exception:
            # If status fetch fails, keep last known state
            return

        # Shape based on your sample:
        # {
        #   "payload": {
        #     "devices": [
        #       {
        #         "id": "...",
        #         "states": [
        #           {"capability":"st.healthCheck","name":"status","value":"Online"},
        #           {"capability":"st.lock","name":"lockState","value":"Unlocked"},
        #           {"capability":"st.lock","name":"lockMode","value":0},
        #           {"capability":"st.batteryLevel","name":"level","value":5}
        #         ]
        #       }
        #     ]
        #   }
        # }
        payload = data.get("payload") or {}
        devices = payload.get("devices") or []
        if not devices:
            return

        dev = devices[0]
        states = dev.get("states") or dev.get("state") or []

        if isinstance(states, dict):
            states = [states]

        lock_state: bool | None = None
        battery_level: int | None = None
        health_status: str | None = None

        for s in states:
            cap = (s.get("capability") or "").lower()
            name = (s.get("name") or s.get("attribute") or "").lower()
            value = s.get("value")

            # Health
            if cap == "st.healthcheck" and name == "status":
                if isinstance(value, str):
                    health_status = value

            # Lock state
            if cap == "st.lock" and name == "lockstate":
                if isinstance(value, str):
                    v = value.lower()
                    if v == "locked":
                        lock_state = True
                    elif v == "unlocked":
                        lock_state = False

            # Battery
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
