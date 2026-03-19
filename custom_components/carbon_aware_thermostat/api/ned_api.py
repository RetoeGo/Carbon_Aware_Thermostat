import requests
import pandas as pd
import os
from dotenv import load_dotenv
from ned_mappings import MAPPINGS

# Load environment variables from a .env file located in the project root
load_dotenv()

# Get API Key from environment variables
API_KEY = os.getenv("NED_API_KEY")

BASE_URL = "https://api.ned.nl/v1/utilizations"

# Parameters for the request
# Refer to the API manual for allowed values
# https://ned.nl/nl/handleiding-api
# https://ned.nl/nl/definities
PARAMS = {
    'point': 0,             # 0 = Netherlands, see handleiding for provinces
    'type': 27,              # 27 = ElectricityMix, 28 = GasMix, see handleiding for more
    'granularity': 4,       # 3 = 10 minutes, 4 = 15 min, 5 = Hour, 6 = Day, 7 = Month, 8 = Year
    'granularitytimezone': 1, # 0 = UTC, 1 = CET
    'classification': 2,    # 1 = Forecast, 2 = Current,
    'activity': 1,          # 1 = Providing, 2 = Consuming, 3 = Import, 4 = Export, 5= Storage in, 6 = Storage out, 7 = Storage
    'validfrom[before]': '2025-12-31',
    'validfrom[after]': '2025-01-01'
}

OUTPUT_FILE = 'ned_data.csv'


def fetch_data(api_key, params):
    """
    Fetches data from the NED API.
    """
    headers = {
        'X-AUTH-TOKEN': api_key,
        'Accept': 'application/ld+json'
    }

    try:
        response = requests.get(BASE_URL, headers=headers, params=params)
        response.raise_for_status() # Raise error for bad status codes
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching data: {e}")
        return None



def clean_value(value):
    """
    Extracts the ID from a URL-like string (e.g., '/v1/types/2' -> 2).
    Returns the integer if possible, otherwise returns the original value.
    """
    if isinstance(value, str) and value.startswith('/v1/'):
        try:
            return int(value.split('/')[-1])
        except ValueError:
            pass
    return value





def save_to_csv(data, filename):
    """
    Parses the JSON response into a pandas DataFrame, cleans the data, and saves it to a CSV file.
    """
    if isinstance(data, dict):
        records = data.get('hydra:member', [])
    elif isinstance(data, list):
        records = data
    else:
        records = []

    if not records:
        print("Could not find records in the response.")
        return

    print(f"Found {len(records)} records.")

    df = pd.DataFrame(records)

    # Drop columns that are not necessary
    df.drop(columns=['@id', '@type'], inplace=True)

    # Columns to clean and map
    cols_to_map = ['activity', 'classification', 'granularity', 'granularitytimezone', 'point', 'type']

    for col in cols_to_map:
        if col in df.columns:
            # Clean the value (remove /v1/.../ prefix)
            df[col] = df[col].apply(clean_value)
            # Map the integer to the readable string using MAPPINGS
            df[col] = df[col].map(MAPPINGS.get(col, {})).fillna(df[col])

    # Save to CSV
    try:
        df.to_csv(filename, index=False)
        print(f"Successfully saved data to {filename}")
    except IOError as e:
        print(f"Error writing to file: {e}")

if __name__ == "__main__":
    if not API_KEY:
        print("WARNING: Please set your NED_API_KEY in the .env file before running.")
    else:
        data = fetch_data(API_KEY, PARAMS)
        if data:
            save_to_csv(data, OUTPUT_FILE)
