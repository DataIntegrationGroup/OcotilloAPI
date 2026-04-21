locals {
  service_labels = {
    service = var.service_name
    stack   = "stac"
  }

  cloud_sql_proxy_image = "gcr.io/cloud-sql-connectors/cloud-sql-proxy:2.19.0"
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
  name                = var.service_name
  location            = var.region
  ingress             = var.ingress
  deletion_protection = var.deletion_protection

  template {
    service_account = google_service_account.stac_api.email
    labels          = local.service_labels

    scaling {
      min_instance_count = var.min_instance_count
      max_instance_count = var.max_instance_count
    }

    containers {
      name       = "stac-api"
      image      = var.image
      depends_on = ["cloud-sql-proxy"]

      ports {
        container_port = var.container_port
      }

      env {
        name  = "PGHOST"
        value = "127.0.0.1"
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

      env {
        name  = "CORS_ORIGINS"
        value = var.cors_origins
      }
    }

    containers {
      name  = "cloud-sql-proxy"
      image = local.cloud_sql_proxy_image
      args = [
        "--address",
        "0.0.0.0",
        "--port",
        "5432",
        var.cloud_sql_connection_name,
      ]

      startup_probe {
        tcp_socket {
          port = 5432
        }

        period_seconds    = 5
        timeout_seconds   = 3
        failure_threshold = 12
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
