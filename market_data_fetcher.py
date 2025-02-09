import requests
import pandas as pd
import re
import time
import os
from dotenv import load_dotenv

load_dotenv()

# Disable SSL warnings when verify=False is used
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

CACHED_SYMBOLS = None
PRIMARY_URL = "https://api.dappier.com/app/aimodel/am_01j749h8pbf7ns8r1bq9s2evrh"
FALLBACK_URL = "https://api.dappier.com/app/aimodel/am_01j749h8pbf7ns8r1bq9s2evrh-fallback"
LOCAL_FALLBACK_DATA = {
    "symbols": ["AAPL", "META", "GOOGL", "MSFT", "AMZN", "TSLA", "NVDA", "IBM", "ORCL"]
}

def robust_post(body, headers, timeout=30, verify=False, max_retries=3):
    for attempt in range(max_retries):
        try:
            with requests.Session() as session:
                response = session.post(PRIMARY_URL, headers=headers, json=body, timeout=timeout, verify=verify)
                return response
        except requests.exceptions.RequestException as e:
            if attempt < max_retries - 1:
                time.sleep(2)
                print(f"Connection error, retrying... (attempt {attempt+2})")
            else:
                print(f"Warning: Error after {max_retries} attempts to primary: {e}")
                break
    
    try:
        print("Attempting fallback endpoint...")
        with requests.Session() as session:
            response = session.post(FALLBACK_URL, headers=headers, json=body, timeout=timeout, verify=verify)
            return response
    except requests.exceptions.RequestException as e:
        print(f"Warning: Fallback failed as well: {e}")
        return None

def get_valid_symbols():
    global CACHED_SYMBOLS
    if CACHED_SYMBOLS is not None:
        return CACHED_SYMBOLS

    headers = {
        "Authorization": f"Bearer {os.getenv('DAPPIER_API_KEY', 'ak_01jkk8qs48e4986nm5q6vfx8ap')}",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }
    body = {"query": "List all available stock symbols"}

    response = robust_post(body, headers)
    if not response:
        print("Warning: Request failed, using local fallback data.")
        CACHED_SYMBOLS = set(LOCAL_FALLBACK_DATA["symbols"])
        return CACHED_SYMBOLS

    if response.status_code == 200:
        data = response.json()
        message = data.get('message', '')
        found_symbols = re.findall(r'\b[A-Z]{1,5}\b(?![\w\d])', message)
        if found_symbols:
            CACHED_SYMBOLS = set(found_symbols)
            return CACHED_SYMBOLS
    
    print("Warning: Using local fallback data.")
    CACHED_SYMBOLS = set(LOCAL_FALLBACK_DATA["symbols"])
    return CACHED_SYMBOLS

def get_market_data(symbol, debug=False):
    headers = {
        "Authorization": f"Bearer {os.getenv('DAPPIER_API_KEY', 'ak_01jkk8qs48e4986nm5q6vfx8ap')}",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }
    body = {"query": f"What is the latest 3-minute stock price data for {symbol}?"}

    response = robust_post(body, headers)
    if not response:
        print("Error: Request failed. Returning None.")
        return None

    if response.status_code != 200:
        print(f"Error: API request failed with status code {response.status_code}")
        return None

    data = response.json()
    message = data.get('message', '')
    if debug:
        print("Full API Response:", message)

    price_pattern = r'\*\*Price:\*\*\s*\$([\d\.]+)'
    size_pattern = r'\*\*Size:\*\*\s*(\d+)'
    timestamp_pattern = r'\*\*Timestamp:\*\*\s*(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} UTC)'
    
    prices = re.findall(price_pattern, message)
    sizes = re.findall(size_pattern, message)
    timestamps = re.findall(timestamp_pattern, message)

    if not (prices and sizes and timestamps):
        print("Error: Could not parse all required data from response")
        print(f"Found {len(prices)} prices, {len(sizes)} sizes, {len(timestamps)} timestamps")
        return None

    price_data = []
    for price, size, timestamp in zip(prices, sizes, timestamps):
        try:
            price_data.append({
                'timestamp': pd.to_datetime(timestamp, utc=True),
                'price': float(price),
                'volume': int(size)
            })
        except ValueError as e:
            print(f"Error parsing entry: {e}")
            continue

    if not price_data:
        print("No valid price data found")
        return None

    df = pd.DataFrame(price_data)
    df = df.sort_values('timestamp')
    
    df_ohlc = df.groupby('timestamp').agg({
        'price': ['first', 'max', 'min', 'last'],
        'volume': 'sum'
    }).reset_index()
    
    df_ohlc.columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
    return df_ohlc.set_index('timestamp')