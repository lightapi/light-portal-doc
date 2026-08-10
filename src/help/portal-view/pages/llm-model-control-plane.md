# LLM Model Control Plane

Use `/app/genai/LlmModelControlPlane` to assemble the configuration that Portal
publishes to a `light-gateway` instance. Authoring records are usable as soon as
they are created. Portal keeps `active` as a backend-managed soft-delete flag;
it is not an operator workflow field.

Portal validates record shape and cross-record consistency during commands and
again on Publish. It does not call the provider or resolve API keys. Provider
connectivity is tested through the live gateway after publication, where the
runtime secret is available.

## Recommended order

Create records in this order:

1. Model catalog entry
2. Registration
3. Provider Account
4. Network Zone, only for an approved private provider
5. Provider Endpoint
6. Provider Deployment
7. Provider Credential reference
8. Public Alias
9. Alias Route
10. Pricing
11. Optional policy and policy binding
12. Publish, review, and create the gateway snapshot

If Publish reports a problem, return to the named tab, correct that record, and
publish again.

## NVIDIA Nemotron embeddings demo

The hosted NVIDIA demo uses:

- Provider: `nvidia`
- Physical model: `nvidia/nemotron-3-embed-1b`
- Protocol: `openai_embeddings`
- Base URL: `https://integrate.api.nvidia.com/v1`
- Endpoint authentication: `BEARER`
- Secret reference: `env:NVIDIA_API_KEY`
- Network profile: `PUBLIC_TLS`
- Termination: `NATIVE`

Do not enter the NVIDIA key in Portal. Inject `NVIDIA_API_KEY` into the target
`light-gateway` process.

### Model contract

Set Model operations to `["embed"]`. The declared capabilities are the static
contract used by publication and gateway compilation:

```json
{
  "operations": ["embed"],
  "embedding": {
    "maxBatchItems": 1,
    "maxInputTokensPerItem": 4096,
    "maxAggregateInputTokens": 4096,
    "supportedDimensions": [2048],
    "supportedEncodings": ["float"],
    "maxResponseBytes": 16777216,
    "space": {
      "spaceId": "nvidia-nemotron-3-embed-1b-float-v1",
      "revision": 1,
      "dimension": 2048,
      "normalization": "l2",
      "distanceMetric": "cosine",
      "documentInputTransformVersion": "document-v1"
    }
  }
}
```

The embedding-space identity is immutable. A model, dimension, normalization,
distance metric, or document-transform change requires a new space identity and
newly indexed vectors.

### Account and Endpoint

Create the Account with a stable quota group such as `nvidia-free-embedding-demo`.
Create the Endpoint under that Account with the protocol, URL, authentication,
and network values above. `apiKeyHeader` must be empty for `BEARER`.

Safe non-secret headers may be configured, but Authorization, cookies, proxy
credentials, and secret-looking values are rejected.

### Deployment

Select the Nemotron Registration, NVIDIA Account, and NVIDIA Endpoint. Preserve
the exact protocol, physical model, and base URL. Use a stable revision and
runtime-capacity declaration. A functional demo may use one Deployment for both
Knowledge Base lanes; production isolation requires distinct physical capacity,
not merely different names.

### Credential

Use purpose `ENDPOINT`, select the NVIDIA Endpoint, and set Secret Reference to
`env:NVIDIA_API_KEY`. Effective Time must be current or earlier. Expiration Time
is optional. Portal stores and publishes the reference only.

### Aliases and Routes

Create `kb-index` and `kb-query` as embedding-only internal workload Aliases.
For each Alias:

- operations: `["embed"]`
- require expected embedding space: `true`
- lane: `kb_index` or `kb_query`
- required embedding space: exactly the six-field space object above
- bound workload principal: the intended Knowledge Base workload

Create one priority-zero Route from each Alias to the Nemotron Deployment. The
command rejects missing, cross-host, environment-mismatched, protocol-mismatched,
or embedding-space-incompatible references.

### Pricing

Create an `embed` Pricing record for the Deployment. Embedding pricing accepts
an input rate and forbids an output rate. A zero demo rate is valid when that is
the intended accounting contract.

## Network Zones

Network Zones are required only for private TLS or explicitly approved private
plaintext endpoints. A public hosted NVIDIA Endpoint does not use a Network
Zone. Empty Network Zones are normal and should not be deleted merely because
the NVIDIA demo does not need one.

## Publish and test

Publish performs final validation across Accounts, Endpoints, Deployments,
Credentials, Aliases, Routes, Pricing, and static model capabilities. A valid
publication contains declared capabilities and secret references, never raw
keys.

After the gateway loads the snapshot, validate the live path with the documented
curl-first embeddings request. This confirms DNS, TLS, authentication, provider
protocol, model availability, response shape, dimension, and embedding-space
expectations from the customer runtime.

Follow [Validate LLM Embeddings Through The Live Gateway](../tasks/validate-llm-embeddings.md)
for the checked curl helper, optional Rust wrapper, safe evidence, and corrective
workflow.

## Common failures

- **Route references are incompatible:** ensure Alias and Registration use the
  same environment, the Deployment uses `openai_embeddings`, and the complete
  embedding-space objects match.
- **No eligible Credential:** check Endpoint purpose, effective/expiration
  timestamps, and the secret reference format.
- **Raw provider secrets rejected:** use `env:NVIDIA_API_KEY`, never the key.
- **No active records:** no non-deleted rows exist for that tab; create one only
  when the workflow requires it.
- **Publication rejected:** correct the record named by the Publish validation
  result and publish a new candidate.
