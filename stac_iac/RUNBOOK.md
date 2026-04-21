# STAC Terraform Runbook

This runbook covers provisioning the dedicated STAC API on Cloud Run with the
Terraform in [stac_iac](/Users/jross/Programming/DIG/OcotilloAPI/stac_iac) and
manually initializing or upgrading `pgstac`.

## Prerequisites

- `gcloud` installed and authenticated
- `terraform` installed
- `cloud-sql-proxy` installed
- access to the target GCP project
- an existing Cloud SQL Postgres instance
- a container image for `stac-fastapi-pgstac`
- local access to `psql`
- local access to `pypgstac`

If you are using this repo for the manual `pgstac` work, activate the repo
virtualenv first:

```bash
cd /Users/jross/Programming/DIG/OcotilloAPI
source .venv/bin/activate
```

If `pypgstac` is not installed in that environment yet, install the CLI extras:

```bash
uv sync --locked --extra cli
```

## 1. Select the target project

```bash
export PROJECT_ID="your-gcp-project"
export REGION="us-central1"
export SQL_INSTANCE_NAME="your-postgres-instance"
export CLOUD_SQL_CONNECTION_NAME="${PROJECT_ID}:${REGION}:${SQL_INSTANCE_NAME}"

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

## 3. Create the runtime Secret Manager secrets

The Terraform expects existing Secret Manager secret ids for the STAC API
runtime database username and password.

Set the values locally first:

```bash
export STAC_DB_USER="stac_runtime"
export STAC_DB_PASSWORD="your_db_password"
```

Create the secrets:

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

If the secrets already exist, add new versions instead:

```bash
printf '%s' "$STAC_DB_USER" | \
  gcloud secrets versions add stac-postgres-user \
  --data-file=-

printf '%s' "$STAC_DB_PASSWORD" | \
  gcloud secrets versions add stac-postgres-password \
  --data-file=-
```

Verify:

```bash
gcloud secrets describe stac-postgres-user
gcloud secrets describe stac-postgres-password
```

## 4. Create the Artifact Registry repository and mirror the image

Cloud Run cannot deploy directly from `ghcr.io`, so mirror the image into an
Artifact Registry Docker repository first.

Create the repository:

```bash
export ARTIFACT_REPO="stac"

gcloud artifacts repositories create "$ARTIFACT_REPO" \
  --project="$PROJECT_ID" \
  --location="$REGION" \
  --repository-format=docker \
  --description="STAC container images" \
  --immutable-tags \
  --disable-vulnerability-scanning
```

If the repository already exists, `gcloud` will return an already-exists error;
in that case, continue to the next step.

Configure Docker auth, pull from GHCR, tag, and push to Artifact Registry:

```bash
gcloud auth configure-docker "${REGION}-docker.pkg.dev"

docker pull --platform linux/amd64 ghcr.io/stac-utils/stac-fastapi-pgstac:latest
docker tag ghcr.io/stac-utils/stac-fastapi-pgstac:latest \
  "${REGION}-docker.pkg.dev/${PROJECT_ID}/${ARTIFACT_REPO}/stac-fastapi-pgstac:latest"
docker push \
  "${REGION}-docker.pkg.dev/${PROJECT_ID}/${ARTIFACT_REPO}/stac-fastapi-pgstac:latest"
```

If the push fails with an IAM error, the account doing the push needs Artifact
Registry write access such as `roles/artifactregistry.writer`.

Cloud Run requires Linux x86_64 (`linux/amd64`) container images. If you mirror
the image from an Apple Silicon machine without `--platform linux/amd64`, Docker
can select an ARM variant that will fail on Cloud Run with `exec format error`.

## 5. Create the Terraform variables file

Start from the example:

```bash
cd /Users/jross/Programming/DIG/OcotilloAPI/stac_iac
cp terraform.tfvars.example terraform.tfvars
```

Edit `terraform.tfvars` with real values:

```hcl
project_id                  = "your-gcp-project"
region                      = "us-central1"
service_name                = "stac-api"
service_account_name        = "stac-api"
image                       = "us-central1-docker.pkg.dev/your-gcp-project/stac/stac-fastapi-pgstac:latest"
cloud_sql_connection_name   = "your-gcp-project:us-central1:your-postgres-instance"
postgres_database           = "postgres"
postgres_user_secret_id     = "stac-postgres-user"
postgres_password_secret_id = "stac-postgres-password"
cors_origins                = "*"
min_instance_count          = 0
max_instance_count          = 10
allow_unauthenticated       = true
deletion_protection         = false
```

Use an image hosted in `docker.io`, `gcr.io`, or Artifact Registry. Cloud Run
rejects `ghcr.io` image URLs directly.

`cors_origins = "*"` configures `stac-fastapi-pgstac` to return wildcard CORS
headers, including `Access-Control-Allow-Origin: *`, when the request includes
an `Origin` header. Set a narrower comma-delimited list if the service should
only allow specific origins.

## 6. Initialize Terraform

```bash
cd /Users/jross/Programming/DIG/OcotilloAPI/stac_iac
terraform init
terraform fmt
terraform validate
```

## 7. Review the deployment plan

```bash
terraform plan -out=tfplan
```

Review these resources carefully:

- `google_service_account.stac_api`
- `google_project_iam_member.cloudsql_client`
- `google_project_iam_member.secret_accessor`
- `google_cloud_run_v2_service.stac_api`
- `google_cloud_run_v2_service_iam_member.public_invoker`

## 8. Manually initialize or upgrade `pgstac`

This step is manual. Terraform does not create or run a bootstrap job.

Complete this before applying the Cloud Run service. The `stac-fastapi-pgstac`
container opens its database connection during application startup, so the
service can fail to become healthy if `pgstac` is not installed yet or the
runtime role does not exist.

Use a database user that can create extensions and run `pypgstac migrate`.
For Cloud SQL PostgreSQL, a built-in user created with `gcloud sql users create`
is a practical choice.

Set the admin credentials and target database:

```bash
export PGHOST=127.0.0.1
export PGPORT=5432
export PGDATABASE="postgres"
export PGUSER="stac_bootstrap"
export PGPASSWORD="your_bootstrap_db_password"
export RUNTIME_PGUSER="$STAC_DB_USER"
export RUNTIME_PGPASSWORD="$STAC_DB_PASSWORD"
```

Start the Cloud SQL Auth Proxy in a separate terminal:

```bash
cloud-sql-proxy "$CLOUD_SQL_CONNECTION_NAME" --port 5432
```

Run the manual bootstrap:

```bash
psql -v ON_ERROR_STOP=1 -c "CREATE EXTENSION IF NOT EXISTS postgis;"
psql -v ON_ERROR_STOP=1 -c "CREATE EXTENSION IF NOT EXISTS btree_gist;"
pypgstac migrate
psql -v ON_ERROR_STOP=1 -c \
  "ALTER DATABASE \"$PGDATABASE\" SET search_path TO pgstac, public;"
psql -v ON_ERROR_STOP=1 -v runtime_user="$RUNTIME_PGUSER" -v runtime_password="$RUNTIME_PGPASSWORD" <<'SQL'
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'runtime_user') THEN
        EXECUTE format(
            'CREATE ROLE %I LOGIN PASSWORD %L',
            :'runtime_user',
            :'runtime_password'
        );
    END IF;
END $$;
SQL
psql -v ON_ERROR_STOP=1 -v runtime_user="$RUNTIME_PGUSER" -c \
  "GRANT pgstac_read TO \"$RUNTIME_PGUSER\";"
psql -v ON_ERROR_STOP=1 -v runtime_user="$RUNTIME_PGUSER" -c \
  "ALTER ROLE \"$RUNTIME_PGUSER\" SET search_path TO pgstac, public;"
```

Re-run this section whenever you need to upgrade `pgstac`.

## 9. Apply

```bash
terraform apply tfplan
```

Or without a saved plan:

```bash
terraform apply
```

## 10. Verify the deployment

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

Verify `pgstac` manually:

```bash
psql -v ON_ERROR_STOP=1 -c "SELECT extname FROM pg_extension WHERE extname IN ('postgis', 'btree_gist');"
psql -v ON_ERROR_STOP=1 -c "SELECT schemaname, tablename FROM pg_tables WHERE schemaname = 'pgstac' LIMIT 5;"
psql -v ON_ERROR_STOP=1 -c "SHOW search_path;"
```

## 11. Troubleshooting

If manual `pgstac` setup fails:

- verify the admin user can create extensions
- verify the target database is correct
- verify `cloud-sql-proxy` is connected to the intended instance
- verify `pypgstac` is installed in the active virtualenv
- verify the STAC API image version is compatible with the target `pgstac` version

If Cloud Run cannot reach Cloud SQL:

- verify `cloud_sql_connection_name`
- verify the Cloud Run service account has `roles/cloudsql.client`
- verify the database is accepting the supplied runtime username and password
- verify the service is using an Artifact Registry, `gcr.io`, or `docker.io` image path rather than `ghcr.io`
- verify you completed the manual `pgstac` setup before `terraform apply`
- inspect the Cloud Run revision logs for the underlying startup exception

If secret access fails:

- verify `postgres_user_secret_id` and `postgres_password_secret_id`
- verify the service account has `roles/secretmanager.secretAccessor`
- verify the secrets have at least one enabled version

If the API starts but queries fail:

- confirm `pgstac` is installed in the target database
- confirm the runtime user exists and has the expected `pgstac_read` grant
- confirm the runtime user's `search_path` includes `pgstac, public`
- re-run the manual `pgstac` bootstrap after changing the target `pypgstac` version
