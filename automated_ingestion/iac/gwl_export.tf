# Groundwater level bulk export (OCO-79): the Cloud Run job Dagster launches
# for each step, the bucket it publishes to, and the identities involved.
#
# Nothing here is created until `gwl_export` has an entry for an environment
# (it defaults to {}), so applying this file to an existing state is a no-op
# until someone decides to stand the export up.
#
# Two service accounts, deliberately:
#
# * ocotillo-gwl-export -- the job's runtime identity. Reads the replica,
#   writes the export bucket. Nothing else.
# * ocotillo-ingestion  -- the Dagster+ code location (main.tf). Gains only the
#   right to *run* the job with overrides and to read the step reports. It
#   cannot read the replica through the job's identity or write the bucket.

locals {
  gwl_export_envs = var.gwl_export
}

resource "google_storage_bucket" "gwl_export" {
  for_each = local.gwl_export_envs

  name     = "ocotillo-timeseries-${each.key}"
  project  = var.project_id
  location = var.bucket_location

  uniform_bucket_level_access = true
  # Public read is a separate, explicit switch (below). Until it is on, the
  # bucket refuses public grants outright.
  public_access_prevention = each.value.public_read ? "inherited" : "enforced"
  force_destroy            = false

  # Published files live at fixed paths and are overwritten in place, so
  # versioning is what keeps the previous file recoverable. Old versions go
  # after 30 days: the database is the record, not this bucket.
  versioning {
    enabled = true
  }

  lifecycle_rule {
    condition {
      days_since_noncurrent_time = 30
      with_state                 = "ARCHIVED"
    }
    action {
      type = "Delete"
    }
  }

  # Per-snapshot working files. Kept two weeks for debugging a failed check,
  # then deleted -- every one of them is reproducible from the database.
  lifecycle_rule {
    condition {
      age            = 14
      matches_prefix = ["_runs/"]
    }
    action {
      type = "Delete"
    }
  }

  # Browser downloads (STAC Browser, notebooks in JupyterLite) need CORS.
  cors {
    origin          = ["*"]
    method          = ["GET", "HEAD"]
    response_header = ["Content-Type", "Content-Length", "ETag", "Range"]
    max_age_seconds = 3600
  }

  labels = {
    component = "gwl-export"
    env       = each.key
  }
}

# Anyone may read. Off by default: turning it on publishes every object in the
# bucket -- including _runs/ and _state/, which hold only public-well data but
# are not meant as products. Settle OCO-79's SBAC question first.
resource "google_storage_bucket_iam_member" "gwl_export_public_read" {
  for_each = { for k, v in local.gwl_export_envs : k => v if v.public_read }

  bucket = google_storage_bucket.gwl_export[each.key].name
  role   = "roles/storage.objectViewer"
  member = "allUsers"
}

resource "google_service_account" "gwl_export" {
  count = length(local.gwl_export_envs) > 0 ? 1 : 0

  account_id   = "ocotillo-gwl-export"
  display_name = "Ocotillo groundwater level export"
  description  = "Runtime identity of the gwl-export Cloud Run job: reads the replica, writes the export bucket."
  project      = var.project_id
}

resource "google_storage_bucket_iam_member" "gwl_export_writer" {
  for_each = google_storage_bucket.gwl_export

  bucket = each.value.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.gwl_export[0].email}"
}

# See main.tf: objectAdmin lacks storage.buckets.get, and the client's
# existence check reads a denial as absence.
resource "google_storage_bucket_iam_member" "gwl_export_bucket_reader" {
  for_each = google_storage_bucket.gwl_export

  bucket = each.value.name
  role   = "roles/storage.legacyBucketReader"
  member = "serviceAccount:${google_service_account.gwl_export[0].email}"
}

resource "google_project_iam_member" "gwl_export_cloudsql_client" {
  count = length(local.gwl_export_envs) > 0 ? 1 : 0

  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.gwl_export[0].email}"
}

resource "google_project_iam_member" "gwl_export_cloudsql_instance_user" {
  count = length(local.gwl_export_envs) > 0 ? 1 : 0

  project = var.project_id
  role    = "roles/cloudsql.instanceUser"
  member  = "serviceAccount:${google_service_account.gwl_export[0].email}"
}

# IAM database users are created on the primary and replicate to its read
# replicas. Grants come from automated_ingestion/sql/gwl_export_role.sql.
resource "google_sql_user" "gwl_export" {
  count = length(local.gwl_export_envs) > 0 && var.cloud_sql_instance != null ? 1 : 0

  name     = trimsuffix(google_service_account.gwl_export[0].email, ".gserviceaccount.com")
  instance = var.cloud_sql_instance
  project  = var.project_id
  type     = "CLOUD_IAM_SERVICE_ACCOUNT"
}

resource "google_cloud_run_v2_job" "gwl_export" {
  for_each = local.gwl_export_envs

  name     = "gwl-export-${each.key}"
  project  = var.project_id
  location = var.gwl_export_region

  template {
    # Defaults only: Dagster overrides args, task count and timeout per step.
    task_count = 1

    template {
      service_account = google_service_account.gwl_export[0].email
      timeout         = "3600s"
      # Every step is repeatable, so one task retry is safe. Dagster retries
      # the whole step on top of this.
      max_retries = 1

      containers {
        image = each.value.image

        resources {
          limits = {
            cpu    = "2"
            memory = "4Gi"
          }
        }

        env {
          name  = "GWL_EXPORT_ROOT"
          value = "gs://${google_storage_bucket.gwl_export[each.key].name}"
        }
        env {
          name  = "DB_DRIVER"
          value = "cloudsql"
        }
        # The read replica, never the primary.
        env {
          name  = "CLOUD_SQL_INSTANCE_NAME"
          value = each.value.replica_connection_name
        }
        env {
          name  = "CLOUD_SQL_DATABASE"
          value = each.value.database
        }
        env {
          name  = "CLOUD_SQL_USER"
          value = trimsuffix(google_service_account.gwl_export[0].email, ".gserviceaccount.com")
        }
        env {
          name  = "CLOUD_SQL_IAM_AUTH"
          value = "1"
        }
        env {
          name  = "DB_POOL_SIZE"
          value = "1"
        }
        dynamic "env" {
          for_each = each.value.stac_api_url == "" ? [] : [each.value.stac_api_url]
          content {
            name  = "STAC_API_URL"
            value = env.value
          }
        }
        dynamic "env" {
          for_each = each.value.stac_api_audience == "" ? [] : [each.value.stac_api_audience]
          content {
            name  = "STAC_API_AUDIENCE"
            value = env.value
          }
        }
      }
    }
  }

  lifecycle {
    # Image tags are rolled forward by the build, not by Terraform.
    ignore_changes = [template[0].template[0].containers[0].image, client, client_version]
  }

  labels = {
    component = "gwl-export"
    env       = each.key
  }
}

# The Dagster+ code location may run the job with per-step overrides, and read
# its executions. Scoped to the job, not the project.
#
# If polling the long-running operation returns 403 in practice, the missing
# permission is run.operations.get; grant roles/run.viewer to this account at
# project level rather than widening anything here.
resource "google_cloud_run_v2_job_iam_member" "dagster_runs_gwl_export" {
  for_each = google_cloud_run_v2_job.gwl_export

  project  = var.project_id
  location = each.value.location
  name     = each.value.name
  role     = "roles/run.jobsExecutorWithOverrides"
  member   = "serviceAccount:${google_service_account.ingestion.email}"
}

# Dagster reads each step's report back for run metadata. Read only.
resource "google_storage_bucket_iam_member" "dagster_reads_gwl_reports" {
  for_each = google_storage_bucket.gwl_export

  bucket = each.value.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.ingestion.email}"
}

resource "google_storage_bucket_iam_member" "dagster_lists_gwl_reports" {
  for_each = google_storage_bucket.gwl_export

  bucket = each.value.name
  role   = "roles/storage.legacyBucketReader"
  member = "serviceAccount:${google_service_account.ingestion.email}"
}

output "gwl_export" {
  description = "Per environment: the values for GWL_EXPORT_ROOT and GWL_EXPORT_CLOUD_RUN_* on the Dagster+ code location."
  value = {
    for k, job in google_cloud_run_v2_job.gwl_export : k => {
      GWL_EXPORT_ROOT              = "gs://${google_storage_bucket.gwl_export[k].name}"
      GWL_EXPORT_CLOUD_RUN_PROJECT = var.project_id
      GWL_EXPORT_CLOUD_RUN_REGION  = job.location
      GWL_EXPORT_CLOUD_RUN_JOB     = job.name
    }
  }
}
