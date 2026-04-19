output "service_url" {
  description = "Cloud Run URL for the STAC API"
  value       = google_cloud_run_v2_service.stac_api.uri
}

output "service_account_email" {
  description = "Service account used by Cloud Run"
  value       = google_service_account.stac_api.email
}
