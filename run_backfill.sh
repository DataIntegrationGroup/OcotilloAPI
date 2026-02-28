#!/usr/bin/env bash

# This script is used to run the backfill process on the staging database.
# backfill is different from transfer. Transfer refers to moving the legacy data from NM_Aquifer into ocotillo
# (ideally with minimal transformation). Backfill refers to populating additional fields in ocotillo that were not part of the original data transfer,
# e.g. state, county, quad_name,etc. It will also be used to handle data refactors/corrections in the future.

# Load environment variables from .env and run the staging backfill.
# Usage: ./run_backfill.sh

# github workflow equivalent: for reference only
#- name: Run backfill script on staging database
#  env:
#    DB_DRIVER: "cloudsql"
#    CLOUD_SQL_INSTANCE_NAME: "${{ secrets.CLOUD_SQL_INSTANCE_NAME }}"
#    CLOUD_SQL_DATABASE: "${{ vars.CLOUD_SQL_DATABASE }}"
#    CLOUD_SQL_USER: "${{ secrets.CLOUD_SQL_USER }}"
#    CLOUD_SQL_IAM_AUTH: true
#    GCS_SERVICE_ACCOUNT_KEY: "${{ secrets.GCS_SERVICE_ACCOUNT_KEY }}"
#    GCS_BUCKET_NAME: "${{ vars.GCS_BUCKET_NAME }}"
#  run: |
#    uv run python -m transfers.backfill.backfill


set -euo pipefail

ENV_FILE=".env"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing $ENV_FILE; aborting." >&2
  exit 1
fi

# Export variables from .env
set -a
source "$ENV_FILE"
set +a

uv run alembic upgrade head

python -m transfers.backfill.backfill
