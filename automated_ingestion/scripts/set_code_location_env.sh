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
# Variables are set at deployment scope. See the comment on set_var for why
# location scoping through dg does not work, and what to do instead if these
# values must not be visible to the other code locations in this deployment.
#
# Usage:
#     ./automated_ingestion/scripts/set_code_location_env.sh storage
#     ./automated_ingestion/scripts/set_code_location_env.sh credentials
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

# --global sets the variable at deployment level. That is broader than ideal --
# this deployment also hosts aqueduct_dagster_defs_definitions and
# die-orchestration, which can then read these values -- but it is the scope
# that actually reaches the container.
#
# Location scoping through dg does not work here: dg names the location from the
# project (`OcotilloAPI`), not from `location_name` in dagster_cloud.yaml
# (`ocotillo-automated-ingestion`), and `code_location_name` in [tool.dg.project]
# is ignored for this command. Dagster+ accepts the unknown name without
# complaint, so the variable shows as set in the UI and is absent in the
# container -- which costs an afternoon to work out from a
# DefaultCredentialsError.
#
# To scope properly, set the variable in the Dagster+ UI against
# `ocotillo-automated-ingestion` instead.
set_var() { echo "  $1"; $DG plus create env "$@" --global -y >/dev/null; }

case "$PHASE" in
storage)
  # The image copies the repository to /opt/dagster/app but never installs it,
  # so db/ and domain/ are importable only if that directory is on the path.
  # The process that loads the code location has it; the process that executes a
  # step does not reliably, which shows up as ModuleNotFoundError for db at
  # execution while the location itself loads fine. Setting PYTHONPATH removes
  # the guesswork instead of depending on how each process was launched.
  echo "Import path:"
  set_var PYTHONPATH /opt/dagster/app

  echo "Raw-zone buckets (different value per scope):"
  set_var INGESTION_GCS_BUCKET ocotillo-ingestion-production --scope full
  set_var INGESTION_GCS_BUCKET ocotillo-ingestion-staging --scope branch
  ;;
credentials)
  : "${INGESTION_GCP_CREDENTIALS_JSON:?export the service account key JSON, not a path}"
  # Serverless runs outside GCP, so there is no metadata server and nothing
  # supplies Application Default Credentials. Both the Cloud SQL connector and
  # gcsfs need them. Mint the key with:
  #   gcloud iam service-accounts keys create /dev/stdout \
  #     --iam-account ocotillo-ingestion@waterdatainitiative-271000.iam.gserviceaccount.com
  echo "GCP credentials (key JSON read from this shell, not echoed):"
  set_var INGESTION_GCP_CREDENTIALS_JSON --from-local-env
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
  echo "usage: $0 {storage|credentials|vendor|database}" >&2
  exit 64
  ;;
esac

echo "Done. Verify in Dagster+ under Deployment -> Environment variables."
