from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import CarbonAwareCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the carbon-aware thermostat from a config entry."""

    # carbon_sensor = entry.data.get("carbon_sensor")
    # weather_entity = entry.data.get("weather_entity")
    api = entry.data.get("api")

    # Initialize and fetch first data
    coordinator = CarbonAwareCoordinator(hass, entry, api)
    await coordinator.async_config_entry_first_refresh()

    # Store coordinator for platforms (climate.py) to access
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    # Forward the setup to the climate platform
    await hass.config_entries.async_forward_entry_setups(entry, ["climate"])

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, ["climate"])
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok