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

set_var() { echo "  $1"; $DG plus create env "$@" --global -y >/dev/null; }

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
  set_var CLOUD_SQL_USER ocotillo_ingestion
  set_var CLOUD_SQL_INSTANCE_NAME --from-local-env
  set_var CLOUD_SQL_DATABASE --from-local-env
  # Prefer IAM auth: it removes the password entirely, and ingestion_role.sql
  # documents creating the role as "ocotillo-ingestion@PROJECT.iam" instead.
  if [ -n "${CLOUD_SQL_PASSWORD:-}" ]; then
    set_var CLOUD_SQL_PASSWORD --from-local-env
  else
    echo "  CLOUD_SQL_PASSWORD unset -- assuming IAM auth"
    set_var CLOUD_SQL_IAM_AUTH 1
  fi
  ;;
*)
  echo "usage: $0 {storage|vendor|database}" >&2
  exit 64
  ;;
esac

echo "Done. Verify in Dagster+ under Deployment -> Environment variables."
