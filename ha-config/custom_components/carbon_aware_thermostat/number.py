from __future__ import annotations

from homeassistant.components.number import NumberEntity
from homeassistant.const import UnitOfTemperature
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTR_INDOOR_TEMPERATURE, CONF_MODE, DOMAIN


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    if entry.data.get(CONF_MODE) == "demo":
        async_add_entities([DemoIndoorTemperatureNumber(coordinator)])


class DemoIndoorTemperatureNumber(CoordinatorEntity, NumberEntity):
    _attr_has_entity_name = True
    _attr_name = "Demo indoor temperature"
    _attr_native_min_value = 5.0
    _attr_native_max_value = 35.0
    _attr_native_step = 0.5
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_should_poll = False

    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_unique_id = f"carbon_aware_thermostat_demo_temp_{coordinator.entry.entry_id}"

    @property
    def native_value(self):
        return self.coordinator.data.get(ATTR_INDOOR_TEMPERATURE)

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_set_demo_indoor_temperature(float(value))
