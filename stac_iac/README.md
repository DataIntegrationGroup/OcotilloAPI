# stac_iac

Terraform for the dedicated STAC API stack.

This directory owns:
- Cloud Run deployment for `stac-fastapi-pgstac`
- service account and IAM bindings
- Secret Manager wiring for database credentials
- Cloud SQL connectivity to the existing PostGIS instance
- optional custom domain inputs for the STAC API

This directory does not manage GeoServer.

## Expected inputs

- Existing GCP project and region
- Existing Cloud SQL Postgres instance with `pgstac` installed
- Existing Secret Manager secrets for database username and password
- Container image for `stac-fastapi-pgstac`

## Files

- `versions.tf`: Terraform and provider versions
- `variables.tf`: stack inputs
- `main.tf`: Cloud Run, service account, IAM, and service wiring
- `outputs.tf`: useful deployment outputs
- `terraform.tfvars.example`: example variable values
- `RUNBOOK.md`: step-by-step setup and deployment instructions

## Notes

- The STAC API is intended to run independently from OcotilloAPI.
- `pgstac` initialization and upgrades are manual operational steps documented in the runbook, not Terraform-managed resources.
- The Cloud Run service sets `CORS_ORIGINS` for `stac-fastapi-pgstac`; the default `*` allows the app to emit `Access-Control-Allow-Origin: *` for cross-origin requests.
