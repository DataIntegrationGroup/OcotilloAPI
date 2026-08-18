#!/usr/bin/env bash
# Set every environment variable the ocotillo-automated-ingestion code location
# needs, in one pass.
#
# Requires a Dagster+ *user* token -- an agent token authenticates but is not
# authorized for these mutations, and dg reports that as an unhelpful KeyError:
#     dg plus config set --api-token 'user:...'
#
# Secrets are never passed as arguments. `--from-local-env` reads them from this
# shell, so nothing sensitive reaches the command line, your shell history, or
# the Dagster+ audit log's argument capture. Export them first:
#
#     read -rs "DIVERHUB_USERNAME?Diver-HUB username: "; echo
#     read -rs "DIVERHUB_PASSWORD?Diver-HUB password: "; echo
#     export DIVERHUB_USERNAME DIVERHUB_PASSWORD
#
# Variables are scoped to this code location, not the deployment. If an earlier
# run set them with --global, delete those deployment-level entries in the
# Dagster+ UI afterwards -- otherwise both exist and which one wins is not
# obvious from either place.
#
# Usage:
#     ./automated_ingestion/scripts/set_code_location_env.sh storage
#     ./automated_ingestion/scripts/set_code_location_env.sh vendor
#     ./automated_ingestion/scripts/set_code_location_env.sh database
#
# The phases are separate on purpose. `database` should wait until
# automated_ingestion/sql/ingestion_role.sql has been run: setting CLOUD_SQL_*
# against a role that does not exist yet makes database_connectivity fail in a
# way that looks like the serverless-to-Cloud-SQL problem it is meant to test.
set -euo pipefail

DG="uv run --with dagster-dg-cli dg"
PHASE="${1:-}"

# No --global: that sets the variable at deployment level, where every other
# code location in this deployment can read it. This deployment is shared, so
# the vendor and database credentials stay scoped to this location.
set_var() { echo "  $1"; $DG plus create env "$@" -y >/dev/null; }

case "$PHASE" in
storage)
  echo "Raw-zone buckets (different value per scope):"
  set_var INGESTION_GCS_BUCKET ocotillo-ingestion-production --scope full
  set_var INGESTION_GCS_BUCKET ocotillo-ingestion-staging --scope branch
  ;;
vendor)
  : "${DIVERHUB_USERNAME:?export it first, see the header}"
  : "${DIVERHUB_PASSWORD:?export it first, see the header}"
  echo "Diver-HUB credentials (values read from this shell, not echoed):"
  set_var DIVERHUB_USERNAME --from-local-env
  set_var DIVERHUB_PASSWORD --from-local-env
  ;;
database)
  : "${CLOUD_SQL_INSTANCE_NAME:?export it first}"
  : "${CLOUD_SQL_DATABASE:?export it first}"
  echo "Cloud SQL connection:"
  set_var DB_DRIVER cloudsql
  set_var CLOUD_SQL_IP_TYPE public
  set_var CLOUD_SQL_INSTANCE_NAME --from-local-env
  set_var CLOUD_SQL_DATABASE --from-local-env

  # CLOUD_SQL_USER means different things in the two auth modes, and db/engine.py
  # passes it straight to the connector either way. Under IAM auth it must be the
  # service account with the .gserviceaccount.com suffix stripped; a plain
  # Postgres role name there fails as an authentication error that reads like a
  # missing grant. Deriving it here keeps the two settings from contradicting
  # each other.
  if [ -n "${CLOUD_SQL_PASSWORD:-}" ]; then
    echo "  (password auth)"
    set_var CLOUD_SQL_IAM_AUTH 0
    set_var CLOUD_SQL_USER ocotillo_ingestion
    set_var CLOUD_SQL_PASSWORD --from-local-env
  else
    IAM_SA="${INGESTION_SERVICE_ACCOUNT:-ocotillo-ingestion@waterdatainitiative-271000.iam.gserviceaccount.com}"
    IAM_USER="${IAM_SA%.gserviceaccount.com}"
    echo "  (IAM auth as ${IAM_USER})"
    set_var CLOUD_SQL_IAM_AUTH 1
    set_var CLOUD_SQL_USER "$IAM_USER"
  fi
  ;;
*)
  echo "usage: $0 {storage|vendor|database}" >&2
  exit 64
  ;;
esac

echo "Done. Verify in Dagster+ under Deployment -> Environment variables."
