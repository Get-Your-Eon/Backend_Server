#!/usr/bin/env bash
# Simple infra diagnostic script for this project
# Checks: environment variables (masked), DB TCP reachability, psql basic queries (if psql available),
# curl to local FastAPI /health, and running uvicorn/gunicorn processes and listening ports.

set -euo pipefail
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

mask() {
  # mask password in a URL-like string
  local s="$1"
  # simple masking: replace :<pass>@ with :****@
  echo "$s" | sed -E 's#(:\/\/[^:]+:)[^@]+@#\1****@#'
}

echo "--- Environment (masked) ---"
echo "DATABASE_URL: "$( [ -n "${DATABASE_URL-}" ] && mask "$DATABASE_URL" || echo "(not set)" )
echo "LIBPQ_DATABASE_URL: "$( [ -n "${LIBPQ_DATABASE_URL-}" ] && mask "$LIBPQ_DATABASE_URL" || echo "(not set)" )
echo "FRONTEND_API_KEYS: "$( [ -n "${FRONTEND_API_KEYS-}" ] && echo "(set)" || echo "(not set)" )
echo "ADMIN_API_KEY: "$( [ -n "${ADMIN_API_KEY-}" ] && echo "(set)" || echo "(not set)" )
echo

# Determine which DB URL to use for CLI tools
DB_URL=""
if [ -n "${LIBPQ_DATABASE_URL-}" ]; then
  DB_URL="$LIBPQ_DATABASE_URL"
elif [ -n "${DATABASE_URL-}" ]; then
  # convert sqlalchemy async URI to libpq style if necessary
  DB_URL="${DATABASE_URL/postgresql+asyncpg:/postgresql:}"
fi

if [ -n "$DB_URL" ]; then
  echo "--- DB connectivity checks (using masked DB URL) ---"
  echo "DB URL: $(mask "$DB_URL")"

  # try to parse host and port using Python helper
  PY_PARSE="import sys
from urllib.parse import urlparse
u=urlparse(sys.argv[1])
host=u.hostname or ''
port=u.port or 5432
print(host, port)
"
  read DB_HOST DB_PORT < <(python3 - <<PY "$DB_URL"
$PY_PARSE
PY
  )

  echo "Resolved DB host: $DB_HOST port: $DB_PORT"

  echo "-- TCP reachability (3s timeout) --"
  python3 - <<PY
import socket,sys
host='$DB_HOST'
port=int($DB_PORT)
try:
    s=socket.create_connection((host,port),timeout=3)
    s.close()
    print('TCP OK')
except Exception as e:
    print('TCP FAIL:',e)
    sys.exit(0)
PY

  # If psql exists, run a basic SELECT 1 and count subsidies
  if command -v psql >/dev/null 2>&1; then
    echo "-- psql binary found, running sanity queries (may prompt if auth not in URL) --"
    set +e
    psql "$DB_URL" -c 'SELECT version();' 2>&1 | sed -n '1,6p'
    psql "$DB_URL" -c 'SELECT 1 as ok;' 2>&1 | sed -n '1,6p'
    psql "$DB_URL" -c "SELECT count(*) FROM subsidies;" 2>&1 | sed -n '1,6p'
    psql "$DB_URL" -c "SELECT PostGIS_full_version();" 2>&1 | sed -n '1,6p'
    set -e
  else
    echo "psql not found in PATH — skip psql checks"
  fi
else
  echo "No DB URL configured (LIBPQ_DATABASE_URL or DATABASE_URL). Skipping DB checks."
fi

echo
echo "--- FastAPI / health check (local) ---"
if command -v curl >/dev/null 2>&1; then
  set +e
  curl -sS -D - --max-time 5 http://127.0.0.1:8000/health || true
  set -e
else
  echo "curl not available; please curl http://127.0.0.1:8000/health manually"
fi

echo
echo "--- Process & Listening port checks ---"
echo "Processes matching 'uvicorn' or 'gunicorn' (excluding this grep):"
ps aux | egrep 'uvicorn|gunicorn|hypercorn' | egrep -v 'egrep|check_services.sh' || true

echo
echo "Listening TCP ports for :8000 (if any):"
if command -v lsof >/dev/null 2>&1; then
  lsof -iTCP -sTCP:LISTEN -P -n | egrep ':8000\b' || true
else
  echo "lsof not available; use 'lsof -iTCP -sTCP:LISTEN -P -n' to inspect ports"
fi

echo
echo "Diagnostics complete. If DB TCP fails or psql fails to connect, ensure LIBPQ_DATABASE_URL is exported in this shell and reachable from this host."

exit 0
