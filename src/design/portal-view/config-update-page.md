# Config Update Page

The current `portal-view` configuration admin area is complete but split across
many table pages and generated forms. A customer Settings page shows a denser
workflow: list applicable config properties in a tree, edit scalar values
inline, and open a modal for list/map values. This document proposes a similar
page for `portal-view` that can update config property overrides at the
environment, product, product version, instance, API, app, and app-api levels.
In this document, API, app, and app-api mean the instance-linked config
override scopes represented by `instanceApiId`, `instanceAppId`, and
`instanceApiId + instanceAppId`.

## Current Implementation

The customer Settings implementation is centered on these files:

- `Settings.jsx`
- `SettingsListView.jsx`
- `SettingsListMapModal.jsx`
- `InputForm.jsx`
- `JsonSchemaForm.jsx`

The useful behavior is:

- one page loads applicable config properties and the current custom values
- properties are displayed as a tree under `configName`
- scalar values are edited inline
- list and map values open a modal with form, raw JSON, and raw YAML tabs
- save chooses create or update based on whether the override exists
- delete removes the override and lets the inherited value show again

The customer implementation currently handles instance, instance API, instance
app, and instance app API targets. It chooses the query/write action from
`instanceId`, `instanceApiId`, and `instanceAppId`.

`portal-view` already has separate config override pages:

- `src/pages/config/ConfigEnvironment.tsx`
- `src/pages/config/ConfigProduct.tsx`
- `src/pages/config/ConfigProductVersion.tsx`
- `src/pages/config/ConfigInstance.tsx`
- `src/pages/config/ConfigInstanceApi.tsx`
- `src/pages/config/ConfigInstanceApp.tsx`
- `src/pages/config/ConfigInstanceAppApi.tsx`

Those pages use Material React Table, fetch one override aggregate at a time,
and navigate to generated `react-schema-form` routes for create/update. The form
definitions live in `src/data/Forms.json`, and the generic form runner is
`src/components/Form/Form.tsx`.

The existing form approach works for CRUD, but it is inefficient for config
editing because the user must pick a config, pick a property, leave the list
page, edit one value, and return.

## Goals

- Provide a single task-oriented config editor for the seven override scopes.
- Show the property catalog and current override values together.
- Preserve the existing config-command write APIs.
- Preserve optimistic concurrency by carrying `aggregateVersion` for existing
  override rows.
- Avoid client-side joins across independently paginated result sets.
- Keep existing table pages and generated forms available as admin fallback
  routes.
- Support scalar editing inline and structured list/map editing in a modal.
- Show inherited/default value and custom override value separately.
- Make delete/reset mean "remove this override", not "delete the base property".
- Support read-only and hidden states when the user lacks write permission for
  a scope or target.

## Non-Goals

- Do not replace `react-schema-form` globally.
- Do not replace the existing config list pages during the first release.
- Do not edit `File` or `Cert` property values inline in the first release.
  Those can continue to use existing generated forms.
- Do not require every config property to have a typed form schema before the
  page is useful.
- Do not add a bulk transaction command in the first release. The UI can stage
  multiple changes and then orchestrate the existing single-row commands.

## Recommended UX

Add a `Config Update` page under the configuration task area. The first row is
a scope and target selector:

- Scope: Environment, Product, Product Version, Instance, API, App, App API
- Target: the selected scope's identity, such as `environment`, `productId`,
  `productVersionId`, `instanceId`, `instanceApiId`, `instanceAppId`, or both
  app/API ids for app-api
- Optional filters: config phase, config type, property type, resource type,
  and "show overridden only"
- Save mode: staged changes by default, with optional single-row Apply for
  quick edits

Below the selectors, render a tree/table:

- group rows by `configName`
- property leaf rows show `propertyName`
- columns: value type, inherited value, override value, effective source,
  required, resource type, config phase, description, status
- row status: inherited, overridden, dirty, saving, conflict, error
- toolbar actions: expand all, collapse all, refresh, reset override,
  review changes, apply changes
- row action menu: view history, open fallback form, copy identifiers

Editing behavior:

- `string`: inline text editor or larger popover editor for long values
- `boolean`: select true/false
- `integer` and `float`: numeric editor with validation before save
- `list` and `map`: open a structured modal
- unsupported `valueType`: view-only with a link to the existing form route
- `propertyType` `File` or `Cert`: open the existing create/update form in a
  drawer or modal overlay

The page should keep the inherited/default value visible while editing an
override. If the override is deleted, the row remains visible and falls back to
the inherited value.

The staged-change panel should list every pending create, update, and reset
before applying. This matters for coordinated changes such as enabling a flag
and setting a related URL. The backend commands can still run one by one, but
the user gets a review step and can see partial failures without losing the
full set of intended changes.

The row action menu should include View History. It should link to the audit
log or history page pre-filtered by `configId`, `propertyId`, and the selected
scope target. The row already shows `updateUser` and `updateTs`; history gives
operators the deeper trail they need when debugging production configuration
changes.

## Structured Value Modal

The modal should start with raw JSON and raw YAML tabs. If a schema is available
for the property, add a Form tab.

The customer code loads schema assets with:

```text
schemas/<propertyName>/<propertyName>.json
schemas/<propertyName>/config.js
```

`portal-view` does not currently have this property-schema convention, so the
first implementation should not depend on local schema assets. Use raw
JSON/YAML with syntax and JSON validation first. Typed form support should come
from the light-portal schema registry through `schema-query`, `schema-command`,
and `schema_t`.

If a row has a `schemaId` and `schemaVersion`, the dialog should lazily fetch
the published schema body from `schema-query` when the user opens the structured
editor. The main `getConfigUpdateProperties` response should include schema
metadata but not `schemaBody`, so the paginated table does not move large schema
documents unnecessarily.

The schema association should key by `configId + propertyId`. Human-friendly
keys such as `configName + propertyName` can be shown in the UI, but should not
be used as the durable validation key.

List/map values should be saved as compact JSON strings because the command
APIs store `propertyValue` as a string.

## Schema Registry Validation

The schema registry should be used for structured `map` and `list` values once
the registry is hardened enough for production validation. The config update
page should treat the registry as optional per property: rows with no schema
still use `valueType` validation and raw JSON/YAML editing.

`getConfigUpdateProperties` should return lightweight schema metadata:

```json
{
  "schemaId": "security-jwt-claim-mapping",
  "schemaVersion": "1.0.0",
  "schemaType": "json",
  "schemaStatus": "P",
  "hasSchema": true
}
```

The UI should enable the Form tab only when the schema exists, is published, and
is compatible with the property value type. Schema documents should be cached by
`hostId + schemaId + schemaVersion`, with host-specific lookup falling back to a
global schema.

Validation must run in both places:

- frontend validation gives immediate editor feedback and highlights the JSON
  path that failed
- backend validation remains authoritative in the config command handlers before
  a create or update override is accepted

Backend validation should parse `propertyValue` according to `valueType` before
running JSON Schema validation. The UI should normalize YAML input to compact
JSON before sending the command payload, so the command APIs continue to receive
string values.

The schema registry needs a config-property binding before this can be enabled.
The preferred minimal binding is `schemaId + schemaVersion` on the base config
property definition. If tenant-specific schemas are needed later, schema lookup
can resolve the same schema id/version against the selected `hostId` first and
then fall back to the global row.

## API Matrix

The write side can reuse the current command APIs.

| Scope | Create | Update | Delete |
| --- | --- | --- | --- |
| Environment | `createConfigEnvironment` | `updateConfigEnvironment` | `deleteConfigEnvironment` |
| Product | `createConfigProduct` | `updateConfigProduct` | `deleteConfigProduct` |
| Product Version | `createConfigProductVersion` | `updateConfigProductVersion` | `deleteConfigProductVersion` |
| Instance | `createConfigInstance` | `updateConfigInstance` | `deleteConfigInstance` |
| API | `createConfigInstanceApi` | `updateConfigInstanceApi` | `deleteConfigInstanceApi` |
| App | `createConfigInstanceApp` | `updateConfigInstanceApp` | `deleteConfigInstanceApp` |
| App API | `createConfigInstanceAppApi` | `updateConfigInstanceAppApi` | `deleteConfigInstanceAppApi` |

For existing override rows, the update/delete payload must include the current
`aggregateVersion` so the event persistence layer can enforce the monotonic
version check. For new override rows, the page sends the scope identity,
`configId`, `propertyId`, and `propertyValue`.

## Security And RBAC

The page must not assume that a user who can view configuration can write every
override scope. The selected scope and target should be checked against the
same permission model used by the existing config admin routes and command
handlers.

Recommended behavior:

- hide scopes the user cannot see
- show read-only rows for scopes the user can read but cannot update
- disable apply/reset controls when the selected target is not writable
- show a lock icon or tooltip for read-only rows
- keep backend command authorization authoritative, even when the UI already
  filtered the control

Unauthorized command responses should be mapped back to the row that triggered
the command. The page should not fail the entire table because one row is not
writable.

## Read Model

The instance-facing scopes already have applicable-property queries:

- `getApplicableConfigPropertiesForInstance`
- `getApplicableConfigPropertiesForInstanceApi`
- `getApplicableConfigPropertiesForInstanceApp`
- `getApplicableConfigPropertiesForInstanceAppApi`

These queries return property metadata and inherited/effective values, including:

- `configId`
- `configName`
- `configPhase`
- `configType`
- `propertyId`
- `propertyName`
- `propertyType`
- `propertyValue`
- `propertySource`
- `propertySourceType`
- `valueType`
- `resourceType`
- `required`
- `displayOrder`

The same page needs current override metadata from:

- `getConfigInstance`
- `getConfigInstanceApi`
- `getConfigInstanceApp`
- `getConfigInstanceAppApi`

The page should not join applicable rows and override rows across separately
paginated API calls. That produces brittle pagination, filtering, sorting, and
row-count behavior. Instead, Phase 1 should add a merged backend read model that
returns one row per configurable property with inherited value, override value,
effective value, override metadata, and permission hints.

Environment, product, and product version currently have list/getFresh queries
for existing overrides, but they do not have equivalent applicable-property
queries:

- `getConfigEnvironment`
- `getConfigProduct`
- `getConfigProductVersion`

The new merged query should cover these scopes before they are exposed in the
new page. A temporary client merge is acceptable only for a local prototype with
unpaginated data; it should not be shipped as the production page behavior.

## Proposed Generic Query

Add a Phase 1 query such as `getConfigUpdateProperties` in `config-query`.

Request:

```json
{
  "hostId": "host uuid",
  "scope": "instance",
  "target": {
    "instanceId": "instance uuid"
  },
  "filters": {
    "configPhases": ["R"],
    "propertyTypes": ["Config"],
    "resourceTypes": ["all"]
  },
  "offset": 0,
  "limit": 1000,
  "active": true
}
```

Response:

```json
{
  "total": 1,
  "properties": [
    {
      "scope": "instance",
      "hostId": "host uuid",
      "configId": "config uuid",
      "configName": "security.yml",
      "configPhase": "R",
      "propertyId": "property uuid",
      "propertyName": "jwt.clockSkew",
      "propertyType": "Config",
      "valueType": "integer",
      "resourceType": "all",
      "required": false,
      "schemaId": "security-jwt-clock-skew",
      "schemaVersion": "1.0.0",
      "schemaType": "json",
      "schemaStatus": "P",
      "defaultValue": "60",
      "defaultSourceType": "config_property",
      "overrideValue": "120",
      "overrideAggregateVersion": 3,
      "effectiveValue": "120",
      "effectiveSourceType": "config_instance",
      "canUpdate": true,
      "canDeleteOverride": true
    }
  ]
}
```

This query should be read-only. It does not need new write commands.

The query owns inheritance and candidate selection. The frontend owns
presentation, editing state, and calls to the existing command APIs.

## Frontend Structure

Recommended files:

```text
src/pages/config/update/ConfigUpdatePage.tsx
src/pages/config/update/ConfigUpdateTable.tsx
src/pages/config/update/ConfigValueEditor.tsx
src/pages/config/update/ConfigStructuredValueDialog.tsx
src/pages/config/update/configUpdateScopes.ts
src/pages/config/update/configUpdateApi.ts
src/pages/config/update/configValue.ts
src/pages/config/update/configUpdateDraft.ts
```

`configUpdateScopes.ts` should be the single source of truth for scope metadata:

```ts
type ConfigUpdateScope = {
  id: 'environment' | 'product' | 'productVersion' | 'instance' | 'api' | 'app' | 'appApi';
  label: string;
  targetKeys: string[];
  applicableQuery?: string;
  overrideQuery: string;
  overrideResponseKey: string;
  createAction: string;
  updateAction: string;
  deleteAction: string;
  getFreshAction?: string;
  defaultResourceTypes?: string[];
  defaultConfigPhases?: string[];
};
```

The page should avoid hard-coding create/update/delete branching inside cell
handlers. The handler asks the selected scope metadata which action and keys to
use.

## Draft And Apply Flow

The default edit mode should stage changes locally. A dirty row is not saved
until the user chooses Apply for that row or Review & Apply from the toolbar.

The draft model should track:

- operation: create, update, reset
- previous effective value
- next override value
- scope target keys
- `configId`
- `propertyId`
- current `aggregateVersion`
- validation state

The review dialog should group changes by operation and show enough context for
operators to catch mistakes before applying. If multiple commands are applied
and one fails, the dialog should show which rows succeeded and which rows need
attention. The page should refetch or refresh successful rows and leave failed
rows dirty with their error state intact.

## Save Flow

1. User edits a row.
2. UI validates the value against `valueType` and the schema registry when a
   published schema is attached to the property.
3. UI marks the row dirty and stores a draft operation.
4. User applies a row or opens Review & Apply.
5. UI builds payload from selected scope, row `configId`, row `propertyId`, and
   normalized `propertyValue`.
6. If an active override row exists, call the update action and include
   `aggregateVersion`.
7. If no active override row exists, call the create action.
8. On success, update the row with returned aggregate version or refetch that
   row.
9. On conflict or error, keep the draft value, restore the displayed committed
   value, and show the row error.

The local override map should store the full override row, not just the string
value. At minimum it needs:

- `propertyValue`
- `aggregateVersion`
- `active`
- scope identity fields
- `updateUser`
- `updateTs`

Before update or delete, the UI should support the same `getFresh*` pattern
used by the existing admin pages. If the row has been open for a while, the
Apply action can fetch the latest row to get the freshest `aggregateVersion`.
At minimum, a version conflict must offer a "Refresh Row & Try Again" action
that reloads that row, compares the current backend value with the user's draft,
and lets the user reapply intentionally.

Validation errors should stay close to the edited cell. For example, an invalid
integer should keep the cell in edit/error state with a short message. Backend
validation, authorization, and conflict errors should be attached to the row
that caused them, not only shown as a global toast.

## Reset Flow

Reset means delete the override for the selected target and property.

1. User selects an overridden row.
2. UI calls the scope's delete action with target keys, `propertyId`, and
   `aggregateVersion`.
3. On success, clear `overrideValue` and `overrideAggregateVersion`.
4. The displayed effective value reverts to the inherited/default value.

Rows with no override should not allow reset.

Like update, reset should support `getFresh*` before delete or expose the same
"Refresh Row & Try Again" conflict path.

## Routing

Add a route such as:

```text
/app/config/update
```

The route should accept task context and target context through query params:

```text
/app/config/update?scope=api&instanceApiId=...&task=mcp-onboard-api
```

Existing config table pages can link to it when they already have target
context. Existing generated forms should remain available from row overflow
actions for advanced edits and File/Cert values.

The View History row action should preserve context by opening the audit trail
in a drawer, modal, or task-aware route with filters already applied. The filter
payload should include the selected scope, target keys, `configId`, and
`propertyId`.

For fallback forms, prefer opening the existing `react-schema-form` experience
inside a drawer or modal over navigating away from the table. That keeps the
user's current scope, filters, expansion state, selected row, and staged changes
intact. Full-page navigation can remain as a secondary fallback for complex
forms that cannot safely render in an overlay.

## Implementation Plan

Phase 0: schema registry foundation for config validation

- Harden `schema-query`, `schema-command`, and `schema_t` enough for production
  JSON Schema lookup.
- Add a durable config-property-to-schema association with `schemaId` and
  `schemaVersion`.
- Make schema lookup tenant-aware: host-specific schema first, global schema
  second.
- Validate schema bodies on schema create/update.
- Add backend config value validation for create/update override commands.
- Add tests for schema CRUD, tenant/global lookup, version pinning, and invalid
  config property values.

Phase 1: merged read model and instance-facing MVP

- Add `getConfigUpdateProperties` or an equivalent merged query in
  `config-query`.
- Return candidate properties, inherited values, current override values,
  override metadata, schema metadata, and permission hints in one
  paginated/sortable result.
- Build the page for Instance, API, App, and App API.
- Use existing command APIs for create/update/delete.
- Support scalar inline edits.
- Support list/map raw JSON/YAML modal.
- Support staged changes and Review & Apply.
- Support row-level validation/error/conflict states.
- Enable the typed Form tab only for properties with a published schema.

Phase 2: higher-level scopes

- Add Environment, Product, and Product Version selectors.
- Expose each scope only through the merged read model, not a client-side
  paginated join.
- Ensure product version respects product-version config/property mappings
  where available.

Phase 3: typed structured forms

- Use the schema registry for list/map config properties.
- Support custom validators by property key.
- Add tests for string array, object array, map, and malformed JSON/YAML values.

Phase 4: task integration

- Link from configuration task panels to `/app/config/update`.
- Add contextual next actions from instance, API, app, and app-api pages.
- Keep generated create/update forms as drawer/modal fallback actions.

## Risks And Open Questions

- Environment inheritance needs a precise target rule. Existing applicable
  instance queries include `environment_property` as an inherited source, but
  the target environment is not selected by the current instance-facing query
  contract.
- Product and product-version candidate lists can be too broad if they are
  loaded from all config properties. Product version should eventually use the
  product version config mappings.
- The customer Settings code stores custom values in a map keyed by
  `propertyId`; for `portal-view`, the key should include scope target plus
  `propertyId` to avoid collisions when multiple targets are loaded.
- `propertyId` is the stable merge key only after the candidate list has been
  constrained to the selected target. If multiple configs can contain the same
  property id in unusual imports, use `configId + propertyId`.
- The page should avoid silently editing `File` or `Cert` values as plain text.
- Staged apply is not atomic until a bulk command exists. The UI must show
  partial success and partial failure clearly.
- Overlaying generated forms in a drawer depends on the form runner handling
  router state, success/failure navigation, and task context without forcing a
  full-page transition.
- The schema registry is not fully implemented and tested yet. Schema-backed
  validation should not be enabled until tenant-aware lookup, version pinning,
  and backend command validation are in place.

## Recommendation

Build the page as a new task-oriented editor, not as a rewrite of the existing
config admin tables. Make the merged `getConfigUpdateProperties` read model a
Phase 1 backend requirement so the frontend does not perform brittle
pagination-sensitive joins. Start frontend exposure with the four
instance-facing scopes, then add environment, product, and product version once
the same merged query handles their inheritance and candidate-selection rules.

Implement the minimal schema registry foundation before enabling schema-backed
validation in the config update page. The raw JSON/YAML editor and scalar
`valueType` validation can be built in parallel, but the Form tab and backend
schema enforcement should wait for the registry work.
