import os
from typing import Optional

import pandas as pd
import requests
from dotenv import load_dotenv
from urllib.parse import urljoin
import time

from ned_mappings import MAPPINGS

load_dotenv()

API_KEY = os.getenv("NED_API_KEY")
BASE_URL = "https://api.ned.nl/v1/utilizations"
API_HOST = "https://api.ned.nl"
OUTPUT_FILE = "ned_data_with_temperature.csv"

# Delft city centre coordinates. Open-Meteo returns archive weather for these coordinates.
DELFT_LATITUDE = 52.0116
DELFT_LONGITUDE = 4.3571
OPEN_METEO_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"

PARAMS = {
    "point": 0,
    "type": 27,  # ElectricityMix
    "granularity": 4,  # 15 minutes
    "granularitytimezone": 0,  # UTC to match Open-Meteo UTC responses cleanly
    "classification": 2,  # Current
    "activity": 1,  # Providing
    "validfrom[before]": "2026-01-01",
    "validfrom[after]": "2025-01-01",
}


def clean_value(value):
    if isinstance(value, str) and value.startswith("/v1/"):
        try:
            return int(value.split("/")[-1])
        except ValueError:
            pass
    return value


def fetch_data(api_key: str, params: dict) -> dict:
    headers = {
        "X-AUTH-TOKEN": api_key,
        "Accept": "application/ld+json",
    }

    all_records = []
    current_url = BASE_URL
    request_params = params.copy()
    page_count = 0

    while current_url:
        page_count += 1
        print(f"Fetching NED page {page_count} from {current_url}...")
        try:
            response = requests.get(current_url, headers=headers, params=request_params, timeout=60)
            response.raise_for_status()
            json_data = response.json()
            records = json_data.get("hydra:member", [])
            all_records.extend(records)
            request_params = {}

            next_page_path = None
            if "hydra:view" in json_data and "hydra:next" in json_data["hydra:view"]:
                next_page_path = json_data["hydra:view"]["hydra:next"]

            total_items = json_data.get("hydra:totalItems", "Unknown")
            if next_page_path:
                current_url = urljoin(API_HOST, next_page_path)
                print(
                    f"Collected {len(all_records)} records so far (Total: {total_items}). "
                    "Waiting 1.6 seconds before next request..."
                )
                time.sleep(1.6)
            else:
                current_url = None
        except requests.exceptions.RequestException as exc:
            print(f"Error fetching NED data: {exc}")
            break

    return {"hydra:member": all_records}


def build_ned_dataframe(data: dict) -> pd.DataFrame:
    records = data.get("hydra:member", []) if isinstance(data, dict) else []
    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records)

    cols_to_drop = ["@id", "@type"]
    df.drop(columns=[c for c in cols_to_drop if c in df.columns], inplace=True)

    cols_to_map = ["activity", "classification", "granularity", "granularitytimezone", "point", "type"]
    for col in cols_to_map:
        if col in df.columns:
            df[col] = df[col].apply(clean_value)
            df[col] = df[col].map(MAPPINGS.get(col, {})).fillna(df[col])

    for col in ["validfrom", "validto", "lastupdate"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], utc=True, errors="coerce")

    for col in ["capacity", "volume", "percentage", "emission", "emissionfactor"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    if "emissionfactor" in df.columns:
        df["carbon_intensity_gco2_per_kwh"] = df["emissionfactor"] * 1000.0

    df = df.sort_values("validfrom").reset_index(drop=True)
    return df


def fetch_open_meteo_hourly_temperature(start_utc: pd.Timestamp, end_utc: pd.Timestamp) -> pd.DataFrame:
    start_date = start_utc.strftime("%Y-%m-%d")
    end_date = end_utc.strftime("%Y-%m-%d")

    params = {
        "latitude": DELFT_LATITUDE,
        "longitude": DELFT_LONGITUDE,
        "start_date": start_date,
        "end_date": end_date,
        "hourly": "temperature_2m",
        "timezone": "UTC",
    }

    print(
        f"Fetching hourly Delft temperature from Open-Meteo for {start_date} to {end_date} "
        f"at {DELFT_LATITUDE}, {DELFT_LONGITUDE}..."
    )
    response = requests.get(OPEN_METEO_ARCHIVE_URL, params=params, timeout=60)
    response.raise_for_status()
    payload = response.json()

    hourly = payload.get("hourly", {})
    times = hourly.get("time", [])
    temps = hourly.get("temperature_2m", [])

    if not times or not temps:
        raise ValueError("Open-Meteo response did not include hourly temperature_2m data.")

    temp_df = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(times, utc=True, errors="coerce"),
            "temperature_c": pd.to_numeric(temps, errors="coerce"),
        }
    ).dropna(subset=["timestamp"])

    temp_df = temp_df.sort_values("timestamp").drop_duplicates(subset=["timestamp"])
    return temp_df


def attach_temperature(ned_df: pd.DataFrame, temp_df: pd.DataFrame) -> pd.DataFrame:
    if ned_df.empty:
        return ned_df

    target_index = pd.DatetimeIndex(ned_df["validfrom"]).sort_values()

    hourly = temp_df.set_index("timestamp")["temperature_c"].sort_index()
    expanded = hourly.reindex(hourly.index.union(target_index)).sort_index()
    interpolated = expanded.interpolate(method="time").reindex(target_index)

    out = ned_df.copy()
    out["temperature_c_delft"] = interpolated.to_numpy()
    out["temperature_source"] = "Open-Meteo historical hourly archive interpolated to 15 minutes"
    return out


async def get_carbon_intensity() -> Optional[float]:
    """Return the latest carbon intensity in gCO2/kWh."""
    if not API_KEY:
        raise RuntimeError("Missing NED_API_KEY in environment or .env file.")

    data = fetch_data(API_KEY, PARAMS)
    df = build_ned_dataframe(data)
    if df.empty:
        return None

    latest = df.dropna(subset=["carbon_intensity_gco2_per_kwh"]).iloc[-1]
    return float(latest["carbon_intensity_gco2_per_kwh"])


def main():
    if not API_KEY:
        print("WARNING: Please set your NED_API_KEY in the .env file before running.")
        return

    data = fetch_data(API_KEY, PARAMS)
    ned_df = build_ned_dataframe(data)
    if ned_df.empty:
        print("No NED data fetched to save.")
        return

    try:
        temp_df = fetch_open_meteo_hourly_temperature(
            ned_df["validfrom"].min(),
            ned_df["validto"].max(),
        )
        merged_df = attach_temperature(ned_df, temp_df)
    except Exception as exc:
        print(f"Error fetching temperature data: {exc}")
        merged_df = ned_df.copy()
        merged_df["temperature_c_delft"] = pd.NA
        merged_df["temperature_source"] = pd.NA

    merged_df.to_csv(OUTPUT_FILE, index=False)
    print(f"Successfully saved merged data to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
