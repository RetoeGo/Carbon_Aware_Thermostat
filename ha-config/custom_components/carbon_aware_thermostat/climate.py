from __future__ import annotations

from typing import Any

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import ClimateEntityFeature, HVACMode
from homeassistant.const import CONF_NAME, UnitOfTemperature
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_APPLIED_HEATING_MODE,
    ATTR_CARBON_FORECAST_LIST,
    ATTR_CONTROL_APPLIED,
    ATTR_CONTROL_REASON,
    ATTR_FORECAST_TIMESTAMPS,
    ATTR_INDOOR_TEMPERATURE,
    ATTR_LAST_UPDATED,
    ATTR_MANUAL_TARGET_TEMP,
    ATTR_MODE,
    ATTR_OUTSIDE_TEMP_FORECAST_LIST,
    ATTR_PLOT_ACTUAL_CARBON_HISTORY,
    ATTR_PLOT_ESTIMATED_CARBON_HISTORY,
    ATTR_PLOT_HISTORY_TIMESTAMPS,
    ATTR_PLOT_INDOOR_TEMPERATURE_HISTORY,
    ATTR_PLOT_RECOMMENDED_HEATING_LEVEL_HISTORY,
    ATTR_PLOT_RECOMMENDED_SETPOINT_HISTORY,
    ATTR_RECOMMENDED_HEATING_LEVEL_LIST,
    ATTR_RECOMMENDED_HEATING_LEVEL_NOW,
    ATTR_RECOMMENDED_SETPOINT,
    ATTR_SIMULATED_ROOM_TEMPERATURE_LIST,
    ATTR_TARGET_MODE,
    ATTR_TARGET_TEMPERATURE_LIST,
    DOMAIN,
)


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([CarbonAwareThermostat(coordinator, entry.data)])


class CarbonAwareThermostat(CoordinatorEntity, ClimateEntity):
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT]
    _attr_hvac_mode = HVACMode.HEAT
    _attr_should_poll = False
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
    _attr_min_temp = 5.0
    _attr_max_temp = 30.0

    def __init__(self, coordinator, config: dict[str, Any]):
        super().__init__(coordinator)
        self._attr_name = config[CONF_NAME]
        self._attr_unique_id = f"carbon_aware_thermostat_{coordinator.entry.entry_id}"

    @property
    def current_temperature(self):
        return self.coordinator.data.get(ATTR_INDOOR_TEMPERATURE)

    @property
    def target_temperature(self):
        return self.coordinator.data.get(ATTR_RECOMMENDED_SETPOINT)

    async def async_set_temperature(self, **kwargs):
        value = kwargs.get("temperature")
        if value is None:
            return
        self.coordinator.data[ATTR_RECOMMENDED_SETPOINT] = float(value)
        self.async_write_ha_state()

    async def async_set_hvac_mode(self, hvac_mode):
        self._attr_hvac_mode = hvac_mode
        self.async_write_ha_state()

    @property
    def extra_state_attributes(self):
        return {
            ATTR_MODE: self.coordinator.data.get(ATTR_MODE),
            ATTR_TARGET_MODE: self.coordinator.data.get(ATTR_TARGET_MODE),
            ATTR_MANUAL_TARGET_TEMP: self.coordinator.data.get(ATTR_MANUAL_TARGET_TEMP),
            ATTR_TARGET_TEMPERATURE_LIST: self.coordinator.data.get(ATTR_TARGET_TEMPERATURE_LIST, []),
            ATTR_INDOOR_TEMPERATURE: self.coordinator.data.get(ATTR_INDOOR_TEMPERATURE),
            ATTR_OUTSIDE_TEMP_FORECAST_LIST: self.coordinator.data.get(ATTR_OUTSIDE_TEMP_FORECAST_LIST, []),
            ATTR_CARBON_FORECAST_LIST: self.coordinator.data.get(ATTR_CARBON_FORECAST_LIST, []),
            ATTR_RECOMMENDED_HEATING_LEVEL_LIST: self.coordinator.data.get(ATTR_RECOMMENDED_HEATING_LEVEL_LIST, []),
            ATTR_SIMULATED_ROOM_TEMPERATURE_LIST: self.coordinator.data.get(ATTR_SIMULATED_ROOM_TEMPERATURE_LIST, []),
            ATTR_RECOMMENDED_HEATING_LEVEL_NOW: self.coordinator.data.get(ATTR_RECOMMENDED_HEATING_LEVEL_NOW),
            ATTR_RECOMMENDED_SETPOINT: self.coordinator.data.get(ATTR_RECOMMENDED_SETPOINT),
            ATTR_CONTROL_APPLIED: self.coordinator.data.get(ATTR_CONTROL_APPLIED),
            ATTR_CONTROL_REASON: self.coordinator.data.get(ATTR_CONTROL_REASON),
            ATTR_APPLIED_HEATING_MODE: self.coordinator.data.get(ATTR_APPLIED_HEATING_MODE),
            ATTR_LAST_UPDATED: self.coordinator.data.get(ATTR_LAST_UPDATED),
            ATTR_FORECAST_TIMESTAMPS: self.coordinator.data.get(ATTR_FORECAST_TIMESTAMPS, []),
            ATTR_PLOT_HISTORY_TIMESTAMPS: self.coordinator.data.get(ATTR_PLOT_HISTORY_TIMESTAMPS, []),
            ATTR_PLOT_ACTUAL_CARBON_HISTORY: self.coordinator.data.get(ATTR_PLOT_ACTUAL_CARBON_HISTORY, []),
            ATTR_PLOT_ESTIMATED_CARBON_HISTORY: self.coordinator.data.get(ATTR_PLOT_ESTIMATED_CARBON_HISTORY, []),
            ATTR_PLOT_INDOOR_TEMPERATURE_HISTORY: self.coordinator.data.get(ATTR_PLOT_INDOOR_TEMPERATURE_HISTORY, []),
            ATTR_PLOT_RECOMMENDED_HEATING_LEVEL_HISTORY: self.coordinator.data.get(
                ATTR_PLOT_RECOMMENDED_HEATING_LEVEL_HISTORY, []
            ),
            ATTR_PLOT_RECOMMENDED_SETPOINT_HISTORY: self.coordinator.data.get(
                ATTR_PLOT_RECOMMENDED_SETPOINT_HISTORY, []
            ),
        }
