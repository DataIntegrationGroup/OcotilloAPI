output "bucket_names" {
  description = "Raw-zone bucket per environment. The matching value goes into INGESTION_GCS_BUCKET on the Dagster+ code location."
  value       = { for k, b in google_storage_bucket.ingestion_raw : k => b.name }
}

output "service_account_email" {
  description = "Ingestion service account. Grant nothing else to it without revisiting the least-privilege rationale in README.md."
  value       = google_service_account.ingestion.email
}
