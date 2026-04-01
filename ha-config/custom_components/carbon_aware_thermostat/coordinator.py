from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import numpy as np

from homeassistant.components.recorder.history import get_significant_states
from homeassistant.const import ATTR_TEMPERATURE, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

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
    CONF_AGGRESSIVE_OFFSET,
    CONF_CARBON_INTENSITY_SENSOR,
    CONF_CLIMATE_ENTITY,
    CONF_CONTROL_REAL_THERMOSTAT,
    CONF_ECO_OFFSET,
    CONF_FORECAST_POINTS,
    CONF_FORECAST_STEP_MINUTES,
    CONF_MANUAL_TARGET_TEMP,
    CONF_MODE,
    CONF_MPC_HORIZON,
    CONF_PREFERRED_OFFSET,
    CONF_TARGET_MODE,
    CONF_WEATHER_ENTITY,
    DEFAULT_AGGRESSIVE_OFFSET,
    DEFAULT_ECO_OFFSET,
    DEFAULT_FORECAST_POINTS,
    DEFAULT_FORECAST_STEP_MINUTES,
    DEFAULT_MANUAL_TARGET_TEMP,
    DEFAULT_MPC_HORIZON,
    DEFAULT_PREFERRED_OFFSET,
    DEFAULT_TARGET_MODE,
    HEATING_LEVEL_AGGRESSIVE,
    HEATING_LEVEL_ECO,
    HEATING_LEVEL_PREFERRED,
    LOGGER,
    PLOT_HISTORY_MAX_POINTS,
    TARGET_MODE_MANUAL,
    TARGET_MODE_PREFERRED_WARMER,
)
from .mpc import RLS, mpc_control


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
        self._forecast_archive: dict[datetime, float] = {}
        self._comparison_timestamps: list[str] = []
        self._actual_carbon_history: list[float] = []
        self._estimated_carbon_history: list[float] = []
        self._indoor_temperature_history: list[float] = []
        self._recommended_heating_level_history: list[int] = []
        self._recommended_setpoint_history: list[float] = []

    async def async_shutdown(self) -> None:
        return None

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            mode = self.entry.data.get(CONF_MODE, "live")
            points = self._forecast_points()
            outside_temp_list = await self._fetch_outside_temperature_forecast(points)
            carbon_current, carbon_list = await self._fetch_carbon_forecast(outside_temp_list, points)
            indoor_temp = self._read_indoor_temperature()
            if indoor_temp is None:
                raise UpdateFailed("Could not read indoor temperature from climate entity")
            data = await self._build_result(indoor_temp, outside_temp_list, carbon_list)
            self._update_plot_buffers(carbon_current, data)
            if mode == "live" and self.entry.data.get(CONF_CONTROL_REAL_THERMOSTAT) and self.entry.data.get(CONF_CLIMATE_ENTITY):
                await self._apply_recommended_control(data)
            return data
        except Exception as err:
            raise UpdateFailed(str(err)) from err

    def _step_minutes(self) -> int:
        return max(15, int(self.entry.data.get(CONF_FORECAST_STEP_MINUTES, DEFAULT_FORECAST_STEP_MINUTES)))

    def _forecast_points(self) -> int:
        configured = int(self.entry.data.get(CONF_FORECAST_POINTS, DEFAULT_FORECAST_POINTS))
        horizon = int(self.entry.data.get(CONF_MPC_HORIZON, DEFAULT_MPC_HORIZON))
        return max(DEFAULT_FORECAST_POINTS, configured, horizon)

    def _horizon(self) -> int:
        return max(1, int(self.entry.data.get(CONF_MPC_HORIZON, DEFAULT_MPC_HORIZON)))

    def _current_slot(self) -> datetime:
        now = datetime.now(timezone.utc)
        step_seconds = self._step_minutes() * 60
        epoch = int(now.timestamp())
        floored = epoch - (epoch % step_seconds)
        return datetime.fromtimestamp(floored, tz=timezone.utc)

    def _read_indoor_temperature(self) -> float | None:
        climate_entity = self.entry.data.get(CONF_CLIMATE_ENTITY)
        if not climate_entity:
            return None
        state = self.hass.states.get(climate_entity)
        if state is None:
            return None

        for key in ("current_temperature", "temperature"):
            value = state.attributes.get(key)
            result = self._coerce_float(value, default=None)
            if result is not None:
                return result

        return self._coerce_float(state.state, default=None)

    async def _fetch_outside_temperature_forecast(self, points: int) -> list[float]:
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

        hourly = [self._coerce_float(item.get("temperature"), default=None) for item in forecast_items]
        hourly = [float(temp) for temp in hourly if temp is not None]
        if not hourly:
            return [fallback] * points
        return self._expand_hourly_to_step(hourly, points, self._step_minutes(), fallback)

    async def _fetch_carbon_forecast(self, outside_temp_list: list[float], points: int) -> tuple[float, list[float]]:
        entity_id = self.entry.data.get(CONF_CARBON_INTENSITY_SENSOR)
        if not entity_id:
            return 300.0, [300.0] * points

        state = self.hass.states.get(entity_id)
        current = self._coerce_float(None if state is None else state.state, default=300.0) or 300.0
        history = await self._get_sensor_history(entity_id)
        if len(history) < 8:
            return current, [current] * points

        series = self._resample_history(history, self._step_minutes())
        if len(series) < 16:
            return current, [current] * points

        forecast = self._rolling_half_hour_forecast(series, outside_temp_list, points, current)
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
                if value is not None:
                    result.append((st.last_updated.astimezone(timezone.utc), value))
            return result

        recorder_instance = self.hass.data.get("recorder_instance")
        if recorder_instance is None:
            LOGGER.debug("Recorder not ready yet; skipping carbon history lookup for %s", entity_id)
            return []

        try:
            return await recorder_instance.async_add_executor_job(_load)
        except Exception as err:
            LOGGER.debug("Recorder history unavailable for %s: %s", entity_id, err)
            return []

    async def _get_climate_history(self, entity_id: str) -> list[tuple[datetime, float, int, float]]:
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=3)

        def _load() -> list[tuple[datetime, float, int, float]]:
            states = get_significant_states(
                self.hass,
                start,
                end,
                [entity_id],
                include_start_time_state=True,
                significant_changes_only=False,
            )
            result: list[tuple[datetime, float, int, float]] = []
            for st in states.get(entity_id, []):
                current = self._coerce_float(st.attributes.get("current_temperature"), default=None)
                if current is None:
                    current = self._coerce_float(st.attributes.get("temperature"), default=None)
                target = self._coerce_float(st.attributes.get("temperature"), default=current)
                hvac_action = str(st.attributes.get("hvac_action", "")).lower()
                hvac_mode = str(st.attributes.get("hvac_mode", "")).lower()
                if current is None:
                    continue
                level = self._infer_heating_level(current, target, hvac_action, hvac_mode)
                result.append((st.last_updated.astimezone(timezone.utc), current, level, target if target is not None else current))
            return result

        recorder_instance = self.hass.data.get("recorder_instance")
        if recorder_instance is None:
            LOGGER.debug("Recorder not ready yet; skipping climate history lookup for %s", entity_id)
            return []

        try:
            return await recorder_instance.async_add_executor_job(_load)
        except Exception as err:
            LOGGER.debug("Recorder climate history unavailable for %s: %s", entity_id, err)
            return []

    def _infer_heating_level(self, current: float, target: float | None, hvac_action: str, hvac_mode: str) -> int:
        if hvac_mode == "off" or hvac_action in {"off", "idle"}:
            return HEATING_LEVEL_ECO
        if target is None:
            return HEATING_LEVEL_PREFERRED
        delta = float(target) - float(current)
        if delta >= 1.5:
            return HEATING_LEVEL_AGGRESSIVE
        if delta <= 0.25:
            return HEATING_LEVEL_ECO
        return HEATING_LEVEL_PREFERRED

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
                last_value = float(np.mean(bucket))
            resampled.append((current_ts, last_value))
            current_ts += timedelta(minutes=step_minutes)
        return resampled

    def _rolling_half_hour_forecast(self, series: list[tuple[datetime, float]], outside_temp_list: list[float], points: int, current: float) -> list[float]:
        if not series:
            return [current] * points

        step_minutes = self._step_minutes()
        step = timedelta(minutes=step_minutes)
        values = np.array([float(value) for _, value in series], dtype=float)
        timestamps = [ts for ts, _ in series]
        value_by_ts = {ts: float(value) for ts, value in series}

        slots_per_day = max(1, int(round(24 * 60 / max(step_minutes, 1))))
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
            slot = ((ts.hour * 60) + ts.minute) // max(step_minutes, 1)
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
            slot = ((next_ts.hour * 60) + next_ts.minute) // max(step_minutes, 1)
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

    async def _build_result(self, indoor_temp: float, outside_temp_list: list[float], carbon_list: list[float]) -> dict[str, Any]:
        """Build the full coordinator payload for sensors/entities.

        High level flow:
        1. Build the target-temperature schedule.
        2. Build / update the RLS model from thermostat history.
        3. Ask MPC which heating level it would choose at each step.
        4. Convert the current heating level to a thermostat setpoint.
        """
        mode = self.entry.data.get(CONF_MODE, "live")
        points = min(self._forecast_points(), len(outside_temp_list), len(carbon_list))
        outside_temp_list = outside_temp_list[:points]
        carbon_list = carbon_list[:points]
        target_mode = self.entry.data.get(CONF_TARGET_MODE, DEFAULT_TARGET_MODE)
        manual_target_temp = float(self.entry.data.get(CONF_MANUAL_TARGET_TEMP, DEFAULT_MANUAL_TARGET_TEMP))
        target_temp_list = self._build_target_temperature_list(points, target_mode, manual_target_temp)
        # Learn a simple 1-step room model from the thermostat's recent history.
        rls_model = await self._build_rls_model()
        simulated_room_temperature_list = self._simulate_room_temperature(indoor_temp, outside_temp_list, target_temp_list, carbon_list, rls_model)

        horizon = min(self._horizon(), points)
        recommended_level_list: list[int] = []
        current_temp = float(indoor_temp)

        for idx in range(points):
            segment_length = min(horizon, points - idx)
            level = mpc_control(
                RLS_model=rls_model,
                N=segment_length,
                T0=current_temp,
                T_target=target_temp_list[idx : idx + segment_length],
                T_out=outside_temp_list[idx : idx + segment_length],
                carbon_intensity=carbon_list[idx : idx + segment_length],
            )
            recommended_level_list.append(int(level))
            a, b, c, d = [float(v) for v in rls_model.theta[:, 0]]
            current_temp = float(a * current_temp + b * level + c * outside_temp_list[idx] + d)

        recommended_level_now = recommended_level_list[0] if recommended_level_list else HEATING_LEVEL_ECO
        recommended_setpoint = self._map_level_to_setpoint(recommended_level_now, target_temp_list[0])
        current_slot = self._current_slot()
        forecast_timestamps = [
            (current_slot + timedelta(minutes=self._step_minutes() * idx)).isoformat() for idx in range(points)
        ]
        return {
            ATTR_MODE: mode,
            ATTR_TARGET_MODE: target_mode,
            ATTR_MANUAL_TARGET_TEMP: manual_target_temp,
            ATTR_INDOOR_TEMPERATURE: float(indoor_temp),
            ATTR_OUTSIDE_TEMP_FORECAST_LIST: [float(x) for x in outside_temp_list],
            ATTR_CARBON_FORECAST_LIST: [float(x) for x in carbon_list],
            ATTR_TARGET_TEMPERATURE_LIST: [float(x) for x in target_temp_list],
            ATTR_RECOMMENDED_HEATING_LEVEL_LIST: recommended_level_list,
            ATTR_SIMULATED_ROOM_TEMPERATURE_LIST: simulated_room_temperature_list,
            ATTR_RECOMMENDED_HEATING_LEVEL_NOW: int(recommended_level_now),
            ATTR_RECOMMENDED_SETPOINT: float(recommended_setpoint),
            ATTR_APPLIED_HEATING_MODE: self._level_mode_label(recommended_level_now),
            ATTR_CONTROL_APPLIED: False,
            ATTR_CONTROL_REASON: "not_applied" if mode != "live" else "not_enabled",
            ATTR_LAST_UPDATED: datetime.now(timezone.utc).isoformat(),
            ATTR_FORECAST_TIMESTAMPS: forecast_timestamps,
            ATTR_PLOT_HISTORY_TIMESTAMPS: list(self._comparison_timestamps),
            ATTR_PLOT_ACTUAL_CARBON_HISTORY: list(self._actual_carbon_history),
            ATTR_PLOT_ESTIMATED_CARBON_HISTORY: list(self._estimated_carbon_history),
            ATTR_PLOT_INDOOR_TEMPERATURE_HISTORY: list(self._indoor_temperature_history),
            ATTR_PLOT_RECOMMENDED_HEATING_LEVEL_HISTORY: list(self._recommended_heating_level_history),
            ATTR_PLOT_RECOMMENDED_SETPOINT_HISTORY: list(self._recommended_setpoint_history),
        }

    def _simulate_room_temperature(self, indoor_temp: float, outside_temp_list: list[float], target_temp_list: list[float], carbon_list: list[float], rls_model: RLS) -> list[float]:
        if not outside_temp_list:
            return []
        horizon = min(self._horizon(), len(outside_temp_list))
        current_temp = float(indoor_temp)
        simulated: list[float] = []
        for idx in range(len(outside_temp_list)):
            segment_length = min(horizon, len(outside_temp_list) - idx)
            level = mpc_control(
                RLS_model=rls_model,
                N=segment_length,
                T0=current_temp,
                T_target=target_temp_list[idx : idx + segment_length],
                T_out=outside_temp_list[idx : idx + segment_length],
                carbon_intensity=carbon_list[idx : idx + segment_length],
            )
            a, b, c, d = [float(v) for v in rls_model.theta[:, 0]]
            current_temp = float(a * current_temp + b * level + c * outside_temp_list[idx] + d)
            simulated.append(current_temp)
        return simulated

    async def _build_rls_model(self) -> RLS:
        """Fit the RLS model from recent climate history.

        We infer a discrete heating level from thermostat behaviour and then fit:
            T_next = a*T_now + b*level + c*T_out + d
        """
        model = RLS(a=0.96, b=0.6, c=0.03, d=0.0)
        climate_entity = self.entry.data.get(CONF_CLIMATE_ENTITY)
        if not climate_entity:
            return model
        history = await self._get_climate_history(climate_entity)
        if len(history) < 3:
            return model

        weather = await self._fetch_outside_temperature_forecast(max(len(history), self._forecast_points()))
        step_seconds = self._step_minutes() * 60
        buckets: dict[datetime, list[tuple[float, int, float]]] = {}
        for ts, current, level, target in history:
            epoch = int(ts.timestamp())
            bucket_epoch = epoch - (epoch % step_seconds)
            bucket_ts = datetime.fromtimestamp(bucket_epoch, tz=timezone.utc)
            buckets.setdefault(bucket_ts, []).append((current, level, target))
        ordered = sorted((ts, vals) for ts, vals in buckets.items())
        if len(ordered) < 3:
            return model

        aggregated: list[tuple[datetime, float, int]] = []
        for ts, vals in ordered:
            temps = [v[0] for v in vals]
            levels = [v[1] for v in vals]
            aggregated.append((ts, float(np.mean(temps)), int(round(float(np.mean(levels))))))

        last_outside = weather[0] if weather else 10.0
        # Feed each observed transition into RLS so the model gradually learns
        # how this room reacts to outside temperature and heating effort.
        for idx in range(len(aggregated) - 1):
            _, temp_now, level = aggregated[idx]
            _, temp_next, _ = aggregated[idx + 1]
            outside = weather[min(idx, len(weather) - 1)] if weather else last_outside
            last_outside = outside
            model.update(T_k=temp_now, u_k=level, T_outk=outside, T_k1=temp_next)
        return model

    def _build_target_temperature_list(self, points: int, target_mode: str, manual_target_temp: float) -> list[float]:
        if points <= 0:
            return []
        if target_mode == TARGET_MODE_MANUAL:
            return [float(manual_target_temp)] * points
        current_slot = self._current_slot()
        target_list: list[float] = []
        for idx in range(points):
            ts = current_slot + timedelta(minutes=self._step_minutes() * idx)
            hour = ts.hour + (ts.minute / 60.0)
            target_list.append(float(self._profile_target_for_hour(hour, target_mode)))
        return target_list

    @staticmethod
    def _profile_target_for_hour(hour: float, target_mode: str) -> float:
        if target_mode == TARGET_MODE_PREFERRED_WARMER:
            if hour < 6:
                return 15.0
            if hour < 9:
                return 21.0
            if hour < 14:
                return 18.0
            if hour < 22:
                return 21.0
            return 15.0
        return 21.0

    def _map_level_to_setpoint(self, heating_level: int, base_target: float) -> float:
        eco_offset = float(self.entry.data.get(CONF_ECO_OFFSET, DEFAULT_ECO_OFFSET))
        preferred_offset = float(self.entry.data.get(CONF_PREFERRED_OFFSET, DEFAULT_PREFERRED_OFFSET))
        aggressive_offset = float(self.entry.data.get(CONF_AGGRESSIVE_OFFSET, DEFAULT_AGGRESSIVE_OFFSET))
        if heating_level <= HEATING_LEVEL_ECO:
            return float(base_target + eco_offset)
        if heating_level >= HEATING_LEVEL_AGGRESSIVE:
            return float(base_target + aggressive_offset)
        return float(base_target + preferred_offset)

    @staticmethod
    def _level_mode_label(heating_level: int) -> str:
        if heating_level <= HEATING_LEVEL_ECO:
            return "eco"
        if heating_level >= HEATING_LEVEL_AGGRESSIVE:
            return "aggressive"
        return "preferred"

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
        self._append_history(self._recommended_heating_level_history, int(data.get(ATTR_RECOMMENDED_HEATING_LEVEL_NOW, 0) or 0))
        self._append_history(self._recommended_setpoint_history, float(data.get(ATTR_RECOMMENDED_SETPOINT, 0.0) or 0.0))

        forecast_values = data.get(ATTR_CARBON_FORECAST_LIST, []) or []
        for idx, value in enumerate(forecast_values):
            ts = current_slot + timedelta(minutes=self._step_minutes() * idx)
            self._forecast_archive[ts] = float(value)

        cutoff = current_slot - timedelta(days=3)
        self._forecast_archive = {ts: val for ts, val in self._forecast_archive.items() if ts >= cutoff}

        data[ATTR_PLOT_HISTORY_TIMESTAMPS] = list(self._comparison_timestamps)
        data[ATTR_PLOT_ACTUAL_CARBON_HISTORY] = list(self._actual_carbon_history)
        data[ATTR_PLOT_ESTIMATED_CARBON_HISTORY] = list(self._estimated_carbon_history)
        data[ATTR_PLOT_INDOOR_TEMPERATURE_HISTORY] = list(self._indoor_temperature_history)
        data[ATTR_PLOT_RECOMMENDED_HEATING_LEVEL_HISTORY] = list(self._recommended_heating_level_history)
        data[ATTR_PLOT_RECOMMENDED_SETPOINT_HISTORY] = list(self._recommended_setpoint_history)

    def _append_history(self, target: list[Any], value: Any) -> None:
        target.append(value)
        if len(target) > PLOT_HISTORY_MAX_POINTS:
            del target[0 : len(target) - PLOT_HISTORY_MAX_POINTS]

    async def _apply_recommended_control(self, data: dict[str, Any]) -> None:
        climate_entity = self.entry.data.get(CONF_CLIMATE_ENTITY)
        setpoint = data.get(ATTR_RECOMMENDED_SETPOINT)
        if not climate_entity or setpoint is None:
            return
        try:
            await self.hass.services.async_call(
                "climate",
                "set_temperature",
                {"entity_id": climate_entity, "temperature": float(setpoint)},
                blocking=True,
            )
            data[ATTR_CONTROL_APPLIED] = True
            data[ATTR_CONTROL_REASON] = "temperature_set"
        except Exception as err:
            data[ATTR_CONTROL_APPLIED] = False
            data[ATTR_CONTROL_REASON] = f"failed: {err}"

    @staticmethod
    def _expand_hourly_to_step(hourly: list[float], points: int, step_minutes: int, fallback: float) -> list[float]:
        if step_minutes >= 60:
            stride = max(1, int(round(step_minutes / 60)))
            result = [hourly[min(i * stride, len(hourly) - 1)] for i in range(points)]
            return result if result else [fallback] * points

        ratio = max(1, int(round(60 / step_minutes)))
        expanded: list[float] = []
        for value in hourly:
            expanded.extend([float(value)] * ratio)
            if len(expanded) >= points:
                break
        if not expanded:
            expanded = [fallback]
        if len(expanded) < points:
            expanded.extend([expanded[-1]] * (points - len(expanded)))
        return expanded[:points]

    @staticmethod
    def _coerce_float(value: Any, default: float | None = None) -> float | None:
        try:
            if value in (None, STATE_UNKNOWN, STATE_UNAVAILABLE):
                return default
            return float(value)
        except (TypeError, ValueError):
            return default

    def clear_plot_history(self) -> None:
        self._comparison_timestamps.clear()
        self._actual_carbon_history.clear()
        self._estimated_carbon_history.clear()
        self._indoor_temperature_history.clear()
        self._recommended_heating_level_history.clear()
        self._recommended_setpoint_history.clear()

