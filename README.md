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

#### 2. Set up virtual environment and install depdencies


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
* PostgreSQL port is 54321 (default is 5432). Update your postgresql.conf to `port = 54321`


In development set `MODE=development` to allow lexicon enums to be populated.

#### 5. Database and server


<table>
<tr>
<td>
    PostgreSQL + PostGIS installed locally
</td>
<td>
    Docker
</td>
</tr>
<tr>
<td>

```bash
#run database migrations
alembic upgrade head

# start development server
uvicorn app.main:app --reload
```
    
</td>
<td>

```bash
# include -d flag for silent/detached build
docker compose up --build
```

</td>
</tr>
<tr>
<td>
Requires PostgreSQL and PostGIS extensions to be installed locally
</td>
<td>
Requires Docker Desktop to be installed locally
</td>
</tr>
<tr>
<td>
</td>
<td>
Run <code>docker exec -it nmsamplelocations-app-1 bash</code> to open a shell inside the running app container.
</td>
</tr>
<tr>
<td>
</td>
<td>
After the database container is running, you can run tests with Pytest from your local command line (not necessarily inside the app container).
</td>
</tr>
</table>


#### Staging Data

To get staging data into the database run `python -m transfers.transfer` from the root directory of the project.

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
