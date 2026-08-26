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
Both legacy transfer drivers are **deprecated** (see `transfers/README.md`); they
raise `DeprecationWarning` and take no new migrations, but stay runnable for
backfills.
```bash
# NM_Aquifer (AMPAPI) -> new schema. Deprecated.
python -m transfers.transfer

# NM_Wells (geothermal) Phase-1 staging mirror. Deprecated.
python -m transfers.transfer_geothermal
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

**`AMP.Staging`** is a standalone group, not a fourth AMP tier — `AMPAdmin`
does not satisfy it. It gates the hydrograph corrector's publish and range-delete
routes while the workbench is being validated against real logger files, so they
ship dark. Read **`docs/hydrograph-correction-publish.md`** before changing
them.

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

**`/ogcapi-internal` is gated outside `Depends()`.** It is a raw Starlette
Mount, so `core/internal_ogc_auth.py` gates it at the ASGI layer instead. It
accepts a bearer Authentik JWT carrying `OGCInternal`, **or** a static API key
presented as a bearer token, as the Basic password, or as `?token=`. Only the
key digests are stored, as `label:sha256hex` entries in `INTERNAL_OGC_API_KEYS`
— sourced in deployed environments from the Secret Manager secret
`internal-ogc-api-keys` at deploy time, so revoking a key needs a redeploy.
Never a GitHub secret. The static keys exist because
ArcGIS Pro cannot send a bearer token at all and neither desktop client can
refresh an Authentik token. Read **`docs/internal-ogc-desktop-gis.md`** before
changing the credential paths.

**`/ogcapi-internal` carries landowner PII.** The `water_well_field_operations`
collection publishes contact name, organization, role, phone and email for well
owners and operators, plus staff-written access notes. Every credential the
mount accepts reaches it, the static keys included. It is internal-only with
**no public twin** — `ogc_water_well_field_operations` does not exist and must
never be created. The layer also honours `end_date` when reading history
tables, unlike `ogc_actively_monitored_wells`, so "may we sample here" cannot
outlive the permission that granted it. Read
**`docs/water-well-field-operations-layer.md`** before changing it, and
**`docs/water-well-field-operations-columns.md`** for where each column comes
from.

### OGC field descriptions

Per-column `title`/`description`/unit for every collection lives in
`core/ogc-field-descriptions.yml`, keyed by backing relation, and is published
on `/schema` and `/queryables` through `core/feature_provider.py` and a wrapper
over pygeoapi's queryables handler. The feature leans on unpinned behaviour of
the pinned pygeoapi version — most sharply, `BaseProvider.fields` returns
`self._fields` and never calls `get_fields()`. Read
**`docs/ogc-field-descriptions.md`** before changing field metadata or
upgrading pygeoapi.

### Access control and release state

**`ADR5.md`** decides the shape of the access-control work: two grant tables
(internal permission vs landowner publication consent), one visibility layer,
one field-projection chokepoint.

The storage and the evaluator exist; the field projection does not.

- **`services/visibility.py` is the only evaluator.** `may()` answers internal
  authorization, `published_things()` answers "what does this destination
  get". It loads rows and calls `domain/access.py`, which holds the rules and
  touches no database. Do not filter by grant or consent anywhere else --
  migration `baba91fe5e83` is what distributed filtering already cost.
- **`api/access.py` (`/access`) is its only tenant.** Grants, destinations,
  consent, and a `/access/decision` introspection route. No pre-existing
  endpoint consults the layer yet, so release_status still governs what the
  OGC views publish. The prefix is `/access`, not `/publication`, because
  `api/publication.py` is the bibliography.
- **Fields are published by allowlist, per audience.**
  `core/field-allowlists.yml` says what each audience receives;
  `services/field_projection.py` applies it below the routes, so a new route
  cannot skip it. An audience with no entry gets an empty record, and the
  `never_public` block overrides every allowlist. Protection includes
  transformation -- public coordinates are rounded, not withheld. The public
  OGC collections go through it too: `core/feature_provider.py` turns each
  collection's allowlist into pygeoapi's `properties`, so an unlisted column
  is never selected, and a collection with no entry publishes nothing. The
  internal mount is outside it. Read
  **`docs/access-field-projection.md`** before touching the allowlists.
- **The role baseline is seeded by hand, per environment.**
  `oco seed-access-grants` writes one global grant per (Authentik role,
  capability, data type) so today's roles keep today's access; it previews by
  default and needs `--apply` to write. Idempotent, and it will not resurrect
  a seeded grant somebody revoked, because narrowing the baseline is the point.
  Until it is run in an environment, `/access/decision` denies everyone there.
- **Default deny, no wildcards, expiry at use.** A grant with no matching row
  is a no; a grant names its `data_type` (there is no term meaning "all"); and
  nothing sweeps expired rows, so every check compares against the date asked
  about. `services/access_admin.py` writes an `authorization_audit` row in the
  same transaction as every change.

Two vocabulary fixes from it have landed and matter when reading models:

- **`db/field_access_consent.py`** (`FieldAccessConsent`, table
  `field_access_consent`, formerly `PermissionHistory` / `permission_history`)
  is a landowner's consent to *physical site access*. It is not authorization.
  Its `permission_type` / `permission_allowed` columns keep their names, and
  Thing responses still publish it under the `permissions` key.
- **`ReleaseMixin` has two axes**: `release_status` is the release *level*
  (who may see it) and `data_maturity` is the review state (`provisional`,
  `in review`, `approved`, NULL = not stated). The `release_status` lexicon
  still lists `provisional` and `final` for historical rows; new code should
  put review state in `data_maturity`.

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

**Deprecated.** Both legacy drivers are frozen -- `transfers/transfer.py`
(NM_Aquifer/AMPAPI) and `transfers/transfer_geothermal.py` (NM_Wells, with
`nmw_mirror_transfer.py`, `nmw_sql_dump.py`, `export_nmw_csvs.py`). Entry points
raise `DeprecationWarning`. Do not add new migrations to either. They remain
runnable because live API routes still read the `NMA_*` and `NMW_*` tables.
Read **`transfers/README.md`** before touching this layer.

Their tests live in `tests/transfers/` and **do not gate CI** --
`.github/workflows/tests.yml` runs pytest with `--ignore=tests/transfers`, and
`transfers/*` is omitted from coverage in `pyproject.toml`. Run them by hand:
`uv run pytest tests/transfers`. Tests for the `NMA_*`/`NMW_*` ORM models
(`db/nma_legacy.py`, `db/nmw_legacy.py`) stay in `tests/` proper and still gate
CI, since live routes depend on those models.

Still live, *not* deprecated: `services/scoped_transfer.py` and the
`oco scoped-transfer` command, which import the individual NM_Aquifer
transferers directly.

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

## Working Guidelines

Behavioral guidelines to reduce common LLM coding mistakes. These bias toward
caution over speed; for trivial tasks, use judgment.

### 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

### 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

### 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

### 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" -> "Write tests for invalid inputs, then make them pass"
- "Fix the bug" -> "Write a test that reproduces it, then make it pass"
- "Refactor X" -> "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:

```
1. [Step] -> verify: [check]
2. [Step] -> verify: [check]
3. [Step] -> verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it
work") require constant clarification.

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer
rewrites due to overcomplication, and clarifying questions come before
implementation rather than after mistakes.
