# DB

This directory contains SQLAlchemy models, engine/session setup, and database initialization helpers.

## Key files

- `db/base.py`: shared ORM base mixins and common fields
- `db/engine.py`: engine/session configuration
- `db/initialization.py`: schema/bootstrap utilities

## Schema changes

- Use Alembic migrations under `alembic/versions/` for all DDL changes.
- Keep model nullability/defaults aligned with migrations.
- Prefer idempotent data migrations and safe re-runs.

## Local usage

```bash
source .venv/bin/activate
alembic upgrade head
```
