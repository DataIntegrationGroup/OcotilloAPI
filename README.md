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
- PostgreSQL with PostGIS extension
- [`uv`](https://github.com/astral-sh/uv) package manager
- Docker Desktop 4+

### Installation & Development Setup

#### 1. Clone the repository

```bash
git clone https://github.com/DataIntegrationGroup/NMSampleLocations.git
cd NMSampleLocations
```

#### 2. Set up virtual environment and install depdencies

Mac/Linux
```bash
uv venv
source .venv/bin/activate # (Mac/Linux)
uv pip install -r requirements.txt
```

Windows
```bash
uv venv
source .venv/Scripts/activate # (Windows)
uv pip install -r requirements.txt
```

#### 3. Setup pre-commit hookes

```bash
pre-commit install
```

#### 4. Setup environment variables

```bash
# Set up environment variables
cp .env.example .env
# Edit `.env` to configure database connection and app settings
```

#### 5. Build Docker images and start services

Builds the images for the server, database, and app and starts the services.

```bash
docker compose up --build # -d for silent/detached build
```

Notes:
- To access the app run `docker exec -it nmsamplelocations-app-1 bash`
- Pytest can be run through the command line outside of the app.

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
├── db/                     # Database models, sessions, migrations
├── docker/                 # Custom Docker files
├── migrations/             # Scripts to migrate data from NM_Aquifer to current db schema
├── schemas/                # Pydantic data models
├── services/               # Reusable database interactions
├── services/               # Business logic and helpers
└── tests/                  # Code tests
```