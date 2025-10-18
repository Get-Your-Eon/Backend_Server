#!/usr/bin/env bash
# Usage: ./delete_redis_key.sh <redis-host> <redis-port> <redis-password> <key>
# If password is empty string, pass an empty string as argument.
set -euo pipefail
if [[ $# -lt 4 ]]; then
  echo "Usage: $0 REDIS_HOST REDIS_PORT REDIS_PASSWORD KEY"
  exit 2
fi
REDIS_HOST=$1
REDIS_PORT=$2
REDIS_PASSWORD=$3
KEY=$4
if [[ -z "$REDIS_PASSWORD" ]]; then
  redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" DEL "$KEY"
else
  redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" -a "$REDIS_PASSWORD" DEL "$KEY"
fi
echo "Deleted key: $KEY"