from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers import selector
import homeassistant.helpers.config_validation as cv

from .const import (
    CONF_AGGRESSIVE_OFFSET,
    CONF_CARBON_INTENSITY_SENSOR,
    CONF_CLIMATE_ENTITY,
    CONF_CONTROL_REAL_THERMOSTAT,
    CONF_ECO_OFFSET,
    CONF_MANUAL_TARGET_TEMP,
    CONF_MODE,
    CONF_NAME,
    CONF_PREFERRED_OFFSET,
    CONF_TARGET_MODE,
    CONF_WEATHER_ENTITY,
    DEFAULT_AGGRESSIVE_OFFSET,
    DEFAULT_ECO_OFFSET,
    DEFAULT_MANUAL_TARGET_TEMP,
    DEFAULT_MODE,
    DEFAULT_NAME,
    DEFAULT_PREFERRED_OFFSET,
    DEFAULT_TARGET_MODE,
    DOMAIN,
    TARGET_MODE_OPTIONS,
)


class CarbonAwareThermostatConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 8

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            data = {**user_input, CONF_MODE: DEFAULT_MODE}
            return self.async_create_entry(title=str(data.get(CONF_NAME, DEFAULT_NAME)), data=data)

        schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default=DEFAULT_NAME): cv.string,
                vol.Required(CONF_CLIMATE_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="climate")
                ),
                vol.Required(CONF_CARBON_INTENSITY_SENSOR): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Required(CONF_WEATHER_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="weather")
                ),
                vol.Required(CONF_TARGET_MODE, default=DEFAULT_TARGET_MODE): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=TARGET_MODE_OPTIONS,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                        translation_key=CONF_TARGET_MODE,
                    )
                ),
                vol.Required(CONF_MANUAL_TARGET_TEMP, default=DEFAULT_MANUAL_TARGET_TEMP): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=5, max=30, step=0.5, mode=selector.NumberSelectorMode.BOX)
                ),
                vol.Required(CONF_ECO_OFFSET, default=DEFAULT_ECO_OFFSET): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=-10, max=10, step=0.5, mode=selector.NumberSelectorMode.BOX)
                ),
                vol.Required(CONF_PREFERRED_OFFSET, default=DEFAULT_PREFERRED_OFFSET): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=-10, max=10, step=0.5, mode=selector.NumberSelectorMode.BOX)
                ),
                vol.Required(CONF_AGGRESSIVE_OFFSET, default=DEFAULT_AGGRESSIVE_OFFSET): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=-10, max=10, step=0.5, mode=selector.NumberSelectorMode.BOX)
                ),
                vol.Required(CONF_CONTROL_REAL_THERMOSTAT, default=False): bool,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema)
