from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall

from .const import DOMAIN
from .coordinator import CarbonAwareCoordinator

PLATFORMS: list[Platform] = [Platform.CLIMATE, Platform.SENSOR]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    hass.data.setdefault(DOMAIN, {})

    async def _async_handle_refresh(call: ServiceCall) -> None:
        target_entry_id = call.data.get("entry_id")
        for entry_id, coordinator in hass.data.get(DOMAIN, {}).items():
            if target_entry_id and entry_id != target_entry_id:
                continue
            await coordinator.async_request_refresh()

    async def _async_handle_clear_plot_history(call: ServiceCall) -> None:
        target_entry_id = call.data.get("entry_id")
        for entry_id, coordinator in hass.data.get(DOMAIN, {}).items():
            if target_entry_id and entry_id != target_entry_id:
                continue
            coordinator.clear_plot_history()
            await coordinator.async_request_refresh()

    if not hass.services.has_service(DOMAIN, "refresh"):
        hass.services.async_register(DOMAIN, "refresh", _async_handle_refresh)
    if not hass.services.has_service(DOMAIN, "clear_plot_history"):
        hass.services.async_register(DOMAIN, "clear_plot_history", _async_handle_clear_plot_history)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})
    coordinator = CarbonAwareCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    hass.data[DOMAIN][entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        coordinator = hass.data[DOMAIN].pop(entry.entry_id, None)
        if coordinator is not None:
            await coordinator.async_shutdown()
    return unload_ok
