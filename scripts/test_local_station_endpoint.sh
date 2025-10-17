#!/usr/bin/env bash
# Usage: export FRONTEND_API_KEYS=localtestkey
# ./scripts/test_local_station_endpoint.sh 37.5 127.0

LAT=${1}
LON=${2}
API_KEY=${FRONTEND_API_KEYS}

if [ -z "$LAT" ] || [ -z "$LON" ]; then
  echo "Usage: $0 <lat> <lon>"
  exit 1
fi

if [ -z "$API_KEY" ]; then
  echo "Please export FRONTEND_API_KEYS with your test key (see .env.example)"
  exit 1
fi

curl -s -G \
  -H "x-api-key: $API_KEY" \
  --data-urlencode "lat=$LAT" \
  --data-urlencode "lon=$LON" \
  "http://127.0.0.1:8000/api/v1/stations" | jq
