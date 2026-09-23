#!/usr/bin/env bash
# Deploy the API to Cloud Run. Needs: gcloud CLI, a GCP project, billing enabled.
# Free-tier alternative that needs no billing account: see infra/README.md.
set -euo pipefail

PROJECT="${GOOGLE_CLOUD_PROJECT:?set GOOGLE_CLOUD_PROJECT}"
REGION="${REGION:-asia-south1}"
SERVICE="${SERVICE:-jansetu-api}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "Building ${SERVICE} from ${REPO_ROOT}"
cd "${REPO_ROOT}"

gcloud builds submit \
  --project "${PROJECT}" \
  --tag "gcr.io/${PROJECT}/${SERVICE}" \
  --config=/dev/null . 2>/dev/null || \
gcloud builds submit --project "${PROJECT}" --tag "gcr.io/${PROJECT}/${SERVICE}" .

gcloud run deploy "${SERVICE}" \
  --project "${PROJECT}" \
  --region "${REGION}" \
  --image "gcr.io/${PROJECT}/${SERVICE}" \
  --platform managed \
  --allow-unauthenticated \
  --memory 512Mi \
  --min-instances 0 \
  --set-env-vars "GEMINI_MODEL=gemini-2.0-flash" \
  --set-secrets "GEMINI_API_KEY=gemini-api-key:latest"

gcloud run services describe "${SERVICE}" --project "${PROJECT}" \
  --region "${REGION}" --format 'value(status.url)'
