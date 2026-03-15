import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers import selector
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN


class CarbonAwareThermostatConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step where the user adds the integration."""

        if user_input is not None:
            # Here you could add a check to validate the API key
            return self.async_create_entry(
                title="Carbon Aware Thermostat",
                data=user_input
            )

        # Define the schema for the UI form
        data_schema = vol.Schema({
            vol.Required("name", default="Living Room"): cv.string,

            # Input Sensors
            vol.Required("carbon_sensor"): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            ),
            vol.Optional("weather_entity"): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="weather")
            ),

            # Target Hardware
            vol.Required("target_climate"): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="climate")
            ),

            # Logic Parameters
            vol.Required("co2_threshold", default=300): vol.Coerce(int),
            vol.Required("eco_offset", default=-1.5): vol.Coerce(float),
            vol.Required("preheat_offset", default=1.0): vol.Coerce(float),
        })

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
        )

