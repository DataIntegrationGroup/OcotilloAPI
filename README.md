# NMSampleLocations aka OcotilloAPI

[![Code Format](https://github.com/DataIntegrationGroup/NMSampleLocations/actions/workflows/format_code.yml/badge.svg)](https://github.com/DataIntegrationGroup/NMSampleLocations/actions/workflows/format_code.yml)
[![Dependabot Updates](https://github.com/DataIntegrationGroup/NMSampleLocations/actions/workflows/dependabot/dependabot-updates/badge.svg)](https://github.com/DataIntegrationGroup/NMSampleLocations/actions/workflows/dependabot/dependabot-updates)
[![Sentry Release](https://github.com/DataIntegrationGroup/NMSampleLocations/actions/workflows/release.yml/badge.svg)](https://github.com/DataIntegrationGroup/NMSampleLocations/actions/workflows/release.yml)
[![Tests](https://github.com/DataIntegrationGroup/NMSampleLocations/actions/workflows/tests.yml/badge.svg)](https://github.com/DataIntegrationGroup/NMSampleLocations/actions/workflows/tests.yml)
[![codecov](https://codecov.io/gh/DataIntegrationGroup/NMSampleLocations/graph/badge.svg?token=Y20QB357OO)](https://codecov.io/gh/DataIntegrationGroup/NMSampleLocations)

**Geospatial Sample Data Management System**  
_New Mexico Bureau of Geology and Mineral Resources_

OcotilloAPI is a FastAPI-based backend service designed to manage geospatial sample location data across New Mexico. It 
supports research, field operations, and public data delivery for the Bureau of Geology and Mineral Resources.

---

## 🚀 Features

- 🌐 RESTful API for managing sample location data
- 🗺️ Native GeoJSON support via PostGIS
- 🔎 Filtering by location, date, type, and more
- 📦 PostgreSQL + PostGIS database backend
- 🔐 Optional authentication and role-based access
- 🧾 Interactive API documentation via OpenAPI and ReDoc

---

## 🗺️ OGC API - Features

The API exposes OGC API - Features endpoints under `/ogcapi` using `pygeoapi`.

### Landing & metadata

```bash
curl http://localhost:8000/ogcapi
curl http://localhost:8000/ogcapi/conformance
curl http://localhost:8000/ogcapi/collections
curl http://localhost:8000/ogcapi/collections/locations
```

### Items (GeoJSON)

```bash
curl "http://localhost:8000/ogcapi/collections/locations/items?limit=10&offset=0"
curl "http://localhost:8000/ogcapi/collections/wells/items?limit=5"
curl "http://localhost:8000/ogcapi/collections/springs/items?limit=5"
curl "http://localhost:8000/ogcapi/collections/locations/items/123"
```

### BBOX + datetime filters

```bash
curl "http://localhost:8000/ogcapi/collections/locations/items?bbox=-107.9,33.8,-107.8,33.9"
curl "http://localhost:8000/ogcapi/collections/wells/items?datetime=2020-01-01/2024-01-01"
```

### Polygon filter (CQL2 text)

Use `filter` + `filter-lang=cql2-text` with `WITHIN(...)`:

```bash
curl "http://localhost:8000/ogcapi/collections/locations/items?filter=WITHIN(geometry,POLYGON((-107.9 33.8,-107.8 33.8,-107.8 33.9,-107.9 33.9,-107.9 33.8)))&filter-lang=cql2-text"
```

### OpenAPI UI

```bash
curl "http://localhost:8000/ogcapi/openapi?ui=swagger"
```
    

---

## 🛠️ Getting Started

### Prerequisites

- Python 3.11+
- [`uv`](https://github.com/astral-sh/uv) package manager
- Docker Desktop 4+ if wanting to host server/database locally with containers
- PostgreSQL with PostGIS extension if wanting to host server/database locally without containers

### Installation & Setup

#### 1. Clone the repository

```bash
git clone https://github.com/DataIntegrationGroup/OcotilloAPI.git
cd OcotilloAPI
```

#### 2. Set up virtual environment and install dependencies


<table>
<tr>
<td>
    Mac/Linux 
</td>
<td>
    Windows
</td>
</tr>
<tr>
<td>

```bash
uv venv
source .venv/bin/activate
uv sync --locked
```
    
</td>
<td>

```bash
uv venv
source .venv/Scripts/activate
uv sync --locked
```

</td>
</tr>
</table>


#### 3. Setup pre-commit hookes

```bash
pre-commit install
```

#### 4. Setup environment variables

```bash
# Edit `.env` to configure database connection and app settings
cp .env.example .env
```
Notes:
* Create file gcs_credentials.json in the root directory of the project, and obtain its contents from a teammate.
* PostgreSQL uses the default port 5432.

Minimum vars to set in `.env` for local development:
* `POSTGRES_USER`
* `POSTGRES_PASSWORD`
* `POSTGRES_DB` (`ocotilloapi_dev` when using Docker Compose dev)
* `POSTGRES_HOST` (`localhost` for local psql/pytest against mapped Docker port)
* `POSTGRES_PORT` (`5432`)
* `MODE` (`development` recommended locally)
* `SESSION_SECRET_KEY`

Auth-related vars (required when auth is enabled, optional when `AUTHENTIK_DISABLE_AUTHENTICATION=1`):
* `AUTHENTIK_DISABLE_AUTHENTICATION`
* `AUTHENTIK_URL`
* `AUTHENTIK_CLIENT_ID`
* `AUTHENTIK_AUTHORIZE_URL`
* `AUTHENTIK_TOKEN_URL`

pygeoapi vars:
* `PYGEOAPI_MOUNT_PATH` (default `/ogcapi`)
* `PYGEOAPI_RUNTIME_DIR` (default `/tmp/pygeoapi`)
* `PYGEOAPI_POSTGRES_HOST`
* `PYGEOAPI_POSTGRES_PORT`
* `PYGEOAPI_POSTGRES_DB`
* `PYGEOAPI_POSTGRES_USER`
* `PYGEOAPI_POSTGRES_PASSWORD`

Optional telemetry vars:
* `SENTRY_DSN`
* `APITALLY_CLIENT_ID`
* `ENVIRONMENT`

In development set `MODE=development` to allow lexicon enums to be populated. When `MODE=development`, the app attempts to seed the database with 10 example records via `transfers/seed.py`; if a `contact` record already exists, the seed step is skipped.

#### 5. Database and server

Choose one of the following:

**Option A: Local PostgreSQL + PostGIS**

```bash
# run database migrations
alembic upgrade head

# start development server
uvicorn app.main:app --reload
```

Notes:
* Requires PostgreSQL with PostGIS installed locally.
* Use the `POSTGRES_*` settings in `.env` for your local instance.

**Option B: Docker Compose (dev)**

```bash
# include -d flag for silent/detached build
docker compose up --build
```

Notes:
* Requires Docker Desktop.
* By default, spins up two containers: `db` (PostGIS/PostgreSQL) and `app` (FastAPI API service).
* `db` initializes both application databases in the same Postgres service:
  * `ocotilloapi_dev`
  * `ocotilloapi_test`
* `alembic upgrade head` runs on app startup after `docker compose up`.
* Compose uses hardcoded DB names:
  * dev: `ocotilloapi_dev`
  * test: `ocotilloapi_test` (created by init SQL in `docker/db/init/01-create-test-db.sql`)
* The database listens on port `5432` both inside the container and on your host. Ensure `POSTGRES_PORT=5432` and `POSTGRES_DB=ocotilloapi_dev` in your `.env` to run local commands against the Docker dev DB (e.g., `uv run pytest`, `uv run python -m transfers.transfer`).

#### Staging Data

To get staging data into the database: `python -m transfers.transfer` from the root directory of the project.

### 🧭 Project Structure
```text
app/
├── .env                    # Environment variables
├── .pre-commit-config.yaml # pre-commit hook configuration file
├── constants.py            # Static variables used throughout the code
├── docker-compose.yml      # Docker compose file to build database and start server
├── entrypoint.sh           # Used by Docker to run database migrations and start server
├── main.py                 # FastAPI entry point
|
├── alembic/                # Alembic configuration and migration scripts
├── api/                    # Route declarations
├── core/                   # Settings, application config, and dependencies
├── db/                     # Database models, sessions, and engine
├── docker/                 # Custom Docker files
├── schemas/                # Pydantic schemas and validations
├── services/               # Reusable business logic, helpers, and database interactions
├── tests/                  # Code tests
└── transfers/              # Scripts to transfer data from NM_Aquifer to current db schema
```

## Model Changes

1. Revise models in the `db/` directory
2. Revise schemas in the `schemas/` directory
    1. Add validators for both fields and models as necessary
      1. Validations on incoming data only should be handled by Pydantic and 422 errors will be raised (default Pydantic)
      2. Validations against values in the database will be handled at the endpoint with custom checks and 409 errors will be raised
3. Revise tests
    1. Revise fixtures in `tests/conftest.py`
    2. Revise fields in POST test payloads and asserts
    3. Revise fields in PATCH test payloads and asserts
    4. Revise fields in GET all and GET by ID test asserts
    5. Add tests for validations as necessary

Bonus:
- Update transfer scripts by revising fields and delineating where they come from in `NM_Aquifer`

Notes:
- All `Create` schema fields are defined as `<type>` if non-nullable and `<type> | None = None` if nullable
- All `Update` schema fields are optional and default to `None`
- All `Response` schema fields are defined as `<type>` if non-nullable and `<type> | None` if nullable
- All raised exceptions should use the `PydanticStyleException` as defined in `services/exceptions_helper.py`
- Errors handled by the database should be enumerated and handled in a database_error_handler in each router's file---

## 📦 Ocotillo CLI

The `oco` command exposes project automation and bulk data utilities.

```bash
# Display available commands
oco --help

# Bulk import water level data from a CSV
oco water-levels bulk-upload --file water_levels.csv --output json
```

The bulk upload command parses and validates each row, creates the corresponding field events/samples/observations, and prints a JSON summary (matching the API response shape) so the workflow can be automated or scripted.
## 🧪 Testing

```bash
# Run unit tests
pytest

# Run Behave BDD specs
behave tests/features
```

> Tests require a local Postgres/PostGIS instance. Set `POSTGRES_*` values in `.env`, run migrations, and ensure the database is reachable before running the suites.

## 🔄 Data Transfers

Legacy or staging datasets can be imported using the transfer utilities:

```bash
python -m transfers.transfer
```

Configure the `.env` file with the appropriate credentials before running transfers.

If contact transfers fail with `OwnerKey normalization collisions`, add or update
`transfers/data/owners_ownerkey_mapper.json` to map inconsistent `OwnerKey` values
to a single canonical spelling before re-running the transfer.

To drop the existing schema and rebuild from migrations before transferring data, set:

```bash
export DROP_AND_REBUILD_DB=true
```
