#!/bin/sh
set -eu

DB_HOST="${POSTGRES_HOST:-db}"
DB_PORT="${POSTGRES_PORT:-5432}"
DB_NAME="${POSTGRES_DB:-postgres}"
APP_MODULE="${APP_MODULE:-main:app}"
APP_PORT="${APP_PORT:-8000}"
RUN_MIGRATIONS="${RUN_MIGRATIONS:-true}"
UVICORN_RELOAD="${UVICORN_RELOAD:-false}"

# Wait for PostgreSQL to be ready
until PGPASSWORD="$POSTGRES_PASSWORD" pg_isready -h "$DB_HOST" -p "$DB_PORT" -U "$POSTGRES_USER" -d "$DB_NAME"; do
  echo "Waiting for postgres at ${DB_HOST}:${DB_PORT}/${DB_NAME}..."
  sleep 2
done
echo "PostgreSQL is ready!"

if [ "$RUN_MIGRATIONS" = "true" ]; then
  echo "Applying migrations..."
  alembic upgrade head

  # Lexicon terms (principal_type, capability, ...) are seeded from
  # core/lexicon.json separately from the migration that adds the tables
  # referencing them -- see alembic/versions/79a3ab24627e_add_access_control_tables.py.
  # Idempotent (on_conflict_do_nothing), safe to run on every start.
  echo "Seeding lexicon..."
  oco initialize-lexicon
fi

echo "Starting the application..."
if [ "$UVICORN_RELOAD" = "true" ]; then
  uvicorn "$APP_MODULE" --host 0.0.0.0 --port "$APP_PORT" --reload
else
  uvicorn "$APP_MODULE" --host 0.0.0.0 --port "$APP_PORT"
fi
