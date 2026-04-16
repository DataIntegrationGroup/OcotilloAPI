variable "project_id" {
  type        = string
  description = "GCP project ID"
}

variable "region" {
  type        = string
  description = "GCP region"
  default     = "us-west4"
}

variable "zone" {
  type        = string
  description = "GCP zone"
  default     = "us-west4-a"
}

variable "domain_name" {
  type        = string
  description = "Public DNS name for GeoServer"
  default     = "geoserver.newmexicowaterdata.org"
}

variable "network_name" {
  type        = string
  description = "VPC network name"
  default     = "default"
}

variable "machine_type" {
  type        = string
  description = "Compute Engine machine type"
  default     = "e2-standard-4"
}

variable "boot_disk_size_gb" {
  type        = number
  description = "Boot disk size in GB"
  default     = 30
}

variable "instance_image" {
  type        = string
  description = "Compute Engine boot image for the GeoServer VM"
  default     = "projects/debian-cloud/global/images/family/debian-12"
}

variable "geoserver_image" {
  type        = string
  description = "GeoServer container image"
  default     = "docker.osgeo.org/geoserver:2.28.0"
}

variable "geoserver_data_bucket" {
  type        = string
  description = "Existing GCS bucket name that backs the GeoServer data directory mount"
}

variable "geoserver_data_mount_point" {
  type        = string
  description = "Host mount point for the GeoServer data bucket"
  default     = "/mnt/disks/geoserver-data"
}

variable "geoserver_data_only_dir" {
  type        = string
  description = "Optional prefix within the bucket to mount as the GeoServer data directory"
  default     = "data_dir"
}

variable "geoserver_data_read_only" {
  type        = bool
  description = "Whether the GeoServer data bucket should be mounted read-only"
  default     = true
}

variable "admin_ssh_cidr" {
  type        = string
  description = "Admin public IP in CIDR notation, for example 203.0.113.10/32"
}
