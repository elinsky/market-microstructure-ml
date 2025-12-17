# Deployment

How QuoteWatch is deployed to Google Cloud Run.

## Overview

- **Hosting:** Google Cloud Run (us-central1)
- **CI/CD:** GitHub Actions (auto-deploy on merge to main)
- **Authentication:** Workload Identity Federation (no service account keys)

## Auto-Deploy Pipeline

When a PR is merged to `main`:
1. GitHub Actions CI workflow triggers (`.github/workflows/ci.yml`)
2. `lint` and `test` jobs run in parallel
3. If both pass, `deploy` job runs
4. Deploy job authenticates to GCP via Workload Identity Federation
5. `gcloud run deploy` builds and deploys the container
6. Cloud Run performs zero-downtime rolling deployment

On PRs, only `lint` and `test` run - no deployment.

## Manual Deployment

For emergencies or testing:

```bash
gcloud run deploy quotewatch \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --memory 512Mi \
  --cpu 1 \
  --min-instances 1 \
  --max-instances 1 \
  --timeout 3600 \
  --concurrency 80
```

## Rollback

Cloud Run keeps revision history. To roll back:

```bash
# List recent revisions
gcloud run revisions list --service=quotewatch --region=us-central1

# Route traffic to a previous revision
gcloud run services update-traffic quotewatch \
  --region=us-central1 \
  --to-revisions=REVISION_NAME=100
```

---

## GCP Infrastructure Setup

One-time setup for Workload Identity Federation. This allows GitHub Actions to authenticate to GCP without service account keys.

### Configuration

| Setting | Value |
|---------|-------|
| GCP Project ID | `quotewatch-prod` |
| GCP Project Number | *(run `gcloud projects describe quotewatch-prod --format="value(projectNumber)"`)* |
| GitHub Repo | `elinsky/market-microstructure-ml` |
| Workload Identity Pool | `github-pool` |
| OIDC Provider | `github-provider` |
| Service Account | `github-deploy@quotewatch-prod.iam.gserviceaccount.com` |

### 1. Enable Required APIs

```bash
gcloud services enable iamcredentials.googleapis.com
```

### 2. Create Workload Identity Pool

```bash
gcloud iam workload-identity-pools create "github-pool" \
  --location="global" \
  --display-name="GitHub Actions Pool"
```

### 3. Create OIDC Provider for GitHub

```bash
gcloud iam workload-identity-pools providers create-oidc "github-provider" \
  --location="global" \
  --workload-identity-pool="github-pool" \
  --display-name="GitHub Provider" \
  --attribute-mapping="google.subject=assertion.sub,attribute.actor=assertion.actor,attribute.repository=assertion.repository" \
  --attribute-condition="assertion.repository=='elinsky/market-microstructure-ml'" \
  --issuer-uri="https://token.actions.githubusercontent.com"
```

### 4. Create Service Account

```bash
gcloud iam service-accounts create "github-deploy" \
  --display-name="GitHub Actions Deploy"
```

### 5. Grant IAM Roles to Service Account

```bash
PROJECT_ID="quotewatch-prod"

# Cloud Run Admin - deploy services
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
  --member="serviceAccount:github-deploy@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/run.admin"

# Storage Admin - upload source code during build
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
  --member="serviceAccount:github-deploy@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/storage.admin"

# Service Account User - act as compute service account
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
  --member="serviceAccount:github-deploy@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/iam.serviceAccountUser"
```

### 6. Allow GitHub Actions to Impersonate Service Account

```bash
PROJECT_ID="quotewatch-prod"
PROJECT_NUMBER="<from step above>"
REPO="elinsky/market-microstructure-ml"

gcloud iam service-accounts add-iam-policy-binding \
  "github-deploy@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/github-pool/attribute.repository/${REPO}"
```

### 7. Configure GitHub Actions Variables

In GitHub repo settings (Settings > Secrets and variables > Actions > Variables):

| Variable | Value |
|----------|-------|
| `GCP_PROJECT_ID` | `quotewatch-prod` |
| `GCP_PROJECT_NUMBER` | *(from step above)* |
| `WIF_PROVIDER` | `projects/<PROJECT_NUMBER>/locations/global/workloadIdentityPools/github-pool/providers/github-provider` |
| `WIF_SERVICE_ACCOUNT` | `github-deploy@quotewatch-prod.iam.gserviceaccount.com` |

---

## How Workload Identity Federation Works

1. GitHub Actions requests an OIDC token from GitHub
2. The workflow sends this token to GCP's Security Token Service
3. GCP validates the token against GitHub's OIDC issuer
4. GCP checks the attribute condition (must be from `elinsky/market-microstructure-ml`)
5. GCP issues short-lived credentials (~1 hour) for the service account
6. The workflow uses these credentials to deploy

No persistent secrets. No keys to rotate. Credentials expire automatically.

---

## References

- [Workload Identity Federation](https://cloud.google.com/iam/docs/workload-identity-federation)
- [google-github-actions/auth](https://github.com/google-github-actions/auth)
- [Cloud Run Deployment](https://cloud.google.com/run/docs/deploying)