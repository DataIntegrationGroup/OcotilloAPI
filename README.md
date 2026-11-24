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

The API serves OGC API - Features endpoints through `pygeoapi` under two paths:

- `/ogcapi` serves publicly available data.
- `/ogcapi-internal` is for internal use only. It is not filtered by `release_status`, so it serves private and draft records as well, such as wells and observations. It also includes contact details (name, organization, role, phone, email) for well owners and operators.

Access to `/ogcapi-internal` requires an API key or an Authentik account in the `OGC.Internal` group. A Data Services team member can grant access to `OGC. Internal`. `OGC.Internal` members mint their own API keys through the `/api_key` endpoints; keys expire within 365 days. Treat a key as a credential for personal data. See [docs/api-key-management.md](docs/api-key-management.md) and [docs/internal-ogc-desktop-gis.md](docs/internal-ogc-desktop-gis.md) for details.

When the API runs in App Engine, both paths are part of the same application as the main API. The application is meant to shut down outside business hours and stay available during the workday. Cloud Scheduler keeps it awake by sending requests to `/_ah/warmup`.

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
uv sync --locked --all-extras --dev --group cli --group ingestion
```
    
</td>
<td>

```bash
uv venv
source .venv/Scripts/activate
uv sync --locked --all-extras --dev --group cli --group ingestion
```

</td>
</tr>
</table>

This is the same sync CI runs (`.github/workflows/tests.yml`). What each flag does:

* `--locked`: install exactly what `uv.lock` pins, and fail if the lockfile is
  out of date with `pyproject.toml`.
* `--group cli`: openpyxl, the Google API client, dlt, gcsfs and pyarrow, used by
  the `oco` chemistry ingest and Drive sync commands. Tests import these, so
  `uv run pytest` fails without them.
* `--group ingestion`: dagster plus the same dlt/gcsfs/pyarrow stack, for the
  Dagster+ code location in `automated_ingestion/`.
* `--dev`: pytest, behave, black, flake8, pre-commit. uv installs this group by
  default, so the flag is only there to make it explicit.
* `--all-extras`: does nothing today, because the project defines no
  `[project.optional-dependencies]`. It is kept to match CI.

`cli` and `ingestion` are separate groups because the API never imports them.
Keeping them out of `dependencies` keeps them out of the production requirements
export (`uv export --no-dev`) and the API image. `uv sync` also uninstalls
packages from groups you don't request, so a bare `uv sync --locked` removes
them again.


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
* `PYGEOAPI_POSTGRES_USER` (same as `POSTGRES_USER` for local development)
* `PYGEOAPI_POSTGRES_PASSWORD` (same as `POSTGRES_PASSWORD` for local development)

Optional telemetry vars:
* `SENTRY_DSN`
* `APITALLY_CLIENT_ID`
* `ENVIRONMENT`

In development set `MODE=development` to allow lexicon enums to be populated. When `MODE=development`, the app attempts to seed the database with 10 example records via `transfers/seed.py`; if a `contact` record already exists, the seed step is skipped.

#### 5. Setup GCS credentials
Create the file `gcs_credentials.json` in the root directory of the project and obtain its contents from a teammate. Set the
environment `GOOGLE_APPLICATION_CREDENTIALS` variable in `.env` to the absolute
path to `gcs_credentials.json`. Set it as the absolute path, not relative, since relative
only works when if the app is spun up from the project root directory. Docker sets its own path
so using an absolute path will not adversely effect the app if Docker is used.

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
This data can be used for a variety of development purposes, such as OcotilloIU or to test data ingestion. Note: `transfers/transfers.py`
is no longer maintained and kept only for staging data and backfills. See [transfers/README.md](./transfers/README.md) for more
information.

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
├── .release-please-manifest.json # Contains the current version. Do not update by hand
├── ADR{n}.md               # Documents containing architectural decision records
├── docker-compose.yml      # Docker compose file to build database and start server
├── entrypoint.sh           # Used by Docker to run database migrations and start server
├── main.py                 # FastAPI entry point
|
├── alembic/                # Alembic configuration and migration scripts
├── api/                    # Custom route declarations
├── cli/                    # Custom-built CLI for interacting with the API and DB, such as data ingestion protocols
├── core/                   # Settings, application config, ogc api config, constants, and dependencies
├── data_migrations/        # Used to migrate data from one form to another. For data that already exists in DB, not for transferring data to the DB
├── db/                     # Database models, sessions, and engine
├── docker/                 # Custom Docker files
├── docs/                   # Documentation about the app, such as decisions made and how things work
├── schemas/                # Pydantic schemas and validations
├── scripts/                # Unique scripts for unique tasks. They do not comprise part of the API
├── services/               # Reusable business logic, helpers, and database interactions
├── tests/                  # Code tests
└── transfers/              # Scripts to transfer data from legacy systems to current db schema, as well as seed staging data
```

## Model Changes

1. Revise models in the `db/` directory
2. Run alembic to create upgrade/downgrade scripts
    1. Make sure data is not lost due to upgrades/downgrades
3. Revise schemas in the `schemas/` directory
    1. Add validators for both fields and models as necessary
      1. Validations on incoming data only should be handled by Pydantic and 422 errors will be raised (default Pydantic)
      2. Validations against values in the database will be handled at the endpoint with custom checks and 409 errors will be raised
4. Revise tests
    1. Revise fixtures and testing data
    2. Revise tests and/or code so they all pass
    3. Add new tests as necessary
5. Revise documentation

Notes:
- All `Create` schema fields are defined as `<type>` if non-nullable and `<type> | None = None` if nullable
- All `Update` schema fields are optional and default to `None`
- All `Response` schema fields are defined as `<type>` if non-nullable and `<type> | None` if nullable
- All raised exceptions should use the `PydanticStyleException` as defined in `services/exceptions_helper.py`
- Errors handled by the database should be enumerated and handled in a database_error_handler in each router's file

## OGC

### EDR

#### Collections Dictionary
EDR collections are broadly defined via a list of dictionaries in `core/pygeoapi.py` called `EDR_COLLECTIONS`. Each item in `EDR_COLLECTIONS` defines a collection. The dictionaries work as follows:

```python
{
  "id": "the id of the collection, which defines the route as /collections/{id}",
  "title": "the title of the collection",
  "description": "the description of the collection",
  "keywords": ["keyword 1", "keyword 2", ..., "keyword n"],
  "table": "the database table or view from which the collection's data is queried. It must start with 'ogc_' and have a matching 'ogc_internal_' view.",
  "parameter_columns": [
    {
      "name_column": "the column in the table or view that holds parameter names",
      "unit_column": "the column in the table or view that holds the parameters' units" | None,
      "value_column": "the column in the table or view that holds the values",
      "data_type": "string" | "integer" | "float",
      "lexicon_category": "the lexicon category associated with terms if the parameter is categorical" | None
    },
    ...
  ],
  "station_properties": [
    "property 1 to include in the properties for a feature in the FeatureCollection, must be a column in the database table or view",
    "property 2 to include in the properties for a feature in the FeatureCollection, must be a column in the database table or view",
    ...,
    "property n to include in the properties for a feature in the FeatureCollection, must be a column in the database table or view"
  ],
  "independent_axis": {
    "axis": "t" | "z",
    "column": "the column in the table or view that holds the independent axis values"
  },
  "instance_field": "the column in the table or view that holds in the instance values" | None
}
```

**Notes**
- `z` is planned as an independent axis value but not yet implemented.
- `parameter_columns` is a list because one row may contain multiple parameters (e.g. observation and qualifier) and each column may have multiple parameters (e.g. multiple analytes in a single column).

#### Field Descriptions
Parameter names in EDR collections are discovered from the data. They are also described in `core/ogc-field-descriptions.yml`.
If a parameter name from a collection exists in the database, but is not described in `core/ogc-field-descriptions.yml`, then
the description and label in the CoverageCollection and the title and description in `/schema` default to the parameter name as it exists in the database. In this situation a `warning` level message will be logged describing what occurred and why. To have a different description and label than just the parameter name `core/ogc-field-descriptions.yml` will need to be updated for that collection and the API will need to be relaunched. The parameter name in `core/ogc-field-descriptions.yml` must match the parameter name that the backing view or table emits.

#### Categories
Parameters that have restricted values - categories in a CoverageCollection - are determined from the lexicon tables. They are populated by the terms associated with a category. They are greedy, so *every* term associated with a category is used. If only a subset of terms are desired add a new category to the `lexicon_category` table and then associate the desired terms with that category. The lexicon term and category tables will need to be updated in `core/lexicon.json` and then in the database with `oco initialize-lexicon`. Afterward the `lexicon_category` in the `EDR_COLLECTIONS` dictionary needs to be updated to the new category, requiring the API to be relaunched.

#### Parameters & Units
Each parameter can have one, and only one, unit. The units are defined in the database tables or backing views, nowhere else. If there are multiple units reported for a parameter then that parameter is dropped from the collection and a `warning` level message is logged. The data must be fixed; the API should not account for these edge cases.

#### Duplicate Independent Axis Values
If two records share an independent axis value - e.g. the same timestamp - the record with the lowest `id` is kept whole and the other is skipped with a `warning` level message logged.

## 📦 Ocotillo CLI

The `oco` command exposes project automation, database utilities, and data ingestion utilities.
There are different commands, most of which have and require multiple sub-commands.

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

# Run Behave BDD specs - these tags mimic what is run in CI
# drops and rebuilds ocotilloapi_test db by default
uv run behave tests/features --tags="@backend and @production and not @skip" --no-capture
```

Tests import the `cli` and `ingestion` dependency groups, so install them first
(see step 2 of setup). Tests require a local Postgres/PostGIS instance.
Set `POSTGRES_*` values in `.env`, run migrations, and ensure the database is reachable before running the suites.
