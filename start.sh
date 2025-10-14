# #!/usr/bin/env bash
# set -euo pipefail

# # Render start script
# # - Run DB migrations (prefer poetry if available)
# # - Start the ASGI server (uvicorn)

# echo "=== Running migrations ==="
# if command -v poetry >/dev/null 2>&1; then
#   poetry run migrate || alembic upgrade head
# else
#   alembic upgrade head || true
# fi

# echo "=== Starting server ==="
# exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"


#!/usr/bin/env bash
set -euo pipefail

# --------------------------------------
# Preserve read-only DATABASE_URL for app
# --------------------------------------
# If DATABASE_URL_READONLY is set, use it as DATABASE_URL for app
export DATABASE_URL="${DATABASE_URL_READONLY:-$DATABASE_URL}"

# --------------------------------------
# Run DB migrations with admin account
# --------------------------------------
if [ -n "${DATABASE_URL:-}" ] && [ -n "${MIGRATION_DATABASE_URL:-}" ]; then
  echo "=== Running migrations with MIGRATION_DATABASE_URL ==="
  # temporarily override DATABASE_URL with admin account
  export DATABASE_URL="$MIGRATION_DATABASE_URL"
  if command -v poetry >/dev/null 2>&1; then
    poetry run migrate || alembic upgrade head
  else
    alembic upgrade head || true
  fi
  # restore read-only DATABASE_URL
  export DATABASE_URL="${DATABASE_URL_READONLY}"
fi

# --------------------------------------
# Start ASGI server
# --------------------------------------
echo "=== Starting server with read-only DB ==="
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
