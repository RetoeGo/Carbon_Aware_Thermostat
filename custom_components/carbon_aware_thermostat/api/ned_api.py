import requests
import pandas as pd
import os
from dotenv import load_dotenv
from ned_mappings import MAPPINGS
import time
from urllib.parse import urljoin

# Load environment variables from a .env file located in the project root
load_dotenv()

# Get API Key from environment variables
API_KEY = os.getenv("NED_API_KEY")

BASE_URL = "https://api.ned.nl/v1/utilizations"
API_HOST = "https://api.ned.nl" # For constructing full URLs from relative paths

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
    'validfrom[before]': '2026-01-01',
    'validfrom[after]': '2025-01-01'
}

OUTPUT_FILE = 'ned_data.csv'

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

def fetch_data(api_key, params):
    """
    Fetches data from the NED API, handling pagination and rate limits.
    """
    headers = {
        'X-AUTH-TOKEN': api_key,
        'Accept': 'application/ld+json'
    }
    
    all_records = []
    current_url = BASE_URL
    
    # For the first request, use params. For subsequent requests, params are part of the next_page_url
    request_params = params
    
    page_count = 0
    while current_url:
        page_count += 1
        print(f"Fetching page {page_count} from {current_url}...")
        try:
            response = requests.get(current_url, headers=headers, params=request_params)
            response.raise_for_status() # Raise error for bad status codes
            json_data = response.json()

            records = json_data.get('hydra:member', [])
            all_records.extend(records)
            
            # Reset request_params after the first request, as subsequent URLs will contain them
            request_params = {} 

            # Check for pagination link
            next_page_path = None
            if 'hydra:view' in json_data and 'hydra:next' in json_data['hydra:view']:
                next_page_path = json_data['hydra:view']['hydra:next']
            
            # Attempt to get total items if available
            total_items = json_data.get('hydra:totalItems', 'Unknown')

            if next_page_path:
                # Construct the full URL for the next page
                current_url = urljoin(API_HOST, next_page_path)
                print(f"Collected {len(all_records)} records so far (Total: {total_items}). Waiting 1.6 seconds before next request...")
                time.sleep(1.6)
            else:
                current_url = None # No more pages
            
        except requests.exceptions.RequestException as e:
            print(f"Error fetching data: {e}")
            break # Exit loop on error
            
    return {'hydra:member': all_records} # Return in a format compatible with save_to_csv

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
        print("No records to save.") # Changed from "Could not find records" to be more accurate
        return

    print(f"Found {len(records)} records.")

    df = pd.DataFrame(records)

    # Drop columns that are not necessary
    cols_to_drop = ['@id', '@type']
    # Only drop columns that exist in the DataFrame
    df.drop(columns=[col for col in cols_to_drop if col in df.columns], inplace=True)

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
        if data and data.get('hydra:member'): # Check if data and records exist
            save_to_csv(data, OUTPUT_FILE)
        else:
            print("No data fetched to save.")
