#!/usr/bin/env bash
set -euo pipefail

# Run Alembic migrations safely against remote Render DB.
# This script will:
#  - optionally create a DB backup (if you answer Y)
#  - stamp the daa5cac943ac revision (mark as applied)
#  - run alembic upgrade heads
#  - show schema for stations/chargers/api_logs
#
# Usage: chmod +x scripts/run_migrations.sh && ./scripts/run_migrations.sh
# You will be prompted for the DB password interactively (not stored).

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

echo "This script will apply Alembic migrations to the Render DB."
read -p "Proceed? [y/N]: " proceed
proceed_lc="$(printf '%s' "$proceed" | tr '[:upper:]' '[:lower:]')"
if [[ "$proceed_lc" != "y" ]]; then
  echo "Aborted by user."
  exit 1
fi

# Read DB password securely
read -s -p "Enter DB password for user 'chirsharam': " DB_PW
echo

# Compose libpq connection string parts (avoid URL quoting issues)
HOST="dpg-d3jsqajipnbc73coagq0-a.oregon-postgres.render.com"
PORT="5432"
DBNAME="postgre_urqi"
USER="chirsharam"

# Ask for optional backup
read -p "Do you want to create a pg_dump backup first? [y/N]: " do_backup
do_backup_lc="$(printf '%s' "$do_backup" | tr '[:upper:]' '[:lower:]')"
if [[ "$do_backup_lc" == "y" ]]; then
  BACKUP_PATH="$HOME/db-before-charger-location.dump"
  echo "Creating backup to: $BACKUP_PATH (this may take a while)"
  PGPASSWORD="$DB_PW" pg_dump "host=$HOST port=$PORT dbname=$DBNAME user=$USER sslmode=require" -Fc -f "$BACKUP_PATH"
  echo "Backup complete: $BACKUP_PATH"
fi

# Export DATABASE_URL for alembic to use (env var)
export DATABASE_URL="postgresql://$USER:$DB_PW@$HOST:$PORT/$DBNAME?sslmode=require"
export REDIS_HOST='localhost'
export REDIS_PORT='6379'
# Ensure libpq tools use SSL when connecting
export PGSSLMODE='require'

echo "Stamping migration daa5cac943ac as applied..."
alembic stamp daa5cac943ac

echo "Upgrading all heads..."
alembic upgrade heads

echo "Upgrade finished. Showing schema for stations, chargers, api_logs"
PGPASSWORD="$DB_PW" psql "host=$HOST port=$PORT dbname=$DBNAME user=$USER sslmode=require" -c "\d+ stations"
PGPASSWORD="$DB_PW" psql "host=$HOST port=$PORT dbname=$DBNAME user=$USER sslmode=require" -c "\d+ chargers"
PGPASSWORD="$DB_PW" psql "host=$HOST port=$PORT dbname=$DBNAME user=$USER sslmode=require" -c "\d+ api_logs"

echo "Done. If you see the new columns (external_bid/raw_data/last_synced_at on stations and external_charger_id/connector_types/location on chargers), migrations succeeded."