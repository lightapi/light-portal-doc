# LLM Model Control Plane

Use the LLM Model Control Plane to define the models a host can use, connect
them to provider accounts and deployments, expose governed aliases, apply
policy and pricing, and publish an immutable configuration to the gateway.

The model inventory is available under **Marketplace > LLM Model Catalog**.
The operational tabs are under **Administration > GenAI Admin > LLM Models**.

## Before You Start

- Select the host that owns the LLM configuration. Every record is host scoped.
- Use an account with the role permissions and rules for the LLM query and
  command endpoints.
- Create dependent records in this order: Catalog, Registration, Account,
  Deployment, Credential, Alias, Route, Pricing, Policy, Binding, Publication.
- Keep the `aggregateVersion` returned by a query. Update and delete commands
  require it for optimistic concurrency.

## Using The JSON Draft Editor

Every resource page has a **Create draft** button. It opens a JSON editor with:

```json
{
  "hostId": "selected-host-id",
  "active": true
}
```

Add the fields required for the selected resource and choose **Save**. The
server creates the resource id when it is omitted. Use valid JSON types: do not
put numbers, booleans, arrays, or objects in quotes unless the field is a
string.

The edit action loads the current sanitized record into the same editor. Keep
its id, `hostId`, and `aggregateVersion`, change the intended fields, and save.
The delete action sends the selected id, `hostId`, and `aggregateVersion` after
confirmation.

The editor sends the versioned Portal command contract. Do not paste an API
key, bearer token, password, or other secret value into any draft.

## LLM Model Catalog

Open **Marketplace > LLM Model Catalog** to define provider model inventory.
A catalog record describes a physical model independently of an environment,
account, credential, or deployment.

Required create fields:

- `providerType`
- `physicalModelId`
- `modelFamily`
- `contextTokenLimit`
- `outputTokenLimit`

Optional fields include `modelVersion`, `modalities`, `operations`,
`declaredCapabilities`, `lifecycleStatus`, `categoryIds`, and `tagIds`.

The Create and Update forms load active global and host-specific categories and
tags whose entity type is `llm_model`. The selected identifiers are carried in
the `LlmModelCreatedEvent` or `LlmModelUpdatedEvent`; the Portal projection
updates `llm_model_t`, `entity_category_t`, and `entity_tag_t` in one database
transaction. Taxonomy identifiers from another host, another entity type, or
an inactive taxonomy row are rejected before an event is emitted.

Create a catalog entry before creating a Registration that refers to its
`modelId`.

## Registrations Tab

Use Registrations to approve a catalog model for an environment, one or more
regions, data classifications, and capability restrictions.

Required create fields are `modelId` and `environment`. Use the
`regions`, `dataClassifications`, and `capabilityRestrictions` fields to narrow
where and how the registered model may be used.

## Accounts Tab

Use Accounts for provider billing and quota ownership. An account is metadata;
it does not contain a provider secret.

Required create fields are `accountName`, `providerType`, `billingPrincipal`,
and `quotaGroupId`. `capacityMetadata` can hold provider-specific capacity
information that is safe to store in Portal.

## Deployments Tab

Use Deployments to connect a Registration and Account to a provider endpoint.

Required create fields are:

- `modelRegistrationId`
- `providerAccountId`
- `deploymentName`
- `providerType`
- `physicalModelId`
- `baseUrl`
- `quotaGroupId`

`baseUrl` must use HTTPS. After saving, use **Validate** for deployment
validation and **Conformance** to run the provider conformance workflow. A
deployment in `PASS` state must carry the complete, matching, unexpired
`conformanceResult` and digest evidence.

## Credentials Tab

Use Credentials to associate a versioned external secret reference with a
deployment. Portal does not accept or display raw provider credentials.

Required create fields are `providerDeploymentId`, `credentialVersion`,
`secretReference`, and `effectiveTs`. `secretReference` must be an external URI,
for example a supported vault URI. `expiresTs` is optional.

Never enter the secret value itself. Fields resembling API keys, passwords,
authorization headers, or tokens are rejected.

## Aliases Tab

Use Aliases to define the stable model name consumed by applications and
agents. An alias can constrain operations, capabilities, token and request
limits, data classification, logging, and PII behavior.

Required create fields are `environment` and `aliasName`.

- `PUBLIC` aliases cannot set `boundAgentDefId`.
- `INTERNAL_LEGACY` aliases require a UUID `boundAgentDefId`.
- `replacementAliasId` can direct migration from a retiring alias.

Use **Preview routes** to inspect which deployments are eligible and why. The
preview excludes credential references and provider error material.

## Routes Tab

Use Routes to connect an Alias to an eligible Deployment and establish routing
priority and fallback behavior.

Required create fields are `publicAliasId`, `providerDeploymentId`, and
`routePriority`. The current MVP requires `routeWeight` to be `1` and
`canaryPercent` to be `0`. Use `fallbackEnabled` and `residencyConditions` for
the supported fallback and residency controls.

## Pricing Tab

Use Pricing to record an effective, versioned price for a Deployment. Monetary
values are integer micros per million tokens.

Required create fields are `providerDeploymentId`, `pricingVersion`,
`inputMicrosPerMillion`, `outputMicrosPerMillion`, `effectiveTs`, `source`, and
`approvedBy`. Optional fields include `cachedInputMicrosPerMillion` and
`expiresTs`.

## Policies Tab

Use Policies to group access, budget, content, cache, PII, and native extension
controls under a reusable policy name.

`policyName` is required. Add the applicable policy objects:
`accessPolicy`, `budgetPolicy`, `contentPolicy`, `cachePolicy`, `piiPolicy`, and
`nativeExtensionPolicy`.

## Bindings Tab

Use Bindings to assign a Policy to a subject and optionally scope it to an
Alias or mark it as the agent default.

Required create fields are `modelPolicyId`, `subjectType`, and `subjectId`.
Optional fields are `publicAliasId` and `agentDefault`.

## Publication Tab

Use Publication to append a complete, immutable configuration version for one
gateway environment.

1. Enter the target `Environment`.
2. Edit the Publication JSON.
3. Resolve every validation and gateway compatibility warning.
4. Review the version, resource count, requested features, and compiler
   acknowledgement.
5. Choose **Validate and publish** and confirm the operation.

A publication requires `environment`, `publicationVersion`, a semantic
`minimumGatewayVersion`, a full `manifest`, and at least one full-root resource.
Supported resource types are `llm-deployment`, `llm-route`, `llm-policy`, and
`llm-pricing`. Each resource needs an id, version, sequence, schema version, and
complete payload.

Rollback is append-only. To enable **Append rollback**, provide
`rollbackOfPublicationId` and a complete replacement publication. Rollback
creates a new history entry; it does not modify an earlier publication.

## Endpoint Authorization And 403 Responses

The browser uses two HTTP transport paths, but access control is registered
against each versioned service endpoint:

| Operation | HTTP path | Endpoint identity | Scope |
| --- | --- | --- | --- |
| List and preview | `/portal/query` | `lightapi.net/genai/<queryAction>/0.1.0` | `portal.r` |
| Create, update, delete, validate, conformance, publish, rollback | `/portal/command` | `lightapi.net/genai/<commandAction>/0.1.0` | `portal.w` |

Register and authorize these actions for the interactive page:

| Page or tab | Query action | Command actions |
| --- | --- | --- |
| Models | `getLlmModel` | `createLlmModel`, `updateLlmModel`, `deleteLlmModel` |
| Registrations | `getLlmModelRegistration` | `createLlmModelRegistration`, `updateLlmModelRegistration`, `deleteLlmModelRegistration` |
| Accounts | `getLlmProviderAccount` | `createLlmProviderAccount`, `updateLlmProviderAccount`, `deleteLlmProviderAccount` |
| Deployments | `getLlmProviderDeployment` | `createLlmProviderDeployment`, `updateLlmProviderDeployment`, `deleteLlmProviderDeployment`, `validateLlmProviderDeployment`, `runLlmProviderConformance` |
| Credentials | `getLlmProviderCredential` | `createLlmProviderCredential`, `updateLlmProviderCredential`, `deleteLlmProviderCredential` |
| Aliases | `getLlmPublicAlias`, `previewLlmAliasRoutes` | `createLlmPublicAlias`, `updateLlmPublicAlias`, `deleteLlmPublicAlias` |
| Routes | `getLlmAliasRoute` | `createLlmAliasRoute`, `updateLlmAliasRoute`, `deleteLlmAliasRoute` |
| Pricing | `getLlmPricingVersion` | `createLlmPricingVersion`, `updateLlmPricingVersion`, `deleteLlmPricingVersion` |
| Policies | `getLlmModelPolicy` | `createLlmModelPolicy`, `updateLlmModelPolicy`, `deleteLlmModelPolicy` |
| Bindings | `getLlmModelPolicyBinding` | `createLlmModelPolicyBinding`, `updateLlmModelPolicyBinding`, `deleteLlmModelPolicyBinding` |
| Publication | `getLlmGatewayPublication` | `publishLlmGatewayConfiguration`, `rollbackLlmGatewayConfiguration` |

For every endpoint, confirm that the API endpoint record, endpoint scope, rule
association, and role permission are active for the selected host. A user who
can list records may still receive `403` on Save because query and command
actions have separate endpoint permissions.

If authorization is correct but an update still fails, check that `hostId`
matches the authenticated host and that the JSON contains the current
`aggregateVersion`. Those contract errors are distinct from a missing endpoint,
role, rule, or scope.

## Common Errors

- **Select a host**: choose the owning host before opening the catalog or admin
  page.
- **403 on Save or Delete**: authorize the exact command action, not only its
  corresponding query action.
- **JSON parse error**: remove comments and trailing commas and use valid JSON.
- **Update conflict**: reload the tab and retry with the latest
  `aggregateVersion`.
- **Referenced record not found**: create the dependency first and verify that
  it belongs to the same host.
- **Invalid lifecycle transition**: reload the current state and choose a
  forward transition; terminal states cannot return to draft.
- **Publication button disabled**: fix the displayed candidate validation or
  gateway compatibility warnings first.
