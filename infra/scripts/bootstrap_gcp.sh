#!/usr/bin/env bash
# Idempotent GCP bootstrap. Enable APIs, create service account + buckets.
# This is OPTIONAL — the local stack works without it.
set -euo pipefail

: "${GCP_PROJECT_ID:?must set GCP_PROJECT_ID}"
: "${GCP_REGION:=us-central1}"

echo "==> Setting project to $GCP_PROJECT_ID"
gcloud config set project "$GCP_PROJECT_ID"

echo "==> Enabling APIs"
gcloud services enable \
  aiplatform.googleapis.com \
  run.googleapis.com \
  firestore.googleapis.com \
  storage.googleapis.com \
  secretmanager.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com

SA_NAME="methods-reconstructor"
SA_EMAIL="${SA_NAME}@${GCP_PROJECT_ID}.iam.gserviceaccount.com"

if ! gcloud iam service-accounts describe "$SA_EMAIL" >/dev/null 2>&1; then
  echo "==> Creating service account $SA_EMAIL"
  gcloud iam service-accounts create "$SA_NAME" --display-name="Methods Reconstructor"
fi

for role in roles/aiplatform.user roles/datastore.user roles/storage.objectAdmin roles/run.invoker; do
  gcloud projects add-iam-policy-binding "$GCP_PROJECT_ID" \
    --member="serviceAccount:$SA_EMAIL" --role="$role" --condition=None --quiet
done

for bucket in "${GCP_PROJECT_ID}-mr-uploads" "${GCP_PROJECT_ID}-mr-exports"; do
  if ! gcloud storage buckets describe "gs://${bucket}" >/dev/null 2>&1; then
    echo "==> Creating bucket gs://${bucket}"
    gcloud storage buckets create "gs://${bucket}" --location="$GCP_REGION"
  fi
done

if ! gcloud firestore databases describe --database='(default)' >/dev/null 2>&1; then
  echo "==> Creating Firestore database in $GCP_REGION"
  gcloud firestore databases create --location="$GCP_REGION"
fi

echo
echo "Done. Add the following to your .env:"
echo "  GCP_PROJECT_ID=$GCP_PROJECT_ID"
echo "  GCP_REGION=$GCP_REGION"
echo "  GCS_BUCKET_UPLOADS=${GCP_PROJECT_ID}-mr-uploads"
echo "  GCS_BUCKET_EXPORTS=${GCP_PROJECT_ID}-mr-exports"
