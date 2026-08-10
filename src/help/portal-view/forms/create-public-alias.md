# Create Public Alias

Use this form to create a stable, environment-specific model name and the
policy contract that every route behind that name must satisfy. Applications
use the Alias Name instead of a provider Deployment or physical model ID.

Despite the entity name, an Alias can be generally available (`PUBLIC`) or
restricted to an agent or workload identity. Start a new Alias in `DRAFT`, add
and validate its Routes, credentials, pricing, and deployment qualification,
and make it `ACTIVE` only when it is ready for publication.

> **Important:** `operations`, `requiredCapabilities.embeddingSpace`,
> `requireExpectedEmbeddingSpace`, and `embeddingWorkloadLane` form an
> immutable routing contract. To change any of them, create a new Alias
> revision instead of updating the existing Alias.

## Fields

| Field | Description | Example |
| --- | --- | --- |
| Host Id | Read-only tenant boundary supplied by Portal. All referenced records must belong to this host. | `10000000-0000-4000-8000-000000000001` |
| Environment | Environment in which clients use the Alias. Its Routes must use compatible registrations and Deployments. | `loc` |
| Alias Name | Stable model name presented to applications and agents. It must be unique within the host and environment. | `kb-index` |
| Operations | JSON or YAML array containing `generate`, `embed`, or both. Choose **Apply** after editing structured data. | `["embed"]` |
| Required Capabilities | JSON or YAML object that every eligible Deployment must satisfy. Embedding Aliases require the complete `embeddingSpace` object described below. | See [Embedding space](#embedding-space) |
| Require Expected Embedding Space | When enabled, embedding clients must send the expected space ID and revision. Enable this for Knowledge Base Aliases. | `true` |
| Embedding Workload Lane | `standard`, `kb_query`, or `kb_index`. The two Knowledge Base lanes provide separate query and indexing admission paths. | `kb_index` |
| Maximum Input Tokens | Optional Alias-level input-token limit. It must not exceed the selected model and qualified Deployment. | `4096` |
| Maximum Output Tokens | Optional generation output limit. Leave it empty for an embedding-only Alias. | `8192` |
| Maximum Request Bytes | Optional maximum serialized request size accepted through the Alias. | `1048576` |
| Data Classification | Optional classification used by data-handling and route policy. Use the vocabulary established for the host. | `public` |
| Logging Mode | `NONE`, `METADATA`, or `REDACTED`. | `METADATA` |
| PII Mode | `DENY`, `REDACT`, `TOKENIZE`, or `ALLOW`. Choose the most restrictive mode compatible with the use case. | `DENY` |
| Lifecycle Status | `DRAFT`, `ACTIVE`, `DEPRECATED`, or `RETIRED`. `DRAFT` is the safe creation value. | `DRAFT` |
| Replacement Alias | Optional intended successor for migration. It is not an automatic redirect and cannot reference the Alias being created. | `governed-chat-v2` |
| Alias Visibility | `PUBLIC`, `INTERNAL_LEGACY`, or `INTERNAL_WORKLOAD`. The visibility determines which identity binding fields are allowed. | `INTERNAL_WORKLOAD` |
| Bound Agent Definition | Required only for `INTERNAL_LEGACY`; select the single agent allowed to resolve the Alias. Leave it empty for the other visibility modes. | `Legacy Support Agent` |
| Bound Workload Principal | Required only for `INTERNAL_WORKLOAD`. It must exactly match the principal derived from the workload's bearer token. | `knowledge-indexer` |

`Operations` and `Required Capabilities` are structured editors. After changing
their JSON or YAML value, choose **Apply** before submitting the form.

## Visibility and identity rules

Use exactly one of these shapes:

| Visibility | Bound Agent Definition | Bound Workload Principal | Intended use |
| --- | --- | --- | --- |
| `PUBLIC` | Empty | Empty | Normal model discovery and routing |
| `INTERNAL_LEGACY` | Required | Empty | One selected legacy agent |
| `INTERNAL_WORKLOAD` | Empty | Required | A service or worker authenticated as the exact workload principal |

A non-standard Knowledge Base lane (`kb_query` or `kb_index`) additionally
requires all of the following:

- `operations` is exactly `["embed"]`;
- **Require Expected Embedding Space** is enabled; and
- **Alias Visibility** is `INTERNAL_WORKLOAD` with a non-empty workload
  principal.

The Alias names `kb-query` and `kb-index` use hyphens. The corresponding lane
identifiers `kb_query` and `kb_index` use underscores. They are distinct
contracts and must not be substituted for each other.

## Embedding space

An embedding Alias must declare exactly these six fields under
`requiredCapabilities.embeddingSpace`:

| Field | Meaning |
| --- | --- |
| `spaceId` | Operator-assigned identity for vectors that are safe to compare. Include the provider/model/output profile when that makes the identity unambiguous. |
| `revision` | Positive revision of that vector-space contract. |
| `dimension` | Exact number of floating-point values returned for each vector. |
| `normalization` | `none` or `l2`. |
| `distanceMetric` | `cosine`, `inner_product`, or `l2`. |
| `documentInputTransformVersion` | Versioned document preprocessing contract used before embedding, such as `document-v1`. |

Matching dimensions alone do not make two embedding spaces compatible. Both
Knowledge Base Aliases and every eligible primary or fallback Deployment must
publish exactly the same six-field contract.

## NVIDIA Nemotron Knowledge Base example

For `nvidia/nemotron-3-embed-1b`, NVIDIA currently documents a native
2048-dimensional float embedding, a 4096-token NIM limit, and no reduced
dimension support. NVIDIA's model card describes the output as L2-normalized,
so the example uses L2 normalization with cosine distance. See the
[NVIDIA NIM support matrix](https://docs.nvidia.com/nim/nemo-retriever/text-embedding/latest/support-matrix.html)
and [NVIDIA model card](https://huggingface.co/nvidia/Nemotron-3-Embed-1B-BF16).

Create the indexing Alias first:

```json
{
  "environment": "loc",
  "aliasName": "kb-index",
  "operations": ["embed"],
  "requiredCapabilities": {
    "embeddingSpace": {
      "spaceId": "nvidia-nemotron-3-embed-1b-float-v1",
      "revision": 1,
      "dimension": 2048,
      "normalization": "l2",
      "distanceMetric": "cosine",
      "documentInputTransformVersion": "document-v1"
    }
  },
  "requireExpectedEmbeddingSpace": true,
  "embeddingWorkloadLane": "kb_index",
  "maxInputTokens": 4096,
  "maxRequestBytes": 1048576,
  "dataClassification": "public",
  "loggingMode": "METADATA",
  "piiMode": "DENY",
  "lifecycleStatus": "DRAFT",
  "aliasVisibility": "INTERNAL_WORKLOAD",
  "boundWorkloadPrincipal": "knowledge-indexer"
}
```

Then create the query Alias with the same embedding-space object and policy,
changing only:

```json
{
  "aliasName": "kb-query",
  "embeddingWorkloadLane": "kb_query",
  "boundWorkloadPrincipal": "knowledge-service"
}
```

The two workload-principal examples assume that the indexing and query bearer
tokens resolve to `knowledge-indexer` and `knowledge-service`. If your tokens
use different subjects, enter those exact resolved principal IDs instead.

NVIDIA retrieval models distinguish document (`passage`) input from query
input. The Alias records the immutable vector-space and document-transform
identity, but provider-specific request transformation remains a Deployment
and gateway responsibility. Verify that the qualified provider path applies
the corresponding passage and query behavior before activating the Routes.

## General generation example

For a generally available generation Alias:

```json
{
  "environment": "prod",
  "aliasName": "governed-chat",
  "operations": ["generate"],
  "requiredCapabilities": {
    "tools": true,
    "streaming": true
  },
  "maxInputTokens": 128000,
  "maxOutputTokens": 8192,
  "maxRequestBytes": 1048576,
  "dataClassification": "internal",
  "loggingMode": "METADATA",
  "piiMode": "REDACT",
  "lifecycleStatus": "DRAFT",
  "aliasVisibility": "PUBLIC"
}
```

The backend creates the Public Alias Id and aggregate version. The `active`
state is backend-managed through soft delete and is not part of this form.
