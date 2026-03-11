#!/bin/sh
set -eu

DB_HOST="${POSTGRES_HOST:-db}"
DB_PORT="${POSTGRES_PORT:-5432}"
DB_NAME="${POSTGRES_DB:-postgres}"
APP_MODULE="${APP_MODULE:-main:app}"
APP_PORT="${APP_PORT:-8000}"
RUN_MIGRATIONS="${RUN_MIGRATIONS:-true}"

# Wait for PostgreSQL to be ready
until PGPASSWORD="$POSTGRES_PASSWORD" pg_isready -h "$DB_HOST" -p "$DB_PORT" -U "$POSTGRES_USER" -d "$DB_NAME"; do
  echo "Waiting for postgres at ${DB_HOST}:${DB_PORT}/${DB_NAME}..."
  sleep 2
done
echo "PostgreSQL is ready!"

if [ "$RUN_MIGRATIONS" = "true" ]; then
  echo "Applying migrations..."
  alembic upgrade head
fi

echo "Starting the application..."
uvicorn "$APP_MODULE" --host 0.0.0.0 --port "$APP_PORT" --reload
