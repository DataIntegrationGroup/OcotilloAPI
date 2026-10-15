# NMSampleLocations aka OcotilloAPI

[![Code Format](https://github.com/DataIntegrationGroup/NMSampleLocations/actions/workflows/format_code.yml/badge.svg)](https://github.com/DataIntegrationGroup/NMSampleLocations/actions/workflows/format_code.yml)
[![Dependabot Updates](https://github.com/DataIntegrationGroup/NMSampleLocations/actions/workflows/dependabot/dependabot-updates/badge.svg)](https://github.com/DataIntegrationGroup/NMSampleLocations/actions/workflows/dependabot/dependabot-updates)
[![Sentry Release](https://github.com/DataIntegrationGroup/NMSampleLocations/actions/workflows/release.yml/badge.svg)](https://github.com/DataIntegrationGroup/NMSampleLocations/actions/workflows/release.yml)
[![Tests](https://github.com/DataIntegrationGroup/NMSampleLocations/actions/workflows/tests.yml/badge.svg)](https://github.com/DataIntegrationGroup/NMSampleLocations/actions/workflows/tests.yml)

**Geospatial Sample Data Management System**  
_New Mexico Bureau of Geology and Mineral Resources_

OcotilloAPI is a FastAPI-based backend service designed to manage geospatial sample location data across New Mexico. It 
supports research, field operations, and public data delivery for the Bureau of Geology and Mineral Resources.

---

## 🚀 Features

- 🌐 RESTful API for managing sample location data
- 🗺️ Native GeoJSON support via PostGIS
- 🔎 Filtering by location, date, type, and more  
  Refine-powered list pages send JSON filters via repeated `filter=` query params. Virtual fields (`contacts` on things, `things` on contacts) implement association search in SQL. Background and rationale: [docs/refine-json-filters-and-virtual-fields.md](docs/refine-json-filters-and-virtual-fields.md).
- 📦 PostgreSQL + PostGIS database backend
- 🔐 Optional authentication and role-based access
- 🧾 Interactive API documentation via OpenAPI and ReDoc
- 🗺️ OGC API - Features endpoints and documentation via OpenAPI and ReDoc

---

## 🗺️ OGC API - Features

The API exposes OGC API - Features endpoints under `/ogcapi` for publicly available data
and `/ogcapi-internal` for both public and privata data using `pygeoapi`.
In App Engine deployments, `/ogcapi` and `/ogcapi-internal` are served from the same
application as the primary API. The services are intended to scale to zero
outside business hours and be kept warm during the workday with Cloud Scheduler
hits to `/_ah/warmup`. Access to `/ogcapi-internal` requires api keys, which are available 
through the Data Services team.

### Landing & metadata

```bash
curl http://localhost:8000/ogcapi
curl http://localhost:8000/ogcapi/conformance
curl http://localhost:8000/ogcapi/collections
curl http://localhost:8000/ogcapi/collections/water_wells
```

### Items (GeoJSON)

```bash
curl "http://localhost:8000/ogcapi/collections/water_wells/items?limit=10&offset=0"
curl "http://localhost:8000/ogcapi/collections/springs/items?limit=5"
curl "http://localhost:8000/ogcapi/collections/water_wells/items/123"
```

### BBOX + datetime filters

```bash
curl "http://localhost:8000/ogcapi/collections/water_wells/items?bbox=-107.9,33.8,-107.8,33.9"
curl "http://localhost:8000/ogcapi/collections/water_wells/items?datetime=2020-01-01/2024-01-01"
```

### Polygon filter (CQL2 text)

Use `filter` + `filter-lang=cql2-text` with `WITHIN(...)`:

```bash
curl "http://localhost:8000/ogcapi/collections/water_wells/items?filter=WITHIN(geometry,POLYGON((-107.9 33.8,-107.8 33.8,-107.8 33.9,-107.9 33.9,-107.9 33.8)))&filter-lang=cql2-text"
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
* PostgreSQL uses the default port 5432.

Minimum vars to set in `.env` for local development:
* `POSTGRES_USER`
* `POSTGRES_PASSWORD`
* `POSTGRES_DB` (`ocotilloapi_dev` when using Docker Compose dev)
* `POSTGRES_HOST` (`localhost` for local psql/pytest against mapped Docker port)
* `POSTGRES_PORT` (`5432`)
* `MODE` (`development` recommended locally)

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

#### 5. Setup GCS credentials
Create file gcs_credentials.json in the root directory of the project, and obtain its contents from a teammate.

#### 6. Database and server

Choose one of the following:

**Option A: Local PostgreSQL + PostGIS**

From the root folder of the project...

```bash
# run database migrations
alembic upgrade head

# start development server
uvicorn main:app --reload
```

Notes:
* Requires PostgreSQL with PostGIS installed locally.
* Use the `POSTGRES_*` settings in `.env` for your local instance.

**Option B: Docker Compose (dev)**

From the root folder of the project...

```bash
# include -d flag for silent/detached build
docker compose up --build
```

Notes:
* Requires Docker Desktop.
* By default, spins up two containers:
  * `db` for PostGIS/PostgreSQL
  * `app` for the primary API and OGC API on `http://localhost:8000`
* `db` initializes both application databases in the same Postgres service:
  * `ocotilloapi_dev`
  * `ocotilloapi_test`
* `alembic upgrade head` runs in the `app` container on startup.
* Compose uses hardcoded DB names:
  * dev: `ocotilloapi_dev`
  * test: `ocotilloapi_test` (created by init SQL in `docker/db/init/01-create-test-db.sql`)
* The database listens on port `5432` both inside the container and on your host. Ensure `POSTGRES_PORT=5432` and `POSTGRES_DB=ocotilloapi_dev` in your `.env` to run local commands against the Docker dev DB (e.g., `uv run pytest`, `uv run python -m transfers.transfer`).
* To restore a local or GCS-backed SQL dump into your local target DB, run `source .venv/bin/activate && python -m cli.cli restore-local-db path/to/dump.sql` or `source .venv/bin/activate && python -m cli.cli restore-local-db gs://ocotillo/sql-exports/latest.sql.gz`.

#### Staging Data

To get staging data into the database run `uv run python -m transfers.transfer` from the root directory of the project.
This data can be used for a variety of development purposes, such as OcotilloIU or to test data ingestion.

Configure the `.env` file with the appropriate credentials before running transfers.

If contact transfers fail with `OwnerKey normalization collisions`, add or update
`transfers/data/owners_ownerkey_mapper.json` to map inconsistent `OwnerKey` values
to a single canonical spelling before re-running the transfer.

To drop the existing schema and rebuild from migrations before transferring data, run:

```bash
export DROP_AND_REBUILD_DB=true
```

or set `DROP_AND_REBUILD_DB=true` in `.env`.

### 🧭 Project Structure
```text
app/

├── .dockerignore           # Files and directories for Docker to ignore
├── .env                    # Environment variables
├── .gitignore              # Files and directories for git to ignore
├── .gcloudignore           # Files and directories for Google Cloud to ignore
├── .pre-commit-config.yaml # pre-commit hook configuration file
├── .release-please-manifest.json # Contains the current version. Do not updated by hand
├── ADR{n}.md               # Documents containing architectual decision records
├── docker-compose.yml      # Docker compose file to build database and start server
├── entrypoint.sh           # Used by Docker to run database migrations and start server
├── main.py                 # FastAPI entry point
|
├── alembic/                # Alembic configuration and migration scripts
├── api/                    # Custom route declarations
├── cli/                    # Custom-built CLI for interacting with the API and DB, such as data ingestion protocols
├── core/                   # Settings, application config, ogc api config, constants, and dependencies
├── data_migrations         # Used to migrate data from one form to another. For data that already exists in DB, not for transferring data to the DB
├── db/                     # Database models, sessions, and engine
├── docker/                 # Custom Docker files
├── docs/                   # Documentation about the app, such as decisions made and how things work
├── schemas/                # Pydantic schemas and validations
├── scripts/                # Unique scripts for unique tasks. They do not comprise part of the API
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

The `oco` command exposes project automation, database utilities, and data ingestion utilities.
There are different commands (entry points), each of which has multiple sub-commands.

```bash
# Display available commands, some of which have or require sub-commands 
oco --help

# Display available sub-commands
oco {command} --help
```

## 🧪 Testing

```bash
# Run unit tests
uv run pytest

# Run Behave BDD specs
uv run behave tests/features
```

> Tests require a local Postgres/PostGIS instance. Set `POSTGRES_*` values in `.env`, run migrations, and ensure the database is reachable before running the suites.
