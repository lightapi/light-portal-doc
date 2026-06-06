# Schema Registry

The schema registry is the portal-owned catalog for reusable schema contracts.
The first release should focus on JSON Schema documents for UI form generation,
backend validation, external schema discovery, and operational auditability. The
model should remain extensible enough to add Protobuf later if
gRPC-over-WebSocket contract discovery becomes a real requirement, but Protobuf
support is not required for the initial hardening pass. This design focuses on
hardening the current `schema-query`, `schema-command`, and `schema_t`
implementation so it can safely validate configuration property values and
support future schema reuse across portal features.

## Current State

The portal already has the core pieces of a schema registry:

- `schema_t` stores schema metadata and the schema body.
- `schema-query` exposes read actions such as `getSchema`, `getSchemaLabel`,
  `getSchemaById`, and `getFreshSchema`.
- `schema-command` exposes create, update, and delete actions.
- `schema_t.host_id` supports tenant-specific rows, with `NULL` representing a
  global schema.
- `schema_t.schema_status` tracks draft, published, and retired states.
- `schema_t.spec_version` records the schema language version, such as a JSON
  Schema draft.

The implementation is not ready to be treated as an authoritative validation
service yet. The main gaps are:

- schema lookup is not consistently tenant-aware
- version lookup semantics are not explicit enough for config validation
- schema bodies are not clearly validated before being stored
- published schema immutability is not defined
- schema type and body validation rules are not explicit
- schema rows do not have a stable URL-friendly public alias
- config properties do not currently reference schemas
- backend config command handlers do not validate values against schemas
- tests for schema CRUD, tenant/global lookup, versioning, and config
  validation are incomplete

## Goals

- Store JSON Schema documents with clear tenant/global ownership.
- Support immutable published schema versions.
- Let config properties reference an exact schema id and version.
- Validate structured config property values on both frontend and backend.
- Preserve existing schema registry CRUD pages and generated forms.
- Add a Marketplace Schema Catalog entry for browse-first schema discovery.
- Add URL-friendly schema aliases so external applications can retrieve
  published schemas through `portal-service`.
- Keep schema lookup cheap for list pages by returning schema metadata first
  and loading schema bodies lazily.
- Support schema status transitions: draft, published, retired.
- Make validation errors specific enough for editors to highlight the failing
  JSON path.
- Categorize and tag schemas for easier discovery and filtering.

## Non-Goals

- Do not build a full schema compatibility engine in the first release.
- Do not require every config property to have a schema.
- Do not replace OpenAPI schemas or the existing API spec registry.
- Do not implement Protobuf parsing, compatibility, config form generation, or
  runtime validation in the first release.
- Do not make the config update page depend on schema registry completion for
  basic scalar and raw JSON/YAML editing.
- Do not allow unpublished schemas to validate production config overrides.

## Data Model

The existing `schema_t` table is a reasonable starting point. It already has:

- `schema_id`
- `host_id`
- `schema_version`
- `schema_type`
- `spec_version`
- `schema_body`
- `schema_status`
- ownership, active, audit, and aggregate-version fields

Before production validation depends on this table, the versioning model should
be made explicit. The recommended model is:

- `schema_id` is the stable, lower-case, URL-friendly logical schema id.
- `schema_version` identifies an immutable schema version.
- `host_id IS NULL` means a global schema.
- `host_id IS NOT NULL` means a tenant-specific schema.
- a published schema body is immutable
- changing a published schema creates a new version
- retiring a schema version marks it unavailable for new bindings but keeps it
  readable for historical audit and existing references

The current table uses `schema_id` as the primary key while also defining
unique indexes on `(schema_id, schema_version)` and
`(host_id, schema_id, schema_version)`. That conflicts with a true immutable
version-row model. The preferred correction is to introduce a surrogate row key
such as `schema_uid UUID` and keep uniqueness on the logical reference:

```text
schema_uid       UUID primary key
schema_lineage_id UUID not null
host_id          UUID nullable
schema_id        VARCHAR(126)
schema_alias     VARCHAR(126) nullable
schema_version   VARCHAR(12)
schema_type      VARCHAR(16)
spec_version     VARCHAR(12)
schema_body      TEXT
schema_status    CHAR(1)
external_visible BOOLEAN
aggregate_version BIGINT
...
```

The registry should keep unique constraints for:

- global schema versions: `schema_id + schema_version` where `host_id IS NULL`
- tenant schema versions: `host_id + schema_id + schema_version` where
  `host_id IS NOT NULL`
- version rows within one logical lineage: `schema_lineage_id + schema_version`

`schema_lineage_id` is the stable identity for a logical schema within a scope.
All immutable versions of the same global schema share one lineage id. All
immutable versions of the same tenant schema share a different lineage id. This
prevents category and tag assignments from colliding when a global schema and a
tenant schema use the same `schema_id`.

`schema_alias` is an optional URL-friendly external identifier for a schema
lineage. It should use the same lower-case, URL-friendly character policy as
`schema_id`, and it should be stable across immutable versions of the same
lineage. `schema_alias` is allowed to differ from `schema_id` so operators can
rename an external contract URL without changing internal schema ids.

Because alias and taxonomy are lineage-level metadata, the clean target is a
small lineage table:

```text
schema_lineage_t
  schema_lineage_id UUID primary key
  host_id UUID nullable
  schema_id VARCHAR(126)
  schema_alias VARCHAR(126) nullable
  external_visible BOOLEAN not null default false
  ...

schema_t
  schema_uid UUID primary key
  schema_lineage_id UUID references schema_lineage_t(schema_lineage_id)
  schema_version VARCHAR(12)
  schema_body TEXT
  ...
```

If a separate lineage table is too large for the first pass, `schema_alias` and
`external_visible` can be stored on `schema_t` with command-side enforcement that
all versions in one lineage share the same alias and visibility. The migration
should still move them to `schema_lineage_t` when the immutable version-row model
is introduced.

Alias uniqueness should be scoped the same way as schemas:

- global aliases: unique `schema_alias` where `host_id IS NULL`
- tenant aliases: unique `host_id + schema_alias` where `host_id IS NOT NULL`

If a surrogate key migration is too disruptive for the first hardening pass, the
minimum acceptable interim model is to keep the current row shape but document
that `schema_id` represents the current mutable aggregate. That is weaker for
config validation because a schema body can drift under an existing config
property reference. The immutable version-row model should be the target.

## Schema Types

`schema_type` should be treated as a controlled value. The first supported value
is:

| `schema_type` | `schema_body` meaning | `spec_version` examples | First-release use |
| --- | --- | --- | --- |
| `json` | JSON Schema document | `draft-07`, `2019-09`, `2020-12` | Config form generation, frontend validation, backend config command validation, catalog discovery |

For `json` schemas, `schema-command` must parse `schema_body` as JSON and
validate it as a JSON Schema document before the schema can be published.

`protobuf` should remain a reserved future `schema_type`, not an MVP
requirement. If future gRPC-over-WebSocket support needs Protobuf contracts, add
Protobuf parsing and either a schema artifact table or a schema bundle table for
multi-file imports and compiled descriptors. Do not overload the JSON Schema
validation path to make Protobuf fit.

## Classification and Discovery

Schemas must support categorization and tagging using the portal's common
`category_t`, `tag_t`, `entity_category_t`, and `entity_tag_t` infrastructure,
similar to APIs, workflows, agents, and skills.

- `entity_type` will be `'schema'`.
- `entity_id` should be `schema_lineage_id::text`, not raw `schema_id`. This
  lets tags and categories apply to the logical schema lineage rather than a
  specific immutable version, while still separating global and tenant schemas
  that use the same `schema_id`.
- `entity_category_t` connects schemas to categories.
- `entity_tag_t` connects schemas to tags.
- `schema-command` create/update payloads should use `categoryIds` and `tagIds`
  to match the existing taxonomy contract used by API, workflow, and skill
  forms.
- When `categoryIds` or `tagIds` are present on update, the command should
  replace that assignment set. An empty array clears assignments. An omitted
  field leaves the current assignment set unchanged.

These mappings enable discovery across the portal using category and tag
filters. Query paths must join through `category_t` and `tag_t`, enforce
`active = TRUE` on mapping rows and taxonomy rows, and resolve global plus
host-specific taxonomy labels for the selected host.

## Marketplace Schema Catalog

Add a Schema Catalog entry under Marketplace alongside API Catalog and Workflow
Catalog. If the navigation uses short labels, the menu label can be `Schema`,
but the page title should be `Schema Catalog`.

Recommended route:

```text
/app/marketplace/schema
```

Visible records should include:

- published global schemas visible to the caller
- published tenant schemas for the selected host
- draft or retired schemas only when the caller owns or administers the schema
- `json` schemas in the first release

Common filters:

- search text for schema id, name, description, source, and owner metadata
- schema type, starting with `json`
- schema status, such as draft, published, and retired
- categories from `getCategoryLabelByType(entityType = "schema")`
- grouped tags from `getTagLabelByType(entityType = "schema")`
- active or inactive state
- sort and card/list view options

Catalog cards should show a compact contract summary:

- schema id, name, latest published version, and type
- spec version, source, status, and scope provenance
- schema alias and external URL when external access is enabled
- categories and grouped tags
- whether a schema body is available for preview
- whether a JSON Schema can be used for config-backed form generation

Common actions:

- open a read-only schema details drawer
- preview JSON Schema source
- copy a schema reference, including `schemaId`, `schemaVersion`, and
  `schemaType`
- copy an external schema URL when `schema_alias` and `external_visible` are set
- create a new version when the user has schema write permission
- edit draft metadata and taxonomy assignments when permitted
- open the schema administration page for table-based management

## External Schema Access

External applications should be able to retrieve published schemas through
`portal-service/apps/portal-service`, similar to the existing `/r/data`
reference-data endpoint. The recommended route is:

```text
GET /r/schema/{schemaAlias}
```

Query parameters:

- `host` is optional. When present, the service first resolves a tenant schema
  for `host + schemaAlias`, then falls back to a global schema with the same
  alias. When omitted, only global schemas are considered.
- `version` is optional. When omitted, the service returns the latest published
  active version for the resolved alias. When present, the service returns that
  exact published or retired active version if it is still externally visible.
- `envelope` is optional. The default should return the schema body directly for
  external validators. `envelope=true` should return metadata plus
  `schemaBody`.

Default response for `schema_type = "json"` should be the JSON Schema document
itself with `Content-Type: application/schema+json` where possible. The response
should include headers such as:

```text
X-Schema-Id: security-jwt-claim-mapping
X-Schema-Alias: jwt-claim-mapping
X-Schema-Version: 1.0.0
X-Schema-Type: json
X-Schema-Source: global|tenant
```

Envelope response:

```json
{
  "schemaAlias": "jwt-claim-mapping",
  "schemaId": "security-jwt-claim-mapping",
  "schemaVersion": "1.0.0",
  "schemaType": "json",
  "specVersion": "2020-12",
  "schemaStatus": "P",
  "source": "global",
  "schemaBody": { }
}
```

The external route must only serve schemas that are:

- active
- published, or retired when an exact `version` is requested
- `external_visible = TRUE`
- visible in the requested host scope

Draft schemas must never be returned by `/r/schema/{schemaAlias}`. A missing,
inactive, private, or unauthorized alias should return `404` instead of leaking
that the schema exists.

`portal-service` should add a lightweight schema lookup service and cache,
separate from the `/r/data` reference cache. Suggested cache key:

```text
host + schemaAlias + version + envelope
```

The cache should be invalidated when a schema is published, retired, deleted, or
when alias/external visibility changes.

## Config Property Binding

Config property validation needs an explicit link from a config property to a
schema. The simplest useful binding is to add these nullable fields to the base
config property definition:

```text
config_property_t.schema_id
config_property_t.schema_version
```

This works because a config property has at most one schema for its value shape.
The selected `hostId` is still used during lookup so tenants can override the
global schema with the same `schemaId + schemaVersion` when needed.

The binding should be optional:

- scalar properties can continue to use `valueType` validation only
- `map` and `list` properties can attach JSON Schema for structured validation
- `File` and `Cert` properties should keep using their existing generated forms
  until file-specific schema handling is designed

The registry lookup for config validation should resolve in this order:

1. tenant-specific schema for `hostId + schemaId + schemaVersion`
2. global schema for `schemaId + schemaVersion`
3. no schema found, which disables schema-backed validation for that row

Only published schemas should be used to validate active config override
commands.

## API Changes

The existing `schema-query` actions can remain, but config validation needs a
tenant-aware versioned lookup. Add or evolve an action such as
`getSchemaByRef`:

```json
{
  "hostId": "host uuid",
  "schemaId": "security-jwt-claim-mapping",
  "schemaVersion": "1.0.0",
  "active": true
}
```

Response:

```json
{
  "schemaId": "security-jwt-claim-mapping",
  "schemaAlias": "jwt-claim-mapping",
  "schemaVersion": "1.0.0",
  "schemaType": "json",
  "specVersion": "v2020-12",
  "schemaStatus": "P",
  "schemaBody": "{...}",
  "source": "tenant"
}
```

`getSchema` should remain a metadata list query. It should not return
`schemaBody` by default because schema bodies can be large and are usually not
needed for table rendering.

`querySchemaCatalog` or an evolved `getSchema` should support server-side
catalog filtering:

```json
{
  "hostId": "host uuid",
  "offset": 0,
  "limit": 20,
  "active": true,
  "schemaTypes": ["json"],
  "schemaStatus": "P",
  "categoryIds": ["..."],
  "tagIds": ["..."],
  "tagMatch": "all",
  "globalFilter": "jwt"
}
```

Category filters should use OR semantics. Tag filters should support
`tagMatch = "all"` and `tagMatch = "any"`. The response should return
`categoryIds`, `categories`, `tagIds`, and `tags`, but omit `schemaBody` unless a
details action explicitly asks for it. It should also return `schemaAlias`,
`externalVisible`, and the derived external URL when alias-based access is
enabled.

`schema-command` should validate `schemaBody` before create or update. It
should reject invalid JSON Schema documents for `schema_type = "json"`. It
should also enforce the status rules:

- draft schemas can be edited
- publishing validates the schema body and makes that version available
- published schema bodies are immutable
- retired schemas remain readable but cannot be newly bound to config
  properties

`schema-command` should also support `schemaAlias` and `externalVisible`.
`schemaAlias` must be lower-case and URL-friendly, unique in the selected
global/host scope, and stable across versions of the same lineage.
`externalVisible` controls whether the alias can be served by
`portal-service /r/schema/{schemaAlias}`. A draft schema may carry an alias, but
the external route must not serve it until a published version exists.

Schema delete should remain a soft delete or retire operation for schemas that
may be referenced by config properties or historical overrides.

`schema-command` should support linking `categoryIds` and `tagIds` during schema
creation and update. `schema-query` already has `getSchemaByCategoryId` and
`getSchemaByTagId`; those actions should be hardened rather than reintroduced.
They must honor `hostId`, `offset`, `limit`, `active`, active taxonomy mapping
rows, active taxonomy labels, and active schema rows. They should return schema
metadata for catalog browsing and filtering, not full schema bodies by default.

## Config Update Page Integration

`getConfigUpdateProperties` should include schema metadata but not schema body:

```json
{
  "configId": "config uuid",
  "propertyId": "property uuid",
  "propertyName": "jwt.claimMapping",
  "valueType": "map",
  "schemaId": "security-jwt-claim-mapping",
  "schemaVersion": "1.0.0",
  "schemaType": "json",
  "schemaStatus": "P",
  "hasSchema": true
}
```

When the user opens a `map` or `list` editor, the frontend calls the
tenant-aware schema lookup and caches the result by:

```text
hostId + schemaId + schemaVersion
```

The structured editor should always provide raw JSON and YAML tabs. The Form tab
is enabled only when a published compatible schema is available. YAML input is
normalized to compact JSON before it is sent to the existing config command API,
because config property values are stored as strings.

## Validation Flow

Validation runs in two layers.

Frontend validation:

- parse scalar values according to `valueType`
- parse `list` values as JSON arrays
- parse `map` values as JSON objects
- run JSON Schema validation when a schema is available
- show validation errors next to the row or field that failed
- keep the draft dirty until the value is valid

Backend validation:

- load the config property metadata by `configId + propertyId`
- parse `propertyValue` according to `valueType`
- resolve the published schema for `hostId + schemaId + schemaVersion`
- validate the parsed value against the schema
- reject the command before event persistence when validation fails

Backend validation is authoritative. Frontend validation improves usability but
cannot replace command-side enforcement.

Validation errors should include enough detail for row-level UI feedback:

```json
{
  "code": "CONFIG_PROPERTY_SCHEMA_VALIDATION_FAILED",
  "configId": "config uuid",
  "propertyId": "property uuid",
  "schemaId": "security-jwt-claim-mapping",
  "schemaVersion": "1.0.0",
  "errors": [
    {
      "path": "$.issuer",
      "keyword": "required",
      "message": "issuer is required"
    }
  ]
}
```

## Security And RBAC

Schema registry access should follow the same tenant ownership model used by
other portal resources:

- global schemas are readable by authorized portal users
- tenant schemas are readable only within the selected host context
- schema create/update/delete requires write permission
- config command validation may read a schema internally even when the end user
  only has config update permission
- command authorization remains separate from schema validation

The frontend should not expose tenant-specific schema bodies from another host.
The backend lookup must enforce this even if the UI sends a forged `hostId`.

External schema access has a stricter rule: `/r/schema/{schemaAlias}` should
only return active schemas that are explicitly marked `external_visible = TRUE`.
It should return `404` for missing, private, draft, inactive, or unauthorized
aliases so external callers cannot enumerate private schema names.

## Testing

The first hardening pass should include tests for:

- create draft schema
- reject invalid `schemaBody`
- publish schema
- reject edits to published schema body
- retire schema
- tenant-specific lookup
- global fallback lookup
- schema metadata list excluding body
- schema body lookup by `hostId + schemaId + schemaVersion`
- schema alias validation and global/tenant uniqueness
- external visibility enforcement
- `/r/schema/{schemaAlias}` latest published lookup
- `/r/schema/{schemaAlias}?version=...` exact version lookup
- `/r/schema/{schemaAlias}` host-specific lookup with global fallback
- `/r/schema/{schemaAlias}` direct body and envelope response shapes
- create/update schema with `categoryIds` and `tagIds`
- replace and clear schema taxonomy assignments on update
- schema category and tag catalog filters, including active mapping rows
- tenant/global taxonomy collision prevention through `schema_lineage_id`
- JSON Schema `schema_type` validation
- Schema Catalog visibility, filters, and body-lazy result shape
- config property binding
- valid map/list config property override
- invalid map/list config property override
- scalar validation still works when no schema is attached
- version mismatch and `getFreshSchema`

## Implementation Order

Implement the schema registry foundation before enabling schema-backed
validation in the config update page. The registry work does not need to block
the entire config update page, but it must block the Form tab and backend schema
enforcement.

Recommended order:

1. Harden schema registry data model, lookup, and command validation.
2. Add schema alias and external visibility support.
3. Add taxonomy linkage through `categoryIds`, `tagIds`, and
   `schema_lineage_id`.
4. Add the Marketplace Schema Catalog entry and body-lazy catalog query.
5. Add `/r/schema/{schemaAlias}` in `portal-service/apps/portal-service`.
6. Add config-property-to-schema binding.
7. Add backend config property value validation in config command handlers.
8. Extend `getConfigUpdateProperties` to return schema metadata.
9. Add lazy schema lookup and typed Form tab in `portal-view`.
10. Add end-to-end tests for schema-backed config updates and catalog discovery.

The config update page can still ship a useful MVP with scalar validation and
raw JSON/YAML editors while the registry is being hardened. Once the registry
foundation is complete, the same page can enable schema-backed forms and command
validation without changing the operator workflow.

## Recommendation

Use the schema registry as the authoritative source for structured config
property schemas. Do not implement a separate local schema convention in
`portal-view`. Stabilize the registry enough for versioned, tenant-aware,
published-schema lookup, then use it to validate `map` and `list` config
property values in both the frontend editor and the backend command path.
