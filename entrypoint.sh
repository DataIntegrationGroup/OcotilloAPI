#!/bin/sh
# Wait for PostgreSQL to be ready (only in local docker-compose environment)
# Skip this check if POSTGRES_HOST is not "db" (e.g., on Render)
if [ "${POSTGRES_HOST:-db}" = "db" ]; then
  echo "Checking local PostgreSQL readiness..."
  until PGPASSWORD="$POSTGRES_PASSWORD" pg_isready -h db -p 5432 -U "$POSTGRES_USER"; do
    echo "Waiting for postgres..."
    sleep 2
  done
  echo "PostgreSQL is ready!"
fi

echo "Applying migrations..."
alembic upgrade head

echo "Starting the application..."
# Use PORT environment variable (Render provides this), default to 8000
PORT=${PORT:-8000}
echo "Starting server on port $PORT"

# Production server: gunicorn with uvicorn workers
# Use --reload only if RELOAD_ENABLED=true (for local development)
if [ "${RELOAD_ENABLED:-false}" = "true" ]; then
  echo "Running in development mode with auto-reload"
  uvicorn main:app --host 0.0.0.0 --port "$PORT" --reload
else
  echo "Running in production mode with gunicorn"
  gunicorn main:app --workers 4 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:"$PORT"
fi