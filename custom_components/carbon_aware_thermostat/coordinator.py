from datetime import timedelta

import async_timeout
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.const import STATE_UNKNOWN, STATE_UNAVAILABLE
import aiohttp
import asyncio

from .const import DOMAIN, LOGGER


class CarbonAwareCoordinator(DataUpdateCoordinator):
    """Handles fetching pull-based data like carbon intensity and weather forecast."""

    def __init__(self, hass, entry, api):
        super().__init__(
            hass, LOGGER, name="Carbon Aware Coordinator",
            config_entry=entry,
            update_interval=timedelta(minutes=30),
            always_update=True
        )
        self.api = api

    async def _async_update_data(self):
        """Fetch current states for the specific entities configured."""
        # carbon_state = self.hass.states.get(self.carbon_intensity_sensor)
        # weather_state = self.hass.states.get(self.weather_forecast_entity)

        # Safe conversion for carbon intensity
        # carbon_val = 0
        # if carbon_state and carbon_state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
        #     try:
        #         carbon_val = float(carbon_state.state)
        #     except ValueError:
        #         LOGGER.error("Invalid carbon intensity: %s", carbon_state.state)
        #
        # return {
        #     "carbon_intensity": carbon_val,
        #     "outdoor_temp": weather_state.attributes.get("temperature", 0) if weather_state else 0,
        #     "forecast": weather_state.attributes.get("forecast", []) if weather_state else []
        # }

        try:
            async with async_timeout.timeout(10):
                # context not required if there is no need to limit
                # data retrieved from API
                listening_idx = set(self.async_contexts())
                return await self.my_api.fetch_data(listening_idx)
        except aiohttp.ClientResponseError as err:
            if err.status == 401:
                raise ConfigEntryAuthFailed from err
            raise UpdateFailed(f"Error communicating with API: {err}")
        except (asyncio.TimeoutError, aiohttp.ClientError) as err:
            raise UpdateFailed(f"Error communicating with API: {err}")
        except Exception as err:
            raise UpdateFailed(retry_after=60)