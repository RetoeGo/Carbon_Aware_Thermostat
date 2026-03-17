from __future__ import annotations

from datetime import datetime, timedelta, timezone
from statistics import mean
from typing import Any

import numpy as np

from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.history import get_significant_states
from homeassistant.const import ATTR_TEMPERATURE, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    ATTR_CARBON_FORECAST_LIST,
    ATTR_CONTROL_APPLIED,
    ATTR_CONTROL_REASON,
    ATTR_FORECAST_TIMESTAMPS,
    ATTR_INDOOR_TEMPERATURE,
    ATTR_LAST_UPDATED,
    ATTR_MODE,
    ATTR_OUTSIDE_TEMP_FORECAST_LIST,
    ATTR_PLOT_ACTUAL_CARBON_HISTORY,
    ATTR_PLOT_ESTIMATED_CARBON_HISTORY,
    ATTR_PLOT_HISTORY_TIMESTAMPS,
    ATTR_PLOT_INDOOR_TEMPERATURE_HISTORY,
    ATTR_PLOT_RECOMMENDED_POWER_HISTORY,
    ATTR_PLOT_RECOMMENDED_SETPOINT_HISTORY,
    ATTR_RECOMMENDED_POWER_LIST,
    ATTR_RECOMMENDED_POWER_NOW,
    ATTR_RECOMMENDED_SETPOINT,
    ATTR_SIMULATED_ROOM_TEMPERATURE_LIST,
    ATTR_TARGET_CLIMATE,
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
    CONF_PREHEAT_OFFSET,
    CONF_TARGET_CLIMATE,
    CONF_THERMOSTAT_POWER,
    CONF_WEATHER_ENTITY,
    CONF_WINDOW_PERCENT,
    DEFAULT_FORECAST_POINTS,
    DEFAULT_FORECAST_STEP_MINUTES,
    LOGGER,
    PLOT_HISTORY_MAX_POINTS,
)
from .entities.mpc import mpc_control
from .entities.room import Thermostat, VirtualRoom


class CarbonAwareCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    def __init__(self, hass: HomeAssistant, entry):
        step_minutes = int(entry.data.get(CONF_FORECAST_STEP_MINUTES, DEFAULT_FORECAST_STEP_MINUTES))
        super().__init__(
            hass,
            LOGGER,
            name="Carbon Aware Thermostat Coordinator",
            config_entry=entry,
            update_interval=timedelta(minutes=step_minutes),
            always_update=True,
        )
        self.entry = entry
        self._demo_indoor_temp_override: float | None = None
        self._forecast_archive: dict[datetime, float] = {}
        self._comparison_timestamps: list[str] = []
        self._actual_carbon_history: list[float] = []
        self._estimated_carbon_history: list[float] = []
        self._indoor_temperature_history: list[float] = []
        self._recommended_power_history: list[float] = []
        self._recommended_setpoint_history: list[float] = []

    async def async_set_demo_indoor_temperature(self, value: float) -> None:
        self._demo_indoor_temp_override = float(value)
        await self.async_request_refresh()

    async def async_shutdown(self) -> None:
        return None

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            mode = self.entry.data.get(CONF_MODE, "live")
            outside_temp_list = await self._fetch_outside_temperature_forecast()
            carbon_current, carbon_list = await self._fetch_carbon_forecast(outside_temp_list)
            indoor_temp = self._read_indoor_temperature()
            data = await self._build_result(indoor_temp, outside_temp_list, carbon_list)
            self._update_plot_buffers(carbon_current, data)
            if mode == "live" and self.entry.data.get(CONF_CONTROL_REAL_THERMOSTAT) and self.entry.data.get(CONF_CLIMATE_ENTITY):
                await self._apply_recommended_control(data)
            return data
        except Exception as err:
            raise UpdateFailed(str(err)) from err

    def _step_minutes(self) -> int:
        return max(5, int(self.entry.data.get(CONF_FORECAST_STEP_MINUTES, DEFAULT_FORECAST_STEP_MINUTES)))

    def _forecast_points(self) -> int:
        return max(1, int(self.entry.data.get(CONF_FORECAST_POINTS, DEFAULT_FORECAST_POINTS)))

    def _current_slot(self) -> datetime:
        now = datetime.now(timezone.utc)
        step_seconds = self._step_minutes() * 60
        epoch = int(now.timestamp())
        floored = epoch - (epoch % step_seconds)
        return datetime.fromtimestamp(floored, tz=timezone.utc)

    def _read_indoor_temperature(self) -> float | None:
        if self.entry.data.get(CONF_MODE) == "demo":
            if self._demo_indoor_temp_override is not None:
                return self._demo_indoor_temp_override
            return float(self.entry.data.get(CONF_DEMO_ROOM_TEMP, 20.0))

        climate_entity = self.entry.data.get(CONF_CLIMATE_ENTITY)
        if not climate_entity:
            return self._coerce_float(self.entry.data.get(CONF_DEMO_ROOM_TEMP), default=20.0)
        state = self.hass.states.get(climate_entity)
        if state is None:
            return self._coerce_float(self.entry.data.get(CONF_DEMO_ROOM_TEMP), default=20.0)
        value = state.attributes.get("current_temperature")
        if value in (None, STATE_UNKNOWN, STATE_UNAVAILABLE):
            return self._coerce_float(self.entry.data.get(CONF_DEMO_ROOM_TEMP), default=20.0)
        return self._coerce_float(value, default=20.0)

    async def _fetch_outside_temperature_forecast(self) -> list[float]:
        points = self._forecast_points()
        weather_entity = self.entry.data.get(CONF_WEATHER_ENTITY)
        if not weather_entity:
            return [10.0] * points

        forecast_items: list[dict[str, Any]] = []
        try:
            response = await self.hass.services.async_call(
                "weather",
                "get_forecasts",
                {"type": "hourly", "entity_id": [weather_entity]},
                blocking=True,
                return_response=True,
            )
            if isinstance(response, dict):
                forecast_items = response.get(weather_entity, {}).get("forecast", []) or []
        except Exception:
            forecast_items = []

        fallback = 10.0
        state = self.hass.states.get(weather_entity)
        if state is not None:
            fallback = self._coerce_float(state.attributes.get(ATTR_TEMPERATURE), default=10.0) or 10.0

        if not forecast_items:
            return [fallback] * points

        hourly: list[float] = []
        for item in forecast_items:
            temp = self._coerce_float(item.get("temperature"), default=None)
            if temp is not None:
                hourly.append(temp)

        if not hourly:
            return [fallback] * points

        return self._expand_hourly_to_step(hourly, points, self._step_minutes(), fallback)

    async def _fetch_carbon_forecast(self, outside_temp_list: list[float]) -> tuple[float, list[float]]:
        points = self._forecast_points()
        entity_id = self.entry.data.get(CONF_CARBON_INTENSITY_SENSOR)
        if not entity_id:
            return 300.0, [300.0] * points

        state = self.hass.states.get(entity_id)
        current = self._coerce_float(None if state is None else state.state, default=300.0) or 300.0
        history = await self._get_sensor_history(entity_id)
        if len(history) < 8:
            return current, [current] * points

        step_minutes = self._step_minutes()
        series = self._resample_history(history, step_minutes)
        if len(series) < 16:
            return current, [current] * points

        forecast = self._rolling_half_hour_forecast(series, outside_temp_list, points, current, step_minutes)
        return current, forecast

    async def _get_sensor_history(self, entity_id: str) -> list[tuple[datetime, float]]:
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=7)

        def _load() -> list[tuple[datetime, float]]:
            states = get_significant_states(
                self.hass,
                start,
                end,
                [entity_id],
                include_start_time_state=True,
                significant_changes_only=False,
            )
            result: list[tuple[datetime, float]] = []
            for st in states.get(entity_id, []):
                value = self._coerce_float(st.state, default=None)
                if value is None:
                    continue
                result.append((st.last_updated.astimezone(timezone.utc), value))
            return result

        instance = get_instance(self.hass)
        return await instance.async_add_executor_job(_load)

    def _resample_history(self, history: list[tuple[datetime, float]], step_minutes: int) -> list[tuple[datetime, float]]:
        sorted_history = sorted(history, key=lambda item: item[0])
        if not sorted_history:
            return []

        step_seconds = step_minutes * 60

        def floor_step(ts: datetime) -> datetime:
            epoch = int(ts.timestamp())
            floored = epoch - (epoch % step_seconds)
            return datetime.fromtimestamp(floored, tz=timezone.utc)

        buckets: dict[datetime, list[float]] = {}
        for ts, value in sorted_history:
            buckets.setdefault(floor_step(ts), []).append(float(value))

        start_ts = floor_step(sorted_history[0][0])
        end_ts = floor_step(sorted_history[-1][0])
        current_ts = start_ts
        resampled: list[tuple[datetime, float]] = []
        last_value = float(sorted_history[0][1])
        while current_ts <= end_ts:
            bucket = buckets.get(current_ts)
            if bucket:
                last_value = float(mean(bucket))
            resampled.append((current_ts, last_value))
            current_ts += timedelta(minutes=step_minutes)
        return resampled

    def _rolling_half_hour_forecast(
        self,
        series: list[tuple[datetime, float]],
        outside_temp_list: list[float],
        points: int,
        current: float,
        step_minutes: int,
    ) -> list[float]:
        step = timedelta(minutes=step_minutes)
        values = np.array([float(value) for _, value in series], dtype=float)
        timestamps = [ts for ts, _ in series]
        value_by_ts = {ts: float(value) for ts, value in series}

        slots_per_day = max(1, int(round(24 * 60 / step_minutes)))
        recent_window = min(len(values), max(slots_per_day * 2, 16))
        recent_values = values[-recent_window:]
        recent_mean = float(np.mean(recent_values))
        recent_std = max(1.0, float(np.std(recent_values)))

        trend_window = min(len(values), max(10, slots_per_day))
        trend_slice = values[-trend_window:]
        recent_slope = 0.0
        if len(trend_slice) >= 2:
            recent_slope = float((trend_slice[-1] - trend_slice[0]) / (len(trend_slice) - 1))

        slot_buckets: dict[int, list[float]] = {}
        weekday_buckets: dict[int, list[float]] = {}
        for ts, value in series:
            slot = ((ts.hour * 60) + ts.minute) // step_minutes
            slot_buckets.setdefault(int(slot), []).append(float(value))
            weekday_buckets.setdefault(ts.weekday(), []).append(float(value))

        slot_means = {slot: float(np.mean(bucket)) for slot, bucket in slot_buckets.items() if bucket}
        weekday_means = {day: float(np.mean(bucket)) for day, bucket in weekday_buckets.items() if bucket}

        weather_mean = float(np.mean(outside_temp_list[:points])) if outside_temp_list else 10.0
        temp_sensitivity = min(5.0, max(-5.0, 0.08 * recent_std))

        results: list[float] = []
        previous_prediction = current
        next_ts = timestamps[-1] + step
        for idx in range(points):
            slot = ((next_ts.hour * 60) + next_ts.minute) // step_minutes
            slot_level = slot_means.get(int(slot), recent_mean)
            weekday_level = weekday_means.get(next_ts.weekday(), recent_mean)

            lag_values: list[tuple[float, float]] = []
            for days_back, weight in ((1, 1.0), (2, 0.7), (3, 0.45), (7, 0.25)):
                lag_ts = next_ts - timedelta(days=days_back)
                lag_value = value_by_ts.get(lag_ts)
                if lag_value is not None:
                    lag_values.append((lag_value, weight))
            if lag_values:
                lag_level = float(sum(v * w for v, w in lag_values) / sum(w for _, w in lag_values))
            else:
                lag_level = slot_level

            trend_level = recent_mean + recent_slope * min(idx + 1, slots_per_day)
            weather = float(outside_temp_list[idx]) if idx < len(outside_temp_list) else weather_mean
            weather_adjustment = temp_sensitivity * (weather_mean - weather) * 0.08

            prediction = (
                0.52 * lag_level
                + 0.18 * slot_level
                + 0.10 * weekday_level
                + 0.10 * trend_level
                + 0.10 * previous_prediction
                + weather_adjustment
            )

            lower = max(0.0, recent_mean - 3.0 * recent_std)
            upper = recent_mean + 3.0 * recent_std
            clipped = float(np.clip(prediction, lower, upper))
            results.append(clipped)
            previous_prediction = clipped
            value_by_ts[next_ts] = clipped
            next_ts += step

        if len(results) < points:
            fill = results[-1] if results else current
            results.extend([fill] * (points - len(results)))
        return results[:points]

    async def _build_result(self, indoor_temp, outside_temp_list, carbon_list) -> dict[str, Any]:
        mode = self.entry.data.get(CONF_MODE, "live")
        points = min(self._forecast_points(), len(outside_temp_list), len(carbon_list))
        outside_temp_list = outside_temp_list[:points]
        carbon_list = carbon_list[:points]
        step_minutes = self._step_minutes()
        dt_seconds = step_minutes * 60
        target_temp = float(self.entry.data.get(CONF_TARGET_CLIMATE, self.entry.data.get(CONF_DEMO_TARGET_TEMP, 21.0)))
        comfort_setpoint = float(self.entry.data.get(CONF_COMFORT_SETPOINT, target_temp))
        if indoor_temp is None:
            indoor_temp = float(self.entry.data.get(CONF_DEMO_ROOM_TEMP, target_temp))

        room, rls_model = self._build_virtual_room(indoor_temp)
        horizon = max(1, int(self.entry.data.get(CONF_MPC_HORIZON, points)))
        max_power = float(self.entry.data.get(CONF_THERMOSTAT_POWER, 1500.0))
        eco_offset = float(self.entry.data.get(CONF_ECO_OFFSET, -1.0))
        preheat_offset = float(self.entry.data.get(CONF_PREHEAT_OFFSET, 0.0))

        recommended_power_list: list[float] = []
        simulated_room_temperature_list: list[float] = []

        clean_threshold = float(np.quantile(np.array(carbon_list, dtype=float), 0.35)) if carbon_list else 0.0
        for idx in range(points):
            carbon_h = carbon_list[idx : idx + horizon]
            outside_h = outside_temp_list[idx : idx + horizon]
            dynamic_target = comfort_setpoint + (preheat_offset if carbon_list[idx] <= clean_threshold else eco_offset)
            u = mpc_control(
                rls_model=rls_model,
                N=min(horizon, len(outside_h), len(carbon_h)) or 1,
                T0=room.temp,
                T_target=dynamic_target,
                T_out=outside_h,
                carbon_intensity=carbon_h,
                max_power=max_power,
            )
            recommended_power_list.append(float(u))
            room.thermostat.power = float(u)
            simulated = room.update_temp(
                dt_seconds=dt_seconds,
                T_out=outside_temp_list[idx],
                window_percent=float(self.entry.data.get(CONF_WINDOW_PERCENT, 0.3)),
            )
            simulated_room_temperature_list.append(float(simulated))

        recommended_setpoint = comfort_setpoint if recommended_power_list and recommended_power_list[0] > 0 else comfort_setpoint + eco_offset
        current_slot = self._current_slot()
        forecast_timestamps = [(current_slot + timedelta(minutes=step_minutes * idx)).isoformat() for idx in range(points)]
        return {
            ATTR_MODE: mode,
            ATTR_TARGET_CLIMATE: float(target_temp),
            ATTR_INDOOR_TEMPERATURE: float(indoor_temp),
            ATTR_OUTSIDE_TEMP_FORECAST_LIST: [float(x) for x in outside_temp_list],
            ATTR_CARBON_FORECAST_LIST: [float(x) for x in carbon_list],
            ATTR_RECOMMENDED_POWER_LIST: recommended_power_list,
            ATTR_SIMULATED_ROOM_TEMPERATURE_LIST: simulated_room_temperature_list,
            ATTR_RECOMMENDED_POWER_NOW: recommended_power_list[0] if recommended_power_list else 0.0,
            ATTR_RECOMMENDED_SETPOINT: float(recommended_setpoint),
            ATTR_CONTROL_APPLIED: False,
            ATTR_CONTROL_REASON: "not_applied" if mode != "live" else "not_enabled",
            ATTR_LAST_UPDATED: datetime.now(timezone.utc).isoformat(),
            ATTR_FORECAST_TIMESTAMPS: forecast_timestamps,
            ATTR_PLOT_HISTORY_TIMESTAMPS: list(self._comparison_timestamps),
            ATTR_PLOT_ACTUAL_CARBON_HISTORY: list(self._actual_carbon_history),
            ATTR_PLOT_ESTIMATED_CARBON_HISTORY: list(self._estimated_carbon_history),
            ATTR_PLOT_INDOOR_TEMPERATURE_HISTORY: list(self._indoor_temperature_history),
            ATTR_PLOT_RECOMMENDED_POWER_HISTORY: list(self._recommended_power_history),
            ATTR_PLOT_RECOMMENDED_SETPOINT_HISTORY: list(self._recommended_setpoint_history),
        }

    def _update_plot_buffers(self, carbon_current: float, data: dict[str, Any]) -> None:
        current_slot = self._current_slot()
        current_estimate = self._forecast_archive.pop(current_slot, None)
        if current_estimate is None:
            forecast_list = data.get(ATTR_CARBON_FORECAST_LIST, []) or []
            current_estimate = float(forecast_list[0]) if forecast_list else float(carbon_current)

        self._append_history(self._comparison_timestamps, current_slot.isoformat())
        self._append_history(self._actual_carbon_history, float(carbon_current))
        self._append_history(self._estimated_carbon_history, float(current_estimate))
        self._append_history(self._indoor_temperature_history, float(data.get(ATTR_INDOOR_TEMPERATURE, 0.0) or 0.0))
        self._append_history(self._recommended_power_history, float(data.get(ATTR_RECOMMENDED_POWER_NOW, 0.0) or 0.0))
        self._append_history(self._recommended_setpoint_history, float(data.get(ATTR_RECOMMENDED_SETPOINT, 0.0) or 0.0))

        step_minutes = self._step_minutes()
        forecast_values = data.get(ATTR_CARBON_FORECAST_LIST, []) or []
        for idx, value in enumerate(forecast_values):
            ts = current_slot + timedelta(minutes=step_minutes * idx)
            self._forecast_archive[ts] = float(value)

        cutoff = current_slot - timedelta(days=3)
        self._forecast_archive = {ts: val for ts, val in self._forecast_archive.items() if ts >= cutoff}

        data[ATTR_PLOT_HISTORY_TIMESTAMPS] = list(self._comparison_timestamps)
        data[ATTR_PLOT_ACTUAL_CARBON_HISTORY] = list(self._actual_carbon_history)
        data[ATTR_PLOT_ESTIMATED_CARBON_HISTORY] = list(self._estimated_carbon_history)
        data[ATTR_PLOT_INDOOR_TEMPERATURE_HISTORY] = list(self._indoor_temperature_history)
        data[ATTR_PLOT_RECOMMENDED_POWER_HISTORY] = list(self._recommended_power_history)
        data[ATTR_PLOT_RECOMMENDED_SETPOINT_HISTORY] = list(self._recommended_setpoint_history)

    def _append_history(self, target: list[Any], value: Any) -> None:
        target.append(value)
        if len(target) > PLOT_HISTORY_MAX_POINTS:
            del target[0 : len(target) - PLOT_HISTORY_MAX_POINTS]

    def _build_virtual_room(self, indoor_temp: float):
        height = float(self.entry.data.get(CONF_DEMO_ROOM_HEIGHT, 2.6))
        width = float(self.entry.data.get(CONF_DEMO_ROOM_WIDTH, 5.0))
        length = float(self.entry.data.get(CONF_DEMO_ROOM_LENGTH, 8.0))
        exposed_area = float(self.entry.data.get(CONF_DEMO_EXPOSED_AREA, 33.8))
        thermostat_power = float(self.entry.data.get(CONF_THERMOSTAT_POWER, 1500.0))
        room_size = height * width * length
        room = VirtualRoom(indoor_temp, room_size, exposed_area, Thermostat(thermostat_power))
        rls_model = room.generate_rls(
            dt_seconds=self._step_minutes() * 60,
            window_percent=float(self.entry.data.get(CONF_WINDOW_PERCENT, 0.3)),
        )
        return room, rls_model

    async def _apply_recommended_control(self, data: dict[str, Any]) -> None:
        climate_entity = self.entry.data.get(CONF_CLIMATE_ENTITY)
        if not climate_entity:
            return
        setpoint = data.get(ATTR_RECOMMENDED_SETPOINT)
        if setpoint is None:
            return
        try:
            await self.hass.services.async_call(
                "climate",
                "set_temperature",
                {"entity_id": climate_entity, "temperature": float(setpoint)},
                blocking=True,
            )
            data[ATTR_CONTROL_APPLIED] = True
            data[ATTR_CONTROL_REASON] = "set_temperature_called"
        except HomeAssistantError as err:
            data[ATTR_CONTROL_APPLIED] = False
            data[ATTR_CONTROL_REASON] = str(err)

    @staticmethod
    def _expand_hourly_to_step(hourly: list[float], points: int, step_minutes: int, fallback: float) -> list[float]:
        if not hourly:
            return [fallback] * points
        if step_minutes >= 60:
            factor = max(1, int(round(step_minutes / 60)))
            reduced = [hourly[min(i * factor, len(hourly) - 1)] for i in range(points)]
            return reduced[:points]

        scale = 60.0 / step_minutes
        values: list[float] = []
        for idx in range(points):
            position = idx / scale
            low = int(np.floor(position))
            high = min(low + 1, len(hourly) - 1)
            frac = position - low
            interpolated = float(hourly[low] * (1.0 - frac) + hourly[high] * frac)
            values.append(interpolated)
        return values[:points]

    @staticmethod
    def _coerce_float(value: Any, default: float | None) -> float | None:
        if value in (None, "unknown", "unavailable"):
            return default
        try:
            return float(value)
        except (TypeError, ValueError):
            return default


    def clear_plot_history(self) -> None:
        self._comparison_timestamps.clear()
        self._actual_carbon_history.clear()
        self._estimated_carbon_history.clear()
        self._indoor_temperature_history.clear()
        self._recommended_power_history.clear()
        self._recommended_setpoint_history.clear()
        self._forecast_archive.clear()
