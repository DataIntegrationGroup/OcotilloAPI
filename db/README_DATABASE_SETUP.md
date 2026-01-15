# Database Setup Guide

This directory contains SQL files to help you set up and populate a new OcotilloAPI database instance.

## Files

- **`schema_dump.sql`** - Complete PostgreSQL database schema with PostGIS support
- **`sample_data.sql`** - Sample data for testing and demonstration
- **`README_DATABASE_SETUP.md`** - This file

## Quick Start

### Option 1: Using Alembic Migrations (Recommended)

The preferred method is to use Alembic, which will create the schema and keep it in sync:

```bash
# 1. Set up environment variables
export DATABASE_URL="postgresql://user:password@host:5432/dbname"

# 2. Run migrations
alembic upgrade head

# 3. Initialize lexicon and parameters
python -c "from core.initializers import init_lexicon, init_parameter; init_lexicon(); init_parameter()"

# 4. (Optional) Load sample data
psql $DATABASE_URL -f db/sample_data.sql
```

### Option 2: Using SQL Dump Files

If you prefer to use the SQL dump files directly:

```bash
# 1. Create database
createdb ocotillo_dev

# 2. Load schema
psql ocotillo_dev -f db/schema_dump.sql

# 3. Initialize lexicon and parameters (via Python)
export DATABASE_URL="postgresql://user:password@localhost:5432/ocotillo_dev"
python -c "from core.initializers import init_lexicon, init_parameter; init_lexicon(); init_parameter()"

# 4. (Optional) Load sample data
psql ocotillo_dev -f db/sample_data.sql
```

## Schema Details

### Extensions Required

- **PostGIS** - For geographic data types and spatial queries
- **uuid-ossp** - For UUID generation

### Key Table Groups

1. **Vocabulary Tables** - Lexicon terms, categories, and semantic relationships
2. **Geographic Tables** - Locations, aquifer systems, geologic formations
3. **Things** - Wells, springs, and other monitoring points
4. **Contacts** - People and organizations with emails, phones, addresses
5. **Sensors** - Equipment inventory and deployment history
6. **Sampling** - Field events, activities, samples, and observations
7. **Parameters** - Measurable properties and analysis methods
8. **Groups** - Project and monitoring network organization
9. **Publications** - Research papers and authorship
10. **Polymorphic Tables** - Status history, notes, data provenance

### Spatial Reference System

All geographic coordinates use **SRID 4326** (WGS84):
- Longitude range: -180 to 180
- Latitude range: -90 to 90

### Sample Data

The `sample_data.sql` file includes:

- **5 Contacts** - Scientists and technicians from various agencies
  - Complete with emails, phone numbers, and addresses

- **5 Locations** - Geographic points across New Mexico
  - Albuquerque, Santa Fe, Las Cruces, Los Alamos, Carlsbad

- **5 Wells (Things)** - Monitoring wells with complete metadata
  - Depth, casing, completion details
  - Associated with locations, aquifers, and formations

- **5 Sensors** - Pressure transducers, barometers, acoustic probes
  - Serial numbers, equipment status

- **5 Deployments** - Sensors installed at wells

- **5 Field Events** - Site visits with participants

- **5 Samples** - Water samples collected during field events

- **10 Observations** - Water level and temperature measurements

- **3 Aquifer Systems** - Santa Fe Group, Ogallala, Roswell Basin

- **3 Geologic Formations** - Alluvium, Santa Fe Group, Bandelier Tuff

- **3 Groups/Projects** - Monitoring networks and research projects

## Prerequisites for Sample Data

Before loading `sample_data.sql`, you must initialize:

1. **Lexicon Terms** - Run `init_lexicon()` from `core/initializers.py`
   - Required terms: "water well", "monitoring", "public", "unconfined", etc.

2. **Parameters** - Run `init_parameter()` from `core/initializers.py`
   - Parameter ID 1: depth to water
   - Parameter ID 2: water temperature
   - Additional parameters for chemistry

These are automatically initialized via:
```python
from core.initializers import init_lexicon, init_parameter
init_lexicon()
init_parameter()
```

Or via the seed function:
```python
from transfers.seed import seed_all
seed_all(n=5)  # Creates 5 of each entity type
```

## Using with Docker

If running in Docker:

```bash
# Access the app container
docker compose exec app bash

# Run migrations
alembic upgrade head

# Initialize lexicon and parameters
python -c "from core.initializers import init_lexicon, init_parameter; init_lexicon(); init_parameter()"

# Load sample data
psql $DATABASE_URL -f db/sample_data.sql
```

## Using with Render

On Render, the `preDeployCommand` in `render.yaml` automatically:
1. Creates PostGIS extension
2. Runs Alembic migrations

To load sample data on Render:
1. Access the database via Render Shell
2. Run the SQL file: `psql $DATABASE_URL -f db/sample_data.sql`

## Verification

After loading data, verify with these queries:

```sql
-- Count records
SELECT
    (SELECT COUNT(*) FROM contact) as contacts,
    (SELECT COUNT(*) FROM location) as locations,
    (SELECT COUNT(*) FROM thing) as things,
    (SELECT COUNT(*) FROM sensor) as sensors,
    (SELECT COUNT(*) FROM observation) as observations;

-- List all wells with locations
SELECT t.name, l.county, l.state, ST_AsText(l.point) as coordinates
FROM thing t
JOIN location_thing_association lta ON t.id = lta.thing_id
JOIN location l ON lta.location_id = l.id
WHERE lta.effective_end IS NULL;

-- Check parameter initialization
SELECT COUNT(*) FROM parameter;
SELECT COUNT(*) FROM lexicon_term;
```

## Resetting the Database

To start fresh:

```bash
# Drop and recreate
dropdb ocotillo_dev
createdb ocotillo_dev

# Reload schema and data
psql ocotillo_dev -f db/schema_dump.sql
python -c "from core.initializers import init_lexicon, init_parameter; init_lexicon(); init_parameter()"
psql ocotillo_dev -f db/sample_data.sql
```

Or with Alembic:

```bash
# Downgrade all migrations
alembic downgrade base

# Upgrade to latest
alembic upgrade head

# Reinitialize
python -c "from core.initializers import init_lexicon, init_parameter; init_lexicon(); init_parameter()"
psql $DATABASE_URL -f db/sample_data.sql
```

## Troubleshooting

### PostGIS Extension Not Found

```sql
-- Check if PostGIS is available
SELECT name, default_version FROM pg_available_extensions WHERE name = 'postgis';

-- Enable PostGIS
CREATE EXTENSION IF NOT EXISTS postgis;
```

### Lexicon Terms Not Found

If you get foreign key errors referencing `lexicon_term`, make sure to run:
```python
from core.initializers import init_lexicon
init_lexicon()
```

### Parameter Not Found

If observations fail to insert due to missing parameters:
```python
from core.initializers import init_parameter
init_parameter()
```

## Additional Resources

- **Alembic Migrations**: `/alembic/versions/`
- **Model Definitions**: `/db/*.py`
- **Seed Script**: `/transfers/seed.py`
- **Lexicon Data**: `/core/lexicon.json`
- **Parameter Data**: `/core/parameter.json`

## Support

For questions or issues with database setup, refer to:
- Main README.md
- RENDER_DEPLOYMENT.md (for Render-specific setup)
- Alembic documentation: https://alembic.sqlalchemy.org/
