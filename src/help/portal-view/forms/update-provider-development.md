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
| LLM Registration | `Production / GPT-4o` | Host-scoped approval that supplies the model and environment context. |
| Provider Account | `OpenAI Production` | Host-scoped billing and quota owner. |
| Deployment Name | `openai-gpt4o-ca-prod` | Unique operator-friendly name within the host. |
| Provider Type | `openai` | Provider adapter/format. Changing it reloads Physical Model Id options. |
| Physical Model Id | `gpt-4o` | Exact upstream model served by the endpoint. |
| Base URL | `https://api.openai.com/v1` | HTTPS provider base endpoint without credentials. |
| Region | `ca-central-1` | Optional placement or residency region. |
| Transport Bounds | `{"requestTimeoutMs":60000}` | Optional non-secret transport metadata object. |
| Refresh Before Seconds | `86400` | Positive lead time for scheduling conformance refresh. |
| Lifecycle Status | `ACTIVE` | `DRAFT`, `VALIDATING`, `ACTIVE`, `SUSPENDED`, or `RETIRED`. |

Registration and Account selectors list non-deleted labels under the selected host.
Provider Type comes from `model_provider`; Physical Model Id comes from the
provider-to-model reference relation; Region comes from the host's region
reference data.

## Account-Owned Quota And Conformance

The form does not edit `quotaGroupId`. The selected Provider Account owns that
value, and Portal derives it through the existing Account relationship. Changing
the Account changes the value used by the next publication, but it does not
rewrite an already published gateway snapshot.

Conformance state, digest, validity, and result are workflow-owned and are not
accepted by this administrative update form. Use the Deployment tab's
**Validate** and **Conformance** actions to refresh them.

## Structured Fields

**Transport Bounds** supports JSON and YAML. Choose **Apply** after editing. For
example:

```json
{
  "connectTimeoutMs": 5000,
  "requestTimeoutMs": 60000
}
```

Transport-bound properties remain control-plane annotations unless the
publication contract explicitly maps them to supported gateway settings.
Conformance Result is maintained exclusively by the conformance workflow.

## Identity And Conformance Changes

The provider type, physical model, endpoint, and workflow evidence form one
validated identity. If the provider endpoint or physical model changes, run
validation and conformance again before treating the Deployment as
route-eligible. The selected Account's provider type must match the Deployment.

Changing lifecycle status to `ACTIVE` does not bypass conformance, Credential,
Pricing, Alias Route, or publication requirements. A retired Deployment cannot
transition back to an earlier lifecycle state.

## Save The Update

Choose **Update Provider Deployment**. The form sends
`lightapi.net/genai/updateLlmProviderDeployment/0.1.0` with
`providerDeploymentId` and `aggregateVersion`, then returns to
**Administration > GenAI Admin > LLM Models** after success.

An update changes the Portal control-plane record; it does not rewrite a
previously published gateway snapshot. Validate and publish the intended new
configuration before expecting the gateway to use it.

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
- **403 on Update**: confirm access to
  `lightapi.net/genai/updateLlmProviderDeployment/0.1.0` and the required write
  permission.

For route eligibility and gateway consumption, see the
[Deployments tab guide](../pages/llm-model-control-plane.md#deployments-tab).
