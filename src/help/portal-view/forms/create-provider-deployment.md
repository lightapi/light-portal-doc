# Create Provider Deployment

Use `/app/form/createProviderDeployment` to bind an approved LLM Registration,
Provider Account, and Provider Endpoint to an exact callable model runtime.
Open it from **Administration > GenAI Admin > LLM Models > Deployments**.

A Deployment contains runtime identity, capacity, readiness, and non-secret
transport metadata. Provider credentials remain separate.

## Before you begin

Create these records first under the same host:

- the global catalog Model and environment-specific Registration;
- the Provider Account; and
- the Provider Endpoint.

The Registration, Account, Endpoint, provider type, protocol, physical model,
and base URL must describe the same provider path.

## Fields

| Field | Required | Description |
| --- | --- | --- |
| Host Id | Yes | Read-only host that owns the Deployment. |
| LLM Registration | Yes | Environment-specific approval of the catalog Model. |
| Provider Account | Yes | Billing, quota, and capacity owner. |
| Deployment Name | Yes | Host-unique operator name. |
| Provider Type | Yes | Provider identity, such as `nvidia`. |
| Provider Protocol | Yes | Exact wire contract: `openai_chat`, `openai_responses`, `openai_embeddings`, or `anthropic_messages`. |
| Physical Model Id | Yes | Exact upstream model string. |
| Base URL | Yes | HTTPS compatibility URL. Copy it exactly from the selected Endpoint. |
| Provider Endpoint | Yes | Reusable transport/authentication profile. |
| Deployment Revision Id | Yes | Stable operator revision for this callable runtime configuration. |
| Physical Runtime Id | Yes | Stable identity of the external service, process, or GPU runtime. |
| Capacity Domain Id | Yes | Capacity/isolation domain. Protected query and index lanes must not share one. |
| Runtime Capacity | Yes | JSON object with all five positive bounded-capacity fields shown below. |
| Readiness Policy | Yes | `IMMEDIATE` or `WARM_BEFORE_ELIGIBLE`. |
| Expected Sidecar Identity | No | Sidecar profile/digest object only; leave empty for a native hosted Endpoint. Never include credentials. |
| Region | No | Optional provider placement/residency label. |
| Transport Bounds | No | Additional non-secret transport annotations; use `{}` when none are approved. |
| Refresh Before Seconds | No | Lead time used by trusted refresh/qualification workflows. |
| Lifecycle Status | Yes | New Deployments start as `DRAFT`. |

Runtime Capacity requires exactly usable positive bounds. A suitable demo
starting point is:

```json
{
  "maxParallelRequests": 32,
  "maxQueuedRequests": 32,
  "coldStartTimeoutMs": 30000,
  "streamSetupTimeoutMs": 10000,
  "requestTimeoutMs": 30000
}
```

Choose **Apply** after editing Runtime Capacity, Expected Sidecar Identity, or
Transport Bounds.

## NVIDIA Nemotron embedding example

Select the `loc` NVIDIA Nemotron Registration, Account
`nvidia-free-embedding-demo`, and Endpoint `nvidia-free-embeddings`. Then use:

```json
{
  "deploymentName": "nvidia-nemotron-3-embed-1b-loc",
  "providerType": "nvidia",
  "providerProtocol": "openai_embeddings",
  "physicalModelId": "nvidia/nemotron-3-embed-1b",
  "baseUrl": "https://integrate.api.nvidia.com/v1",
  "deploymentRevisionId": "nvidia-free-embedding-demo/r1",
  "physicalRuntimeId": "nvidia/integrate-api/free-embeddings",
  "capacityDomainId": "nvidia-free-embedding-demo",
  "runtimeCapacity": {
    "maxParallelRequests": 32,
    "maxQueuedRequests": 32,
    "coldStartTimeoutMs": 30000,
    "streamSetupTimeoutMs": 10000,
    "requestTimeoutMs": 30000
  },
  "readinessPolicy": "IMMEDIATE",
  "expectedSidecar": null,
  "region": null,
  "transportBounds": {},
  "lifecycleStatus": "DRAFT"
}
```

The form still requires Base URL and Provider Protocol even though the selected
Endpoint already stores them. Copy the exact values; a mismatch creates an
internally inconsistent legacy/deployment record.

### Protected Knowledge Base lanes

`kb-index` and `kb-query` are separate protected workload lanes. For a
production-like qualification, create distinct index/query Deployments with
different Deployment Revision and Capacity Domain identities, and use provider
Accounts/quota that supply real capacity isolation. Merely giving two records
different strings does not create physical isolation when both consume the
same free external quota.

For a functional local demo, one hosted Deployment can prove transport and
embedding correctness, but it must not be represented as production lane
isolation evidence.

## Qualification and activation

Conformance/qualification evidence is machine-owned and is not editable on
this form. A trusted runner must test the exact protocol, physical model,
operation, credential path, and embedding-space evidence. Do not manufacture a
PASS result.

After creation, provision the Credential, Pricing, Alias, and Route. Move the
Deployment to `ACTIVE` only after the runtime path is ready, then publish a new
gateway candidate. Portal generates Provider Deployment Id and Aggregate
Version; `active` remains backend-managed.

## Common problems

- **Protocol rejected:** use `openai_embeddings`, not `openai` or `nvidia`.
- **Base URL rejected:** use the exact HTTPS base URL without `/embeddings` and
  without a key or query string.
- **Endpoint missing:** create the Provider Endpoint first under the same host.
- **Runtime Capacity rejected:** supply all five positive integer fields and
  choose **Apply**.
- **Provider mismatch:** the Registration, Account, Endpoint, and Deployment
  must all describe NVIDIA.
- **Raw secret rejected:** credentials belong only in an external secret store
  referenced from the Credentials tab.
