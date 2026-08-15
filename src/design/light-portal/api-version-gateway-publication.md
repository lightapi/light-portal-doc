# API Version Publication To Gateway

## Status

Proposed design.

This document defines the Portal workflow for publishing one API version to a
Light Gateway instance and, when requested, replacing older versions of the
same API on that instance. Publication stages desired Gateway configuration in
the Portal projections. Runtime activation remains an explicit configuration
snapshot operation.

## Purpose

Today, an administrator who adds an API endpoint must move through API Detail,
Service Endpoint, Access Overview, Instance Admin, Instance API, and Instance
API Config. The final **Sync Config From API** action pulls access-control data
into an already existing Instance API association. The operator may also have
to remove old `ruleBodies` and `endpointRules` properties before synchronizing.

That workflow separates related decisions across too many pages and does not
model an API-version upgrade as one operation. It also makes Instance Admin the
starting point even though the API version is the source being published.

This design adds **Publish to Gateway** to each API-version row on API Detail.
The action lets an authorized operator:

- select a Gateway instance;
- see versions of the same API already associated with that Gateway;
- choose whether those versions remain active or are retired;
- preview the API-derived configuration being staged; and
- publish the new version and any selected retirements as one auditable
  command.

The design is related to
[Control-Plane Policy Publication Through Config Server](./control-plane-policy-config-server.md).
API-version publication stages the desired instance configuration described
here. A configuration snapshot and current-pointer change remain the immutable
runtime publication boundary described there.

## Decision Summary

1. **Publish to Gateway** is a row action for a specific API version on
   `/app/apiDetail`.
2. Access Overview remains the place to edit and review endpoint access. It
   does not publish Gateway configuration.
3. After a Gateway is selected, Portal shows active and inactive versions of
   the same `apiId` associated with that Gateway.
4. The operator explicitly selects **Keep Existing Versions** or **Replace
   Selected Versions**. Portal does not infer replacement from a version
   string.
5. Portal creates or reactivates the new `instance_api_t` association when
   necessary and reconciles its complete selected property sections.
6. The first publication section is access control, which owns
   `rule.endpointRules` and `rule.ruleBodies`. The contract supports additional
   API-derived sections later.
7. Replacement publishes and validates the new desired state before retiring
   the selected old versions.
8. Retirement is event-backed soft deactivation. It includes the old Instance
   API association and its dependent active records; it is not a direct SQL
   delete.
9. Publication records are immutable audit evidence. Mutable
   `instance_api_property_t` rows remain desired-state projections rather than
   publication history.
10. A successful publication is `STAGED`. It does not prove that a running
    Gateway has loaded the change.
11. Instance Admin retains the snapshot creation, comparison, activation, and
    rollback workflow.
12. The existing **Sync Config From API** action may remain temporarily as an
    administrator repair path, but it is not the normal publication workflow.

## Goals

- Reduce a multi-page operation to one API-version-centered publication flow.
- Support both single-version upgrades and intentional parallel API versions.
- Prevent stale `endpointRules`, `ruleBodies`, or other API-derived properties
  from surviving a replacement.
- Preserve event sourcing, optimistic concurrency, ownership, and replay.
- Keep server-side API data authoritative; the browser never compiles or
  submits final Gateway property values.
- Make the effects of replacement visible before the operator confirms them.
- Avoid an outage by establishing the new association before retiring the old
  one.
- Keep runtime activation immutable and reversible through configuration
  snapshots.
- Leave room for future API-level publication sections without moving the
  action to another page.

## Non-Goals

- Access Overview does not become a deployment or publication page.
- Creating or editing an API version does not automatically change a Gateway.
- Publishing an API version does not automatically activate a configuration
  snapshot.
- Portal does not assume that version strings use Semantic Versioning.
- A higher-looking version does not automatically supersede another version.
- Replacement does not physically delete projection or event history.
- This design does not define traffic draining, request migration, or
  application compatibility between API versions.
- This design does not move Gateway Tool publication back into
  `instance_api_property_t`; the Tool catalog remains its authoritative
  publication path.

## Terminology

| Term | Meaning |
| --- | --- |
| API version | One registered API contract identified by `apiVersionId`. |
| Gateway instance | An active Portal instance eligible to run Light Gateway. |
| Instance API | The association between a Gateway instance and one API version, stored in `instance_api_t`. |
| Publication section | A server-side compiler that owns a declared set of Gateway configuration properties. |
| Keep | Publish the requested version without retiring an existing version. |
| Replace | Publish the requested version, then retire explicitly selected existing Instance APIs. |
| Retire | Soft-deactivate an Instance API and the dependent records that must not return if it is reactivated. |
| Staged | Desired Portal configuration was projected successfully but no new current snapshot has been activated. |
| Activated | A validated configuration snapshot containing the publication became current for the Gateway. |

## User Experience

### API Detail row action

`/app/apiDetail` lists multiple versions, so **Publish to Gateway** belongs in
the action column of each version row. The action receives the row's
`hostId`, `apiId`, and `apiVersionId`. Publication is never an unqualified
API-level action because configuration and replacement decisions are
version-specific.

The action is enabled only when the user may publish the API version. Server
authorization remains authoritative even when the UI disables the action.

### Step 1: Select Gateway

The dialog lists active Gateway instances that the current user may administer.
Each option includes:

- instance name and `instanceId`;
- product and product version;
- environment or environment tag where available;
- existing association status for the selected `apiVersionId`; and
- current configuration snapshot identity and timestamp where available.

The generic instance label query is not sufficient as the long-term contract
because it lists instances without expressing Gateway eligibility,
authorization, or publication status. A publication-candidate query should
return the complete server-authorized view needed by this dialog.

### Step 2: Review existing versions

After a Gateway is selected, Portal shows every active and inactive Instance
API for the same `apiId` on that Gateway. It does not show unrelated APIs.

| Field | Purpose |
| --- | --- |
| API version | Human-readable version currently associated with the Gateway. |
| `instanceApiId` | Durable Instance API identity used for audit and retirement. |
| State | Active, inactive, or selected for replacement. |
| Path prefixes | Indicates whether versions have distinct routing boundaries. |
| Application bindings | Shows consumers that may be affected by retirement. |
| Property count | Shows whether version-specific configuration exists. |
| Last update | Helps identify stale or recently changed associations. |

The operator chooses one publication mode:

#### Keep Existing Versions

The selected API version is created, reactivated, or updated while every other
version remains unchanged. This supports versioned path prefixes, compatibility
windows, canary rollout, and blue/green migration.

#### Replace Selected Versions

The operator selects one or more existing Instance APIs to retire after the new
version is staged successfully. The dialog requires explicit confirmation and
shows dependent path prefixes, application bindings, and properties that will
be retired or migrated.

The initial implementation must not provide a mode named "replace all older
versions." "Older" is ambiguous without an explicit lifecycle policy and
cannot be determined safely by lexical version comparison.

### Step 3: Review publication sections

The dialog previews the sections that Portal will compile. The first section
is:

```text
Access control
  rule.endpointRules
  rule.ruleBodies
```

The preview reports source counts, validation results, and a normalized diff
against the selected Gateway's current Instance API properties. It may show
property values to an authorized administrator, but those values are generated
by the server and are not editable in the publication dialog.

Future sections may be added only with an explicit property-ownership contract.
Two publication sections must not silently write the same property.

### Step 4: Confirm and publish

The confirmation identifies:

- the new API version;
- the target Gateway;
- whether the association will be created, reactivated, or updated;
- the selected sections;
- existing versions that will remain active;
- existing versions that will be retired;
- dependent bindings that will be migrated or retired; and
- the fact that a configuration snapshot must still be activated.

On success, the dialog reports `STAGED` and links to the target Instance API
and Instance Admin snapshot workflow.

## Version Upgrade Policy

### Explicit decision is the default

The first release requires the operator to choose which versions to retire.
This is safer than automatic replacement because two versions may intentionally
coexist. Different path prefixes, consumer migration schedules, or rollback
requirements can all make parallel publication correct.

### Optional automatic policy

Automatic replacement may be added later through an explicit API or Gateway
publication policy:

```text
MULTI_VERSION
SINGLE_ACTIVE_VERSION
```

`MULTI_VERSION` retains existing versions unless the operator selects them for
retirement. `SINGLE_ACTIVE_VERSION` preselects all other active versions of the
same `apiId` for retirement and clearly shows that decision before submission.
The server enforces the policy again when processing the command.

The policy controls lifecycle behavior; it does not derive ordering from
`apiVersion` text.

### Routing conflicts

Keeping multiple versions is valid only when the resulting Gateway routing is
unambiguous. The preview rejects or requires resolution for conflicts such as:

- identical path prefixes with incompatible upstream targets;
- duplicate effective endpoint routes;
- incompatible protocol handler configuration; or
- application bindings that cannot distinguish the versions.

A replacement may reuse a path prefix only when the new configuration and old
retirement are part of the same staged publication.

## Data Model

### Existing projections

The design retains the existing tables:

```text
instance_t
  -> instance_api_t
       -> instance_api_property_t
       -> instance_api_path_prefix_t
       -> instance_app_api_t
            -> instance_app_api_property_t
```

`instance_api_t` already enforces one association for
`(host_id, instance_id, api_version_id)`. `instance_api_property_t` identifies
one override by `(host_id, instance_api_id, property_id)`.

Foreign-key `ON DELETE CASCADE` clauses protect physical deletion, but normal
Portal deletion is soft deactivation. Therefore, retiring an
`instance_api_t` row does not automatically deactivate its child rows.

### Publication record

Add an immutable publication projection, conceptually:

```text
api_gateway_publication_t
  host_id
  publication_id
  instance_id
  api_id
  api_version_id
  instance_api_id
  publication_mode
  selected_sections
  compiled_manifest
  retired_instance_api_ids
  status
  requested_by
  requested_ts
  completed_ts
  aggregate_version
```

`compiled_manifest` stores the exact desired property identities and values,
path-prefix decisions, binding decisions, and source revisions used by the
publication. Replay projects the manifest; it does not recompile mutable API
access tables.

The publication record provides audit and idempotent retry evidence.
`instance_api_property_t` continues to hold the latest mutable desired state
used for snapshot creation.

## Query Contracts

### `getApiGatewayPublicationCandidate`

The candidate query accepts:

```json
{
  "hostId": "uuid",
  "apiVersionId": "uuid"
}
```

It returns only Gateway instances the caller may publish to. Each candidate
contains the target instance metadata, association state for the selected
version, versions of the same API already on that instance, dependent record
counts, current snapshot metadata, and any policy that constrains replacement.

The server resolves `apiId` and `apiVersion` from `apiVersionId`. The client
does not submit them as authoritative identity.

### `previewApiVersionGatewayPublication`

The preview accepts the selected `instanceId`, `apiVersionId`, publication
mode, selected retirement IDs, selected sections, and binding decisions. It
returns:

- resolved source identity and revisions;
- association action: `CREATE`, `REACTIVATE`, or `UPDATE`;
- normalized desired properties;
- create, update, reactivate, deactivate, and unchanged counts;
- routing conflicts and validation errors;
- retirement effects;
- a short-lived `previewToken`; and
- the concurrency versions that must still match at publication time.

The token binds the confirmation to the normalized request and compiled
manifest. It is not a substitute for server-side revalidation.

## Command Contract

### `publishApiVersionToGateway`

The command accepts the decision, not browser-generated configuration:

```json
{
  "hostId": "uuid",
  "apiVersionId": "uuid",
  "instanceId": "uuid",
  "publicationMode": "REPLACE_SELECTED",
  "retireInstanceApiIds": ["uuid"],
  "sections": ["ACCESS_CONTROL"],
  "bindingActions": [],
  "previewToken": "opaque",
  "expectedApiVersionAggregateVersion": 7,
  "expectedInstanceAggregateVersion": 12
}
```

The HTTP request also carries an `Idempotency-Key`. A replay of the same key
and normalized request returns the original publication result. Reusing the
key with a different request is rejected.

The command must not accept `endpointRules`, `ruleBodies`, `instanceApiId`, or
property IDs as authoritative client input. Portal resolves and compiles those
values from current server-side records.

### Result

```json
{
  "publicationId": "uuid",
  "status": "STAGED",
  "instanceId": "uuid",
  "instanceApiId": "uuid",
  "associationAction": "CREATE",
  "properties": {
    "created": 2,
    "updated": 0,
    "reactivated": 0,
    "deactivated": 0,
    "unchanged": 0
  },
  "retiredInstanceApiIds": ["uuid"],
  "snapshotActivationRequired": true
}
```

Partial success is not returned. A failed command reports no successful
retirement and identifies whether the failure occurred during validation,
event append, or synchronous projection.

## Server-Side Compilation

### Authoritative source

The compiler loads the selected active API version and its current endpoint,
permission, filter, and rule projections. It also resolves the registered
property IDs for `rule.endpointRules` and `rule.ruleBodies`.

The compiler must fail closed when a required source query fails. A failed
query is different from a successful query returning no configured entries.

### Complete replacement semantics

Each selected publication section owns a complete property set. For access
control, the desired manifest always addresses both owned properties, including
the empty state. Publication must not omit an event merely because the compiled
map is empty; doing so can leave a stale value active on the Gateway.

The section contract defines whether an empty desired value is represented by:

- an active canonical empty value such as `{}`; or
- a soft-deactivated property that intentionally falls back to a lower scope.

Access-control publication should use the representation required to prevent
stale or inherited rules from granting unintended access. That behavior must
be covered by an explicit empty-source test.

### Reconciliation

For every owned property, the compiler compares the desired manifest with the
target projection:

| Current state | Desired state | Event action |
| --- | --- | --- |
| Missing | Present | Create |
| Inactive | Present | Create/reactivate above the stored aggregate version |
| Active and different | Present | Update |
| Active and identical | Present | No property event |
| Active | Absent by section contract | Delete/deactivate |

Event versions use the greater of the current projection version and event
store version, plus one. The publication manifest records unchanged values even
when no property event is required.

## Association Creation And Concurrency

Portal resolves the Instance API by
`(hostId, instanceId, apiVersionId)`:

- active association: reuse its `instanceApiId`;
- inactive association: reuse and reactivate its `instanceApiId` with a newer
  aggregate version; or
- no association: allocate an `instanceApiId` and emit a create event.

The database uniqueness constraint remains the final guard, but publication
must handle concurrent first publication deliberately. Two requests must not
create different IDs for the same natural identity and allow one request to
fail only during projection. The implementation must serialize creation by the
natural key, use a deterministic identity, or recover the winning association
and retry before appending an incompatible manifest.

The candidate and preview responses are advisory. The command rechecks API,
Gateway, association, property, and retirement aggregate versions immediately
before event creation. A stale decision returns a conflict and requires a new
preview.

## Replacement And Retirement

### Safe ordering

A replacement command builds one ordered event set:

1. record the immutable publication attempt;
2. create or reactivate the new Instance API association when required;
3. create, update, reactivate, or deactivate the new association's selected
   properties;
4. create or migrate required path-prefix and application-binding state;
5. soft-deactivate dependent state for every selected old Instance API;
6. soft-deactivate each selected old `instance_api_t` association; and
7. mark the publication `STAGED`.

The new version is established before the old versions are retired. Event
append treats the publication as one command, and synchronous projection
applies its ordered events in one database transaction.

### Retirement closure

Soft-deactivating only `instance_api_t` makes its properties ineffective in
normal effective-configuration queries, but leaves active child rows behind.
If the association is later reactivated, those stale children can become
effective again. A complete retirement therefore evaluates and handles:

- every active `instance_api_property_t` row;
- every active `instance_api_path_prefix_t` row;
- every active `instance_app_api_t` relationship;
- every active `instance_app_api_property_t` row under those relationships;
  and
- any publication or binding whose domain identity is tied to the retiring
  `instanceApiId`.

The preview classifies each dependency as **Migrate**, **Retire**, **Keep via
old version**, or **Block**. The command rejects a replacement when a required
decision is missing.

Gateway Tool publications are instance-level in the current design. Retirement
must reconcile source bindings that refer to the old API version without
blindly deleting Tools belonging to other API versions or workflows.

### Rollback

Soft-deactivated records retain audit and replay history. Rolling back to a
previous version is another publication:

1. select the previous API version;
2. preview its archived or newly compiled desired configuration;
3. reactivate or reconcile its Instance API graph;
4. optionally retire the currently active version; and
5. create and activate a new configuration snapshot.

Rollback never rewrites or reselects a historical snapshot as though the
desired-state publication had not changed. Snapshot-pointer rollback remains
available for immediate runtime recovery, while a follow-up publication makes
Portal desired state agree with the chosen runtime state.

## Event And Projection Requirements

The design reuses existing domain events where they express the intended
state, including Instance API and Instance API property create, update, and
delete events. It adds a publication event or aggregate that carries the exact
compiled manifest and replacement decision.

Required invariants are:

- event data contains stable IDs and compiled values needed for deterministic
  replay;
- replay never reads current mutable access-control rows to rebuild an old
  publication;
- create, update, reactivation, and retirement use monotonic aggregate
  versions;
- child retirement events are emitted explicitly because parent deletion is
  soft;
- the publication and all affected aggregates share a command correlation ID;
- append failure produces no staged publication;
- synchronous projection failure does not report `STAGED`; and
- replay can complete a canonically appended publication whose synchronous
  projection previously failed.

## Authorization

Publication combines API ownership and Gateway administration. Possessing the
generic `portal.w` scope is necessary but not sufficient.

The server verifies that the caller may:

- read and publish the selected API version;
- administer the selected Gateway instance;
- create or reactivate its Instance API association;
- modify the selected configuration sections; and
- retire every selected old Instance API and affected binding.

The candidate query omits unauthorized Gateway instances. The command performs
the same checks independently to prevent forged IDs or stale browser state.

Host identity comes from trusted request context. A client-supplied `hostId`
must match that context and cannot broaden tenancy.

## Runtime Activation

Publication changes Portal desired state. It does not by itself prove that a
running Light Gateway has loaded the new configuration.

After a publication reaches `STAGED`, Instance Admin performs the established
runtime flow:

1. create an immutable configuration snapshot from the projected desired
   state;
2. compare it with the current snapshot;
3. validate the rendered Gateway configuration;
4. select the new snapshot as current; and
5. observe Gateway reload or restart acknowledgement.

The UI reports these states separately:

```text
STAGED -> SNAPSHOT_CREATED -> CURRENT -> APPLIED
                              \-> APPLY_FAILED
```

An `APPLIED` claim requires runtime evidence. A successful property command or
snapshot-pointer update alone is not sufficient.

## Failure Handling

| Condition | Result |
| --- | --- |
| API version or Gateway is inactive | Reject before preview/publication. |
| Caller lacks either ownership boundary | Reject without revealing unauthorized details. |
| Required access-control query fails | Reject; do not treat as empty configuration. |
| Existing version state changed after preview | Conflict; require refresh and confirmation. |
| Routing conflict remains unresolved | Reject replacement or multi-version publication. |
| Dependent application binding has no decision | Reject replacement. |
| Event append fails | No publication is staged. |
| Synchronous projection fails after append | Report projection failure and allow replay recovery; do not retire versions through a second ad hoc command. |
| Snapshot validation fails | Keep the current snapshot unchanged. |
| Gateway apply fails | Keep or restore the last known good runtime configuration and report `APPLY_FAILED`. |

## Observability And Audit

Every preview and publication should expose or log:

- `publicationId` and command correlation ID;
- `hostId`, `instanceId`, `apiId`, `apiVersionId`, and `instanceApiId`;
- publication mode and selected retirement IDs;
- selected sections and source aggregate versions;
- property and dependency action counts;
- immutable manifest digest;
- requesting user and timestamp;
- event append and projection outcome;
- configuration snapshot ID when later created; and
- runtime apply acknowledgement when available.

Audit views must distinguish an operator decision to keep an old version from
a replacement that failed before retirement.

## Rollout Plan

### Phase 1: Candidate and preview

- Add the API Detail row action and publication dialog.
- Add the Gateway candidate query scoped by API version and authorization.
- Show versions of the same API and their dependency summary.
- Compile and preview access-control properties without writing state.

### Phase 2: Publish without replacement

- Add the idempotent publication command.
- Create, reuse, or reactivate the selected Instance API.
- Reconcile `endpointRules` and `ruleBodies`, including empty desired state.
- Record immutable publication manifests and return `STAGED`.
- Keep the existing Instance API sync action as a repair fallback.

### Phase 3: Explicit replacement

- Add keep/replace selection and dependency decisions.
- Publish the new graph before retiring selected old graphs.
- Add complete child retirement and deterministic replay coverage.
- Reconcile API-version-bound Gateway Tool sources.

### Phase 4: Snapshot handoff and policy

- Link successful publication to snapshot creation and comparison.
- Display snapshot and runtime-apply status in publication history.
- Add optional `MULTI_VERSION` and `SINGLE_ACTIVE_VERSION` policy after
  operational experience confirms the default behavior.
- Deprecate the manual sync path when publication has equivalent repair and
  recovery tooling.

## Validation Strategy

### Unit tests

- Compile permissions, row filters, column filters, rules, and rule bodies into
  deterministic properties.
- Distinguish source-query failure from an empty successful result.
- Create, update, reactivate, deactivate, and unchanged reconciliation.
- Produce explicit empty-state behavior for both access-control properties.
- Reject unauthorized Gateway and retirement IDs.
- Reject stale aggregate versions and expired preview tokens.
- Preserve idempotent results for the same command key.

### Database and projection tests

- Create the first association for a Gateway and API version.
- Reuse an active association without emitting a duplicate create.
- Reactivate an inactive association above both projection and event-store
  versions.
- Resolve concurrent first-publication attempts without violating the natural
  unique key.
- Project association creation before property creation.
- Roll back the entire synchronous projection when a later retirement event
  fails.
- Deactivate the complete dependent graph during replacement.
- Replay the immutable manifest without querying current authoring tables.
- Prove that reactivating an old association does not revive stale children.

### UI tests

- Render **Publish to Gateway** on each API-version row, not Access Overview.
- Filter candidates to authorized Gateway instances.
- Show only versions of the same API after Gateway selection.
- Require explicit keep or replacement selection.
- Warn about path-prefix and application-binding impacts.
- Prevent submission when preview validation fails or becomes stale.
- Report staged, snapshot-required, and runtime-applied states distinctly.

### End-to-end tests

- Publish a new API version to a Gateway with no existing association.
- Republish after adding an endpoint and verify updated `endpointRules`.
- Publish an empty access policy and prove stale values do not survive.
- Keep two versions with non-conflicting path prefixes.
- Replace an old version, migrate selected bindings, and verify the complete old
  graph is inactive.
- Build and activate a snapshot, then verify the Gateway loaded the expected
  endpoint configuration.
- Roll back to the previous API version through a new publication and snapshot.

## Acceptance Criteria

The first complete release is accepted when:

- an authorized operator can publish from the selected API-version row without
  navigating through Instance Admin first;
- the target Gateway dialog shows existing versions of the same API;
- the operator can keep versions or explicitly replace selected versions;
- a missing Instance API is created and configured by one idempotent command;
- active, inactive, missing, changed, unchanged, and empty properties reconcile
  correctly;
- replacement cannot retire an old version before the new version is staged;
- retirement deactivates the old association's complete dependent graph;
- every publication is replayable from an immutable manifest;
- unauthorized API or Gateway combinations are rejected server-side;
- publication reports `STAGED` until snapshot activation and runtime evidence
  prove a later state; and
- configuration snapshot rollback remains available without corrupting Portal
  desired state or publication history.
