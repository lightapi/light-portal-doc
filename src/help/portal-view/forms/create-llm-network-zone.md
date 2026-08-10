# Create Network Zone

Use `/app/form/createLlmNetworkZone` to create an administrator-owned outbound
allowlist for private provider Endpoints. A Network Zone is not required for a
public HTTPS provider.

## Fields

| Field | Required | Description |
| --- | --- | --- |
| Host Id | Yes | Read-only host that owns the Zone and any Endpoint that selects it. |
| Zone Name | Yes | Stable operator-friendly name. |
| Allowed DNS Names | Yes | JSON array of private provider DNS names. Use `[]` only when CIDRs carry the complete allowlist. |
| Allowed CIDRs | Yes | JSON array of approved private IPv4 or IPv6 ranges. Use `[]` only when DNS names carry the complete allowlist. |
| Allowed Ports | Yes | Non-empty JSON array of integer ports from 1 through 65535. |
| Allow Private TLS | Yes | Permit `PRIVATE_TLS` Endpoints in this Zone. |
| Allow Private Plaintext | Yes | Permit explicitly acknowledged `PRIVATE_PLAINTEXT`; keep disabled unless an administrator accepts the risk. |
| Lifecycle Status | Yes | New Zones start as `DRAFT`. |

Example for a private TLS provider:

```json
{
  "zoneName": "private-embedding-provider",
  "dnsNames": ["embedding.internal.example.com"],
  "cidrs": ["10.42.0.0/16"],
  "allowedPorts": [443],
  "allowPrivateTls": true,
  "allowPrivatePlaintext": false,
  "lifecycleStatus": "DRAFT"
}
```

Choose **Apply** after editing each structured array. Portal generates the
Network Zone Id and aggregate version.

## NVIDIA hosted endpoint

Do not create a Network Zone for
`https://integrate.api.nvidia.com/v1`. Its Endpoint uses `PUBLIC_TLS`, so the
Endpoint must leave Network Zone and trust-bundle fields empty. Network Zone
rows are real administrator configuration, not one placeholder row per
Account.

