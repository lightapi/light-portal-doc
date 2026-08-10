# Create Provider Endpoint

Use `/app/form/createLlmProviderEndpoint` to define reusable provider transport,
authentication mode, network profile, and client-refresh settings for one
Provider Account. Endpoint fields never contain raw credentials.

## Authentication contract

| Endpoint Authentication | API Key Header | Meaning |
| --- | --- | --- |
| `NONE` | Empty | Provider call has no Endpoint credential. |
| `BEARER` | Empty | Gateway resolves the Endpoint Credential and sends it as a bearer token. |
| `API_KEY` | `authorization` or `x-api-key` | Gateway resolves the Endpoint Credential and sends it using the selected lowercase header name. |

`API_KEY` requires API Key Header; `NONE` and `BEARER` must omit it. Do not put
an API key in Safe Non-secret Headers, Base URL, or any authentication field.

## Network profile contract

- `PUBLIC_TLS` requires an `https` URL and no Network Zone or private trust
  reference.
- `PRIVATE_TLS` requires `https`, a Network Zone, a managed trust-bundle
  reference, and its resolved SHA-256 digest.
- `PRIVATE_PLAINTEXT` requires `http`, a Network Zone, authentication `NONE`,
  no trust bundle, and explicit plaintext-risk acknowledgement.

Termination is `NATIVE` for the ordinary gateway provider client or
`LIGHT_GATEWAY_SIDECAR` for an explicitly managed sidecar transport.

## NVIDIA Nemotron example

Select the `nvidia-free-embedding-demo` Provider Account and use:

```json
{
  "endpointName": "nvidia-free-embeddings",
  "providerProtocol": "openai_embeddings",
  "baseUrl": "https://integrate.api.nvidia.com/v1",
  "headers": {},
  "endpointAuthMode": "BEARER",
  "apiKeyHeader": null,
  "networkProfileMode": "PUBLIC_TLS",
  "networkTermination": "NATIVE",
  "networkZoneId": null,
  "trustBundleReference": null,
  "poolIdleTimeoutMs": 30000,
  "clientRefreshIntervalMs": 300000,
  "plaintextRiskAcknowledged": false,
  "lifecycleStatus": "DRAFT"
}
```

The Resolved Trust SHA-256 field is read-only and remains empty for this public
TLS Endpoint. Create `env:NVIDIA_API_KEY` later on the Credentials tab; never
paste its value here.

Portal generates Provider Endpoint Id and Aggregate Version. After creating a
compatible Deployment and Credential, activate and publish the Endpoint only
after the runtime path has been verified.

