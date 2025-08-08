# NMSampleLocations

[![Code Format](https://github.com/DataIntegrationGroup/NMSampleLocations/actions/workflows/format_code.yml/badge.svg)](https://github.com/DataIntegrationGroup/NMSampleLocations/actions/workflows/format_code.yml)
[![Dependabot Updates](https://github.com/DataIntegrationGroup/NMSampleLocations/actions/workflows/dependabot/dependabot-updates/badge.svg)](https://github.com/DataIntegrationGroup/NMSampleLocations/actions/workflows/dependabot/dependabot-updates)
[![Sentry Release](https://github.com/DataIntegrationGroup/NMSampleLocations/actions/workflows/release.yml/badge.svg)](https://github.com/DataIntegrationGroup/NMSampleLocations/actions/workflows/release.yml)
[![Tests](https://github.com/DataIntegrationGroup/NMSampleLocations/actions/workflows/tests.yml/badge.svg)](https://github.com/DataIntegrationGroup/NMSampleLocations/actions/workflows/tests.yml)
[![codecov](https://codecov.io/gh/DataIntegrationGroup/NMSampleLocations/graph/badge.svg?token=Y20QB357OO)](https://codecov.io/gh/DataIntegrationGroup/NMSampleLocations)

**Geospatial Sample Data Management System**  
_New Mexico Bureau of Geology and Mineral Resources_

NMSampleLocations is a FastAPI-based backend service designed to manage geospatial sample location data across New Mexico. It supports research, field operations, and public data delivery for the Bureau of Geology and Mineral Resources.

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
git clone https://github.com/DataIntegrationGroup/NMSampleLocations.git
cd NMSampleLocations
```

#### 2. Set up virtual environment and install depdencies


| Mac/Linux | Windows |
| --------- | ------- |
| <pre><code>uv venv<br>source .venv/bin/activate<br>uv pip install -r requirements.txt</code></pre> | <pre><code>uv venv<br>source .venv/Scripts/activate<br>uv pip install -r requirements.txt</code></pre>


#### 3. Setup pre-commit hookes

```bash
pre-commit install
```

#### 4. Setup environment variables

```bash
# Edit `.env` to configure database connection and app settings
cp .env.example .env
```

#### 5. Database and server

| PostgreSQL + PostGIS install locally | Docker|
| -------------------- | ----- |
|<pre><code>#run database migrations<br>alembic upgrade head<br><br># start development server<br>uvicorn app.main:app --reload</code></pre> | <pre><code># include -d flag for silent/detached build<br>docker compose up --build<br><br><br><br></code></pre> |
| Requires PostgreSQL and PostGIS extensions to be installed locally | Requires Docker Desktop to be installed |
| | To access the app run `docker exec -it nmsamplelocations-app-1 bash` |
| | Pytest can be run through the command line outside of the app |


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
├── core/                   # Settings and application config
├── db/                     # Database models, sessions, and engine
├── docker/                 # Custom Docker files
├── migrations/             # Scripts to migrate data from NM_Aquifer to current db schema
├── schemas/                # Pydantic data models
├── services/               # Reusable database interactions
├── services/               # Business logic and helpers
└── tests/                  # Code tests
```