#!/usr/bin/env bash
# Build and publish the dashboard to Firebase Hosting (free Spark plan).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}/frontend"

: "${VITE_API_BASE:?set VITE_API_BASE to the deployed API URL}"
npm ci
npm run build
npx firebase-tools deploy --only hosting
