#!/usr/bin/env bash
# Build the container with Cloud Build and deploy it to Cloud Run (no local Docker needed).
#
# Usage:  PROJECT_ID=my-gcp-project ./scripts/deploy_cloud_run.sh
# Optional: REGION (default europe-west1), SERVICE (default vendormatch-ai)
set -euo pipefail

: "${PROJECT_ID:?Set PROJECT_ID to your Google Cloud project id}"
REGION="${REGION:-europe-west1}"
SERVICE="${SERVICE:-vendormatch-ai}"

gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com \
  --project "$PROJECT_ID"

# Settings, and why:
#   --memory 2Gi           PyTorch + MiniLM need ~1 GB; headroom for /tmp (in-memory) SQLite.
#   --max-instances 1      SQLite is per instance: one instance keeps every visitor's demo consistent.
#   --min-instances 0      Scales to zero (no idle cost); the first visit after idle is a cold start.
#   --cpu-boost            Extra CPU during start-up, which is when the model is loaded.
#   --allow-unauthenticated  Public portfolio demo; there is no user data or login.
#   --timeout 300          Per-request limit; covers a request that arrives during a cold start.
#   --quiet                Non-interactive (accepts creating the Artifact Registry source repo).
gcloud run deploy "$SERVICE" \
  --quiet \
  --project "$PROJECT_ID" \
  --region "$REGION" \
  --source . \
  --allow-unauthenticated \
  --memory 2Gi \
  --cpu 1 \
  --cpu-boost \
  --concurrency 40 \
  --min-instances 0 \
  --max-instances 1 \
  --timeout 300

gcloud run services describe "$SERVICE" --project "$PROJECT_ID" --region "$REGION" --format "value(status.url)"
