# STAC Terraform Runbook

This runbook covers provisioning the dedicated STAC API on Cloud Run with the
Terraform in [`stac_iac`](/Users/jakeross/_Programming/_DIG/OcotilloAPI/stac_iac),
including a Terraform-managed Cloud Run Job that initializes or upgrades
`pgstac`.

## Prerequisites

- `gcloud` installed and authenticated
- `terraform` installed
- access to the target GCP project
- an existing Cloud SQL Postgres instance
- a container image for `stac-fastapi-pgstac`
- a bootstrap container image with `psql` and `pypgstac`

## 1. Select the target project

```bash
export PROJECT_ID="your-gcp-project"
export REGION="us-central1"
export SQL_INSTANCE_NAME="your-postgres-instance"

gcloud config set project "$PROJECT_ID"
gcloud auth application-default login
```

## 2. Enable required APIs

```bash
gcloud services enable \
  run.googleapis.com \
  secretmanager.googleapis.com \
  sqladmin.googleapis.com \
  cloudresourcemanager.googleapis.com
```

## 3. Create Secret Manager secrets

The Terraform expects existing Secret Manager secret ids for:

- the runtime STAC API database user and password
- the bootstrap database user and password used by the Cloud Run Job

The bootstrap user may need elevated database privileges because it creates
extensions and runs `pypgstac migrate`.

Set the values locally first:

```bash
export STAC_DB_USER="stac_runtime"
export STAC_DB_PASSWORD="your_db_password"
export STAC_BOOTSTRAP_DB_USER="stac_bootstrap"
export STAC_BOOTSTRAP_DB_PASSWORD="your_bootstrap_db_password"
```

## 3a. Create the bootstrap Cloud SQL user

Create the dedicated bootstrap user with Cloud SQL built-in authentication:

```bash
gcloud sql users create "$STAC_BOOTSTRAP_DB_USER" \
  --instance="$SQL_INSTANCE_NAME" \
  --password="$STAC_BOOTSTRAP_DB_PASSWORD"
```

Cloud SQL PostgreSQL users created this way are members of the
`cloudsqlsuperuser` role, which is the capability needed to create extensions.

## 3b. Create the runtime secrets

```bash
printf '%s' "$STAC_DB_USER" | \
  gcloud secrets create stac-postgres-user \
  --replication-policy="automatic" \
  --data-file=-

printf '%s' "$STAC_DB_PASSWORD" | \
  gcloud secrets create stac-postgres-password \
  --replication-policy="automatic" \
  --data-file=-
```

The bootstrap job reads these runtime secrets and creates the runtime database
role itself, then grants `pgstac_read` and sets the runtime `search_path`.

## 3c. Create the bootstrap secrets

```bash
printf '%s' "$STAC_BOOTSTRAP_DB_USER" | \
  gcloud secrets create stac-bootstrap-postgres-user \
  --replication-policy="automatic" \
  --data-file=-

printf '%s' "$STAC_BOOTSTRAP_DB_PASSWORD" | \
  gcloud secrets create stac-bootstrap-postgres-password \
  --replication-policy="automatic" \
  --data-file=-
```

## 3d. If the secrets already exist, add new versions instead:

```bash
printf '%s' "$STAC_DB_USER" | \
  gcloud secrets versions add stac-postgres-user \
  --data-file=-

printf '%s' "$STAC_DB_PASSWORD" | \
  gcloud secrets versions add stac-postgres-password \
  --data-file=-

printf '%s' "$STAC_BOOTSTRAP_DB_USER" | \
  gcloud secrets versions add stac-bootstrap-postgres-user \
  --data-file=-

printf '%s' "$STAC_BOOTSTRAP_DB_PASSWORD" | \
  gcloud secrets versions add stac-bootstrap-postgres-password \
  --data-file=-
```

## 3e. Verify:

```bash
gcloud secrets describe stac-postgres-user
gcloud secrets describe stac-postgres-password
gcloud secrets describe stac-bootstrap-postgres-user
gcloud secrets describe stac-bootstrap-postgres-password
```

## 4. Create the Terraform variables file

Start from the example:

```bash
cd /Users/jakeross/_Programming/_DIG/OcotilloAPI/stac_iac
cp terraform.tfvars.example terraform.tfvars
```

Edit `terraform.tfvars` with real values:

```hcl
project_id                  = "your-gcp-project"
region                      = "us-central1"
service_name                = "stac-api"
service_account_name        = "stac-api"
image                       = "ghcr.io/stac-utils/stac-fastapi-pgstac:latest"
bootstrap_job_name          = "stac-bootstrap"
bootstrap_image             = "ghcr.io/your-org/stac-bootstrap:latest"
cloud_sql_connection_name   = "your-gcp-project:us-central1:your-postgres-instance"
postgres_database           = "postgres"
postgres_user_secret_id     = "stac-postgres-user"
postgres_password_secret_id = "stac-postgres-password"
bootstrap_postgres_user_secret_id     = "stac-bootstrap-postgres-user"
bootstrap_postgres_password_secret_id = "stac-bootstrap-postgres-password"
min_instance_count          = 0
max_instance_count          = 10
allow_unauthenticated       = true
```

## 5. Initialize Terraform

```bash
cd /Users/jakeross/_Programming/_DIG/OcotilloAPI/stac_iac
terraform init
terraform fmt
terraform validate
```

## 6. Review the deployment plan

```bash
terraform plan -out=tfplan
```

Review these resources carefully:

- `google_service_account.stac_api`
- `google_project_iam_member.cloudsql_client`
- `google_project_iam_member.secret_accessor`
- `google_cloud_run_v2_job.pgstac_bootstrap`
- `google_cloud_run_v2_service.stac_api`
- `google_cloud_run_v2_service_iam_member.public_invoker`

## 7. Apply

```bash
terraform apply tfplan
```

Or without a saved plan:

```bash
terraform apply
```

## 8. Run the `pgstac` bootstrap job

The Terraform creates the job, but you still execute it explicitly when you
want to initialize or upgrade `pgstac`.

```bash
gcloud run jobs execute stac-bootstrap \
  --region "$REGION" \
  --wait
```

If you changed `bootstrap_job_name`, use that value instead.

Watch execution status:

```bash
gcloud run jobs executions list \
  --job stac-bootstrap \
  --region "$REGION"
```

Inspect logs:

```bash
gcloud logging read \
  "resource.type=cloud_run_job AND resource.labels.job_name=stac-bootstrap" \
  --limit=100 \
  --format="value(textPayload)"
```

The bootstrap job also creates the runtime role from the runtime secrets if it
does not already exist.

## 9. Verify the deployment

Get outputs:

```bash
terraform output
```

Check the Cloud Run service:

```bash
gcloud run services describe stac-api \
  --region "$REGION"
```

Check the service URL:

```bash
SERVICE_URL="$(terraform output -raw service_url)"
curl -i "$SERVICE_URL"
```

If the service is public and `stac-fastapi-pgstac` is configured correctly,
you should get an HTTP response from the STAC API root.

Verify `pgstac` bootstrap job creation:

```bash
terraform output bootstrap_job_name
```

## 10. Troubleshooting

If the bootstrap job fails:

- verify `bootstrap_image` includes both `psql` and `pypgstac`
- verify the bootstrap database user was created as a Cloud SQL built-in user
- verify the bootstrap database user can create extensions
- verify the runtime secrets contain the intended runtime username and password
- verify the bootstrap service account has `roles/cloudsql.client`
- verify the bootstrap service account has `roles/secretmanager.secretAccessor`

If Cloud Run cannot reach Cloud SQL:

- verify `cloud_sql_connection_name`
- verify the Cloud Run service account has `roles/cloudsql.client`
- verify the database is accepting the supplied username and password

If secret access fails:

- verify `postgres_user_secret_id` and `postgres_password_secret_id`
- verify `bootstrap_postgres_user_secret_id` and `bootstrap_postgres_password_secret_id`
- verify the service account has `roles/secretmanager.secretAccessor`
- verify the secrets have at least one enabled version

If the API starts but queries fail:

- confirm `pgstac` is installed in the target database
- confirm the runtime user exists and has the expected pgstac role grants
- confirm the `stac-fastapi-pgstac` image matches the target `pgstac` version
- re-run the bootstrap job after changing the target `pypgstac` version
