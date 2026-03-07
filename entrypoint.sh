#!/bin/sh
set -eu

DB_HOST="${POSTGRES_HOST:-db}"
DB_PORT="${POSTGRES_PORT:-5432}"
DB_NAME="${POSTGRES_DB:-postgres}"

# Wait for PostgreSQL to be ready
until PGPASSWORD="$POSTGRES_PASSWORD" pg_isready -h "$DB_HOST" -p "$DB_PORT" -U "$POSTGRES_USER" -d "$DB_NAME"; do
  echo "Waiting for postgres at ${DB_HOST}:${DB_PORT}/${DB_NAME}..."
  sleep 2
done
echo "PostgreSQL is ready!"

echo "Applying migrations..."
alembic upgrade head
echo "Starting the application..."
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
