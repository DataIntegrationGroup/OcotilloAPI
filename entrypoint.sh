#!/bin/sh
# Wait for PostgreSQL to be ready
until PGPASSWORD="$POSTGRES_PASSWORD" pg_isready -h db -p 5432 -U "$POSTGRES_USER"; do
  echo "Waiting for postgres..."
  sleep 2
done
echo "PostgreSQL is ready!"

echo "Applying migrations..."
alembic upgrade head
echo "Starting the application..."
uvicorn main:app --host 0.0.0.0 --port 8000