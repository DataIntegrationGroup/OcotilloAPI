# Raw-zone storage for the automated ingestion pipeline.
#
# Two buckets, one per environment, plus the service account the Dagster+ code
# location uses to write to them. Deliberately narrow: this configuration owns
# ingestion storage and nothing else, so a mistake here cannot affect the API's
# uploads bucket or any other project resource.
#
# Not applied by CI. Run it by hand, review the plan, and record the applied
# state -- see README.md.

terraform {
  required_version = ">= 1.5"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

locals {
  environments = toset(["production", "staging"])
}

resource "google_storage_bucket" "ingestion_raw" {
  for_each = local.environments

  name     = "ocotillo-ingestion-${each.key}"
  project  = var.project_id
  location = var.bucket_location

  # The raw zone is the replay source for Mode B backfill: reprocessing a
  # mapping bug must not depend on the vendor still serving that window.
  # Deleting an object here is therefore a data-loss event, not a cleanup.
  force_destroy               = false
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"

  versioning {
    enabled = true
  }

  # Raw payloads are read constantly for the first month (recent-window
  # replays), then almost never. Age-out to colder classes rather than
  # deleting: an old window is exactly what a historical replay needs.
  lifecycle_rule {
    condition {
      age = 30
    }
    action {
      type          = "SetStorageClass"
      storage_class = "NEARLINE"
    }
  }

  lifecycle_rule {
    condition {
      age = 365
    }
    action {
      type          = "SetStorageClass"
      storage_class = "COLDLINE"
    }
  }

  # Bucket versioning would otherwise retain every superseded object forever.
  lifecycle_rule {
    condition {
      num_newer_versions = 3
      with_state         = "ARCHIVED"
    }
    action {
      type = "Delete"
    }
  }

  labels = {
    component = "automated-ingestion"
    env       = each.key
  }
}

resource "google_service_account" "ingestion" {
  account_id   = "ocotillo-ingestion"
  display_name = "Ocotillo automated ingestion"
  description  = "Writes raw vendor payloads to the ingestion buckets from the Dagster+ code location."
  project      = var.project_id
}

# Scoped to the two buckets, not granted at project level. objectAdmin rather
# than objectCreator because a replay overwrite rewrites an existing object.
resource "google_storage_bucket_iam_member" "ingestion_object_admin" {
  for_each = google_storage_bucket.ingestion_raw

  bucket = each.value.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.ingestion.email}"
}
