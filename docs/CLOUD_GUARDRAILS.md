# Cloud Guardrails

Methods Reconstructor uses the Google Cloud project `project-49fbac7c-86d0-4054-af8` for Gemini/Vertex AI during local and hosted experiments.

## Budget

- Billing account: `011E18-476678-53D57B`
- Budget ID: `959db45d-5772-4d0b-88d6-87228645f729`
- Display name: `Methods Reconstructor $150 guardrail`
- Budget amount: `$150`
- Budget scope: `projects/3209583131`
- Credit treatment: `EXCLUDE_ALL_CREDITS`
- Thresholds: 50%, 80%, 90%, and 100% current spend

## Kill Switch

Budget alerts publish to:

```text
projects/project-49fbac7c-86d0-4054-af8/topics/budget-kill-switch
```

That topic triggers the Gen 2 Cloud Function:

```text
disable-billing-on-budget
```

The function runs as:

```text
billing-kill-switch@project-49fbac7c-86d0-4054-af8.iam.gserviceaccount.com
```

When a budget Pub/Sub message reports `costAmount >= budgetAmount`, the function calls the Cloud Billing API and unlinks the project from its billing account.

This is a guardrail, not a hard real-time cap. Google Cloud budget notifications can lag behind actual spend.
