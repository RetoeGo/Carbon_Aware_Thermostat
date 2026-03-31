from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import UnitOfTemperature
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_APPLIED_HEATING_MODE,
    ATTR_CARBON_FORECAST_LIST,
    ATTR_FORECAST_TIMESTAMPS,
    ATTR_INDOOR_TEMPERATURE,
    ATTR_PLOT_ACTUAL_CARBON_HISTORY,
    ATTR_PLOT_ESTIMATED_CARBON_HISTORY,
    ATTR_PLOT_HISTORY_TIMESTAMPS,
    ATTR_PLOT_INDOOR_TEMPERATURE_HISTORY,
    ATTR_PLOT_RECOMMENDED_HEATING_LEVEL_HISTORY,
    ATTR_PLOT_RECOMMENDED_SETPOINT_HISTORY,
    ATTR_RECOMMENDED_HEATING_LEVEL_NOW,
    ATTR_RECOMMENDED_SETPOINT,
    DOMAIN,
)


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            EstimatedCarbonSensor(coordinator),
            RecommendedHeatingModeSensor(coordinator),
            RecommendedSetpointSensor(coordinator),
            IndoorTemperatureSensor(coordinator),
        ]
    )


class _BaseSensor(CoordinatorEntity, SensorEntity):
    _attr_should_poll = False

    def __init__(self, coordinator, suffix: str, name: str) -> None:
        super().__init__(coordinator)
        self._attr_has_entity_name = True
        self._attr_name = name
        self._attr_unique_id = f"carbon_aware_thermostat_{suffix}_{coordinator.entry.entry_id}"


class EstimatedCarbonSensor(_BaseSensor):
    _attr_native_unit_of_measurement = "gCO2eq/kWh"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "estimated_carbon", "Estimated carbon intensity")

    @property
    def native_value(self):
        values = self.coordinator.data.get(ATTR_CARBON_FORECAST_LIST, [])
        return float(values[0]) if values else None

    @property
    def extra_state_attributes(self):
        return {
            ATTR_FORECAST_TIMESTAMPS: self.coordinator.data.get(ATTR_FORECAST_TIMESTAMPS, []),
            ATTR_CARBON_FORECAST_LIST: self.coordinator.data.get(ATTR_CARBON_FORECAST_LIST, []),
            ATTR_PLOT_HISTORY_TIMESTAMPS: self.coordinator.data.get(ATTR_PLOT_HISTORY_TIMESTAMPS, []),
            ATTR_PLOT_ACTUAL_CARBON_HISTORY: self.coordinator.data.get(ATTR_PLOT_ACTUAL_CARBON_HISTORY, []),
            ATTR_PLOT_ESTIMATED_CARBON_HISTORY: self.coordinator.data.get(ATTR_PLOT_ESTIMATED_CARBON_HISTORY, []),
        }


class RecommendedHeatingModeSensor(_BaseSensor):
    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "recommended_heating_mode", "Recommended heating mode")

    @property
    def native_value(self):
        return self.coordinator.data.get(ATTR_APPLIED_HEATING_MODE)

    @property
    def extra_state_attributes(self):
        return {
            ATTR_RECOMMENDED_HEATING_LEVEL_NOW: self.coordinator.data.get(ATTR_RECOMMENDED_HEATING_LEVEL_NOW),
            ATTR_PLOT_HISTORY_TIMESTAMPS: self.coordinator.data.get(ATTR_PLOT_HISTORY_TIMESTAMPS, []),
            ATTR_PLOT_RECOMMENDED_HEATING_LEVEL_HISTORY: self.coordinator.data.get(
                ATTR_PLOT_RECOMMENDED_HEATING_LEVEL_HISTORY, []
            ),
        }


class RecommendedSetpointSensor(_BaseSensor):
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_device_class = SensorDeviceClass.TEMPERATURE

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "recommended_setpoint", "Recommended setpoint")

    @property
    def native_value(self):
        value = self.coordinator.data.get(ATTR_RECOMMENDED_SETPOINT)
        return float(value) if value is not None else None

    @property
    def extra_state_attributes(self):
        return {
            ATTR_PLOT_HISTORY_TIMESTAMPS: self.coordinator.data.get(ATTR_PLOT_HISTORY_TIMESTAMPS, []),
            ATTR_PLOT_RECOMMENDED_SETPOINT_HISTORY: self.coordinator.data.get(ATTR_PLOT_RECOMMENDED_SETPOINT_HISTORY, []),
        }


class IndoorTemperatureSensor(_BaseSensor):
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_device_class = SensorDeviceClass.TEMPERATURE

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "indoor_temperature", "Indoor temperature")

    @property
    def native_value(self):
        value = self.coordinator.data.get(ATTR_INDOOR_TEMPERATURE)
        return float(value) if value is not None else None

    @property
    def extra_state_attributes(self):
        return {
            ATTR_PLOT_HISTORY_TIMESTAMPS: self.coordinator.data.get(ATTR_PLOT_HISTORY_TIMESTAMPS, []),
            ATTR_PLOT_INDOOR_TEMPERATURE_HISTORY: self.coordinator.data.get(ATTR_PLOT_INDOOR_TEMPERATURE_HISTORY, []),
        }
