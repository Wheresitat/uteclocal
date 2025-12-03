import aiohttp

class UtecLocalAPI:
    def __init__(self, host):
        self._host = host.rstrip("/")

    async def async_get_devices(self):
        url=f"{self._host}/api/devices"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                resp.raise_for_status()
                data = await resp.json(content_type=None)
        payload=data.get("payload") or {}
        devices=payload.get("devices") or []
        if isinstance(data,list):
            return data
        return devices

    async def async_lock(self, device_id):
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{self._host}/lock", json={"id":device_id}) as resp:
                resp.raise_for_status()

    async def async_unlock(self, device_id):
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{self._host}/unlock", json={"id":device_id}) as resp:
                resp.raise_for_status()
