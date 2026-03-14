import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers import selector

from .const import DOMAIN


class CarbonAwareThermostatConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step where the user adds the integration."""
        errors = {}

        if user_input is not None:
            # Here you could add a check to validate the API key
            return self.async_create_entry(
                title="Carbon Aware Thermostat",
                data=user_input
            )

        # Define the schema for the UI form
        data_schema = vol.Schema({
            # API Key Input
            vol.Required("api_key"): str,
        })

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )

