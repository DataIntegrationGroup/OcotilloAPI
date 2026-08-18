variable "project_id" {
  type        = string
  description = "GCP project that owns the ingestion buckets and service account."
}

variable "region" {
  type        = string
  description = "Default provider region."
  default     = "us-central1"
}

variable "bucket_location" {
  type        = string
  description = "Bucket location. US-CENTRAL1 keeps the raw zone in the same region as Cloud SQL, so replay reads do not cross regions."
  default     = "US-CENTRAL1"
}
