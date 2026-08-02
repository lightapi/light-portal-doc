# Create Alias Route

Use this form to connect a public Alias to a Provider Deployment. Together,
the active Routes for an Alias define its ordered primary and fallback choices.
Applications continue to send the Alias name; they never select the Deployment
ID directly.

The selected Alias and Deployment must belong to the current host. The
Deployment registration must use the Alias environment, and its model
capabilities plus registration restrictions must satisfy the Alias's required
capabilities.

## Fields

| Field | Description | Example |
| --- | --- | --- |
| Host Id | Read-only tenant boundary supplied by the portal. Both referenced records must belong to this host. | `10000000-0000-4000-8000-000000000001` |
| Public Alias | Active Alias that clients use as their stable model name. | `governed-chat` (`20000000-0000-4000-8000-000000000020`) |
| Provider Deployment | Active provider endpoint that can serve the Alias. The command validates its environment and capabilities against the Alias. | `openai-prod-ca` (`30000000-0000-4000-8000-000000000030`) |
| Route Priority | Non-negative ordering value. Lower values are evaluated first and must be unique within the Alias. | `0` |
| Route Weight | Read-only value fixed at `1` for the current MVP. Weighted selection is not supported yet. | `1` |
| Fallback Enabled | Select when this Deployment should be used as a fallback rather than the preferred route. | `false` |
| Canary Percent | Read-only value fixed at `0` for the current MVP. Percentage-based canary routing is not supported yet. | `0` |
| Residency Conditions | JSON or YAML governance object describing route residency constraints. Use **Apply** after editing. Current preview does not evaluate it, and runtime enforcement depends on compiler and gateway support for the chosen vocabulary. | `{"regions":["ca-central-1"]}` |

An Alias cannot contain the same Deployment twice. It also cannot contain two
Routes with the same priority. A common convention is `0` for the preferred
route and increasing values such as `10` and `20` for subsequent choices.

## Primary Route Example

```json
{
  "publicAliasId": "20000000-0000-4000-8000-000000000020",
  "providerDeploymentId": "30000000-0000-4000-8000-000000000030",
  "routePriority": 0,
  "routeWeight": 1,
  "fallbackEnabled": false,
  "canaryPercent": 0,
  "residencyConditions": {
    "regions": ["ca-central-1"]
  }
}
```

## Fallback Route Example

For a second compatible Deployment, use another unique priority and enable
fallback:

```json
{
  "publicAliasId": "20000000-0000-4000-8000-000000000020",
  "providerDeploymentId": "30000000-0000-4000-8000-000000000031",
  "routePriority": 10,
  "routeWeight": 1,
  "fallbackEnabled": true,
  "canaryPercent": 0,
  "residencyConditions": {
    "regions": ["ca-central-1"]
  }
}
```

Creating a Route does not by itself make the Alias publishable. The selected
Deployment must also be active, have current passing conformance, an effective
Credential, and effective Pricing. The backend generates the Alias Route Id
and aggregate version. The `active` state is backend-managed through soft
delete and is not part of this form.
