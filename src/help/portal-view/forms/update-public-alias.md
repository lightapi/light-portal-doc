# Update Public Alias

Use this form to revise mutable policy, visibility, or migration
metadata for an existing Alias. Routes remain separate and are updated from the
Routes tab.

Host Id, Public Alias Id, and Aggregate Version are read-only. Reload the row
after a concurrency conflict instead of changing Aggregate Version manually.

## Immutable embedding contract

The following values are fixed at Alias creation:

- `operations`;
- `requiredCapabilities.embeddingSpace`;
- `requireExpectedEmbeddingSpace`; and
- `embeddingWorkloadLane`.

The update form displays the existing values for context but omits them from
the submitted update. To change an operation, vector-space identity, dimension,
normalization, distance metric, document transform, or workload lane, create a
new Alias and migrate Routes/clients deliberately.

For NVIDIA `kb-index` and `kb-query`, preserve the exact space
`nvidia-nemotron-3-embed-1b-float-v1`, revision `1`, dimension `2048`, L2
normalization, cosine distance, and `document-v1` transform.

## Mutable fields

| Field | Description |
| --- | --- |
| Environment | Environment served by the Alias; Routes must remain compatible. |
| Alias Name | Host/environment-unique stable client name. Renaming requires coordinated client/config changes. |
| Maximum Input/Output Tokens | Alias request limits. Leave output empty for embedding-only Aliases. |
| Maximum Request Bytes | Serialized request-size limit. |
| Data Classification | Host vocabulary used by governance and routing. |
| Logging Mode | `NONE`, `METADATA`, or `REDACTED`. |
| PII Mode | `DENY`, `REDACT`, `TOKENIZE`, or `ALLOW`. |
| Replacement Alias | Intended successor; it is not an automatic redirect. |
| Alias Visibility | `PUBLIC`, `INTERNAL_LEGACY`, or `INTERNAL_WORKLOAD`. |
| Bound Agent Definition | Required only for `INTERNAL_LEGACY`. |
| Bound Workload Principal | Required only for `INTERNAL_WORKLOAD`; must match the authenticated principal exactly. |

For the Knowledge Base Aliases, keep visibility `INTERNAL_WORKLOAD` and ensure
the bound principal matches the query or indexing bearer-token subject. Do not
switch a protected workload Alias to `PUBLIC` merely to bypass an identity
failure; correct the token/principal binding.

Updating the Alias does not make it publishable by itself. It still requires
compatible Routes, Deployments, Endpoint credentials, and Pricing. Soft-delete
state remains backend-managed.
