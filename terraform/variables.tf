# Input variables for QuoteWatch infrastructure

variable "project_id" {
  description = "GCP project ID"
  type        = string
  default     = "quotewatch-prod"
}

variable "region" {
  description = "GCP region for resources"
  type        = string
  default     = "us-central1"
}

variable "warehouse_bucket_name" {
  description = "Name of GCS bucket for Iceberg warehouse"
  type        = string
  default     = "quotewatch-data"
}

variable "cloudsql_instance_name" {
  description = "Name of Cloud SQL instance for Iceberg catalog"
  type        = string
  default     = "quotewatch-iceberg"
}