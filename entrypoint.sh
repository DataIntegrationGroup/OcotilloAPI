#!/bin/sh
# Wait for PostgreSQL to be ready
until PGPASSWORD="$POSTGRES_PASSWORD" pg_isready -h db -p 5432 -U "$POSTGRES_USER"; do
  echo "Waiting for postgres..."
  sleep 2
done
echo "PostgreSQL is ready!"

echo "Don't need to apply migrations to a blank DB"
echo "Starting the application... Seed data will be applied if MODE=development"
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
