#!/usr/bin/env bash
# Creates the PostgreSQL role + database defined in .env (idempotent).
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; source .env; set +a
PSQL=/opt/homebrew/opt/postgresql@16/bin/psql
until /opt/homebrew/opt/postgresql@16/bin/pg_isready -h "$DB_HOST" -p "$DB_PORT" -q; do
  echo "waiting for PostgreSQL on $DB_HOST:$DB_PORT ..."; sleep 1; done
$PSQL -h "$DB_HOST" -p "$DB_PORT" -d postgres -v ON_ERROR_STOP=1 -q <<SQL
DO \$\$ BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '${DB_USER}') THEN
    CREATE ROLE "${DB_USER}" LOGIN PASSWORD '${DB_PASSWORD}';
  END IF;
END \$\$;
SQL
if ! $PSQL -h "$DB_HOST" -p "$DB_PORT" -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='${DB_NAME}'" | grep -q 1; then
  $PSQL -h "$DB_HOST" -p "$DB_PORT" -d postgres -q -c "CREATE DATABASE \"${DB_NAME}\" OWNER \"${DB_USER}\""
fi
echo "Database ${DB_NAME} ready (owner ${DB_USER})"
