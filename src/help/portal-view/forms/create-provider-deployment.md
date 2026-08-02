# Create Provider Deployment

Use `/app/form/createProviderDeployment` to define the callable provider
endpoint for an approved LLM Registration and provider Account. Open the form
from **Administration > GenAI Admin > LLM Models > Deployments** by choosing
**Create provider deployment**.

A Deployment contains endpoint and governance metadata. It does not contain a
raw API key or password. Add an external secret reference later on the
Credentials tab.

## Before You Begin

Create these records first for the same host:

- an LLM Model and environment-specific Registration;
- a provider Account for the intended billing and quota owner.

You also need the provider's HTTPS inference base URL and the physical model
identifier accepted by that endpoint.

## Form Fields

| Field | Required | Example | Description |
| --- | --- | --- | --- |
| Host Id | Yes | `selected-host-id` | Read-only host that owns the Deployment. |
| LLM Registration | Yes | `Production / GPT-4o` | Non-deleted host-scoped Registration that approves the catalog model and environment. The selector submits its `modelRegistrationId`. |
| Provider Account | Yes | `OpenAI Production` | Non-deleted host-scoped billing/quota Account. The selector submits its `providerAccountId`. |
| Deployment Name | Yes | `openai-gpt-5.6-sol-ca-prod` | Operator-friendly name. It must be unique within the host. |
| Provider Type | Yes | `openai` | Provider adapter/format. Select it before Physical Model Id. |
| Physical Model Id | Yes | `gpt-4o` | Exact model name sent to the provider. Options are filtered by Provider Type. |
| Base URL | Yes | `https://api.openai.com/v1` | HTTPS base endpoint used by the provider client. Do not include credentials. |
| Region | No | `ca-central-1` | Placement or residency region associated with the endpoint. |
| Transport Bounds | No | `{"connectTimeoutMs":5000}` | Non-secret JSON object for provider-specific transport annotations. Defaults to `{}`. |
| Refresh Before Seconds | No | `86400` | Positive number of seconds before expiry when conformance becomes due for refresh. |
| Lifecycle Status | No | `DRAFT` | New Deployments are created as drafts. Activate them only after validation and conformance complete. |

The backend creates `providerDeploymentId`. The form does not accept `active`;
that value is backend-managed for soft deletion.

## Registration And Account

Both selectors load non-deleted reference labels for the selected host. The
command rejects an ID that does not exist under that host. Choose a Registration
for the intended environment and an Account whose provider and billing owner
match this endpoint. The Account owns the quota-group identity; the Deployment
does not duplicate it.

## Provider, Model, And Endpoint

Choose **Provider Type** first. **Physical Model Id** then loads the model names
related to that provider. The selected physical model must be the same model
actually served by `baseUrl` and later reported by the conformance result.

`baseUrl` must start with `https://`. Examples include:

```text
https://api.openai.com/v1
https://my-resource.openai.azure.com/openai
https://llm-provider.example.com/v1
```

Do not put a query-string token, API key, password, or authorization header in
the URL or any other Deployment field.

## Transport Bounds

`transportBounds` is an optional object for non-secret transport annotations.
The editor supports **JSON** and **YAML**. For example:

```json
{
  "connectTimeoutMs": 5000,
  "requestTimeoutMs": 60000,
  "maxConnections": 50
}
```

Use `{}` when no annotations are required. Choose **Apply** after editing JSON
or YAML. The Create action remains blocked while a structured draft is invalid
or has unapplied changes.

These properties are currently retained as control-plane metadata. Arbitrary
keys are not automatically projected into or enforced by the gateway runtime.

## Account-Owned Quota Group

There is no Quota Group field on this form. The selected Provider Account owns
`quotaGroupId`, and Portal derives it through `providerAccountId`. During
publication, Portal copies that authoritative value into the immutable gateway
resource. Deployments published under the same quota group share the gateway's
provider-account runtime capacity identity.

## Conformance Fields

Conformance evidence is not editable on this form. Portal creates the
Deployment with state `UNKNOWN` and no digest, validity time, or result. After
creation, use **Validate** and **Conformance** on the Deployments tab.

The workflow produces a result containing the provider, physical model,
validity time, detected capabilities, and captured evidence. If state is
`PASS`, Portal requires all of the following to agree:

- `conformanceDigest` matches the canonical result digest;
- `conformanceValidUntil` matches the result's `validUntil` and is in the
  future;
- the result provider and physical model match `providerType` and
  `physicalModelId`;
- the result contains capability and capability-evidence objects.

Administrative create and update commands reject manually supplied conformance
evidence. Incomplete, mismatched, or expired workflow evidence is rejected and
cannot become a healthy published route.

## Lifecycle Status

New records use `DRAFT`. The update form supports `VALIDATING`, `ACTIVE`,
`SUSPENDED`, and `RETIRED` after creation.

Lifecycle `ACTIVE` alone does not make the Deployment routable. It also needs
unexpired `PASS` conformance evidence, an effective Credential, Pricing, an
Alias Route, and publication.

## Create The Deployment

Choose **Create Provider Deployment**. The form sends
`lightapi.net/genai/createLlmProviderDeployment/0.1.0` and returns to
**Administration > GenAI Admin > LLM Models** after success.

## Common Problems

- **Registration or Account is empty**: create a non-deleted host-scoped record or
  confirm the current host selection.
- **Physical Model Id is empty**: select Provider Type first and confirm the
  provider-to-model reference relation is configured.
- **Base URL is rejected**: use a complete HTTPS URL.
- **Transport Bounds error**: enter an object, correct JSON/YAML syntax, and
  choose **Apply**.
- **Provider mismatch**: select an Account whose provider type matches the
  Deployment.
- **403 on Create**: confirm access to
  `lightapi.net/genai/createLlmProviderDeployment/0.1.0` and the required write
  permission.

For downstream routing and publication behavior, see the
[Deployments tab guide](../pages/llm-model-control-plane.md#deployments-tab).
