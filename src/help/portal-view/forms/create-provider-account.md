# Create Provider Account

Use `/app/form/createProviderAccount` to create the non-secret provider billing
and quota identity that an LLM Deployment will use. This is not a Portal user
account and it does not store an API key, access token, password, or provider
endpoint.

Open the form from **Administration > GenAI Admin > LLM Models > Accounts** by
choosing **Create provider account**.

## Before You Begin

Create an Account before creating a Deployment that refers to it. Decide which
provider, billing owner, and quota pool the new Account represents. If one host
uses multiple provider subscriptions, projects, or cost centers, create a
separate Account for each boundary that must be managed independently.

## Form Fields

| Field | Required | Description |
| --- | --- | --- |
| Host Id | Yes | The selected host. The form supplies this read-only value. |
| Account Name | Yes | An operator-friendly name, such as `openai-production`. It must be unique for the selected provider within the host. |
| Provider Type | Yes | Select the provider type used by the related Deployments, such as `openai`. |
| Billing Principal | Yes | The organization, project, subscription, or cost center responsible for provider charges. Enter an identifier or name, never a credential. |
| Quota Group Id | Yes | A stable identifier for the provider capacity or quota pool shared by related Deployments. |
| Capacity Metadata | No | A JSON object containing non-secret provider capacity information. It defaults to an empty object. |
| Lifecycle Status | No | The administrative state. It defaults to `DRAFT`; supported values are `DRAFT`, `ACTIVE`, `SUSPENDED`, and `RETIRED`. |

The backend creates `providerAccountId`. The form does not ask you to supply
that identifier. The `active` field is also backend-managed and is not part of
the form.

## Billing Principal

Use `billingPrincipal` to identify who is financially responsible for usage.
The exact value depends on your organization and provider. Examples include:

- `genai-platform-cost-center`
- `azure-subscription-production`
- `aws-account-llm-platform`
- `provider-project-customer-support`

This field is governance and audit metadata. Do not enter a provider API key,
secret value, bearer token, password, or authorization header.

## Quota Group Id

Use `quotaGroupId` to name the provider capacity pool shared by deployments,
for example `openai-production-capacity`. Keep the value stable and use the
same intended quota-group identity when configuring the related Deployment and
gateway publication.

Deployments in the same published quota group share the corresponding gateway
capacity identity. Changing an Account later does not automatically rewrite an
already published gateway snapshot.

## Capacity Metadata

`capacityMetadata` is an optional open-ended object for non-secret capacity
annotations. The editor supports **JSON** and **YAML**. For example:

```json
{
  "serviceTier": "production",
  "approvedRpm": 1000,
  "approvedTpm": 2000000
}
```

The equivalent YAML is:

```yaml
serviceTier: production
approvedRpm: 1000
approvedTpm: 2000000
```

Use an empty object when no metadata is needed:

```json
{}
```

After editing JSON or YAML, choose **Apply**. The Create action remains blocked
while the structured draft is invalid or has unapplied changes. Capacity
metadata is currently retained for control-plane governance; the gateway does
not use arbitrary metadata properties to resolve credentials or select routes.

## Create the Account

Review the values and choose **Create Provider Account**. The form sends the
`lightapi.net/genai/createLlmProviderAccount/0.1.0` command. After a successful
command, the browser returns to **Administration > GenAI Admin > LLM Models**.
The new Account can then be selected by a provider Deployment.

## Common Problems

- **Provider Type is empty**: confirm the `model_provider` reference values are
  configured and available to the Portal environment.
- **Required-field validation**: provide Account Name, Provider Type, Billing
  Principal, and Quota Group Id.
- **Capacity Metadata error**: enter an object rather than an array or quoted
  JSON string, correct any JSON/YAML syntax error, and choose **Apply**.
- **Duplicate account**: choose a different Account Name. A host cannot contain
  two Accounts with the same Provider Type and Account Name.
- **403 on Create**: confirm access to the
  `lightapi.net/genai/createLlmProviderAccount/0.1.0` command endpoint and the
  required write permission.

For account lifecycle, deployment relationships, and gateway usage, see the
[LLM Model Control Plane](../pages/llm-model-control-plane.md) guide.
