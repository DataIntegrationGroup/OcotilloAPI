terraform {
  required_version = ">= 1.5.0"

  backend "gcs" {
    bucket = "waterdatainitiative-271000-tfstate-geoserver"
    prefix = "geoserver/prod"
  }

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.50"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = "~> 6.50"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
  zone    = var.zone
}

provider "google-beta" {
  project = var.project_id
  region  = var.region
  zone    = var.zone
}