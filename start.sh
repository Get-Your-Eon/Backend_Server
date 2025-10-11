#!/usr/bin/env bash
set -euo pipefail

# Render start script
# - Run DB migrations (prefer poetry if available)
# - Start the ASGI server (uvicorn)

echo "=== Running migrations ==="
if command -v poetry >/dev/null 2>&1; then
  poetry run migrate || alembic upgrade head
else
  alembic upgrade head || true
fi

echo "=== Starting server ==="
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
