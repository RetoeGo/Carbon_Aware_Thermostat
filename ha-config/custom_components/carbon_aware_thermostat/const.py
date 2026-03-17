from __future__ import annotations

import logging

DOMAIN = "carbon_aware_thermostat"
LOGGER = logging.getLogger(__package__)

CONF_NAME = "name"
CONF_TARGET_CLIMATE = "target_climate"
CONF_CLIMATE_ENTITY = "climate_entity"
CONF_MODE = "mode"
CONF_DEMO_ROOM_TEMP = "demo_room_temp"
CONF_DEMO_TARGET_TEMP = "demo_target_temp"
CONF_DEMO_ROOM_HEIGHT = "demo_room_height"
CONF_DEMO_ROOM_WIDTH = "demo_room_width"
CONF_DEMO_ROOM_LENGTH = "demo_room_length"
CONF_DEMO_EXPOSED_AREA = "demo_exposed_area"
CONF_WINDOW_PERCENT = "window_percent"
CONF_THERMOSTAT_POWER = "thermostat_power"
CONF_CONTROL_REAL_THERMOSTAT = "control_real_thermostat"
CONF_ECO_OFFSET = "eco_offset"
CONF_PREHEAT_OFFSET = "preheat_offset"
CONF_FORECAST_POINTS = "forecast_points"
CONF_FORECAST_STEP_MINUTES = "forecast_step_minutes"
CONF_COMFORT_SETPOINT = "comfort_setpoint"
CONF_MPC_HORIZON = "mpc_horizon"
CONF_CARBON_INTENSITY_SENSOR = "carbon_intensity_sensor"
CONF_WEATHER_ENTITY = "weather_entity"

DEFAULT_NAME = "Carbon Aware Thermostat"
DEFAULT_MODE = "live"
DEFAULT_FORECAST_POINTS = 48
DEFAULT_FORECAST_STEP_MINUTES = 30
DEFAULT_DEMO_ROOM_TEMP = 19.0
DEFAULT_DEMO_TARGET_TEMP = 21.0
DEFAULT_DEMO_ROOM_HEIGHT = 2.6
DEFAULT_DEMO_ROOM_WIDTH = 5.0
DEFAULT_DEMO_ROOM_LENGTH = 8.0
DEFAULT_DEMO_EXPOSED_AREA = 33.8
DEFAULT_WINDOW_PERCENT = 0.30
DEFAULT_THERMOSTAT_POWER = 1500.0
DEFAULT_ECO_OFFSET = -1.0
DEFAULT_PREHEAT_OFFSET = 0.0
DEFAULT_MPC_HORIZON = 48

ATTR_INDOOR_TEMPERATURE = "indoor_temperature"
ATTR_OUTSIDE_TEMP_FORECAST_LIST = "outside_temp_forecast_list"
ATTR_CARBON_FORECAST_LIST = "carbon_forecast_list"
ATTR_RECOMMENDED_POWER_LIST = "recommended_power_list"
ATTR_SIMULATED_ROOM_TEMPERATURE_LIST = "simulated_room_temperature_list"
ATTR_LAST_UPDATED = "last_updated"
ATTR_MODE = "mode"
ATTR_RECOMMENDED_POWER_NOW = "recommended_power_now"
ATTR_RECOMMENDED_SETPOINT = "recommended_setpoint"
ATTR_CONTROL_APPLIED = "control_applied"
ATTR_CONTROL_REASON = "control_reason"
ATTR_TARGET_CLIMATE = "target_climate"
ATTR_FORECAST_TIMESTAMPS = "forecast_timestamps"
ATTR_PLOT_HISTORY_TIMESTAMPS = "plot_history_timestamps"
ATTR_PLOT_ACTUAL_CARBON_HISTORY = "plot_actual_carbon_history"
ATTR_PLOT_ESTIMATED_CARBON_HISTORY = "plot_estimated_carbon_history"
ATTR_PLOT_INDOOR_TEMPERATURE_HISTORY = "plot_indoor_temperature_history"
ATTR_PLOT_RECOMMENDED_POWER_HISTORY = "plot_recommended_power_history"
ATTR_PLOT_RECOMMENDED_SETPOINT_HISTORY = "plot_recommended_setpoint_history"

PLOT_HISTORY_MAX_POINTS = 96
