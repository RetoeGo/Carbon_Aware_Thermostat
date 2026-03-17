from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers import selector
import homeassistant.helpers.config_validation as cv

from .const import (
    CONF_CARBON_INTENSITY_SENSOR,
    CONF_CLIMATE_ENTITY,
    CONF_COMFORT_SETPOINT,
    CONF_CONTROL_REAL_THERMOSTAT,
    CONF_DEMO_EXPOSED_AREA,
    CONF_DEMO_ROOM_HEIGHT,
    CONF_DEMO_ROOM_LENGTH,
    CONF_DEMO_ROOM_TEMP,
    CONF_DEMO_ROOM_WIDTH,
    CONF_DEMO_TARGET_TEMP,
    CONF_ECO_OFFSET,
    CONF_FORECAST_POINTS,
    CONF_FORECAST_STEP_MINUTES,
    CONF_MODE,
    CONF_MPC_HORIZON,
    CONF_NAME,
    CONF_PREHEAT_OFFSET,
    CONF_TARGET_CLIMATE,
    CONF_THERMOSTAT_POWER,
    CONF_WEATHER_ENTITY,
    CONF_WINDOW_PERCENT,
    DEFAULT_DEMO_EXPOSED_AREA,
    DEFAULT_DEMO_ROOM_HEIGHT,
    DEFAULT_DEMO_ROOM_LENGTH,
    DEFAULT_DEMO_ROOM_TEMP,
    DEFAULT_DEMO_ROOM_WIDTH,
    DEFAULT_DEMO_TARGET_TEMP,
    DEFAULT_ECO_OFFSET,
    DEFAULT_FORECAST_POINTS,
    DEFAULT_FORECAST_STEP_MINUTES,
    DEFAULT_MODE,
    DEFAULT_MPC_HORIZON,
    DEFAULT_NAME,
    DEFAULT_PREHEAT_OFFSET,
    DEFAULT_THERMOSTAT_POWER,
    DEFAULT_WINDOW_PERCENT,
    DOMAIN,
)


class CarbonAwareThermostatConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 3

    def __init__(self) -> None:
        self._base_data: dict[str, object] = {}

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            self._base_data = dict(user_input)
            if user_input[CONF_MODE] == "demo":
                return await self.async_step_demo()
            return await self.async_step_live()

        schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default=DEFAULT_NAME): cv.string,
                vol.Required(CONF_MODE, default=DEFAULT_MODE): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=["live", "demo"],
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema)

    async def async_step_demo(self, user_input=None):
        if user_input is not None:
            data = {**self._base_data, **user_input, CONF_CONTROL_REAL_THERMOSTAT: False, CONF_CLIMATE_ENTITY: ""}
            return self.async_create_entry(title=str(data.get(CONF_NAME, DEFAULT_NAME)), data=data)

        schema = vol.Schema(
            {
                vol.Required(CONF_TARGET_CLIMATE, default=DEFAULT_DEMO_TARGET_TEMP): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=5, max=30, step=0.5, mode=selector.NumberSelectorMode.BOX)
                ),
                vol.Required(CONF_DEMO_ROOM_TEMP, default=DEFAULT_DEMO_ROOM_TEMP): vol.Coerce(float),
                vol.Required(CONF_DEMO_TARGET_TEMP, default=DEFAULT_DEMO_TARGET_TEMP): vol.Coerce(float),
                vol.Required(CONF_COMFORT_SETPOINT, default=DEFAULT_DEMO_TARGET_TEMP): vol.Coerce(float),
                vol.Required(CONF_DEMO_ROOM_HEIGHT, default=DEFAULT_DEMO_ROOM_HEIGHT): vol.Coerce(float),
                vol.Required(CONF_DEMO_ROOM_WIDTH, default=DEFAULT_DEMO_ROOM_WIDTH): vol.Coerce(float),
                vol.Required(CONF_DEMO_ROOM_LENGTH, default=DEFAULT_DEMO_ROOM_LENGTH): vol.Coerce(float),
                vol.Required(CONF_DEMO_EXPOSED_AREA, default=DEFAULT_DEMO_EXPOSED_AREA): vol.Coerce(float),
                vol.Required(CONF_WINDOW_PERCENT, default=DEFAULT_WINDOW_PERCENT): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=0.0, max=1.0, step=0.05, mode=selector.NumberSelectorMode.BOX)
                ),
                vol.Required(CONF_THERMOSTAT_POWER, default=DEFAULT_THERMOSTAT_POWER): vol.Coerce(float),
                vol.Required(CONF_MPC_HORIZON, default=DEFAULT_MPC_HORIZON): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=1, max=96, step=1, mode=selector.NumberSelectorMode.BOX)
                ),
                vol.Required(CONF_ECO_OFFSET, default=DEFAULT_ECO_OFFSET): vol.Coerce(float),
                vol.Required(CONF_PREHEAT_OFFSET, default=DEFAULT_PREHEAT_OFFSET): vol.Coerce(float),
                vol.Required(CONF_FORECAST_POINTS, default=DEFAULT_FORECAST_POINTS): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=1, max=96, step=1, mode=selector.NumberSelectorMode.BOX)
                ),
                vol.Required(CONF_FORECAST_STEP_MINUTES, default=DEFAULT_FORECAST_STEP_MINUTES): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=5, max=120, step=5, mode=selector.NumberSelectorMode.BOX)
                ),
                vol.Optional(CONF_CARBON_INTENSITY_SENSOR): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Optional(CONF_WEATHER_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="weather")
                ),
            }
        )
        return self.async_show_form(step_id="demo", data_schema=schema)

    async def async_step_live(self, user_input=None):
        if user_input is not None:
            data = {**self._base_data, **user_input}
            return self.async_create_entry(title=str(data.get(CONF_NAME, DEFAULT_NAME)), data=data)

        schema = vol.Schema(
            {
                vol.Required(CONF_TARGET_CLIMATE, default=DEFAULT_DEMO_TARGET_TEMP): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=5, max=30, step=0.5, mode=selector.NumberSelectorMode.BOX)
                ),
                vol.Optional(CONF_CLIMATE_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="climate")
                ),
                vol.Optional(CONF_CARBON_INTENSITY_SENSOR): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Optional(CONF_WEATHER_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="weather")
                ),
                vol.Required(CONF_DEMO_ROOM_TEMP, default=DEFAULT_DEMO_ROOM_TEMP): vol.Coerce(float),
                vol.Required(CONF_COMFORT_SETPOINT, default=DEFAULT_DEMO_TARGET_TEMP): vol.Coerce(float),
                vol.Required(CONF_DEMO_ROOM_HEIGHT, default=DEFAULT_DEMO_ROOM_HEIGHT): vol.Coerce(float),
                vol.Required(CONF_DEMO_ROOM_WIDTH, default=DEFAULT_DEMO_ROOM_WIDTH): vol.Coerce(float),
                vol.Required(CONF_DEMO_ROOM_LENGTH, default=DEFAULT_DEMO_ROOM_LENGTH): vol.Coerce(float),
                vol.Required(CONF_DEMO_EXPOSED_AREA, default=DEFAULT_DEMO_EXPOSED_AREA): vol.Coerce(float),
                vol.Required(CONF_WINDOW_PERCENT, default=DEFAULT_WINDOW_PERCENT): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=0.0, max=1.0, step=0.05, mode=selector.NumberSelectorMode.BOX)
                ),
                vol.Required(CONF_THERMOSTAT_POWER, default=DEFAULT_THERMOSTAT_POWER): vol.Coerce(float),
                vol.Required(CONF_MPC_HORIZON, default=DEFAULT_MPC_HORIZON): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=1, max=96, step=1, mode=selector.NumberSelectorMode.BOX)
                ),
                vol.Required(CONF_ECO_OFFSET, default=DEFAULT_ECO_OFFSET): vol.Coerce(float),
                vol.Required(CONF_PREHEAT_OFFSET, default=DEFAULT_PREHEAT_OFFSET): vol.Coerce(float),
                vol.Required(CONF_CONTROL_REAL_THERMOSTAT, default=False): bool,
                vol.Required(CONF_FORECAST_POINTS, default=DEFAULT_FORECAST_POINTS): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=1, max=96, step=1, mode=selector.NumberSelectorMode.BOX)
                ),
                vol.Required(CONF_FORECAST_STEP_MINUTES, default=DEFAULT_FORECAST_STEP_MINUTES): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=5, max=120, step=5, mode=selector.NumberSelectorMode.BOX)
                ),
            }
        )
        return self.async_show_form(step_id="live", data_schema=schema)
