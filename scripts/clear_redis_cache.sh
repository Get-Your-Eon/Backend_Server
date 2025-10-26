#!/usr/bin/env bash
# Wrapper to run the clear_redis_cache.py script using environment variables
# Usage:
#   REDIS_HOST=red-d3kkesh5pdvs739ka080 REDIS_PORT=6379 ./scripts/clear_redis_cache.sh "stations:lat37.4073*" --delete

PATTERN=${1:-"stations:lat*"}
EXTRA=${2:-}

echo "Running clear_redis_cache.py pattern=${PATTERN} extra='${EXTRA}'"
python3 scripts/clear_redis_cache.py --pattern "${PATTERN}" ${EXTRA}
