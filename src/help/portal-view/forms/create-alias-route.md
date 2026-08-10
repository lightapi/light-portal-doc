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
| Public Alias | Non-deleted Alias that clients use as their stable model name. Publication validates its routes and provider material. | `kb-index` |
| Provider Deployment | Non-deleted Deployment that can serve the Alias. Its environment and embedding capabilities must match the Alias. | `nvidia-nemotron-3-embed-1b-loc` |
| Route Priority | Non-negative ordering value. Lower values are evaluated first and must be unique within the Alias. | `0` |
| Route Weight | Read-only value fixed at `1` for the current MVP. Weighted selection is not supported yet. | `1` |
| Fallback Enabled | Select when this Deployment should be used as a fallback rather than the preferred route. | `false` |
| Canary Percent | Read-only value fixed at `0` for the current MVP. Percentage-based canary routing is not supported yet. | `0` |
| Residency Conditions | JSON or YAML governance object describing route residency constraints. Use **Apply** after editing. Use `{}` when no approved restriction applies. Current preview does not evaluate arbitrary conditions. | `{}` |

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

Creating a Route does not by itself make the Alias publishable. The Alias and
Deployment must be present and internally consistent, and the Deployment needs
an effective Credential and effective Pricing. The backend generates the
Alias Route Id and aggregate version. The `active` state is backend-managed
through soft delete and is not part of this form.

## NVIDIA Knowledge Base routes

Submit this form twice: create one priority-zero Route for each Knowledge Base
Alias. For the functional demo, both Routes may select the same hosted NVIDIA
Deployment:

| Alias | Deployment | Priority | Fallback | Weight | Canary |
| --- | --- | ---: | --- | ---: | ---: |
| `kb-index` | `nvidia-nemotron-3-embed-1b-loc` | `0` | `false` | `1` | `0` |
| `kb-query` | `nvidia-nemotron-3-embed-1b-loc` | `0` | `false` | `1` | `0` |

First submission:

```json
{
  "publicAliasId": "select kb-index",
  "providerDeploymentId": "select nvidia-nemotron-3-embed-1b-loc",
  "routePriority": 0,
  "routeWeight": 1,
  "fallbackEnabled": false,
  "canaryPercent": 0,
  "residencyConditions": {}
}
```

Second submission uses the same values but selects `kb-query` as Public Alias.
The values shown for the two selectors are dropdown labels; the form submits
their UUIDs.

Use `{}` for Residency Conditions unless the Registration and Deployment carry
an approved region restriction. Every routed Deployment must match the Alias's
complete embedding-space contract, not only dimension `2048`.

Production-protected `kb_index` and `kb_query` lanes require genuinely separate
runtime and capacity/quota domains. Routing both Aliases through one free
shared NVIDIA Deployment is appropriate for this functional demo, but it is
not production-isolation evidence.
