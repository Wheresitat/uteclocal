from homeassistant.components.lock import LockEntity
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from .const import DOMAIN
from .api import UtecLocalAPI

async def async_setup_entry(hass:HomeAssistant, entry:ConfigEntry, async_add_entities):
    host=hass.data[DOMAIN][entry.entry_id]["host"]
    api=UtecLocalAPI(host)
    devices=await api.async_get_devices()

    entities=[]
    for d in devices:
        dev_id=str(d.get("id"))
        name=d.get("name") or f"U-tec Lock {dev_id}"
        entities.append(UtecLocalLock(dev_id, name, api, entry.entry_id))

    async_add_entities(entities)

class UtecLocalLock(LockEntity):
    _attr_has_entity_name=True

    def __init__(self, device_id, name, api, entry_id):
        self._device_id=device_id
        self._attr_unique_id=f"{entry_id}_{device_id}"
        self._attr_name=name
        self._api=api
        self._is_locked=None

    @property
    def is_locked(self):
        return self._is_locked

    @property
    def device_info(self):
        return DeviceInfo(
            identifiers={(DOMAIN,self._device_id)},
            name=self._attr_name,
            manufacturer="U-tec",
            via_device=(DOMAIN,"gateway"),
        )

    async def async_lock(self, **kwargs):
        await self._api.async_lock(self._device_id)
        self._is_locked=True
        self.async_write_ha_state()

    async def async_unlock(self, **kwargs):
        await self._api.async_unlock(self._device_id)
        self._is_locked=False
        self.async_write_ha_state()
