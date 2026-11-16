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
  description = "Bucket location. Must match the Cloud SQL region so replay reads do not cross regions and pay egress. The dataservices instance is in us-west4."
  default     = "US-WEST4"
}

variable "cloud_sql_instance" {
  type        = string
  description = "Cloud SQL instance name for the IAM database user. Leave null to skip the database grants entirely -- useful before the instance is known, or when using password authentication instead."
  default     = null
}

variable "gwl_export" {
  type = map(object({
    image                   = string
    replica_connection_name = string
    database                = string
    stac_api_url            = optional(string, "")
    stac_api_audience       = optional(string, "")
    public_read             = optional(bool, false)
  }))
  description = "Groundwater level export (OCO-79) per environment, keyed production/staging. Empty creates nothing. replica_connection_name is the read replica's project:region:instance."
  default     = {}
}

variable "gwl_export_region" {
  type        = string
  description = "Region of the gwl-export Cloud Run job. Same region as Cloud SQL and the bucket, so the snapshot and uploads do not cross regions."
  default     = "us-west4"
}
