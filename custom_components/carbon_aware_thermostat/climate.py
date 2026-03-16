from homeassistant.components.climate import ClimateEntity, ClimateEntityFeature, HVACMode
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.const import ATTR_TEMPERATURE, CONF_NAME, STATE_UNKNOWN, STATE_UNAVAILABLE
from homeassistant.core import callback
from .const import DOMAIN, LOGGER
from .coordinator import CarbonAwareCoordinator
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant


# async def async_setup_entry(hass, entry, async_add_entities):
#     """Set up climate entity based on config entry."""
    #
    # pull-based api data (e.g., carbon intensity, weather forecast, etc.)
    # api = hass.data[DOMAIN][entry.entry_id]
    #
    # coordinator = CarbonAwareCoordinator(hass, entry, api)
    #
    # push-based data
    # indoor_temp_sensor = entry.data.get("indoor_temp_sensor")
    #
    # async_add_entities([
    #     CarbonAwareThermostat(coordinator, indoor_temp_sensor, idx) for idx, ent in enumerate(coordinator.data)
    # ])


class CarbonAwareThermostat(ClimateEntity):
    """The Thermostat Entity."""

    def __init__(self, hass, config):
        # super().__init__(coordinator, context=idx)
        # self.indoor_temp_sensor = indoor_temp_sensor
        # self.idx = idx
        self.hass = hass
        # Ensure Home Assistant climate base class finds a temperature unit
        # Use the HA instance temperature unit so the entity reports correctly.
        try:
            self._attr_temperature_unit = hass.config.units.temperature_unit
        except Exception:
            # Fallback to a sensible default if hass is not fully available yet
            from homeassistant.const import UnitOfTemperature

            self._attr_temperature_unit = UnitOfTemperature.CELSIUS
        self._carbon_sensor = config["carbon_sensor"]
        # Minimal HVAC attributes so HA can query capabilities without error
        # Provide sensible defaults; callers can override or expand later.
        self._attr_hvac_modes = [HVACMode.HEAT, HVACMode.OFF]
        # Current HVAC mode (single value). Set a safe default.
        self._attr_hvac_mode = HVACMode.OFF
        self._attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
        # Reasonable temperature range and resolution
        self._attr_min_temp = 5.0
        self._attr_max_temp = 30.0
        self._attr_target_temperature_step = 0.5
        # Friendly name for the entity; avoids 'unnamed_device' in logs/UI
        self._attr_name = config.get(CONF_NAME, "Carbon Aware Thermostat")
        #self._target_climate = config["target_climate"]
        #self._weather_entity = config.get("weather_entity")

    # @callback
    # def _handle_coordinator_update(self) -> None:
    #     """Handle updated data from the coordinator."""
    #     self._attr_is_on = self.coordinator.data[self.idx]["state"]
    #     self.async_write_ha_state()
    #
    # async def async_added_to_hass(self):
    #     """Handle entity which will be added."""
    #     await super().async_added_to_hass()
    #
    #     # Track the indoor temperature sensor (PUSH)
    #     # Not sure if this is needed
    #     self.async_on_remove(
    #         async_track_state_change_event(
    #             self.hass, [self.indoor_temp_sensor], self._async_on_temp_change
    #         )
    #     )
    #
    #     # Initial state fetch
    #     # Not sure if this is needed
    #     if state := self.hass.states.get(self.indoor_temp_sensor):
    #         self._update_internal_temp(state)
    #
    # def _update_internal_temp(self, state):
    #     """Logic to parse the temperature string."""
    #     if state and state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
    #         try:
    #             self._current_temp = float(state.state)
    #         except ValueError:
    #             LOGGER.error("Invalid temp: %s", state.state)
    #
    # async def _async_on_temp_change(self, event):
    #     """Update when the indoor sensor changes."""
    #     if new_state := event.data.get("new_state"):
    #         self._update_internal_temp(new_state)
    #         self.async_write_ha_state()

    async def async_added_to_hass(self):
        """Subscribe to carbon sensor changes."""
        self.async_on_remove(
            async_track_state_change_event(self.hass, self._carbon_sensor, self._process_logic)
        )

    async def _get_forecast_temp(self):
        """Retrieve the predicted outdoor temperature."""
        if not self._weather_entity:
            return None

        try:
            # Modern way to fetch forecasts in HA
            forecast_data = await self.hass.services.async_call(
                "weather", "get_forecasts",
                {"entity_id": self._weather_entity, "type": "hourly"},
                blocking=True, return_response=True
            )

            return forecast_data[self._weather_entity]["forecast"]

            # Extract the 3rd hour from the forecast list
            # hourly_forecasts = forecast_data[self._weather_entity]["forecast"]
            # if len(hourly_forecasts) >= 3:
            #     return hourly_forecasts[2]["temperature"]
            # return None
        except Exception as e:
            LOGGER.error("Failed to fetch weather forecast: %s", e)
            return None

    async def _process_logic(self, event):
        """Main logic to adjust the real thermostat."""
        new_state = event.data.get("new_state")
        if new_state is None or new_state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            return

        intensity = float(new_state.state)
        #forecast_temp = await self._get_forecast_temp()

        # Get state of the real underlying thermostat
        #real_thermostat = self.hass.states.get(self._target_climate)
        #current_target = real_thermostat.attributes.get(ATTR_TEMPERATURE)

        # apply algorithm
        new_target = 20
        LOGGER.info("Carbon intensity: %s, setting target to %s", intensity, new_target)

        # Send command to the real hardware
        # await self.hass.services.async_call("climate", "set_temperature", {
        #     "entity_id": self._target_climate,
        #     "temperature": new_target
        # })
async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    """Set up the climate platform for a config entry."""
    # The integration stores the raw entry data under hass.data[DOMAIN][entry.entry_id]
    config = hass.data.get(DOMAIN, {}).get(entry.entry_id, entry.data)

    # Create one thermostat entity per config entry. If you expect multiple
    # thermostats per entry, adapt this to iterate over a list in config.
    entity = CarbonAwareThermostat(hass, config)
    async_add_entities([entity], update_before_add=False)