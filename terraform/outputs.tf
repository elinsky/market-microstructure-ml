# Outputs for QuoteWatch infrastructure
#
# These values are needed to configure the application and CI/CD pipeline.

output "warehouse_bucket" {
  description = "GCS bucket name for Iceberg warehouse"
  value       = google_storage_bucket.warehouse.name
}

output "warehouse_uri" {
  description = "GCS URI for Iceberg warehouse (use as ICEBERG_WAREHOUSE)"
  value       = "gs://${google_storage_bucket.warehouse.name}/warehouse"
}

output "cloudsql_connection_name" {
  description = "Cloud SQL connection name (for --add-cloudsql-instances flag)"
  value       = google_sql_database_instance.iceberg_catalog.connection_name
}

output "secret_name" {
  description = "Secret Manager secret name for catalog URI"
  value       = google_secret_manager_secret.iceberg_catalog_uri.secret_id
}

output "secret_version" {
  description = "Full path to latest secret version (for Cloud Run)"
  value       = "${google_secret_manager_secret.iceberg_catalog_uri.name}/versions/latest"
}