# Update Provider Deployment

Use `/app/form/updateProviderDevelopment` to edit an existing provider
Deployment. Open it from **Administration > GenAI Admin > LLM Models >
Deployments** by choosing the row's edit action.

The route name is `updateProviderDevelopment`, but the form updates a provider
Deployment through `updateLlmProviderDeployment`.

## Read-Only Fields

| Field | Example | Description |
| --- | --- | --- |
| Host Id | `selected-host-id` | Host that owns the Deployment. |
| Provider Deployment Id | `7ee18d9d-...` | Stable Deployment identifier referenced by Credentials, Pricing, and Alias Routes. |
| Aggregate Version | `4` | Current optimistic-concurrency version. A stale version is rejected. |

Do not remove or alter these values. The `active` field is backend-managed and
is not included in the form.

## Editable Fields

| Field | Example | Description |
| --- | --- | --- |
| LLM Registration | `dev — groq / llama-3.3-70b-versatile` | Host-scoped approval; its label combines environment, provider, and physical model. |
| Provider Account | `OpenAI Production` | Host-scoped billing and quota owner. |
| Deployment Name | `openai-gpt4o-ca-prod` | Unique operator-friendly name within the host. |
| Provider Type | `groq` | Provider identity. Changing it reloads Physical Model Id options. |
| Provider Protocol | `openai_embeddings` | Exact gateway wire contract: `openai_chat`, `openai_responses`, `openai_embeddings`, or `anthropic_messages`. |
| Physical Model Id | `gpt-4o` | Exact upstream model served by the endpoint. |
| Base URL | `https://api.openai.com/v1` | HTTPS provider base endpoint without credentials. |
| Provider Endpoint | `nvidia-free-embeddings` | Reusable transport/authentication profile. Protocol and Base URL must remain consistent with it. |
| Deployment Revision Id | `nvidia-free-embedding-demo/r1` | Operator revision of this exact callable configuration. |
| Physical Runtime Id | `nvidia/integrate-api/free-embeddings` | Stable external service/process identity. |
| Capacity Domain Id | `nvidia-free-embedding-demo` | Runtime capacity domain; protected lanes must not share one. |
| Runtime Capacity | `{"maxParallelRequests":32,...}` | Required positive parallel, queue, cold-start, stream-setup, and request timeout bounds. |
| Readiness Policy | `IMMEDIATE` | `IMMEDIATE` or `WARM_BEFORE_ELIGIBLE`. |
| Expected Sidecar Identity | Empty | Profile/digest only for a managed sidecar; leave empty for a native hosted Endpoint. |
| Region | `ca-central-1` | Optional placement or residency region. Leave it empty for a global endpoint. |
| Transport Bounds | `{"requestTimeoutMs":60000}` | Optional non-secret transport metadata object. |

Registration and Account selectors list non-deleted labels under the selected host.
Provider Type comes from `model_provider`; Physical Model Id comes from the
provider-to-model reference relation; Region comes from the host's region
reference data.


The form does not edit `quotaGroupId`. The selected Provider Account owns that
value, and Portal derives it through the existing Account relationship. Changing
the Account changes the value used by the next publication, but it does not
rewrite an already published gateway snapshot.

## Structured Fields

**Runtime Capacity**, **Expected Sidecar Identity**, and **Transport Bounds**
support JSON and YAML. Choose **Apply** after editing. For example:

```json
{
  "connectTimeoutMs": 5000,
  "requestTimeoutMs": 60000
}
```

Transport-bound properties remain control-plane annotations unless the
publication contract explicitly maps them to supported gateway settings.

## Identity Changes

The provider type, provider protocol, physical model, and endpoint form the
callable identity. If the provider endpoint or physical model changes, publish
the updated configuration and test connectivity through the tenant gateway.
The selected Account's provider type must match the Deployment.

An update does not bypass Credential, Pricing, Alias Route, or publication
requirements. Publish performs the final cross-record review.

For the hosted NVIDIA Deployment, preserve Provider Type `nvidia`, Protocol
`openai_embeddings`, Physical Model Id `nvidia/nemotron-3-embed-1b`, Base URL
`https://integrate.api.nvidia.com/v1`, and Endpoint
`nvidia-free-embeddings`. Rotate `env:NVIDIA_API_KEY` through Credentials rather
than changing Endpoint or Deployment fields.

## Save The Update

Choose **Update Provider Deployment**. The form sends
`lightapi.net/genai/updateLlmProviderDeployment/0.1.0` with
`providerDeploymentId` and `aggregateVersion`, then returns to
**Administration > GenAI Admin > LLM Models** after success.

An update changes the Portal control-plane record; it does not rewrite a
previously published gateway snapshot. Publish the intended new configuration
and test it through the tenant gateway before expecting supported runtime
behavior.

## Common Problems

- **Stale aggregate version**: reopen the form from the Deployments tab and
  apply the change to the latest record.
- **Registration or Account is unavailable**: confirm it is not deleted and
  belongs to the selected host.
- **Base URL is rejected**: use a complete HTTPS URL without secrets.
- **Structured edit is blocked**: correct the Transport Bounds JSON/YAML draft and choose
  **Apply**, or choose **Reset** to restore the last valid value.
- **Provider mismatch**: select an Account whose provider type matches the
  Deployment.
- **Provider Protocol is rejected**: choose the exact protocol enum; NVIDIA
  embeddings use `openai_embeddings`.
- **403 on Update**: confirm access to
  `lightapi.net/genai/updateLlmProviderDeployment/0.1.0` and the required write
  permission.

For route eligibility and gateway consumption, see the
[Deployments tab guide](../pages/llm-model-control-plane.md#deployments-tab).
