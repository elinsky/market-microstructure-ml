# Terraform configuration for QuoteWatch production infrastructure
#
# This provisions:
# - GCS bucket for Iceberg warehouse (Parquet files)
# - Cloud SQL Postgres instance for Iceberg catalog
# - Secret Manager secret for database connection string
# - IAM bindings for Cloud Run service account

terraform {
  required_version = ">= 1.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# -----------------------------------------------------------------------------
# GCS Bucket for Iceberg Warehouse
# -----------------------------------------------------------------------------

resource "google_storage_bucket" "warehouse" {
  name          = var.warehouse_bucket_name
  location      = var.region
  storage_class = "STANDARD"

  # Prevent accidental deletion of data
  force_destroy = false

  # Enable versioning for safety (can recover deleted files)
  versioning {
    enabled = true
  }

  # Uniform bucket-level access (recommended)
  uniform_bucket_level_access = true

  labels = {
    environment = "production"
    app         = "quotewatch"
  }
}

# -----------------------------------------------------------------------------
# Cloud SQL Postgres Instance for Iceberg Catalog
# -----------------------------------------------------------------------------

resource "google_sql_database_instance" "iceberg_catalog" {
  name             = var.cloudsql_instance_name
  database_version = "POSTGRES_16"
  region           = var.region

  # Wait for SQL Admin API to be enabled
  depends_on = [google_project_service.sqladmin]

  # Deletion protection - set to false only when destroying
  deletion_protection = true

  settings {
    tier = "db-f1-micro"

    # Public IP enabled but locked down - no authorized networks
    # Cloud Run connects via Unix socket at /cloudsql/CONNECTION_NAME
    # This goes through Google's internal network, not the public internet
    ip_configuration {
      ipv4_enabled = true
      # No authorized_networks = locked down, only Unix socket access
    }

    backup_configuration {
      enabled    = true
      start_time = "03:00" # 3 AM UTC
    }

    database_flags {
      name  = "max_connections"
      value = "50"
    }

    user_labels = {
      environment = "production"
      app         = "quotewatch"
    }
  }
}

# Database for Iceberg metadata
resource "google_sql_database" "iceberg" {
  name     = "iceberg"
  instance = google_sql_database_instance.iceberg_catalog.name
}

# Generate random password for iceberg user
resource "random_password" "iceberg_password" {
  length  = 32
  special = false # Avoid special chars that cause connection string issues
}

# Dedicated user for Iceberg catalog
resource "google_sql_user" "iceberg" {
  name     = "iceberg"
  instance = google_sql_database_instance.iceberg_catalog.name
  password = random_password.iceberg_password.result
}

# -----------------------------------------------------------------------------
# Secret Manager - Database Connection String
# -----------------------------------------------------------------------------

resource "google_secret_manager_secret" "iceberg_catalog_uri" {
  secret_id = "iceberg-catalog-uri"

  # Wait for Secret Manager API to be enabled
  depends_on = [google_project_service.secretmanager]

  replication {
    auto {}
  }

  labels = {
    environment = "production"
    app         = "quotewatch"
  }
}

# The connection string uses Unix socket path for Cloud Run
# Format: postgresql+psycopg2://user:pass@/database?host=/cloudsql/CONNECTION_NAME
resource "google_secret_manager_secret_version" "iceberg_catalog_uri" {
  secret = google_secret_manager_secret.iceberg_catalog_uri.id
  secret_data = "postgresql+psycopg2://${google_sql_user.iceberg.name}:${random_password.iceberg_password.result}@/${google_sql_database.iceberg.name}?host=/cloudsql/${google_sql_database_instance.iceberg_catalog.connection_name}"
}

# -----------------------------------------------------------------------------
# IAM Bindings for Cloud Run Service Account
# -----------------------------------------------------------------------------

# Get project info to construct default service account email
data "google_project" "current" {
}

# Default compute service account: PROJECT_NUMBER-compute@developer.gserviceaccount.com
locals {
  compute_service_account = "${data.google_project.current.number}-compute@developer.gserviceaccount.com"
}

# Cloud Run needs access to GCS bucket
resource "google_storage_bucket_iam_member" "cloud_run_storage" {
  bucket = google_storage_bucket.warehouse.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${local.compute_service_account}"
}

# Cloud Run needs access to Cloud SQL
resource "google_project_iam_member" "cloud_run_cloudsql" {
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${local.compute_service_account}"
}

# Cloud Run needs access to secrets
resource "google_secret_manager_secret_iam_member" "cloud_run_secret_access" {
  secret_id = google_secret_manager_secret.iceberg_catalog_uri.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${local.compute_service_account}"
}

# -----------------------------------------------------------------------------
# Enable Required APIs
# -----------------------------------------------------------------------------

resource "google_project_service" "sqladmin" {
  service            = "sqladmin.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "secretmanager" {
  service            = "secretmanager.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "cloudscheduler" {
  service            = "cloudscheduler.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "cloudfunctions" {
  service            = "cloudfunctions.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "cloudbuild" {
  service            = "cloudbuild.googleapis.com"
  disable_on_destroy = false
}

# -----------------------------------------------------------------------------
# Cloud Function for Snapshot Expiration
# -----------------------------------------------------------------------------
#
# The Cloud Function is deployed automatically via CI on merge to main.
# See .github/workflows/ci.yml for the deploy step.
# Source code: functions/expire_snapshots/

# Cloud Scheduler job to trigger expiration weekly
resource "google_cloud_scheduler_job" "expire_snapshots" {
  name      = "expire-snapshots-weekly"
  region    = var.region
  schedule  = "0 4 * * 0" # 4 AM UTC every Sunday
  time_zone = "UTC"

  depends_on = [google_project_service.cloudscheduler]

  http_target {
    uri         = "https://${var.region}-${var.project_id}.cloudfunctions.net/expire-snapshots"
    http_method = "POST"

    oidc_token {
      service_account_email = local.compute_service_account
    }
  }

  retry_config {
    retry_count = 1
  }
}