# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

NMSampleLocations is a FastAPI-based geospatial sample data management system for the New Mexico Bureau of Geology and Mineral Resources. It uses PostgreSQL with PostGIS for storing and querying spatial data related to sample locations, field observations, water chemistry, geochronology, and more.

This project is **migrating data from the legacy AMPAPI system** (SQL Server, NM_Aquifer schema) to a new PostgreSQL + PostGIS stack. The migration is ~50-60% complete, with transfer scripts in `transfers/` handling data conversion from legacy tables.

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
docker exec -it nmsamplelocations-app-1 bash  # Access app container
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
createdb -h localhost -U <user> nmsamplelocations_test
psql -h localhost -U <user> -d nmsamplelocations_test -c "CREATE EXTENSION IF NOT EXISTS postgis;"
```

**Test Environment Variables**: Tests read from `.env` file. Ensure these are set:
```bash
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=<username>
POSTGRES_PASSWORD=<password>
POSTGRES_DB=nmsamplelocations_test
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
│   ├── sample.py         # CRUD endpoints for samples
│   ├── observation.py    # Endpoints for field observations
│   └── ...
├── core/                 # Application configuration
│   ├── app.py            # FastAPI app initialization
│   ├── dependencies.py   # Dependency injection (auth, DB session)
│   └── permissions.py    # Authentication/authorization logic
├── db/                   # SQLAlchemy models (one file per table/resource)
│   ├── engine.py         # Database connection configuration
│   ├── sample.py         # Sample model
│   ├── observation.py    # Observation model
│   └── ...
├── schemas/              # Pydantic schemas (validation, serialization)
│   ├── sample.py         # Sample Create/Update/Response schemas
│   └── ...
├── services/             # Business logic and database interactions
│   ├── exceptions_helper.py  # PydanticStyleException for consistent error formatting
│   └── ...
├── tests/                # Pytest test suite
│   ├── conftest.py       # Shared fixtures (test data setup)
│   ├── test_sample.py    # Sample CRUD tests
│   └── ...
├── transfers/            # Data migration scripts from AMPAPI (SQL Server)
│   ├── transfer.py       # Main transfer orchestrator
│   ├── well_transfer.py  # Well/thing data migration
│   └── ...
└── main.py               # Application entry point
```

### Authentication & Authorization

The system uses **Authentik** for OAuth2 authentication with role-based access control:

**Permission Levels** (defined in `core/dependencies.py`):
- **Viewer**: Read-only access to all public entities
- **Editor**: Can modify existing records (includes Viewer permissions)
- **Admin**: Can create new records (includes Editor + Viewer permissions)

**AMP-Specific Roles**: `AMPAdmin`, `AMPEditor`, `AMPViewer` for legacy AMPAPI integration

**Dependency Injection**:
```python
from core.dependencies import admin_function, editor_function, viewer_function

@router.post("/sample", dependencies=[Depends(admin_function)])  # Admin required
@router.patch("/sample/{id}", dependencies=[Depends(editor_function)])  # Editor required
@router.get("/sample", dependencies=[Depends(viewer_function)])  # Viewer required
```

### Database Configuration

The application supports two database modes (configured via `DB_DRIVER` in `.env`):

1. **Google Cloud SQL** (`DB_DRIVER=cloud_sql`): Uses Cloud SQL Python Connector
2. **Standard PostgreSQL** (`DB_DRIVER=postgres`): Direct pg8000/asyncpg connection

**Connection String Format** (standard mode):
```
postgresql+pg8000://{user}:{password}@{host}:{port}/{database}
```

See `db/engine.py:108-116` for connection string construction.

### Spatial Data

- **Coordinate System**: WGS84 (SRID 4326) for all geometries
- **Geometry Types**: PostGIS `Point` for thing locations
- **Legacy Migration**: Transfer scripts convert from UTM (SRID 26913) to WGS84
- **GeoAlchemy2**: Used for SQLAlchemy ↔ PostGIS integration

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

When modifying data models (from README.md):

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

- **Test Database**: Requires separate PostgreSQL database with PostGIS extension
- **Test Client**: `TestClient` from FastAPI (`tests/__init__.py:30`)
- **Authentication Override**: Tests bypass Authentik auth using `override_authentication()` fixture
- **Fixtures**: Session-scoped fixtures in `conftest.py` create test data (locations, things, events, etc.)
- **Cleanup Helpers**:
  - `cleanup_post_test(model, id)`: Delete records created by POST tests
  - `cleanup_patch_test(model, payload, original_data)`: Rollback PATCH test changes

**Known Test Issues** (as of Oct 2025):
- Some tests have isolation issues due to session-scoped fixtures
- Foreign key cascade failures in sample deletion tests
- Date format inconsistencies in sample tests

## CI/CD

GitHub Actions workflows (`.github/workflows/`):
- **tests.yml**: Runs pytest with PostGIS Docker service container
- **format_code.yml**: Code formatting checks
- **release.yml**: Sentry release tracking

## Legacy System Migration

**Source**: AMPAPI (SQL Server, `NM_Aquifer` schema)
**Target**: NMSampleLocations (PostgreSQL + PostGIS)
**Progress**: ~50-60% complete

**Key Differences**:
- Geometry format: GeoJSON (legacy) → WKT (new)
- Auth: Fief OAuth2 (legacy) → Authentik (new)
- API versioning: URL path `/v0` (legacy) → Schema versioning (new)

**Transfer Scripts** (`transfers/`):
- `well_transfer.py`: Migrates well/thing data with coordinate transformation
- `waterlevels_transfer.py`: Migrates groundwater level observations
- `contact_transfer.py`: Migrates contact records
- `link_ids_transfer.py`: Migrates legacy ID mappings

## Additional Resources

- **API Docs**: `http://localhost:8000/docs` (Swagger UI) or `/redoc` (ReDoc)
- **Database Visualization**: Use PostGIS-compatible tools (QGIS, pgAdmin with PostGIS plugin)
- **Sentry**: Error tracking and performance monitoring integrated
