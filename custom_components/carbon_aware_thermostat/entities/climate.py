from homeassistant.components.climate import ClimateEntity, ClimateEntityFeature, HVACMode
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.const import ATTR_TEMPERATURE, CONF_NAME, STATE_UNKNOWN, STATE_UNAVAILABLE
from homeassistant.core import callback
from ..const import DOMAIN, LOGGER
from ..coordinator import CarbonAwareCoordinator


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up climate entity based on config entry."""
    api = hass.data[DOMAIN][entry.entry_id]
    coordinator = CarbonAwareCoordinator(hass, entry, api)
    # indoor_temp_sensor = entry.data.get("indoor_temp_sensor")

    async_add_entities([
        CarbonAwareThermostat(coordinator, idx) for idx, ent in enumerate(coordinator.data)
    ])


class CarbonAwareThermostat(CoordinatorEntity, ClimateEntity):
    """The Thermostat Entity."""

    def __init__(self, coordinator, idx):
        super().__init__(coordinator, context=idx)
        self.idx = idx

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_is_on = self.coordinator.data[self.idx]["state"]
        self.async_write_ha_state()

    async def async_added_to_hass(self):
        """Handle entity which will be added."""
        await super().async_added_to_hass()

        # Track the indoor temperature sensor (PUSH)
        # Not sure if this is needed
        self.async_on_remove(
            async_track_state_change_event(
                self.hass, [self._indoor_temp_entity], self._async_on_temp_change
            )
        )

        # Initial state fetch
        # Not sure if this is needed
        if state := self.hass.states.get(self._indoor_temp_entity):
            self._update_internal_temp(state)

    def _update_internal_temp(self, state):
        """Logic to parse the temperature string."""
        if state and state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            try:
                self._current_temp = float(state.state)
            except ValueError:
                LOGGER.error("Invalid temp: %s", state.state)

    async def _async_on_temp_change(self, event):
        """Update when the indoor sensor changes."""
        if new_state := event.data.get("new_state"):
            self._update_internal_temp(new_state)
            self.async_write_ha_state()
