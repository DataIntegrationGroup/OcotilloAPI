#!/bin/sh
# Wait for PostgreSQL to be ready
until PGPASSWORD="$POSTGRES_PASSWORD" pg_isready -h db -p 5432 -U "$POSTGRES_USER"; do
  echo "Waiting for postgres..."
  sleep 2
done
echo "PostgreSQL is ready!"

echo "Ensuring base tables exist..."
python - <<'PY'
from sqlalchemy import inspect, text

from db import Base
from db.engine import engine

with engine.begin() as conn:
    conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))

inspector = inspect(engine)
if "location" not in inspector.get_table_names():
    Base.metadata.create_all(bind=engine)
PY

echo "This Docker Instance does not apply migrations..."
echo "Starting the application..."
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
