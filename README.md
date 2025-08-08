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
- 🧾 Interactive API documentation via Swagger and ReDoc

---

## 🛠️ Getting Started

### Prerequisites

- Python 3.11+
- PostgreSQL with PostGIS extension
- [`uv`](https://github.com/astral-sh/uv) package manager

### Installation

```bash
# Clone the repository
git clone https://github.com/DataIntegrationGroup/NMSampleLocations.git
cd NMSampleLocations

# Set up virtual environment and install dependencies
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt

# Set up pre-commit hooks
pre-commit install

# Set up environment variables
cp .env.example .env
# Edit `.env` to configure database connection and app settings

# Run database migrations
alembic upgrade head  

# Start the development server
uvicorn app.main:app --reload
```

### 🧭 Project Structure
```text
app/
├── api/            # Route declarations
├── core/           # Settings and application config
├── db/             # Database models, sessions, migrations
├── schemas/        # Pydantic data models
├── services/       # Business logic and helpers
└── main.py         # FastAPI entry point
```