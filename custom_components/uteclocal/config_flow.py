import voluptuous as vol
from homeassistant import config_entries
from .const import DOMAIN, DEFAULT_HOST

async def validate_input(hass, data):
    return {"host": data["host"]}

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
