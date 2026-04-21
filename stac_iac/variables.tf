variable "project_id" {
  description = "GCP project id"
  type        = string
}

variable "region" {
  description = "Cloud Run region"
  type        = string
  default     = "us-central1"
}

variable "service_name" {
  description = "Cloud Run service name"
  type        = string
  default     = "stac-api"
}

variable "service_account_name" {
  description = "Service account id for the STAC API"
  type        = string
  default     = "stac-api"
}

variable "image" {
  description = "Container image for stac-fastapi-pgstac"
  type        = string

  validation {
    condition = can(regex(
      "^(?:docker\\.io/|(?:[a-z0-9-]+\\.)?gcr\\.io/|(?:[a-z0-9-]+-)?docker\\.pkg\\.dev/)",
      var.image,
    ))
    error_message = "Cloud Run only accepts images from docker.io, gcr.io, or Artifact Registry (<region>-docker.pkg.dev). Mirror GHCR images into Artifact Registry or use a supported registry path."
  }
}

variable "cloud_sql_connection_name" {
  description = "Cloud SQL instance connection name (project:region:instance)"
  type        = string
}

variable "postgres_database" {
  description = "Database name used by pgstac"
  type        = string
}

variable "postgres_user_secret_id" {
  description = "Secret Manager secret id for the database user"
  type        = string
}

variable "postgres_password_secret_id" {
  description = "Secret Manager secret id for the database password"
  type        = string
}

variable "cors_origins" {
  description = "Comma-delimited CORS origins passed to stac-fastapi-pgstac"
  type        = string
  default     = "*"
}

variable "container_port" {
  description = "Container listen port"
  type        = number
  default     = 8080
}

variable "min_instance_count" {
  description = "Minimum Cloud Run instances"
  type        = number
  default     = 0
}

variable "max_instance_count" {
  description = "Maximum Cloud Run instances"
  type        = number
  default     = 10
}

variable "ingress" {
  description = "Cloud Run ingress setting"
  type        = string
  default     = "INGRESS_TRAFFIC_ALL"
}

variable "allow_unauthenticated" {
  description = "Whether to allow public invoker access"
  type        = bool
  default     = true
}

variable "deletion_protection" {
  description = "Whether to enable Cloud Run deletion protection for the STAC API service"
  type        = bool
  default     = false
}
