locals {
  service_labels = {
    service = var.service_name
    stack   = "stac"
  }
}

resource "google_service_account" "stac_api" {
  account_id   = var.service_account_name
  display_name = "STAC API service account"
}

resource "google_project_iam_member" "cloudsql_client" {
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.stac_api.email}"
}

resource "google_project_iam_member" "secret_accessor" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.stac_api.email}"
}

resource "google_cloud_run_v2_service" "stac_api" {
  name     = var.service_name
  location = var.region
  ingress  = var.ingress

  template {
    service_account = google_service_account.stac_api.email
    labels          = local.service_labels

    scaling {
      min_instance_count = var.min_instance_count
      max_instance_count = var.max_instance_count
    }

    volumes {
      name = "cloudsql"
      cloud_sql_instance {
        instances = [var.cloud_sql_connection_name]
      }
    }

    containers {
      image = var.image

      ports {
        container_port = var.container_port
      }

      volume_mounts {
        name       = "cloudsql"
        mount_path = "/cloudsql"
      }

      env {
        name  = "PGHOST"
        value = "/cloudsql/${var.cloud_sql_connection_name}"
      }

      env {
        name  = "PGPORT"
        value = "5432"
      }

      env {
        name  = "PGDATABASE"
        value = var.postgres_database
      }

      env {
        name = "PGUSER"
        value_source {
          secret_key_ref {
            secret  = var.postgres_user_secret_id
            version = "latest"
          }
        }
      }

      env {
        name = "PGPASSWORD"
        value_source {
          secret_key_ref {
            secret  = var.postgres_password_secret_id
            version = "latest"
          }
        }
      }
    }
  }

  depends_on = [
    google_project_iam_member.cloudsql_client,
    google_project_iam_member.secret_accessor,
  ]
}

resource "google_cloud_run_v2_service_iam_member" "public_invoker" {
  count    = var.allow_unauthenticated ? 1 : 0
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.stac_api.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}
