"""
Usage:
  python scripts/test_external_station_api.py 37.5 127.0

This script reads EXTERNAL_STATION_API_BASE_URL and EXTERNAL_STATION_API_KEY from env and performs
one request to the assumed nearby search endpoint. It prints status code and JSON response.
"""
import os
import sys
import httpx

BASE = os.getenv("EXTERNAL_STATION_API_BASE_URL")
KEY = os.getenv("EXTERNAL_STATION_API_KEY")
AUTH_TYPE = os.getenv("EXTERNAL_STATION_API_AUTH_TYPE", "header")
HEADER_NAME = os.getenv("EXTERNAL_STATION_API_KEY_HEADER_NAME", "Authorization")
TIMEOUT = int(os.getenv("EXTERNAL_STATION_API_TIMEOUT_SECONDS", "10"))

if not BASE or not KEY:
    print("Please set EXTERNAL_STATION_API_BASE_URL and EXTERNAL_STATION_API_KEY in your environment (see .env.example)")
    sys.exit(1)

if len(sys.argv) < 3:
    print("Usage: python scripts/test_external_station_api.py <lat> <lon>")
    sys.exit(1)

lat = sys.argv[1]
lon = sys.argv[2]

url = BASE.rstrip('/') + '/stations/nearby'

headers = {"Accept": "application/json"}
params = {"lat": lat, "lon": lon}
if AUTH_TYPE.lower() == 'header':
    headers[HEADER_NAME] = KEY
else:
    params['api_key'] = KEY

print(f"Requesting {url} with params={params} headers={headers}")

with httpx.Client(timeout=TIMEOUT) as client:
    r = client.get(url, params=params, headers=headers)
    print(f"Status: {r.status_code}")
    try:
        print(r.json())
    except Exception:
        print(r.text)
