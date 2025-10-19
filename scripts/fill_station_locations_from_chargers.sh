#!/usr/bin/env zsh
# Safe runner for fill_station_locations_from_chargers.sql
# Prompts for DB credentials (or uses env vars), shows a preview and requires confirmation.

set -euo pipefail

SQL_FILE="$(dirname -- "$0")/fill_station_locations_from_chargers.sql"

if [[ ! -f "$SQL_FILE" ]]; then
  echo "SQL file not found: $SQL_FILE" >&2
  exit 1
fi

if [[ -z "${PGPASSWORD:-}" ]]; then
  # prompt for password silently in zsh-compatible way
  print -n "Enter DB password (leave blank to use PGPASSWORD env if set): "
  read -rs DBPASS
  echo
  if [[ -n "$DBPASS" ]]; then
    export PGPASSWORD="$DBPASS"
  fi
else
  echo "Using existing PGPASSWORD environment variable."
fi

print -n "Postgres host [dpg-d3jsqajipnbc73coagq0-a.oregon-postgres.render.com]: "
read HOST
HOST=${HOST:-dpg-d3jsqajipnbc73coagq0-a.oregon-postgres.render.com}
print -n "Port [5432]: "
read PORT
PORT=${PORT:-5432}
print -n "DB name [postgre_urqi]: "
read DB
DB=${DB:-postgre_urqi}
print -n "DB user [chirsharam]: "
read USER
USER=${USER:-chirsharam}

export PGSSLMODE=${PGSSLMODE:-require}

echo "Preview: stations that would be updated (station_id, charger_count)"
psql "host=$HOST port=$PORT dbname=$DB user=$USER sslmode=$PGSSLMODE" -c "\
WITH charger_centroids AS (\
  SELECT station_id, COUNT(*) AS charger_count FROM chargers WHERE location IS NOT NULL GROUP BY station_id\
), to_update AS (\
  SELECT s.id AS station_id, c.charger_count FROM stations s JOIN charger_centroids c ON c.station_id = s.id WHERE s.location IS NULL AND c.charger_count > 0\
) SELECT * FROM to_update ORDER BY charger_count DESC LIMIT 200;" || true

print -n "Proceed to update these stations? (yes/[no]) "
read CONFIRM
if [[ "$CONFIRM" != "yes" ]]; then
  echo "Aborted. No changes made."; exit 0
fi

echo "Running update SQL..."
psql "host=$HOST port=$PORT dbname=$DB user=$USER sslmode=$PGSSLMODE" -f "$SQL_FILE"

echo "Done. Verify with: psql \"host=$HOST port=$PORT dbname=$DB user=$USER sslmode=$PGSSLMODE\" -c '\\d+ stations'"
