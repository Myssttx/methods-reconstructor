# Deployment

The repository deploys as two services:

1. **GitHub Pages** hosts the static Next.js frontend.
2. **Google Cloud Run** hosts FastAPI, Vertex AI access, Firestore job state,
   Vertex text embeddings, and the Elastic client.

GitHub Pages cannot run Python, Vertex AI, Elasticsearch, background jobs, or
SSE. A frontend-only Pages deployment will render the site but the tool will
not work until `BACKEND_URL` points to Cloud Run.

## Required GitHub repository variables

| Variable | Example |
|---|---|
| `GCP_PROJECT_ID` | `project-49fbac7c-86d0-4054-af8` |
| `GCP_REGION` | `us-central1` |
| `CLOUD_RUN_SERVICE` | `methods-reconstructor` |
| `ARTIFACT_REGISTRY_REPOSITORY` | `methods-reconstructor` |
| `CLOUD_RUN_RUNTIME_SERVICE_ACCOUNT` | `methods-reconstructor@PROJECT.iam.gserviceaccount.com` |
| `FRONTEND_ORIGIN` | `https://myssttx.github.io` |
| `BACKEND_URL` | Cloud Run service URL, without a trailing slash |
| `ELASTIC_CLOUD_ID_SECRET` | Name of the GCP Secret Manager secret |
| `ELASTIC_API_KEY_SECRET` | Name of the GCP Secret Manager secret |

## Required GitHub secrets

- `GCP_WORKLOAD_IDENTITY_PROVIDER`
- `GCP_DEPLOY_SERVICE_ACCOUNT`

These authenticate GitHub Actions to GCP through Workload Identity Federation.
Do not store service-account JSON keys in the repository.

## GCP prerequisites

- Artifact Registry repository created in `GCP_REGION`.
- Firestore default database created.
- Secret Manager entries for Elastic Cloud ID and API key.
- Runtime service account granted:
  - `roles/aiplatform.user`
  - `roles/datastore.user`
  - `roles/secretmanager.secretAccessor`
- GitHub deploy service account granted Artifact Registry writer and Cloud Run
  deployment permissions.

Deploy the backend workflow first, set `BACKEND_URL` to its printed service
URL, then run the Pages workflow. In GitHub repository settings, select
**GitHub Actions** as the Pages source.
