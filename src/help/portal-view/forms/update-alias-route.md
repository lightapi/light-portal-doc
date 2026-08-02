# Update Alias Route

Use this form to change the Deployment connected to an Alias, reorder a Route,
or change its fallback and residency metadata. Updates affect control-plane
configuration; a gateway sees the change only after a valid new publication is
created and applied.

The **Host Id**, **Alias Route Id**, **Route Weight**, **Canary Percent**, and
**Aggregate Version** are read-only. Weight and canary are fixed by the current
MVP, while the aggregate version prevents an update from silently overwriting
a newer change.

## Fields

| Field | Description | Example |
| --- | --- | --- |
| Host Id | Read-only tenant boundary supplied by the portal. | `10000000-0000-4000-8000-000000000001` |
| Alias Route Id | Read-only identifier generated when the Route was created. | `40000000-0000-4000-8000-000000000040` |
| Public Alias | Alias served by this Route. Changing it revalidates the selected Deployment against the new Alias. | `governed-chat` (`20000000-0000-4000-8000-000000000020`) |
| Provider Deployment | Provider endpoint used by the Route. It must match the Alias environment and required capabilities. | `anthropic-prod-ca` (`30000000-0000-4000-8000-000000000031`) |
| Route Priority | Non-negative ordering value; lower values come first. It must be unique among Routes for the Alias. | `10` |
| Route Weight | Read-only value fixed at `1`. Weighted traffic splitting is not supported by the current MVP. | `1` |
| Fallback Enabled | Whether this Route is intended as a fallback-only choice. | `true` |
| Canary Percent | Read-only value fixed at `0`. Percentage canary routing is not supported by the current MVP. | `0` |
| Residency Conditions | JSON or YAML governance object for residency requirements. Choose **Apply** after editing. Current preview does not evaluate it; runtime enforcement depends on compiler and gateway support. | `{"regions":["ca-central-1"]}` |
| Aggregate Version | Read-only record version sent with the update for optimistic concurrency. Reload the Route if another update has advanced it. | `6` |

## Example

This update makes the Route a Canadian fallback with priority `10`:

```json
{
  "aliasRouteId": "40000000-0000-4000-8000-000000000040",
  "publicAliasId": "20000000-0000-4000-8000-000000000020",
  "providerDeploymentId": "30000000-0000-4000-8000-000000000031",
  "routePriority": 10,
  "routeWeight": 1,
  "fallbackEnabled": true,
  "canaryPercent": 0,
  "residencyConditions": {
    "regions": ["ca-central-1"]
  },
  "aggregateVersion": 6
}
```

The Route preview reports ordering and eligibility, but it does not execute a
provider request or guarantee that fallback will succeed at runtime. Before
publication, confirm that at least one Route for every active Alias has an
active, conformant, credentialed, and priced Deployment. The `active` state is
backend-managed through soft delete and is not part of this form.
