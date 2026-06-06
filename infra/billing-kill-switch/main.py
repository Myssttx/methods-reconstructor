import base64
import json
import os

import functions_framework
from google.api_core import exceptions
from google.cloud import billing_v1


PROJECT_ID = os.environ["TARGET_PROJECT_ID"]
PROJECT_NAME = f"projects/{PROJECT_ID}"


@functions_framework.cloud_event
def stop_billing(cloud_event):
    message = cloud_event.data.get("message", {})
    encoded = message.get("data", "")
    payload = json.loads(base64.b64decode(encoded).decode("utf-8")) if encoded else {}

    cost_amount = float(payload.get("costAmount", 0))
    budget_amount = float(payload.get("budgetAmount", 0))
    print(f"Budget notification received: cost={cost_amount}, budget={budget_amount}")

    if budget_amount <= 0:
        print("Budget amount missing or invalid; no action taken.")
        return

    if cost_amount < budget_amount:
        print("Current cost is below budget; no action taken.")
        return

    client = billing_v1.CloudBillingClient()
    info = client.get_project_billing_info(name=PROJECT_NAME)
    if not info.billing_enabled:
        print("Billing is already disabled.")
        return

    print(f"Disabling billing for {PROJECT_NAME}")
    try:
        response = client.update_project_billing_info(
            name=PROJECT_NAME,
            project_billing_info=billing_v1.ProjectBillingInfo(billing_account_name=""),
        )
        print(f"Billing disabled: {response}")
    except exceptions.PermissionDenied as exc:
        print(f"Permission denied while disabling billing: {exc}")
        raise
