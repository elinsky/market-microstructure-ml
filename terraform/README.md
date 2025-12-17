# Terraform Infrastructure

Provisions GCP resources for QuoteWatch production data persistence.

## Resources Created

| Resource | Purpose |
|----------|---------|
| GCS bucket `quotewatch-data` | Iceberg warehouse (Parquet files) |
| Cloud SQL Postgres `quotewatch-iceberg` | Iceberg catalog metadata |
| Secret Manager `iceberg-catalog-uri` | Database connection string |
| IAM bindings | Cloud Run access to storage, database, secrets |

## Prerequisites

1. Install Terraform >= 1.0
2. Authenticate to GCP: `gcloud auth application-default login`
3. Ensure you have `Owner` or equivalent permissions on `quotewatch-prod`

## Usage

```bash
cd terraform

# Initialize Terraform
terraform init

# Preview changes
terraform plan

# Apply changes
terraform apply

# View outputs (needed for CI/CD config)
terraform output
```

## Outputs

After applying, you'll need these values:

| Output | Used for |
|--------|----------|
| `cloudsql_connection_name` | `--add-cloudsql-instances` flag in deploy |
| `secret_name` | `--set-secrets` flag in deploy |
| `warehouse_uri` | `ICEBERG_WAREHOUSE` env var |

## Destroying Resources

To tear down infrastructure (data will be lost!):

```bash
# First, disable deletion protection on Cloud SQL
# Edit main.tf: deletion_protection = false
terraform apply

# Then destroy
terraform destroy
```

## State Management

State is stored locally in `terraform.tfstate` (gitignored). Keep this file safe - losing it means Terraform can't manage existing resources.