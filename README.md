# Carbon Aware Thermostat

A Home Assistant custom integration plus a small local test environment and a set of data-analysis notebooks.

## Directory structure

```text
Carbon_Aware_Thermostat/
├── README.md
├── .gitignore
├── ha-config/
│   ├── configuration.yaml
│   └── custom_components/
│       └── carbon_aware_thermostat/
│           ├── __init__.py
│           ├── climate.py
│           ├── config_flow.py
│           ├── const.py
│           ├── coordinator.py
│           ├── manifest.json
│           ├── mpc.py
│           ├── sensor.py
│           ├── services.yaml
│           └── strings.json
├── testenv/
│   ├── api.py
│   ├── api_results.csv
│   ├── mpc.py
│   └── room.py
└── data-analysis/
    ├── analysis-emils-2.ipynb
    ├── analysis-pranav.ipynb
    ├── significance_tests-2.ipynb
    ├── significance_tests_old.ipynb
    └── whole-pipeline.ipynb
```

## What is inside each directory

### `ha-config/`
A ready-to-run Home Assistant config folder for local testing in Docker.

- `configuration.yaml`  
  Home Assistant configuration. This includes the fake thermostat test setup and the default Home Assistant panels.

- `custom_components/carbon_aware_thermostat/`  
  The actual custom integration.

### `testenv/`
A standalone sandbox for trying the room model, MPC, API data pull, and CSV-based experiments outside Home Assistant.

### `data-analysis/`
Jupyter notebooks for offline analysis, experiments, and significance testing.

## What is inside each integration file

### `ha-config/custom_components/carbon_aware_thermostat/__init__.py`
Sets up the integration, registers services, and forwards the config entry to the entity platforms.

### `ha-config/custom_components/carbon_aware_thermostat/climate.py`
Defines the climate entity exposed by the custom integration.

### `ha-config/custom_components/carbon_aware_thermostat/config_flow.py`
Defines the UI setup flow that appears in Home Assistant when you add the integration.

### `ha-config/custom_components/carbon_aware_thermostat/const.py`
Shared constants, config keys, attribute names, and defaults used across the integration.

### `ha-config/custom_components/carbon_aware_thermostat/coordinator.py`
The main runtime logic:
- reads thermostat, weather, and carbon data
- builds forecasts
- trains the RLS model from history
- runs MPC
- translates the chosen heating level into a thermostat setpoint

### `ha-config/custom_components/carbon_aware_thermostat/manifest.json`
Required Home Assistant manifest file for the custom integration.

### `ha-config/custom_components/carbon_aware_thermostat/mpc.py`
Human-readable control logic:
- `RLS` learns a simple one-step room temperature model
- `mpc_control()` evaluates the next few steps and picks the best heating level

### `ha-config/custom_components/carbon_aware_thermostat/sensor.py`
Diagnostic and helper sensors that expose recommended values, forecasts, and internal controller outputs.

### `ha-config/custom_components/carbon_aware_thermostat/services.yaml`
Descriptions for custom services so they show nicely in the Home Assistant UI.

### `ha-config/custom_components/carbon_aware_thermostat/strings.json`
UI strings used by Home Assistant for naming and setup text.

## What is inside each `testenv` file

### `testenv/room.py`
Room simulation script used for local experiments. It combines the room model, external data, and MPC loop.

### `testenv/mpc.py`
Standalone MPC + RLS implementation for experimentation outside Home Assistant.

### `testenv/api.py`
Script for fetching carbon intensity and weather data and writing a CSV.

### `testenv/api_results.csv`
Saved API output data used by the test environment and notebooks.

## What is inside each `data-analysis` file

### `data-analysis/analysis-emils-2.ipynb`
Notebook for exploratory analysis.

### `data-analysis/analysis-pranav.ipynb`
Notebook for additional analysis experiments.

### `data-analysis/significance_tests-2.ipynb`
Notebook for statistical significance testing.

### `data-analysis/significance_tests_old.ipynb`
Older significance-testing notebook kept for reference.

### `data-analysis/whole-pipeline.ipynb`
Notebook that ties together a larger end-to-end analysis flow.

## How to run Home Assistant locally

From the project root:

```bash
docker run \
  --name ha-test \
  --rm \
  -it \
  -p 8123:8123 \
  -v $(pwd)/ha-config:/config \
  ghcr.io/home-assistant/home-assistant:stable
```

Then open:

```text
http://localhost:8123
```

On first start, finish the normal Home Assistant onboarding.

## Required integrations

Before adding the custom package, add these integrations in Home Assistant:

### Met.no
Used as the weather source for outside temperature and forecasts.

### Electricity Maps
Used as the electricity-grid / carbon-intensity source.

## How to get the API keys / access

### Met.no
The Home Assistant `Met.no` integration does not need an API key. Just add it from the Home Assistant UI.

### Electricity Maps
You need an Electricity Maps API key. Create an account, sign up for the free tier in the Electricity Maps API portal, and then use that key when adding the Home Assistant integration.

## How to add the custom package

1. Start Home Assistant with the included `ha-config/` folder.
2. Open Home Assistant.
3. Go to **Settings -> Devices & Services**.
4. Add the required integrations first:
   - **Met.no**
   - **Electricity Maps**
5. Then add the custom integration:
   - **Carbon Aware Thermostat**
6. During setup, choose:
   - the thermostat / climate entity
   - the weather entity from Met.no
   - the carbon-intensity sensor from Electricity Maps

## Where to see the results

After the integration is running, you can inspect the created entities in Home Assistant.

For time-series results:
1. Open the **History** tab in the left sidebar.
2. Select the integration entities you want to inspect.
3. View the graphs for temperatures, target values, and controller outputs.

If the History tab is missing, make sure `default_config:` and `recorder:` are enabled in `ha-config/configuration.yaml`.
