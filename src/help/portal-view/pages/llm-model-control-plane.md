# LLM Model Control Plane

Use the LLM Model Control Plane to maintain the global model catalog and define
which models each host can use, connect registrations to provider accounts and
deployments, expose governed aliases, apply policy and pricing, and publish an
immutable configuration to the gateway.

The model inventory is available under **Marketplace > LLM Model Catalog**.
The operational tabs are under **Administration > GenAI Admin > LLM Models**.

## Before You Start

- The **LLM Models** tab is global and does not change when the selected host
  changes. Select a host for Registrations and every downstream operational tab.
- Use an account with the role permissions and rules for the LLM query and
  command endpoints.
- Create dependent records in this order: Catalog, Registration, Account,
  optional Network Zone, Provider Endpoint, Deployment, Credential, Alias,
  Route, Pricing, optional Policy and Binding, then Publication.
- Keep the `aggregateVersion` returned by a query. Update and delete commands
  require it for optimistic concurrency.

## NVIDIA Nemotron embedding demo sequence

The following records form the hosted NVIDIA path used by the
`light-knowledge` demo:

| Step | Tab or page | Key values |
| ---: | --- | --- |
| 1 | LLM Model Catalog | `nvidia`, `nvidia/nemotron-3-embed-1b`, operation `embed`, dimension `2048` |
| 2 | Registrations | Environment `loc`, data classification `public`, no capability restriction beyond the catalog contract |
| 3 | Accounts | `nvidia-free-embedding-demo` with provider type `nvidia`; no secret values |
| 4 | Network Zones | Skip for NVIDIA's public HTTPS endpoint |
| 5 | Provider Endpoints | `nvidia-free-embeddings`, `openai_embeddings`, `https://integrate.api.nvidia.com/v1`, `BEARER`, `PUBLIC_TLS`, `NATIVE` |
| 6 | Deployments | Exact NVIDIA Registration, Account, Endpoint, physical model, protocol, and base URL |
| 7 | Credentials | Purpose `ENDPOINT`, secret reference `env:NVIDIA_API_KEY`, version `1`, initially `PENDING` |
| 8 | Aliases | `kb-index`/`kb_index` and `kb-query`/`kb_query`, both using the same immutable 2048-dimensional embedding space |
| 9 | Routes | Connect each Alias to its compatible embedding Deployment; priority `0`, weight `1`, canary `0` |
| 10 | Pricing | Operation `embed`; omit output pricing. Use the approved free-demo pricing basis described in the Pricing help. |
| 11 | Policies and Bindings | Optional for the initial provider smoke test; required when the host's governance design selects a policy for these workload Aliases |
| 12 | Publication | Activate only verified records, generate a new candidate, publish, and test through the gateway |

The NVIDIA API key never belongs in the catalog, Account, Endpoint,
Deployment, Alias, Route, Pricing, or policy records. Portal stores only the
external reference `env:NVIDIA_API_KEY`; the gateway process receives the
actual environment variable at runtime.

## Forms And Structured Editors

The Models and Registrations tabs use typed Create and Update forms. Model
forms use global taxonomy and do not send `hostId`; Registration forms retain
the selected host. Both preserve arrays and objects as JSON values and keep
record identifiers and `aggregateVersion` read-only on update.

The downstream tabs also use schema-driven Create and Update forms. Structured
arrays and objects offer Form, JSON, and YAML editors; choose **Apply** after
editing JSON or YAML. The server creates resource IDs. Update forms retain the
resource ID, `hostId`, and `aggregateVersion` as read-only values for host
isolation and optimistic concurrency.

The editor sends the versioned Portal command contract. Do not paste an API
key, bearer token, password, or other secret value into any draft. The backend
owns `active`: create and update keep rows active, while delete soft-deletes
them.

## LLM Model Catalog

Open **Marketplace > LLM Model Catalog** to browse the platform-global provider
model inventory. A catalog record describes a canonical provider model
independently of a tenant, environment, account, credential, or deployment.
Only platform catalog administrators create, update, retire, or delete models.

Required create fields:

- `providerType`
- `physicalModelId`
- `modelFamily`
- `contextTokenLimit`
- `outputTokenLimit`

Optional fields include `modelVersion`, `modalities`, `operations`,
`declaredCapabilities`, `lifecycleStatus`, `categoryIds`, and `tagIds`.

The Create and Update forms load active global categories and tags whose entity
type is `llm_model`. The selected identifiers are carried in
the `LlmModelCreatedEvent` or `LlmModelUpdatedEvent`; the Portal projection
updates `llm_model_t`, `entity_category_t`, and `entity_tag_t` in one database
transaction. Host-specific taxonomy, another entity type, or an inactive
taxonomy row is rejected before an event is emitted.

Create a catalog entry before creating a Registration that refers to its
`modelId`.

For NVIDIA Nemotron, create or select the catalog record with provider type
`nvidia`, physical model `nvidia/nemotron-3-embed-1b`, operation `embed`, text
modality, context limit `4096`, and declared native dimension `2048`. See
[Create LLM Model](./create-llm-model.md) for the complete example.

## Registrations Tab

Use Registrations to approve a catalog model for an environment, one or more
regions, data classifications, and capability restrictions.

Choose **Create registration** to open the `createLlmRegistration` form.

- **LLM Model** is required and lists active models from the global catalog.
- **Environment** is required and comes from the host's `environment`
  reference data.
- **Regions** is optional and supports multiple values from the host's `region`
  reference data.
- **Data Classifications** is an optional array. Enter JSON such as
  `["internal", "confidential"]`, or use the YAML tab.
- **Capability Restrictions** is an optional object. Use it to narrow the
  catalog model capabilities for this environment; for example,
  `{"tools": false, "streaming": true}`.
- **Lifecycle Status** starts at `DRAFT`. Supported values are `DRAFT`,
  `ACTIVE`, `SUSPENDED`, and `RETIRED`.

### Data Classifications

Enter a JSON array describing the classes of data this registration may
process. For example:

```json
["internal", "confidential"]
```

Common names include `public`, `internal`, `confidential`, and `restricted`.
The field currently accepts free-form strings, so use the same names in aliases,
routing rules, and policies. Enter an empty array when no classifications are
required:

```json
[]
```

### Capability Restrictions

Enter a JSON object that narrows the capabilities declared by the catalog
model. For example:

```json
{
  "tools": false,
  "streaming": true,
  "images": false,
  "structuredJson": true
}
```

Use capability names consistently with routing and policy configuration. Enter
an empty object when the registration does not impose additional restrictions:

```json
{}
```

The create form submits `createLlmModelRegistration`. A host can have only one
registration for the same `modelId` and `environment` pair.

Choose the row's edit action to open `updateLlmRegistration`. The form submits
`updateLlmModelRegistration`; `hostId`, `modelRegistrationId`, and
`aggregateVersion` are retained for host isolation and optimistic concurrency.
Update the intended fields without removing those read-only values. A retired
registration cannot transition back to an earlier lifecycle state.

`active` is managed by the backend and is not editable in either form. Create
and update events keep the row active; the delete command sets it to false for
soft deletion.

Both forms return to **Administration > GenAI Admin > LLM Models** after a
successful save. A referenced model must exist in the global catalog; otherwise
the command is rejected before an event is emitted.

For the NVIDIA `light-knowledge` demo, select the
`nvidia/nemotron-3-embed-1b` catalog Model and use:

```json
{
  "environment": "loc",
  "regions": [],
  "dataClassifications": ["public"],
  "capabilityRestrictions": {},
  "lifecycleStatus": "DRAFT"
}
```

Do not redefine the embedding dimension in Capability Restrictions unless the
host intentionally narrows a broader catalog declaration. This NVIDIA endpoint
supports only its native 2048-dimensional output.

## Accounts Tab

Use Accounts to describe the provider billing and quota boundary under which
one or more LLM deployments run. An Account is host-scoped, non-secret
governance metadata. It is not a Portal user account and it does not contain an
API key or other provider credential.

### Why Accounts Are Separate

The control plane keeps these concerns separate:

- A **Model** describes a physical model in the catalog.
- A **Registration** approves that model for an environment.
- An **Account** identifies who owns the provider billing and quota boundary.
- A **Deployment** connects a Registration and Account to a provider endpoint.
- A **Credential** gives that Deployment an external secret reference.

This separation allows the same registered model to be deployed through
different provider accounts, quota pools, regions, or endpoints without
duplicating the model catalog entry or storing secrets in account metadata.

### Account Fields

- `accountName` is the operator-friendly name for the account. It must be unique
  for the same `providerType` within a host.
- `providerType` identifies the provider, such as the provider type used by the
  related Deployments.
- `billingPrincipal` identifies the organization, project, subscription, cost
  center, or other principal responsible for provider charges. Enter an
  identifier or name, never a credential.
- `quotaGroupId` identifies the provider capacity or quota pool shared by
  deployments. The Account is the authoritative owner of this value.
- `capacityMetadata` is an optional JSON object for non-secret,
  provider-specific capacity information, such as a service tier or approved
  limits.
- `lifecycleStatus` records the account's administrative state: `DRAFT`,
  `ACTIVE`, `SUSPENDED`, or `RETIRED`.

Required create fields are `accountName`, `providerType`, `billingPrincipal`,
and `quotaGroupId`. For example, the JSON draft can contain:

```json
{
  "hostId": "selected-host-id",
  "accountName": "openai-production",
  "providerType": "openai",
  "billingPrincipal": "genai-platform-cost-center",
  "quotaGroupId": "openai-production-capacity",
  "capacityMetadata": {
    "serviceTier": "production"
  },
  "lifecycleStatus": "DRAFT"
}
```

### How Account Data Is Used

When an Account is created, Portal assigns its stable `providerAccountId` and
stores the row under the selected host. A Deployment must reference that ID;
the database relationship prevents a deployment from referring to a missing
account or an account owned by another host. The account name is also available
as the display label when Portal loads Account reference data.

At the gateway boundary, Portal joins the Deployment to its Account and copies
the Account's `quotaGroupId` into the immutable published deployment material.
The gateway uses the provider identity and quota group to construct the
provider-account runtime identity and to share quota/capacity state among
deployments in the same quota group. Updating an Account does not by itself
rewrite an already published gateway snapshot; the corresponding deployment
publication must carry the intended values.

`billingPrincipal`, `accountName`, and `capacityMetadata` are currently retained
as control-plane governance and audit metadata; the gateway does not use them
to resolve credentials or select a route. Endpoints belong to Deployments, and
secret references belong to Credentials. Route health and publication
validation depend on active, conformant, priced, credentialed deployments, not
on entering a secret or endpoint in the Accounts tab.

As with the other tabs, `active` is backend-managed. Delete soft-deletes the
Account; do not add or edit `active` in the JSON draft.

For the NVIDIA demo, use Account Name and Quota Group Id
`nvidia-free-embedding-demo`, Provider Type `nvidia`, and a non-secret Billing
Principal such as `nvidia-build-api-demo`. See
[Create Provider Account](../forms/create-provider-account.md#nvidia-free-embedding-demo)
for the complete object.

## Network Zones Tab

Network Zones are administrator-owned outbound allowlists for private provider
networks. They define allowed DNS names, CIDRs, ports, and whether private TLS
or explicitly acknowledged private plaintext transport is permitted. A public
internet HTTPS endpoint does not need a Network Zone.

For `https://integrate.api.nvidia.com/v1`, do not create or select a Network
Zone. The NVIDIA Endpoint uses `PUBLIC_TLS`; `networkZoneId`, trust-bundle
fields, and private-plaintext acknowledgement remain empty or false. Existing
rows that show only lifecycle/version data are not placeholders to delete;
only create a Zone when a private Endpoint needs one.

See [Create Network Zone](../forms/create-llm-network-zone.md) and
[Update Network Zone](../forms/update-llm-network-zone.md).

## Provider Endpoints Tab

Provider Endpoints own the reusable transport and authentication profile for a
Provider Account. Deployments reference an Endpoint and still carry the exact
protocol and base URL for the current compatibility contract.

For the NVIDIA hosted embedding endpoint, use:

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
  "poolIdleTimeoutMs": 30000,
  "clientRefreshIntervalMs": 300000,
  "plaintextRiskAcknowledged": false,
  "lifecycleStatus": "DRAFT"
}
```

Select the `nvidia-free-embedding-demo` Account. `BEARER` must omit
`apiKeyHeader`; only `API_KEY` authentication supplies lowercase
`authorization` or `x-api-key`. Never put the NVIDIA key in Headers or any
Endpoint field.

See [Create Provider Endpoint](../forms/create-llm-provider-endpoint.md) and
[Update Provider Endpoint](../forms/update-llm-provider-endpoint.md).

## Deployments Tab

Use Deployments to define a callable provider endpoint for an approved LLM. A
Deployment binds a host-scoped Registration and provider Account to the exact
provider type, protocol, physical model, HTTPS endpoint, and optional region
that Portal will govern. The referenced Account owns the quota group.

### Why Deployments Are Separate

The Registration answers *which catalog model is approved for an environment*.
The Account answers *which billing and quota owner is responsible*. The
Deployment answers *where and how that approved model can actually be called*.
Keeping these records separate allows one Registration to use multiple
provider endpoints, regions, accounts, or capacity pools without duplicating
the catalog or approval records.

A Deployment does not contain a raw provider secret. Credentials attach an
external secret reference to the Deployment, Pricing attaches effective token
prices, and Routes attach public aliases to eligible Deployments.

### How Deployment Data Is Used

- `modelRegistrationId` connects routing eligibility to the catalog model,
  environment, data classifications, and capability restrictions approved by
  the Registration.
- `providerAccountId` identifies the provider Account. Portal derives its
  `quotaGroupId` through the Account foreign key when querying and publishing
  the Deployment.
- `providerType`, `providerProtocol`, `physicalModelId`, `baseUrl`, and
  `providerEndpointId` identify the provider adapter, exact wire contract,
  upstream model, compatibility URL, and reusable Endpoint profile.
- `deploymentRevisionId`, `physicalRuntimeId`, `capacityDomainId`,
  `runtimeCapacity`, and `readinessPolicy` form the runtime identity and bounded
  capacity contract used by protected workloads.
- `region` and `transportBounds` retain control-plane placement and transport
  metadata. Arbitrary transport-bound properties are not automatically enforced
  by the current gateway configuration compiler.
- Conformance fields are retained for a future trusted provider-test runner,
  but they are not part of the current interactive deployment workflow.

Alias Routes reference `providerDeploymentId`. Before a route is publishable,
the Deployment must be active, have lifecycle status `ACTIVE`, and have an
effective Credential and Pricing record. Conformance evidence is optional and
informational because provider testing occurs on the tenant gateway. Publication
materializes the approved deployment information for the
gateway. The gateway resolves the external credential reference, constructs
the provider client from the endpoint and provider format, calls the configured
physical model, applies declared capabilities (and verified evidence when
present), and shares runtime
capacity within the published quota group.

Changing a Deployment does not modify an already published gateway snapshot.
The updated deployment must pass the required validation and publication flow
before the gateway consumes the new materialized values.

### Create And Update

Choose **Create provider deployment** to open
`/app/form/createProviderDeployment`. In addition to the Registration,
Account, provider identity, exact protocol/model, and HTTPS base URL, the
current create contract requires Provider Endpoint, deployment revision,
physical runtime, capacity domain, runtime capacity, and readiness policy.
Valid exact protocol values are `openai_chat`, `openai_responses`,
`openai_embeddings`, and `anthropic_messages`.

Choose a row's edit action to open `/app/form/updateProviderDevelopment`. The
update form retains read-only `hostId`, `providerDeploymentId`, and
`aggregateVersion` values for host isolation and optimistic concurrency.

See [Create Provider Deployment](../forms/create-provider-deployment.md) and
[Update Provider Deployment](../forms/update-provider-development.md) for
field-by-field examples.

Conformance evidence is machine-owned. Do not manufacture a `PASS`, digest,
validity time, or result in an administrative form. A trusted qualification
runner must test the exact provider protocol, physical model, operation,
embedding space, and current credential path before recording evidence used by
production eligibility.

To make a Deployment available, provision its external secret in the target
gateway runtime, change the related Credential to `ACTIVE`, change the
Deployment lifecycle to `ACTIVE`, add effective Pricing and an Alias Route,
and publish the configuration. Provider connectivity is then tested through
the tenant gateway. The backend conformance contract remains reserved for a
future trusted runner.

As with the other tabs, `active` is backend-managed. Create and update keep the
row active; Delete soft-deletes it.

For NVIDIA use Provider Type `nvidia`, Protocol `openai_embeddings`, Physical
Model Id `nvidia/nemotron-3-embed-1b`, Base URL
`https://integrate.api.nvidia.com/v1`, and the `nvidia-free-embeddings`
Endpoint. Copy the protocol and URL exactly even though the Endpoint is also
selected. See
[Create Provider Deployment](../forms/create-provider-deployment.md#nvidia-nemotron-embedding-example).

## Credentials Tab

Use Credentials to tell Portal how a Provider Endpoint or sidecar runtime
authenticates without putting an API key, token, password, or other secret
value in the Portal database. Each row contains a purpose, owner reference,
versioned external secret reference, and eligibility window.

### Why Credentials Are Separate

A Deployment identifies the provider endpoint and physical model, while a
Credential identifies the external secret-manager location used to authenticate
calls to that endpoint. Keeping these records separate allows operators to:

- rotate credentials without replacing the Deployment;
- schedule a new credential before retiring the previous version;
- revoke one credential version without deleting endpoint configuration;
- audit which external reference was eligible during a particular time window;
- keep raw secret material outside Portal and its event stream.

An `ENDPOINT` credential selects `providerEndpointId`; a `SIDECAR_RUNTIME`
credential selects `providerDeploymentId`. The current create command also
expects the Deployment selector to be populated, so for an Endpoint credential
select both the Endpoint and its corresponding Deployment. Create a new,
incremented version for rotation instead of overwriting an older version.

### How Credential Data Is Used

Portal's publication-candidate validation requires every healthy route to have
at least one non-deleted Credential for its Deployment that:

- has lifecycle status `ACTIVE` or `ROTATING`;
- has reached `effectiveTs`; and
- has no `expiresTs`, or has an expiration later than the current time.

If no such row exists, the route is not considered healthy and publication is
rejected even when the Deployment, conformance, Pricing, and Alias Route are
otherwise valid. The candidate check establishes eligibility; operators should
avoid overlapping `ACTIVE` versions except during an intentional `ROTATING`
window so the publication workflow has an unambiguous version to project.

The published `llm-router.providers` property contains a credential reference, not the
credential value. At runtime, the gateway passes that reference to its configured
secret resolver and uses the resolved credential when calling the provider. The
gateway must never receive the raw secret through this form or the Portal event
contract.

### Credential Fields

- `credentialPurpose` is `ENDPOINT` for the central gateway's provider call or
  `SIDECAR_RUNTIME` for a credential resolved inside a provider sidecar.
- `providerEndpointId` is required for `ENDPOINT`.
- `providerDeploymentId` is required for `SIDECAR_RUNTIME` and is also required
  by the current create-command compatibility path.
- `credentialVersion` is a positive, monotonically increasing version for that
  Deployment, such as `1`, `2`, or `3`.
- `secretReference` is normally `env:VARIABLE_NAME`.
  Vault may inject that environment variable. Other URI schemes require an
  explicitly configured gateway resolver.
- `effectiveTs` is the ISO-8601 time at which the version becomes eligible.
- `expiresTs` is an optional ISO-8601 cutoff and must be later than
  `effectiveTs`.
- `lifecycleStatus` controls administrative eligibility: `PENDING`, `ACTIVE`,
  `ROTATING`, `REVOKED`, or `EXPIRED`.

New records start as `PENDING`. After provisioning and testing the referenced
secret, update the record to `ACTIVE`. During rotation, create the next version,
activate it at the intended time, mark the outgoing version `ROTATING` while both
are intentionally eligible, and then move the old version to `REVOKED` or
`EXPIRED`.

Choose **Create provider credential** to open
`/app/form/createProviderCredential`, or choose a row's edit action to open
`/app/form/updateProviderCredential`. See
[Create Provider Credential](../forms/create-provider-credential.md) and
[Update Provider Credential](../forms/update-provider-credential.md) for
field-by-field examples.

Never enter the secret value itself. Fields resembling API keys, passwords,
authorization headers, or tokens are rejected. As with the other tabs,
`active` is backend-managed; Delete soft-deletes the Credential.

For the NVIDIA hosted Endpoint select purpose `ENDPOINT`, Endpoint
`nvidia-free-embeddings`, its Nemotron Deployment, version `1`, and
`env:NVIDIA_API_KEY`. Keep the row `PENDING` until the variable is present and
resolvable in the gateway container. See
[Create Provider Credential](../forms/create-provider-credential.md#nvidia-endpoint-credential).

## Aliases Tab

Aliases give applications and agents a stable model name without exposing a
provider deployment or physical model identifier. This separation allows an
administrator to replace, reprioritize, or temporarily remove provider routes
without requiring every client to change its configured model name.

Each alias belongs to one environment and has a name that is unique in that
environment. It also records the policy requirements that deployments must
satisfy, including supported operations and capabilities, token and request
limits, data classification, logging, and PII handling.

The data is used as follows:

1. The **Routes** tab connects the alias to one or more provider deployments.
   Route validation checks that the alias and registration environments match
   and that the model and registration can satisfy the alias's required
   capabilities.
2. **Preview routes** evaluates the configured routes and explains why each
   deployment is eligible or ineligible. The preview excludes credential
   references and provider error material.
3. Publication validation requires each active alias in the target environment
   to have a healthy, priced, and credentialed route before a gateway candidate
   can be published.
4. The publication layer projects the Alias operation, embedding contract,
   limits, visibility/binding, audit, and PII policy into gateway routing.
5. A `PUBLIC` Alias is available for normal discovery; `INTERNAL_LEGACY` binds
   one agent definition; `INTERNAL_WORKLOAD` binds the exact authenticated
   workload principal.

Required create fields are `environment` and `aliasName`. The other fields are
optional policy constraints:

- `operations` lists `generate`, `embed`, or both.
- `requiredCapabilities` describes capabilities that every eligible route must
  provide. An embedding Alias requires the exact six-field `embeddingSpace`.
- `requireExpectedEmbeddingSpace` forces embedding callers to supply the
  expected space ID and revision.
- `embeddingWorkloadLane` is `standard`, `kb_query`, or `kb_index`.
- `maxInputTokens`, `maxOutputTokens`, and `maxRequestBytes` set alias-level
  request limits.
- `dataClassification`, `loggingMode`, and `piiMode` describe data-handling
  policy.
- `lifecycleStatus` controls whether the alias is draft, active, deprecated, or
  retired.
- `replacementAliasId` records the intended successor for a deprecated or
  retiring alias. It cannot reference the alias itself. It is a governance and
  migration hint; it does not automatically redirect traffic.
- `aliasVisibility` defaults to `PUBLIC`. Public Aliases leave both binding
  fields empty; `INTERNAL_LEGACY` selects `boundAgentDefId`; and
  `INTERNAL_WORKLOAD` supplies `boundWorkloadPrincipal`.

See [Create Public Alias](../forms/create-public-alias.md) and
[Update Public Alias](../forms/update-public-alias.md) for field descriptions
and complete examples. The `active` column is managed by backend soft delete
and is intentionally not shown in either form.

## Routes Tab

Routes connect each stable public Alias to the provider Deployments that can
serve it. Keeping this relationship separate lets administrators change
providers, priorities, or fallback targets without changing the model name
used by applications and agents.

The data is used as follows:

1. When a Route is created or updated, the control plane verifies that the
   Alias and Deployment are active, belong to the same host, use the same
   environment, and have compatible model capabilities and registration
   restrictions.
2. Routes for an Alias are ordered by `routePriority`, with lower numbers
   first. An alias/deployment pair can appear only once, and each priority must
   be unique within that alias.
3. `fallbackEnabled` marks a Deployment as a fallback target rather than the
   preferred route. The Alias route preview returns the priority, fallback
   flag, eligibility result, and reason for each active Route.
4. Publication validation requires every active Alias to have at least one
   healthy, priced, and credentialed Route.
5. Publication preparation uses the ordered Route records to construct the
   `llm-router.aliases` instance property consumed by the gateway snapshot. The gateway reads the
   resulting ordered deployment list and attempt policy; it does not query the
   Portal Route table directly.

Required create fields are `publicAliasId`, `providerDeploymentId`, and
`routePriority`. The other routing fields are:

- `routeWeight` is fixed at `1` by the current MVP. Weighted traffic splitting
  is not yet supported.
- `fallbackEnabled` identifies a fallback-only target. It does not by itself
  make an unhealthy Deployment eligible.
- `canaryPercent` is fixed at `0` by the current MVP. Canary percentage routing
  is not yet supported by this record contract.
- `residencyConditions` records a JSON or YAML object such as
  `{"regions":["ca-central-1"]}`. It is governance input for publication;
  enforcement requires a publication compiler and gateway version that
  understand the selected condition vocabulary. The current preview does not
  evaluate this object.

See [Create Alias Route](../forms/create-alias-route.md) and
[Update Alias Route](../forms/update-alias-route.md) for field descriptions and
complete examples. The `active` column is managed by backend soft delete and
is intentionally not shown in either form.

## Pricing Tab

Pricing records approved, effective-dated rates for each Provider Deployment.
The tab exists because provider prices change independently of model identity,
credentials, routes, and policies. Keeping rates in versioned records provides
an auditable answer to which price was approved for a Deployment and time
period without embedding mutable prices in an Alias or Route.

Monetary values are integer micros per one million tokens. One US dollar is
`1,000,000` micros, so a rate of `$2.50` per million input tokens is stored as
`2500000`.

The data is used as follows:

1. Publication validation requires each active Alias to have a healthy Route
   to a Deployment with at least one active Pricing record whose effective time
   has started and whose expiration has not passed.
2. Publication preparation selects the intended effective rates and includes
   them in the generated `llm-router.deployments` property. The gateway reads
   its immutable config snapshot; it does not query the Portal Pricing table
   during requests.
3. The current gateway configuration consumes the input and output rates. It
   rejects a Deployment whose input or output price is unknown instead of
   silently treating an absent price as zero.
4. Before provider dispatch, the gateway uses the projected rates, token
   limits, and maximum attempts to reserve a worst-case cost against the
   applicable budget. After the provider returns usage, the reservation is
   reconciled to the computed cost and the price snapshot version is retained
   in usage evidence.
5. `pricingVersion`, `source`, and `approvedBy` provide approval and audit
   lineage. `cachedInputMicrosPerMillion` is retained for richer pricing
   governance, but the current MVP gateway `llm-pricing` payload does not yet
   consume a separate cached-input rate.

Required create fields are `providerDeploymentId`, `operation`,
`pricingVersion`, `pricingBasis`, `inputMicrosPerMillion`, `effectiveTs`,
`source`, and `approvedBy`. `outputMicrosPerMillion` is required for `generate`
and must be omitted for `embed`. `cachedInputMicrosPerMillion` and `expiresTs`
are optional.
`expiresTs`, when supplied, must be later than `effectiveTs`.

The pair of Deployment and `pricingVersion` must be unique. The database does
not automatically expire an older record when a new one is created and does
not prohibit overlapping effective windows. Administrators should use clear,
non-overlapping windows and ensure publication selects the intended version.
For a new rate period, create a new Pricing Version instead of rewriting the
historical rate that was already used or published.

See [Create Pricing Version](../forms/create-pricing-version.md) and
[Update Pricing Version](../forms/update-pricing-version.md) for field
descriptions and complete examples. The `active` column is managed by backend
soft delete and is intentionally not shown in either form.

For a free hosted NVIDIA demo, select operation `embed`, omit output pricing,
and use `ZERO_MARGINAL` with zero input/cached-input rates only when your
approved demo contract truly has no marginal charge. Otherwise use
`EXTERNAL_PROVIDER` and enter the approved input rate. See
[Create Pricing Version](../forms/create-pricing-version.md#nvidia-free-endpoint-example).

## Policies Tab

Policies define reusable governance intent for model access, spending, content
handling, caching, PII, and provider-native extensions. The tab keeps these
decisions separate from a particular Alias, Agent, Client, or Deployment so the
same named policy can be reviewed once and assigned consistently to multiple
subjects.

Each Policy has a host-unique `policyName`, six JSON or YAML policy objects,
and a lifecycle status:

- `accessPolicy` describes who may use the governed model capability and which
  operations are intended to be available.
- `budgetPolicy` records request or period spending limits and related budget
  intent.
- `contentPolicy` records logging and prompt or response handling rules.
- `cachePolicy` records whether and under what conditions response caching is
  intended.
- `piiPolicy` records the desired handling of personally identifiable data.
- `nativeExtensionPolicy` allowlists provider-specific request extensions that
  may pass beyond the portable model contract.
- `lifecycleStatus` is `DRAFT`, `ACTIVE`, `SUSPENDED`, or `RETIRED`. A retired
  Policy is terminal, and a Policy cannot return to `DRAFT` after leaving it.

The six policy values are extensible objects rather than a fixed field
vocabulary. The command service verifies that each value is an object and
rejects raw secret material, but it does not prove that arbitrary nested keys
are supported by a publication compiler or gateway. Store secret references in
the Credentials workflow; never enter API keys, passwords, bearer values, or
other secret material in a Policy.

### Why Policies Are Separate

A Public Alias describes a stable callable contract, while a Route identifies
eligible Deployments. A Policy describes the governance that applies to a
consumer of that contract. Separating them avoids copying governance fields
into every Alias or Agent, supports host-scoped reuse, and allows policy changes
to follow their own review and lifecycle process.

Bindings provide the assignment layer. They connect a Policy to an `AGENT`,
`CLIENT`, `PRINCIPAL`, or `PRODUCT_PROFILE`, optionally scope the assignment to
a Public Alias, and can mark the default Alias for an Agent. An Agent definition
may select a `modelPolicyId`; its binding records must then resolve the intended
Alias. Creating a Policy without a Binding does not assign it to anyone.

### How Policy Data Is Used

1. The Policy row stores the reusable control-plane intent and its lifecycle.
2. Binding records select the subject and optional Alias to which the Policy
   applies. Agent default model resolution is primarily binding-based.
3. During publication, an approved compiler must resolve applicable policy
   precedence and translate supported intent into immutable `llm-policy` and,
   where applicable, route material. The gateway reads those published
   resources; it does not query the Portal Policy table during a request.
4. A Policy edit does not mutate an existing gateway snapshot. Validate and
   publish a new candidate before expecting supported runtime behavior to
   change.

The current MVP gateway `llm-policy` payload accepts only its documented
replica-local concurrency, streaming-channel, replay, and request-timeout
bounds. It does not directly consume the six control-plane wrapper objects
listed above, and it rejects unknown runtime policy fields. Therefore, storing
an illustrative key such as `monthlyCostMicros` or `loggingMode` records
governance intent but does not make that key enforceable by itself. Enforcement
requires an approved compiler mapping and a gateway version that supports the
resulting runtime field. Publication should include only intended `ACTIVE`
Policies and supported mappings.

Choose **Create model policy** to open `/app/form/createModelPolicy`. Choose a
row's edit action to open `/app/form/updateModelPolicy`; Host Id, Model Policy
Id, and Aggregate Version are read-only on update. See
[Create Model Policy](../forms/create-model-policy.md) and
[Update Model Policy](../forms/update-model-policy.md) for field descriptions
and examples. The `active` column is managed by backend soft delete and is
intentionally not shown in either form.

## Bindings Tab

Bindings assign a reusable Model Policy to a concrete subject. The tab is the
relationship layer between policy intent and the Agents, Clients, Principals,
or Product Profiles to which that intent applies. Without a Binding, creating a
Policy does not authorize a subject, scope the Policy to an Alias, or provide a
default model for a policy-selected Agent.

### Why Bindings Are Separate

A Policy describes governance once, while a Binding answers *who receives that
Policy and for which Alias*. Keeping assignments in normalized rows allows one
Policy to apply to many subjects and Aliases without duplicating its access,
budget, content, cache, PII, or native-extension objects. Assignments can change
without changing the stable Policy identity.

The supported subject types are:

- `AGENT`: `subjectId` is the exact Agent Definition Id. This is the subject
  type used by the current policy-selected Agent model-resolution path.
- `CLIENT`: `subjectId` is the exact client identity used by the approved
  policy compiler or authorization integration.
- `PRINCIPAL`: `subjectId` is the exact authenticated principal identifier used
  by the integrating identity system.
- `PRODUCT_PROFILE`: `subjectId` is the stable product-profile identifier used
  by the approved policy compiler.

`subjectId` is a bounded string rather than a foreign key because the four
subject types belong to different identity namespaces. Portal cannot verify a
Client, Principal, or Product Profile merely from this row; copy the canonical
identifier from its owning system. The referenced Model Policy and optional
Public Alias do have host-scoped foreign keys and must exist under the selected
host.

### How Binding Data Is Used

1. `modelPolicyId`, `subjectType`, and `subjectId` identify the Policy assignment.
2. An optional `publicAliasId` scopes the assignment to a concrete callable
   Alias. An unscoped Binding records a subject-level Policy assignment but does
   not provide an Alias for Agent default resolution.
3. For a policy-selected Agent, Portal and light-agent find active `AGENT`
   Bindings for the Agent Definition Id and active Aliases. Exactly one Binding
   must identify the selected default Alias with `agentDefault=true`; zero
   defaults produces `NO_DEFAULT`, and an ambiguous result fails resolution.
4. The resolved Alias name is sent as the OpenAI-compatible `model`. The
   gateway does not receive a Policy Id in that field and does not query the
   Portal Binding table during the inference request.
5. `CLIENT`, `PRINCIPAL`, and `PRODUCT_PROFILE` Bindings are control-plane input
   for an approved policy compiler or authorization integration. A stored row
   does not make unsupported policy fields enforceable by itself.

`agentDefault` is meaningful only for an `AGENT` Binding and requires a Public
Alias. The database permits at most one active default for the same host,
Policy, subject type, and subject. A Policy that can authorize several Aliases
may have several scoped Bindings for an Agent, but exactly one should be the
default. The form enforces the required Alias and Agent subject type when the
checkbox is selected.

Binding changes do not rewrite an already published gateway snapshot. Before
making an Alias the Agent default, ensure that the Alias and its Routes,
Deployments, Credentials, and Pricing are eligible and present in the intended
gateway publication. Agent resolution consults current active Binding data, so
changing or deleting a default can affect subsequent model resolution even
though gateway publication is a separate operation.

Choose **Create policy binding** to open `/app/form/createPolicyBinding`.
Choose a row's edit action to open `/app/form/updatePolicyBinding`; Host Id,
Model Policy Binding Id, and Aggregate Version are read-only on update. See
[Create Policy Binding](../forms/create-policy-binding.md) and
[Update Policy Binding](../forms/update-policy-binding.md) for every field and
complete examples. The `active` column is managed by backend soft delete and is
intentionally not shown in either form.

## Publication Tab

The other tabs are the authoring control plane. The Publication tab compiles
their active records into typed `llm-router` config properties and applies one
immutable revision to one explicitly selected Light Gateway instance. Editing
a model record never changes a running gateway by itself.

### What The Tab Does

The tab provides:

- an **Environment** dropdown populated from the selected host's configured
  environments;
- an **LLM Gateway Instance** dropdown listing active, writable instances whose
  product is `lg` and whose host and environment match the selection;
- **Generate from active records**, which joins the ready Aliases, Routes,
  Deployments, Accounts, Credentials, Pricing, Policies, and Bindings into a
  deterministic, read-only property preview;
- source and property-set digests plus a difference count against the selected
  instance's current managed properties;
- **Publish to instance**, which asks the server to regenerate and verify the
  preview digest before atomically applying it; and
- instance-scoped history with **Apply exact revision** for canary promotion or
  rollback without recompiling mutable control-plane rows.

The browser never submits arbitrary property IDs or an editable manifest. The
server resolves the fixed `llm-router` metadata and owns only these properties:

| Property | Type | Purpose |
| --- | --- | --- |
| `llm-router.enabled` | boolean | Enables the LLM router module. |
| `llm-router.developmentFixtures` | boolean | Always published as `false`; production data does not use embedded fixtures. |
| `llm-router.providers` | map | Provider format, base URL, external secret reference, headers, and quota-group identity. |
| `llm-router.deployments` | map | Physical model, declared capabilities, concurrency, and effective pricing. |
| `llm-router.aliases` | map | Public names, ordered deployments, retry/fallback bounds, and request limits. |
| `llm-router.openaiExtensionAllowlist` | list | Explicit OpenAI-compatible extension fields allowed by the generated configuration. |

### Why Publication Is Separate

A publication provides these guarantees:

1. **Atomicity**: all Portal-owned LLM instance properties and ownership rows
   change in the same event-projection transaction.
2. **Immutability**: a generated revision is stored once with canonical source
   and property digests. Corrections create another revision.
3. **Target isolation**: publication changes only the selected instance.
   Another production or canary instance is unaffected.
4. **Exact promotion and rollback**: the same stored property set can be
   applied to another instance without reading changed authoring rows.
5. **Namespace ownership**: the workflow cannot overwrite unrelated instance
   properties.

### Readiness Validation

Before generating a new revision, the backend requires at least one active
Alias and at least one usable Route for every active Alias. A Route is usable
when its Deployment:

- is active and has lifecycle status `ACTIVE`;
- has an effective, unexpired Credential with status `ACTIVE` or `ROTATING`;
  and
- has an effective, unexpired Pricing version.

The target must also be an active, writable `lg` instance in the selected host
and environment. Provider conformance is optional evidence. Portal does not
possess tenant API keys and does not call the provider, so `PENDING` or missing
conformance does not block publication or gateway startup. Structural and
capability compatibility checks still use the declared model and registration
capabilities. Users test provider connectivity through their own gateway after
snapshot and restart.

### Publication Fields

| Preview field | Meaning | Example |
| --- | --- | --- |
| `instanceId` | Explicit config/snapshot target, not an individual replica. | `50000000-0000-4000-8000-000000000001` |
| `sourceDigest` | Canonical digest of the active source records used by the compiler. | `sha256:4f...` |
| `propertySetDigest` | Canonical digest of all generated typed properties. | `sha256:91...` |
| `configProperties` | Read-only property metadata, types, structured values, and canonical JSON storage values. | `[{"propertyName":"providers","valueType":"map",...}]` |
| `differences` | Managed properties whose generated value differs from the selected instance. | `[{"propertyName":"aliases",...}]` |
| `validationResult` | Structural counts and validation status. It is not provider connectivity evidence. | `{"valid":true,"aliasCount":2}` |

### How Gateway Data Is Used

After the instance-publication event is projected:

1. Portal inserts or reuses an immutable revision in
   `llm_gateway_publication_t`.
2. Portal appends an instance application in
   `llm_gateway_instance_publication_t`.
3. The same transaction upserts the six managed values in
   `instance_property_t` and records their ownership. Existing rows are
   reactivated when necessary; an update-only event is not used for absent
   properties.
4. The user creates and promotes a config snapshot for that instance through
   the existing configuration workflow. Publication does not do this
   automatically.
5. The config server renders the typed map/list values into `values.yml`; the
   gateway's `llm-router.yml` template consumes them at startup or explicit
   module reload.
6. Credentials resolve locally from environment variables or the tenant's
   secret-injection mechanism. Secret values never enter Portal properties,
   revisions, snapshots, UI payloads, or logs.

### Publishing And Rollback

To publish:

1. Select the host, **Environment**, and **LLM Gateway Instance**.
2. Choose **Generate from active records** and review the read-only properties,
   digest, and differences.
3. Choose **Publish to instance**. If another author changed source records
   after preview, regenerate instead of publishing stale data.
4. Create and promote a config snapshot for the same instance.
5. Restart or reload the gateway and test the provider through that gateway.
6. If testing fails, edit the control-plane records and repeat the cycle.

For canary promotion or rollback, choose **Apply exact revision** in the
instance history. Portal loads the stored property set and applies it as a new
instance-publication action; it does not regenerate from current records or
mutate history. Create and promote another snapshot after that application.

## Endpoint Authorization And 403 Responses

The browser uses two HTTP transport paths, but access control is registered
against each versioned service endpoint:

| Operation | HTTP path | Endpoint identity | Scope |
| --- | --- | --- | --- |
| List and preview | `/portal/query` | `lightapi.net/genai/<queryAction>/0.1.0` | `portal.r` |
| Create, update, delete, publish, rollback | `/portal/command` | `lightapi.net/genai/<commandAction>/0.1.0` | `portal.w` |
| Reserved conformance runner callbacks | `/portal/command` | `lightapi.net/genai/<conformanceAction>/0.1.0` | `portal.w` |

Register and authorize these actions for the interactive page:

| Page or tab | Query action | Command actions |
| --- | --- | --- |
| Models | `getLlmModel` | `createLlmModel`, `updateLlmModel`, `deleteLlmModel` |
| Registrations | `getLlmModelRegistration` | `createLlmModelRegistration`, `updateLlmModelRegistration`, `deleteLlmModelRegistration` |
| Accounts | `getLlmProviderAccount` | `createLlmProviderAccount`, `updateLlmProviderAccount`, `deleteLlmProviderAccount` |
| Network Zones | `getLlmNetworkZone` | `createLlmNetworkZone`, `updateLlmNetworkZone`, `deleteLlmNetworkZone` |
| Provider Endpoints | `getLlmProviderEndpoint` | `createLlmProviderEndpoint`, `updateLlmProviderEndpoint`, `deleteLlmProviderEndpoint` |
| Deployments | `getLlmProviderDeployment` | `createLlmProviderDeployment`, `updateLlmProviderDeployment`, `deleteLlmProviderDeployment` |
| Credentials | `getLlmProviderCredential` | `createLlmProviderCredential`, `updateLlmProviderCredential`, `deleteLlmProviderCredential` |
| Aliases | `getLlmPublicAlias`, `previewLlmAliasRoutes` | `createLlmPublicAlias`, `updateLlmPublicAlias`, `deleteLlmPublicAlias` |
| Routes | `getLlmAliasRoute` | `createLlmAliasRoute`, `updateLlmAliasRoute`, `deleteLlmAliasRoute` |
| Pricing | `getLlmPricingVersion` | `createLlmPricingVersion`, `updateLlmPricingVersion`, `deleteLlmPricingVersion` |
| Policies | `getLlmModelPolicy` | `createLlmModelPolicy`, `updateLlmModelPolicy`, `deleteLlmModelPolicy` |
| Bindings | `getLlmModelPolicyBinding` | `createLlmModelPolicyBinding`, `updateLlmModelPolicyBinding`, `deleteLlmModelPolicyBinding` |
| Publication | `getEligibleLlmGatewayInstances`, `getLlmGatewayPublicationCandidate`, `getLlmGatewayInstancePublicationHistory` | `publishLlmGatewayConfiguration`, `rollbackLlmGatewayConfiguration` |

For every endpoint, confirm that the API endpoint record, endpoint scope, rule
association, and role permission are active. Model mutations require the global
catalog permission; tenant operations use the selected host. A user who
can list records may still receive `403` on Save because query and command
actions have separate endpoint permissions.

If authorization is correct but a tenant-resource update still fails, check
that `hostId` matches the authenticated host. All updates must contain the
current `aggregateVersion`. Those contract errors are distinct from a missing
endpoint, role, rule, or scope.

## Common Errors

- **Select a host**: a host is unnecessary for the global catalog, but is
  required before using Registrations or any downstream operational tab.
- **403 on Save or Delete**: authorize the exact command action, not only its
  corresponding query action.
- **JSON parse error**: remove comments and trailing commas and use valid JSON.
- **Update conflict**: reload the tab and retry with the latest
  `aggregateVersion`.
- **Referenced record not found**: create the dependency first and verify that
  it belongs to the same host.
- **Invalid lifecycle transition**: reload the current state and choose a
  forward transition; terminal states cannot return to draft.
- **Publication button disabled**: select an eligible gateway instance and
  generate a property preview first.
- **Candidate generation failed**: every active Alias in the selected
  environment needs at least one active Route whose Deployment is `ACTIVE`, has
  an effective `ACTIVE` or `ROTATING` Credential, and effective Pricing. The
  selected target must be an active writable `lg` instance in that environment.
