import aiohttp
import voluptuous as vol
from homeassistant import config_entries

from .const import DEFAULT_HOST, DEFAULT_SCAN_INTERVAL, DOMAIN


async def validate_input(hass, data):
    host = data["host"].rstrip("/")
    url = f"{host}/api/status"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            resp.raise_for_status()
            await resp.json(content_type=None)
    return {"host": host}

class UtecLocalConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION=1
    async def async_step_user(self, user_input=None):
        errors={}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except Exception:
                errors["base"]="cannot_connect"
            else:
                return self.async_create_entry(title="U-tec Local Gateway", data={"host": info["host"]})

        schema = vol.Schema({ vol.Required("host", default=DEFAULT_HOST): str })
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_get_options_flow(self, config_entry):
        return UtecLocalOptionsFlow(config_entry)


class UtecLocalOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        errors={}
        if user_input is not None:
            try:
                await validate_input(self.hass, user_input)
            except Exception:
                errors["base"]="cannot_connect"
            else:
                return self.async_create_entry(title="", data=user_input)

        schema = vol.Schema({
            vol.Required("host", default=self.config_entry.data.get("host", DEFAULT_HOST)): str,
            vol.Required("scan_interval", default=self.config_entry.options.get("scan_interval", DEFAULT_SCAN_INTERVAL)): int,
        })
        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)
