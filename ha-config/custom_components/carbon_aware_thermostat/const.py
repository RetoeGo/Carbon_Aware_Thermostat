from __future__ import annotations

import logging

DOMAIN = "carbon_aware_thermostat"
LOGGER = logging.getLogger(__package__)

CONF_NAME = "name"
CONF_TARGET_MODE = "target_mode"
CONF_MANUAL_TARGET_TEMP = "manual_target_temp"
CONF_CLIMATE_ENTITY = "climate_entity"
CONF_MODE = "mode"
CONF_CONTROL_REAL_THERMOSTAT = "control_real_thermostat"
CONF_ECO_OFFSET = "eco_offset"
CONF_PREFERRED_OFFSET = "preferred_offset"
CONF_AGGRESSIVE_OFFSET = "aggressive_offset"
CONF_FORECAST_POINTS = "forecast_points"
CONF_FORECAST_STEP_MINUTES = "forecast_step_minutes"
CONF_MPC_HORIZON = "mpc_horizon"
CONF_CARBON_INTENSITY_SENSOR = "carbon_intensity_sensor"
CONF_WEATHER_ENTITY = "weather_entity"

TARGET_MODE_MANUAL = "manual"
TARGET_MODE_PREFERRED_WARMER = "preferred_warmer"
TARGET_MODE_OPTIONS = [
    TARGET_MODE_MANUAL,
    TARGET_MODE_PREFERRED_WARMER,
]

DEFAULT_NAME = "Carbon Aware Thermostat"
DEFAULT_MODE = "live"
DEFAULT_FORECAST_POINTS = 12
DEFAULT_FORECAST_STEP_MINUTES = 15
DEFAULT_MANUAL_TARGET_TEMP = 21.0
DEFAULT_TARGET_MODE = TARGET_MODE_MANUAL
DEFAULT_ECO_OFFSET = -2.0
DEFAULT_PREFERRED_OFFSET = 0.0
DEFAULT_AGGRESSIVE_OFFSET = 2.0
DEFAULT_MPC_HORIZON = 12

HEATING_LEVEL_ECO = 0
HEATING_LEVEL_PREFERRED = 1
HEATING_LEVEL_AGGRESSIVE = 2
HEATING_LEVELS = [
    HEATING_LEVEL_ECO,
    HEATING_LEVEL_PREFERRED,
    HEATING_LEVEL_AGGRESSIVE,
]

ATTR_INDOOR_TEMPERATURE = "indoor_temperature"
ATTR_OUTSIDE_TEMP_FORECAST_LIST = "outside_temp_forecast_list"
ATTR_CARBON_FORECAST_LIST = "carbon_forecast_list"
ATTR_RECOMMENDED_HEATING_LEVEL_LIST = "recommended_heating_level_list"
ATTR_SIMULATED_ROOM_TEMPERATURE_LIST = "simulated_room_temperature_list"
ATTR_LAST_UPDATED = "last_updated"
ATTR_MODE = "mode"
ATTR_RECOMMENDED_HEATING_LEVEL_NOW = "recommended_heating_level_now"
ATTR_RECOMMENDED_SETPOINT = "recommended_setpoint"
ATTR_CONTROL_APPLIED = "control_applied"
ATTR_CONTROL_REASON = "control_reason"
ATTR_TARGET_MODE = "target_mode"
ATTR_MANUAL_TARGET_TEMP = "manual_target_temp"
ATTR_TARGET_TEMPERATURE_LIST = "target_temperature_list"
ATTR_FORECAST_TIMESTAMPS = "forecast_timestamps"
ATTR_PLOT_HISTORY_TIMESTAMPS = "plot_history_timestamps"
ATTR_PLOT_ACTUAL_CARBON_HISTORY = "plot_actual_carbon_history"
ATTR_PLOT_ESTIMATED_CARBON_HISTORY = "plot_estimated_carbon_history"
ATTR_PLOT_INDOOR_TEMPERATURE_HISTORY = "plot_indoor_temperature_history"
ATTR_PLOT_RECOMMENDED_HEATING_LEVEL_HISTORY = "plot_recommended_heating_level_history"
ATTR_PLOT_RECOMMENDED_SETPOINT_HISTORY = "plot_recommended_setpoint_history"
ATTR_APPLIED_HEATING_MODE = "applied_heating_mode"

PLOT_HISTORY_MAX_POINTS = 96
