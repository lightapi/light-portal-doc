# Portal Catalog Scope

## Problem

Light Portal supports multiple tenants through `host_id` and can also host
multiple runtime environments in one portal instance. A common deployment shape
is:

| Portal instance | Runtime environments |
| --- | --- |
| Instance A | dev, sit |
| Instance B | stg, prd |

Within an organization or a cloud deployment, operators need a catalog for APIs,
API endpoints, tools, skills, schemas, rules, workflows, categories, and tags.
Some catalog entries are reusable platform knowledge. Other entries are
tenant-owned, environment-bound, or tied to a concrete gateway deployment.

The main design question is whether Light Portal should clone catalog rows into
every host/tenant, or maintain one shared catalog per portal instance and expose
it through a separate single page application and virtual host.

The recommended answer is neither full cloning nor a UI-only split. The portal
should model catalog scope explicitly:

- shared catalog definitions use global scope,
- tenant-specific definitions and overrides use host scope,
- environment-specific runtime bindings use host plus environment scope,
- a separate SPA may expose the same backend catalog, but it should not become
  the catalog authority.

## Goals

- Avoid duplicating the full catalog for every tenant.
- Prevent catalog drift between tenants and between portal instances.
- Preserve tenant isolation for private APIs, private skills, secrets, access
  control, and runtime bindings.
- Let dev and sit share one portal instance while still keeping their runtime
  endpoint targets separate.
- Let stg and prd share another portal instance while keeping production
  controls stricter.
- Support an effective catalog query that combines global definitions with
  host-specific rows and environment-specific bindings.
- Reuse existing portal-query APIs and the `genai-query` catalog direction for
  agent-facing skills and tools.
- Keep `light-gateway` as the runtime MCP execution path for `tools/list` and
  `tools/call`.
- Support promotion or import/export between portal instances instead of
  relying on ad hoc row copies.

## Non-Goals

- Do not clone every global catalog row into every tenant by default.
- Do not make a separate SPA the source of truth for catalog data.
- Do not bypass host-scoped authorization just because a catalog item is global.
- Do not put secrets, client credentials, runtime tokens, or deployment state in
  global catalog rows.
- Do not move MCP tool execution from `light-gateway` into portal-query,
  controller-rs, or the catalog UI.
- Do not require every MCP or API endpoint to be wrapped in a skill before the
  gateway can expose it as a runtime tool.

## Current Model

The database already contains both global-capable and host-scoped patterns.

`category_t` and `tag_t` have nullable `host_id`. A null `host_id` means the
category or tag is global. A non-null `host_id` means the row belongs to one
host. Their unique indexes already separate global uniqueness from host-specific
uniqueness.

The query behavior for category and tag labels returns both host-specific rows
and global rows for a host. This is the right shape for taxonomy and catalog
organization metadata.

Other catalog entities are currently host-scoped:

- `api_t`
- `api_version_t`
- `api_endpoint_t`
- `agent_definition_t`
- `skill_t`
- `tool_t`
- `tool_param_t`
- `agent_skill_t`
- `skill_tool_t`
- `skill_dependency_t`

Those tables use `host_id NOT NULL` and most query paths filter by
`host_id = ?`. This is correct for private tenant data and runtime-bound data,
but it is too narrow for reusable platform catalog definitions if the only
sharing mechanism is row replication.

## Design Decision

Use a scoped catalog inside Light Portal.

The portal backend remains the source of truth. The catalog UI can be part of
the existing portal SPA or exposed through another SPA/virtual host, but both UI
surfaces must read and write through the same portal-query and command APIs.

The durable model is:

```text
global catalog definition
  -> host enablement or host override
    -> environment runtime binding
```

This model allows one shared definition for reusable knowledge and separate
tenant or environment controls where isolation matters.

## Scope Types

| Scope | Storage meaning | Typical data |
| --- | --- | --- |
| Global | `host_id IS NULL` or a dedicated global definition row | Shared categories, tags, reusable schemas, rule templates, workflow templates, public tool definitions, shared skill templates |
| Host | `host_id = ?` | Tenant-owned APIs, private schemas, tenant skills, tenant tools, host-level enablement, access rules |
| Environment | `host_id = ?` plus `env_tag`, service id, target host, instance, or deployment binding | dev/sit/stg/prd endpoint targets, gateway exposure, runtime service bindings, deployment state |
| Instance | Separate portal database or portal deployment | Promotion boundary between dev/sit instance and stg/prd instance |

Global rows are reusable definitions. Host rows are ownership and isolation.
Environment rows are runtime selection.

## Catalog Entity Guidance

| Entity | Recommended scope | Reason |
| --- | --- | --- |
| Category | Global by default, host-specific when private taxonomy is needed | Existing schema already supports nullable `host_id` |
| Tag | Global by default, host-specific when private taxonomy is needed | Existing schema already supports nullable `host_id` |
| API | Host-scoped, with optional shared template support later | API ownership, lifecycle, and visibility are usually tenant-specific |
| API version | Host-scoped | Carries `env_tag`, `target_host`, service id, spec, and runtime-facing version metadata |
| API endpoint | Host-scoped for concrete API versions; may be generated from shared templates | Endpoint availability depends on the owning API version and runtime |
| Tool | Shared definition when generic; host-scoped projection when executable for a tenant | Runtime execution still depends on gateway, endpoint, policy, and service binding |
| Skill | Shared template when reusable; host-scoped copy or override when edited by a tenant | Skills contain prompt guidance that tenants may customize |
| Schema | Global when it is a reusable contract; host-scoped when it contains tenant-private fields or lifecycle | Avoid cloning standard contracts but protect tenant-specific schemas |
| Rule | Global template or host-specific rule | A reusable rule definition is different from enabling that rule for a host |
| Workflow | Global template or host-specific workflow | Templates can be shared, execution bindings should be host or environment scoped |

## Effective Catalog

Consumers should not need to manually merge global and host rows. Portal-query
should expose an effective catalog read model for each host and runtime context.

The effective catalog request should include:

- `hostId`
- `serviceId` when the catalog is for a gateway, agent, or runtime service
- `envTag` when the result is environment-specific
- optional `agentDefId` when the result is for an agent
- optional filters for entity type, category, tag, protocol, routing domain, or
  capability

The effective catalog response should include:

- global definitions visible to the caller,
- host-specific definitions visible to the caller,
- host overrides that shadow global defaults,
- environment bindings for the requested `envTag`,
- active state and catalog version or freshness metadata,
- category and tag labels from both global and host-specific taxonomy rows,
- enough provenance to show whether a row came from global scope, host scope, or
  an environment binding.

Recommended precedence:

```text
environment binding > host override > global definition
```

This keeps shared definitions stable while allowing host and environment
customization.

## Data Model Direction

For tables that already support nullable `host_id`, keep the current pattern:

```text
host_id IS NULL  -> global/shared row
host_id = ?      -> host-specific row
```

For strictly host-scoped catalog tables, do not simply make every `host_id`
nullable without checking foreign keys and runtime assumptions. Some tables are
correctly host-scoped because they point to tenant-owned APIs, credentials,
gateway endpoints, or agent assignments.

Use one of these patterns per entity:

1. Nullable `host_id` on the definition table when the entity can safely be
   global and all references can resolve global plus host rows.
2. Separate template and binding tables when the definition is global but
   enablement is tenant-specific.
3. Keep the current host-scoped table when the entity is inherently tenant or
   runtime bound.

For reusable skills and tools, the safest long-term shape is template plus
binding:

```text
catalog_skill_template_t
  -> host_skill_t or skill_t host override
    -> agent_skill_t assignment

catalog_tool_template_t
  -> host tool projection
    -> skill_tool_t mapping
    -> gateway runtime tools/list verification
```

If the implementation starts smaller, it can add nullable global scope to
selected catalog definition tables first, but the query contract must still
return the effective catalog and indicate scope provenance.

## Separate SPA Or Virtual Host

A separate SPA deployed with LightAPI and sign-in as another BFF virtual host is
useful as a catalog presentation surface. It can provide a marketplace-style
view for shared APIs, tools, skills, schemas, rules, and workflows.

It should not own separate catalog state.

Recommended use:

- browse global catalog definitions,
- request enablement for a host,
- compare host overrides with global definitions,
- review environment bindings,
- publish or promote catalog versions between portal instances.

Avoid using the separate SPA to bypass tenant-aware portal APIs. The BFF should
still pass authenticated requests to portal-query or command APIs, and those
APIs must enforce host, service, environment, and role checks.

## Environment Handling

Within one portal instance, environments should be runtime bindings, not cloned
catalog universes.

For a dev/sit instance:

- one shared catalog can describe a capability,
- dev and sit get separate `env_tag` bindings,
- runtime endpoints can differ through `target_host`, `service_id`, instance,
  deployment, or gateway registration,
- a tool can be visible in both environments but executable only where the
  gateway lists it.

For a stg/prd instance:

- stg and prd can share approved global definitions,
- production enablement should require stricter workflow or authorization,
- secrets, tokens, OAuth clients, runtime instances, and deployment state remain
  environment-specific,
- catalog promotion into prd should preserve stable IDs and versions.

## Promotion Between Portal Instances

The boundary between dev/sit and stg/prd is an instance boundary. Treat it as a
promotion boundary, not as live replication between tenants.

Recommended promotion flow:

1. Author or import catalog definitions in the lower portal instance.
2. Review and approve the global or host-scoped definitions.
3. Export selected catalog rows with their versions and dependencies.
4. Import into the target portal instance.
5. Resolve environment bindings for stg or prd.
6. Verify runtime exposure through the selected `light-gateway` `tools/list`.
7. Activate the target bindings.

Promotion should be idempotent. A repeated import of the same catalog version
should update or confirm the same target definition instead of creating
duplicates.

## Security And Authorization

Global catalog visibility does not mean global execution permission.

Authorization must be checked at these layers:

- portal UI and BFF authentication,
- portal-query read authorization,
- command API write authorization,
- host and environment claim matching,
- category/tag visibility when private taxonomy is used,
- gateway `tools/list` availability,
- gateway `tools/call` policy,
- downstream service authorization.

For runtime catalog reads used by gateways and agents, the token should include
`host`, `sid`, and, when environment-specific data is requested, `env`. The
query handler should compare those claims with the requested `hostId`,
`serviceId`, and `envTag`.

## UI Guidance

The portal UI should show catalog scope explicitly:

- `Global`
- `Host`
- `Environment`

For list pages, include filters for scope, environment, category, tag, active
state, and source protocol. For detail pages, show whether a host row inherits
from a global definition, overrides it, or is private to the host.

For destructive changes, make the target scope clear. Updating a global catalog
definition can affect many hosts, while updating a host override should affect
only that host.

## Migration Approach

1. Keep the existing category and tag nullable `host_id` behavior.
2. Add effective catalog read APIs before broad schema changes so callers have a
   stable contract.
3. Identify which catalog entities need global definitions versus host-only
   rows.
4. Add template or nullable-scope tables for reusable definitions.
5. Add host enablement or override tables for tenant-specific activation.
6. Add environment binding views or APIs for dev, sit, stg, and prd.
7. Add import/export or snapshot support for promotion between portal
   instances.
8. Update portal-view to expose scope and provenance.
9. Keep existing host-scoped APIs working during the migration.

## Open Questions

- Should global reusable skills and tools use nullable `host_id` in the
  existing tables, or separate template tables with host bindings?
- Which catalog entities require approval workflow before production
  activation?
- Should category and tag assignment tables store additional scope metadata, or
  is scope fully inherited from the referenced category or tag?
- What stable external identity should be used during cross-instance catalog
  promotion when UUIDs differ between portal databases?
- Should portal-query expose one broad effective catalog endpoint or multiple
  entity-specific effective endpoints?

