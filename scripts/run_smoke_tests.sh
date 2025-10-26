#!/usr/bin/env bash
# Usage:
# SERVICE_URL="https://<your-service>" API_KEY="<x-api-key>" ADMIN_USER="user:pass" ./scripts/run_smoke_tests.sh
set -euo pipefail

SERVICE_URL=${SERVICE_URL:-}
API_KEY=${API_KEY:-}
ADMIN_USER=${ADMIN_USER:-}

if [[ -z "$SERVICE_URL" || -z "$API_KEY" || -z "$ADMIN_USER" ]]; then
  echo "Usage: SERVICE_URL=... API_KEY=... ADMIN_USER=user:pass $0"
  exit 2
fi

OUT_DIR="tmp/smoke_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$OUT_DIR"

echo "Running smoke tests against $SERVICE_URL, results -> $OUT_DIR"

# Coordinates to test (use the problematic coord as primary)
LAT=37.4073
LON=127.0079

radii=(600 1000 2000 3000 10000)

for r in "${radii[@]}"; do
  ts=$(date --iso-8601=seconds)
  echo "--> Testing radius=$r at $ts"
  curl -s -H "x-api-key: $API_KEY" "$SERVICE_URL/api/v1/stations?lat=${LAT}&lon=${LON}&radius=${r}" -o "$OUT_DIR/stations_r${r}.json"
  echo "  saved -> $OUT_DIR/stations_r${r}.json"
done

# Call admin Redis keys (dry-run) for stations and station_detail
echo "--> Listing Redis keys (admin)"
curl -s -u "$ADMIN_USER" "$SERVICE_URL/admin/redis/keys?pattern=stations:*&count=500" -o "$OUT_DIR/redis_stations_keys.json"
curl -s -u "$ADMIN_USER" "$SERVICE_URL/admin/redis/keys?pattern=station_detail:*&count=500" -o "$OUT_DIR/redis_station_detail_keys.json"

# Optional: call station detail for a station_id if known (user may edit this)
# Example placeholder - replace STATION_ID if you know one
STATION_ID=""
if [[ -n "$STATION_ID" ]]; then
  curl -s -H "x-api-key: $API_KEY" "$SERVICE_URL/api/v1/station/${STATION_ID}/chargers?addr=" -o "$OUT_DIR/station_detail_${STATION_ID}.json"
fi

# Print brief summary
echo "Smoke tests completed. Files in $OUT_DIR"
ls -la "$OUT_DIR"

echo "Please collect application logs from your deployment around the timestamps above and paste them here for analysis."
