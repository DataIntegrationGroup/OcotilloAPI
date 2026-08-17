# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

OcotilloAPI (also known as NMSampleLocations) is a FastAPI-based geospatial sample data management system for the New Mexico Bureau of Geology and Mineral Resources. It uses PostgreSQL with PostGIS for storing and querying spatial data related to sample locations, field observations, water chemistry, and more.

This project is **migrating data from the legacy AMPAPI system** (SQL Server, NM_Aquifer schema) to a new PostgreSQL + PostGIS stack. Transfer scripts in `transfers/` handle data conversion from legacy tables.

## Key Commands

### Environment Setup
```bash
# Install dependencies (requires uv package manager)
uv venv
source .venv/bin/activate  # On Mac/Linux
uv sync --locked

# Setup pre-commit hooks
pre-commit install

# Configure environment
cp .env.example .env
# Edit .env with database credentials
```

### Database Operations
```bash
# Run migrations
alembic upgrade head

# Create a new migration
alembic revision --autogenerate -m "description"

# Rollback one migration
alembic downgrade -1
```

### Development Server
```bash
# Local development (requires PostgreSQL + PostGIS installed)
uvicorn main:app --reload

# Docker (includes database)
docker compose up --build
```

### Testing
```bash
# Run all tests
uv run pytest

# Run specific test file
uv run pytest tests/test_sample.py

# Run specific test function
uv run pytest tests/test_sample.py::test_add_sample

# Run with coverage
uv run pytest --cov

# Set up test database (PostgreSQL with PostGIS required)
createdb -h localhost -U <user> ocotilloapi_test
psql -h localhost -U <user> -d ocotilloapi_test -c "CREATE EXTENSION IF NOT EXISTS postgis;"
```

**Test Database**: Tests automatically use `ocotilloapi_test` database. The test framework sets `POSTGRES_DB=ocotilloapi_test` in `tests/__init__.py` before importing the database engine.

**Environment Variables**: Tests read from `.env` file but override the database name:
```bash
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=<username>
POSTGRES_PASSWORD=<password>
# POSTGRES_DB in .env is ignored during tests - always uses ocotilloapi_test
```

### Data Migration
```bash
# Transfer data from legacy AMPAPI (NM_Aquifer) to new schema
python -m transfers.transfer
```

## Architecture

### Data Model Hierarchy

The system follows a hierarchical structure for field data collection:

```
Location (geographic point)
  └── Thing (monitoring point at location: well, spring, etc.)
      └── FieldEvent (visit to a thing on a date)
          └── FieldActivity (specific activity during event: water level, chemistry, etc.)
              └── Sample (physical sample collected during activity)
                  └── Observation (measurement/result from sample: pH, groundwater level, etc.)
```

**Key Relationships:**
- Each level inherits context from parent (location → thing → event → activity → sample → observation)
- `Thing` has geometry (PostGIS Point, WGS84/SRID 4326) and attributes (depth, construction details)
- `FieldEvent` links participants (contacts) to field visits
- `Sample` can have depth intervals (`depth_top`, `depth_bottom`) and QC types
- `Observation` links to `Parameter` (from lexicon) and stores value/units

### Directory Structure

```
├── alembic/              # Database migrations
├── api/                  # Route handlers (one file per resource)
├── cli/                  # Ocotillo CLI commands (oco)
├── core/                 # Application configuration
│   ├── app.py            # FastAPI app initialization
│   ├── dependencies.py   # Dependency injection (auth, DB session)
│   └── permissions.py    # Authentication/authorization logic
├── db/                   # SQLAlchemy models (one file per table/resource)
│   ├── engine.py         # Database connection configuration
│   └── ...
├── domain/               # Business rules as plain functions (no DB, no HTTP)
├── schemas/              # Pydantic schemas (validation, serialization)
├── services/             # Orchestration: load, call domain rules, persist
├── tests/                # Pytest test suite
│   ├── conftest.py       # Shared fixtures (test data setup)
│   └── __init__.py       # Sets test database (ocotilloapi_test)
├── transfers/            # Data migration scripts from AMPAPI (SQL Server)
│   ├── transfer.py       # Main transfer orchestrator
│   ├── well_transfer.py  # Well/thing data migration
│   └── ...
└── main.py               # Application entry point
```

### Domain Rules

`domain/` holds business rules as plain functions over plain values -- unit
conversion, cross-column validation, deterministic naming. Modules there import
nothing from `api/`, `db/`, `schemas/`, or `services/`, and no `fastapi`,
`sqlalchemy`, `pydantic`, or `httpx`, so the rules are testable without a
database.

`services/` loads the data, calls the rule, and persists the result. Domain
errors subclass `ValueError` because the CSV importers treat a `ValueError`
raised on a row as a per-row validation failure.

Extraction is opportunistic, not a migration: move a rule into `domain/` when
you are already editing it and it is shared, subtle, or awkward to test in
place. Read **`ADR4.md`** before extending the layer.

### Authentication & Authorization

The system uses **Authentik** for OAuth2 authentication with role-based access control:

**Permission Levels** (defined in `core/dependencies.py`):
- **Viewer**: Read-only access to all public entities
- **Editor**: Can modify existing records (includes Viewer permissions)
- **Admin**: Can create new records (includes Editor + Viewer permissions)

The hierarchy is enforced in code, via `authenticated(any_of=[...])` group lists —
`Admin` satisfies an editor- or viewer-gated route without needing all three
Authentik groups granted.

**AMP-Specific Roles**: `AMPAdmin`, `AMPEditor`, `AMPViewer` for legacy AMPAPI integration

**Role families are orthogonal**: general `Admin` confers nothing in the AMP or
Lexicon families. Only tiers *within* a family nest.

**Authorization is opt-in per endpoint** — a `user: <role>_dependency` parameter
in the signature, not a router-level `dependencies=[...]`. Omitting it produces a
fully public endpoint with no error. `tests/test_authorization.py` holds the
allowlist of intentionally anonymous routes and fails on anything else. Note the
annotation must be a *type annotation* (`user: viewer_dependency`), never a
default value (`user=viewer_dependency`) — the latter silently disables the
dependency and FastAPI treats it as a query parameter.

**Development bypass**: `AUTHENTIK_DISABLE_AUTHENTICATION=1` is honored only when
`MODE=development`. Any other `MODE` (including unset) makes
`assert_auth_configuration()` abort startup.

**`@in_public_schema`** (`core/app.py`) controls anonymous OpenAPI visibility
only — it grants no access and removes no dependency. Apply it only to routes
that genuinely have none.

### Database Configuration

The application supports two database modes (configured via `DB_DRIVER` in `.env`):

1. **Google Cloud SQL** (`DB_DRIVER=cloudsql`): Uses Cloud SQL Python Connector
2. **Standard PostgreSQL** (default): Direct pg8000/asyncpg connection

**Connection String Format** (standard mode):
```
postgresql+pg8000://{user}:{password}@{host}:{port}/{database}
```

**Important**: `db/engine.py` uses `load_dotenv(override=False)` so that environment variables set before import (e.g., by the test framework) are preserved.

### Spatial Data

- **Coordinate System**: WGS84 (SRID 4326) for all geometries
- **Geometry Types**: PostGIS `Point` for thing locations
- **Legacy Migration**: Transfer scripts convert from UTM (SRID 26913) to WGS84
- **GeoAlchemy2**: Used for SQLAlchemy ↔ PostGIS integration

### Refine UI list filters

Ocotillo UI passes DataGrid filters as repeated query parameters named `filter`, each containing JSON `{ "field", "operator", "value" }`. Association-backed columns (`contacts` on wells, `things` on contacts) are **virtual**: they map to EXISTS subqueries in `services/query_helper.py`, not to `ILIKE` on an ORM proxy.

Sorting the wells list by **Monitoring status** or **Well status** uses SQL subqueries on `StatusHistory`, not Python `@property` accessors, because `ORDER BY` must see database expressions.

Read **`docs/refine-json-filters-and-virtual-fields.md`** before changing filter behavior or adding virtual fields.

### Error Handling

All custom exceptions should use `PydanticStyleException` for consistent API error responses:

```python
from services.exceptions_helper import PydanticStyleException

raise PydanticStyleException(
    status_code=409,
    detail=[{
        "loc": ["body", "sample_name"],
        "msg": "Sample with sample_name X already exists.",
        "type": "value_error",
        "input": {"sample_name": "X"}
    }]
)
```

**Validation Strategy**:
- **422 errors**: Pydantic validation on incoming request data (automatic)
- **409 errors**: Database constraint violations (manual checks in endpoints)

## Model Change Workflow

When modifying data models:

1. **Update DB Model**: Revise model in `db/` directory
2. **Update Schemas**: Revise Pydantic schemas in `schemas/`
   - Add field validators using `@field_validator` or `@model_validator`
   - Input validation (422 errors) → Pydantic validators
   - Database validation (409 errors) → Manual checks in endpoint
3. **Create Migration**: `alembic revision --autogenerate -m "description"`
4. **Update Tests**:
   - Update fixtures in `tests/conftest.py`
   - Update POST test payloads and assertions
   - Update PATCH test payloads and assertions
   - Update GET test assertions
   - Add validation tests if needed
5. **Update Transfer Scripts**: Revise field mappings in `transfers/` (if migrating legacy data)

**Schema Conventions**:
- `Create` schemas: `<type>` for non-nullable, `<type> | None = None` for nullable
- `Update` schemas: All fields optional with `None` defaults
- `Response` schemas: `<type>` for non-nullable, `<type> | None` for nullable

## Testing Notes

- **Test Database**: Uses `ocotilloapi_test` (set automatically by `tests/__init__.py`)
- **Test Client**: `TestClient` from FastAPI (`tests/__init__.py`)
- **Authentication Override**: Tests bypass Authentik auth using `override_authentication()` fixture
- **Fixtures**: Session-scoped fixtures in `conftest.py` create test data
- **Cleanup Helpers**:
  - `cleanup_post_test(model, id)`: Delete records created by POST tests
  - `cleanup_patch_test(model, payload, original_data)`: Rollback PATCH test changes

## CI/CD

GitHub Actions workflows (`.github/workflows/`):
- **tests.yml**: Runs pytest with PostGIS Docker service container
- **format_code.yml**: Code formatting checks
- **release.yml**: Sentry release tracking

## Legacy System Migration

**Source**: AMPAPI (SQL Server, `NM_Aquifer` schema)
**Target**: OcotilloAPI (PostgreSQL + PostGIS)

**Transfer Scripts** (`transfers/`):
- `well_transfer.py`: Migrates well/thing data with coordinate transformation
- `waterlevels_transfer.py`: Migrates groundwater level observations
- `contact_transfer.py`: Migrates contact records
- `link_ids_transfer.py`: Migrates legacy ID mappings

## Additional Resources

- **API Docs**: `http://localhost:8000/docs` (Swagger UI) or `/redoc` (ReDoc)
- **OGC API**: `http://localhost:8000/ogcapi` for OGC API - Features endpoints
- **CLI**: `oco --help` for Ocotillo CLI commands
- **Sentry**: Error tracking and performance monitoring integrated
