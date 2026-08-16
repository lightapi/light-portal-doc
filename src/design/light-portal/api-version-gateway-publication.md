# API Version Publication To Gateway

## Status

Source implementation complete; integration and runtime qualification remain.

The query, compiler, append-only command, locked graph-revision guard,
replacement event ordering, snapshot-readiness guard, API Detail dialog, and
warning-confirmation workflow are implemented. Source-level unit tests and
builds cover the candidate/preview/publish flow, deterministic compilation,
stale revision handling (including the event-free path), complete child-first
retirement, and the asynchronous success response.

The release is not yet qualified as complete. The PostgreSQL concurrency and
source-query integration suites must run against an isolated test database,
followed by the end-to-end projection, snapshot activation, Gateway apply, and
rollback scenarios in this document.

This document defines the Portal workflow for publishing one API version's
derived configuration to a Light Gateway instance and, when requested,
retiring selected versions of the same API on that instance. Publication
accepts one ordered event batch into Portal's event store. The normal
asynchronous projection worker later updates Portal desired-state tables. A
separate configuration snapshot must then be created, reviewed, selected as
current, and loaded by the Gateway before runtime behavior changes.

## Purpose

Today, an administrator who adds an API endpoint must move through API Detail,
Service Endpoint, Access Overview, Instance Admin, Instance API, and Instance
API Config. The final **Sync Config From API** action pulls access-control data
into an already existing Instance API association. When the desired access
configuration becomes empty, the current sync path can also leave old
`rule.endpointRules` or `rule.ruleBodies` values in place.

That workflow separates related decisions across too many pages and does not
model an API-version upgrade as one operation. It also makes Instance Admin the
starting point even though the API version is the source being published.

This design adds **Publish to Gateway** to each API-version row on API Detail.
The action lets an authorized operator:

- select a Gateway instance;
- see versions of the same API already associated with that Gateway;
- choose whether those versions remain active or are retired;
- preview the API-derived configuration and warnings; and
- update the new version and any selected retirements with one command.

The design is related to
[Control-Plane Policy Publication Through Config Server](./control-plane-policy-config-server.md).
This command records a requested desired instance configuration change. The
immutable configuration snapshot and current-pointer workflow described there
remains the runtime publication boundary.

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
5. Portal creates, reuses, or reactivates the selected `instance_api_t`
   association and reconciles the complete selected property sections.
6. The first publication section is access control, which owns
   `rule.endpointRules` and `rule.ruleBodies`. Additional API-derived sections
   may be added later with explicit property ownership.
7. A successful command means the complete event batch was atomically appended
   to `event_store_t`. Projection is asynchronous; command
   success does not mean that desired-state tables or a Gateway already contain
   the change.
8. Missing rules, missing permission roles, and a completely empty access
   configuration produce visible warnings. A source query failure or invalid
   compiled configuration blocks publication.
9. A confirmed empty access-control section writes canonical active `{}`
   values for both owned properties. The command never leaves an older value
   merely because the new source is empty.
10. Replacement establishes the selected version before explicitly retiring
    the complete dependent graph of each selected old Instance API.
11. No publication status table or immutable publication manifest is added.
    Existing domain events provide history, mutable projections provide current
    desired state, and configuration snapshots provide deployable evidence.
12. Publication-specific `Idempotency-Key` support is deferred. Stale-preview
    protection and optimistic concurrency remain required.
13. Instance Admin retains snapshot creation, comparison, verification,
    activation, and rollback.
14. The existing **Sync Config From API** action may remain temporarily as an
    administrator repair path, but it is not the normal publication workflow.

## Goals

- Reduce a multi-page operation to one API-version-centered publication flow.
- Support intentional parallel API versions and explicit replacement.
- Prevent stale `endpointRules`, `ruleBodies`, or other owned properties from
  surviving an empty publication.
- Preserve event sourcing, optimistic concurrency, ownership, and replay.
- Keep server-side API data authoritative; the browser never compiles or
  submits final Gateway property values.
- Make warnings and replacement effects visible before confirmation.
- Keep runtime activation immutable and reversible through configuration
  snapshots.
- Leave room for future API-level publication sections without moving the
  action to another page.

## Non-Goals

- Access Overview does not become a deployment or publication page.
- Creating or editing an API version does not automatically change a Gateway.
- Publishing an API version does not create or activate a configuration
  snapshot.
- Portal does not assume that version strings use Semantic Versioning.
- A higher-looking version does not automatically supersede another version.
- Replacement does not physically delete projection or event history.
- The first implementation does not automatically migrate application
  bindings between API versions.
- The first implementation does not add a publication history table, a
  publication lifecycle state machine, or exact-publication rollback.
- The first implementation does not guarantee idempotent retry after an
  ambiguous HTTP failure.
- The first implementation does not define proactive event-size limits beyond
  the existing event append safeguards.
- Upgrade migrations are not required during early development; canonical
  fresh-install artifacts remain authoritative.
- This design does not define traffic draining or application compatibility
  between API versions.
- This design does not move Gateway Tool publication back into
  `instance_api_property_t`; the Tool catalog remains its authoritative path.

## Terminology

| Term | Meaning |
| --- | --- |
| API version | One registered API contract identified by `apiVersionId`. |
| Gateway instance | An active Portal instance eligible to run Light Gateway. |
| Instance API | The association between a Gateway instance and one API version, stored in `instance_api_t`. |
| Publication section | A server-side compiler that owns a declared set of Gateway configuration properties. |
| Keep | Update the selected version without retiring another version. |
| Replace | Update the selected version, then retire explicitly selected existing Instance APIs. |
| Retire | Soft-deactivate an Instance API and the dependent records that must not return if it is reactivated. |
| Events accepted | The complete command event batch was stored as canonical history and made available for asynchronous projection. |
| Projected | The asynchronous projection worker applied the complete event transaction to Portal desired-state tables. |
| Snapshot current | A verified immutable snapshot was selected as the Gateway's current configuration. |
| Applied | Runtime evidence shows that the Gateway loaded the current snapshot. |

## User Experience

### API Detail row action

`/app/apiDetail` lists multiple versions, so **Publish to Gateway** belongs in
the action column of each version row. The action receives the row's
`apiVersionId`; the server resolves `hostId`, `apiId`, and version text from
trusted context and current records.

The action is visible to `admin`, `host-admin`, and `api-admin`. Server
authorization remains authoritative even when the UI hides or disables the
action.

### Step 1: Select Gateway

The dialog lists active Gateway instances that the current user may administer.
Each option includes:

- instance name and `instanceId`;
- product and product version;
- environment or environment tag where available;
- existing association status for the selected `apiVersionId`; and
- current configuration snapshot identity and timestamp where available.

The query returns only eligible instances for the trusted host. At minimum, an
eligible target is active, belongs to the host, has an active Gateway product
version such as `productId=gtw`, and is not read-only.

### Step 2: Review existing versions

After a Gateway is selected, Portal shows every active and inactive Instance
API for the same `apiId` on that Gateway. It does not show unrelated APIs.

| Field | Purpose |
| --- | --- |
| API version | Human-readable version currently associated with the Gateway. |
| `instanceApiId` | Durable UUID used for events, configuration, and retirement. |
| State | Active, inactive, or selected for replacement. |
| Path prefixes | Indicates whether versions have distinct routing boundaries. |
| Application bindings | Shows consumers affected by retirement. |
| Property count | Shows whether version-specific configuration exists. |
| Last update | Helps identify stale or recently changed associations. |

The operator chooses one mode:

#### Keep Existing Versions

The selected API version is created, reactivated, or updated while every other
version remains unchanged. This supports compatibility windows, canary rollout,
and blue/green operation when routing remains unambiguous.

#### Replace Selected Versions

The operator selects one or more existing Instance APIs to retire after the new
version's create/update actions in the same ordered event batch. The dialog
requires explicit confirmation and shows dependent path prefixes, application
bindings, and properties that will be retired.

The first implementation does not automatically migrate application bindings.
Each dependency is classified as:

- **Retire** with the old Instance API;
- **Keep old version**, which removes that Instance API from the retirement
  selection; or
- **Block**, when the command cannot safely retire the dependency.

The initial implementation must not provide "replace all older versions."
"Older" is ambiguous without an explicit lifecycle policy.

### Step 3: Preview compiled configuration

The first publication section is:

```text
Access control
  rule.endpointRules
  rule.ruleBodies
```

The server preview reports source counts, validation results, warnings, and a
normalized diff against the selected Instance API properties. Values may be
shown to an authorized administrator but are not editable in this dialog.

Warnings include:

- an endpoint without any configured rule;
- an endpoint without permission roles;
- a permission with no effective principal selection; and
- a completely empty access-control section.

Warnings require acknowledgement but do not by themselves block publication.
Failed source queries, unresolved rule references, invalid compiled values, and
routing conflicts are blocking errors.

Future sections may be added only with an explicit property-ownership contract.
Two sections must not silently write the same property.

### Step 4: Confirm and publish

The confirmation identifies:

- the selected API version and Gateway;
- whether the association will be created, reactivated, or updated;
- the selected sections and acknowledged warnings;
- existing versions that remain active;
- existing versions and dependent records that will be retired; and
- the fact that a configuration snapshot must still be created and activated.

On success, the dialog says **Gateway publication events accepted** and shows
the event transaction or command correlation ID. It explains that projection
is asynchronous and that a snapshot can be created only after projection has
caught up. The dialog does not poll or wait for projection and does not use a
publication status named `STAGED`.

## Routing And Path Prefixes

Keeping multiple versions is valid only when the resulting Gateway routing is
unambiguous. Preview blocks conflicts such as identical path prefixes with
incompatible upstream targets or duplicate effective endpoint routes.

Access-control publication does not infer a path prefix from API version text.
For the first implementation:

- an existing or reactivated Instance API retains its active path prefixes;
- creating a missing Instance API does not silently copy prefixes from another
  version;
- the preview clearly warns when the target association has no active path
  prefix and links to the Instance API Path Prefix workflow; and
- **Replace Selected Versions** is blocked until the target version has the
  path-prefix configuration required to remain routable after retirement.

An explicit path-prefix copy or migration workflow may be added later.

## Data Model And Audit

The design uses the existing desired-state projections:

```text
instance_t
  -> instance_api_t
       -> instance_api_property_t
       -> instance_api_path_prefix_t
       -> instance_app_api_t
            -> instance_app_api_property_t
```

`instance_api_t` enforces one association for
`(host_id, instance_id, api_version_id)`. `instance_api_property_t` identifies
one override by `(host_id, instance_api_id, property_id)`.

Foreign-key `ON DELETE CASCADE` protects physical deletion, but normal Portal
deletion is soft deactivation. Retiring an `instance_api_t` row therefore does
not automatically deactivate its child rows.

No `api_gateway_publication_t` table is added. Audit and replay use:

- the immutable domain events containing the exact IDs and property values;
- the event append transaction identity and a shared command correlation UUID;
- mutable projection rows for current desired state; and
- immutable configuration snapshots for deployable and historical rendered
  configurations.

Every event generated by one command carries the same correlation UUID. Replay
uses the values captured in those events and never recompiles old events from
current access-control tables.

## Query Contracts

### `getApiGatewayPublicationCandidate`

The candidate query accepts `apiVersionId` and returns only server-authorized,
eligible Gateway instances. Each candidate contains target metadata,
association state for the selected version, versions of the same API already on
that instance, dependent record counts, path-prefix readiness, and current
snapshot metadata. It also returns the target graph's accepted and projected
revisions and whether an unresolved projection failure exists.

The server derives the trusted host and resolves `apiId` and version text from
`apiVersionId`. A target whose accepted revision is ahead of its projected
revision, or whose graph has an unresolved projection failure, is shown as not
ready for another publication. This avoids compiling a new event batch from a
stale target projection.

### `previewApiVersionGatewayPublication`

The preview accepts:

```json
{
  "apiVersionId": "uuid",
  "instanceId": "uuid",
  "publicationMode": "REPLACE_SELECTED",
  "retireInstanceApiIds": ["uuid"],
  "sections": ["ACCESS_CONTROL"]
}
```

It returns:

- resolved source identity and revisions;
- association action: `CREATE`, `REACTIVATE`, or `UPDATE`;
- normalized desired properties, including canonical empty values;
- create, update, reactivate, deactivate, and unchanged counts;
- routing and dependency validation results;
- non-blocking access warnings;
- retirement effects; and
- `previewDigest`, calculated over the normalized request, compiled property
  values, relevant source revisions, and target desired-state baseline.

The preview is advisory. It does not reserve records or mutate desired state.

## Command Contract

### `publishApiVersionToGateway`

The command accepts the operator decision, not browser-generated configuration:

```json
{
  "apiVersionId": "uuid",
  "instanceId": "uuid",
  "publicationMode": "REPLACE_SELECTED",
  "retireInstanceApiIds": ["uuid"],
  "sections": ["ACCESS_CONTROL"],
  "acknowledgedWarningCodes": ["ENDPOINT_WITHOUT_PERMISSION_ROLES"],
  "expectedTargetAcceptedRevision": 12,
  "expectedPreviewDigest": "sha256:..."
}
```

The command must not accept `apiId`, API version text, `endpointRules`,
`ruleBodies`, `instanceApiId`, property IDs, or compiled values as authoritative
client input.

Immediately before building events, the command reloads and recompiles all
source and target records. It rejects the request with a conflict when the new
digest differs from `expectedPreviewDigest`. The operator must preview and
confirm the changed result. It also rejects the command when the target graph's
accepted revision is ahead of its projected revision or it has an unresolved
projection failure. The UI need not wait after a successful command, but a
later publication must not compile from projections that have not caught up.

The preview returns `expectedTargetAcceptedRevision`. Event persistence checks
that value while holding the target graph's transaction lock and before
advancing `accepted_revision` or inserting any event. A mismatch returns a
conflict. Checking only in the handler before append is insufficient because
two commands can compile concurrently from the same projected baseline.

Publication-specific `Idempotency-Key` behavior is not part of the first
release. A retry after an ambiguous response refreshes the candidate and
preview before submitting another command.

### Result

```json
{
  "commandCorrelationId": "uuid",
  "eventTransactionId": "uuid",
  "eventsAccepted": true,
  "acceptedEventCount": 4,
  "projectionMode": "ASYNCHRONOUS",
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

The command returns success immediately after the complete event transaction is
accepted. `instanceApiId` is the durable server-generated or existing UUID
captured in the events; for `CREATE`, its projection row might not be queryable
yet. Property and retirement counts describe planned event actions, not
confirmed projection outcomes. The result does not claim partial property or
retirement success.

## Server-Side Compilation

The compiler loads the selected active API version and its current endpoint,
permission, filter, and rule projections. It also resolves the registered
property IDs for `rule.endpointRules` and `rule.ruleBodies`.

A failed source query blocks publication. It must not be treated as a successful
empty result.

Each selected section owns a complete property set. Access-control publication
always addresses both owned properties:

```text
non-empty desired map -> canonical serialized object
empty desired map     -> active canonical {}
```

An empty result is allowed after explicit warning acknowledgement. Writing `{}`
clears the API-specific desired value and prevents a previous value from
surviving accidentally. Deactivation is not used for this case because it could
allow a lower-scope value to become effective.

For each owned property, the compiler compares desired and current state:

| Current state | Desired state | Event action |
| --- | --- | --- |
| Missing | Present, including `{}` | Create |
| Inactive | Present, including `{}` | Reactivate/create above stored version |
| Active and different | Present | Update |
| Active and identical | Present | No property event |

Event versions use the greater of current projection and event-store versions,
plus one.

## Association Creation And Concurrency

Portal resolves the Instance API by
`(hostId, instanceId, apiVersionId)`:

- active association: reuse its `instanceApiId`;
- inactive association: reuse and reactivate its `instanceApiId`; or
- no association: generate a server-side UUID and create it.

The database uniqueness constraint remains the final identity guard. Concurrent
first-publication attempts must not leave a canonical event that can only fail
during projection. Event persistence serializes commands for the target graph
and atomically compares `expectedTargetAcceptedRevision` before accepting the
batch. If another command won, the loser returns `409 Conflict`; the client
refreshes and uses the winning `instanceApiId`. The natural-key check remains a
defense in depth.

## Event Append And Asynchronous Projection

Portal commands use two separate processing stages:

1. **Command acceptance** validates the request, builds the complete ordered
   event batch, and atomically appends the canonical events to `event_store_t`
   through the existing persistence path. This is the only stage the command
   handler waits for.
2. **Asynchronous projection** consumes that event transaction and applies its
   payloads to relational current-state tables such as `instance_api_t` and
   `instance_api_property_t`.

All projection updates for one event transaction run in one database
transaction and in event ordinal order. The UI returns after command acceptance
and does not wait for this work. A newly created Instance API and its properties
therefore become visible only after the projection worker processes the batch.

If asynchronous projection fails:

- the already successful command remains successful because its canonical
  events were accepted;
- the projection transaction rolls back, so no partial desired-state graph is
  visible;
- the failed transaction is visible through the established projection DLQ;
- the canonical events remain available in the event store for repair and
  replay; and
- later publication and snapshot commands reject the target graph until replay
  advances its projected revision to the accepted revision.

There is no publication lifecycle record and no `STAGED` state. The relevant
facts already exist at their owning boundaries: event acceptance in the event
store, projection progress and failures in the projection subsystem and DLQ,
snapshot identity in the snapshot workflow, and runtime application evidence
from the Gateway.

## Replacement And Retirement

A replacement builds one ordered event batch:

1. create or reactivate the selected Instance API when required;
2. create, update, or reactivate its selected properties;
3. retire dependent state for every selected old Instance API; and
4. retire each selected old `instance_api_t` association.

The preview validates the resulting post-command graph, including routing and
dependency decisions, before append. The asynchronous worker later applies the
ordered event transaction atomically to desired-state tables, so readers never
observe a partially projected replacement.

A complete retirement explicitly handles:

- every active `instance_api_property_t` row;
- every active `instance_api_path_prefix_t` row;
- every active `instance_app_api_t` relationship;
- every active `instance_app_api_property_t` row; and
- any other active binding whose domain identity is tied to the retiring
  `instanceApiId`.

Gateway Tool publications are instance-level and remain a separate workflow.
Retiring an Instance API does not mutate the Gateway Tool publication. An
operator uses the existing `REPLACE_API_SCOPE` Gateway Tool publication when
the runtime Tool set must also stop exposing endpoints from the retired API
version; Tools belonging to other API versions or workflows remain untouched.

Automatic binding migration is deferred. When a required dependency cannot be
retired safely, replacement is blocked.

## Authorization

Publication is permitted for authenticated users with one of these Portal
administrative roles:

- `admin`;
- `host-admin`; or
- `api-admin`.

The server also verifies that:

- trusted request host matches every selected record;
- the API version belongs to that host and is active;
- the Gateway belongs to that host, is active, is eligible, and is not
  read-only;
- every retirement target belongs to the selected Gateway and the same API;
  and
- every dependent record being retired belongs to the selected old Instance
  API.

Candidate, preview, and command paths use the same authorization and eligibility
helper. The command repeats all checks to reject forged IDs and stale browser
state.

## Snapshot And Runtime Activation

The command records the requested Portal desired-state change as events. It does
not prove that projections are current or that a running Light Gateway loaded
the configuration.

Before creating a snapshot, Instance Admin verifies for the target graph that:

- `instance_graph_revision_t.accepted_revision` equals
  `projected_revision`; and
- there is no unresolved projection failure for that graph.

If projection is still pending, snapshot creation returns a retryable conflict.
If projection failed, the UI links to the DLQ/repair workflow. This check belongs
to snapshot creation; the publication dialog does not wait or poll for it.

After the projection is current, Instance Admin performs the established flow:

1. create an immutable configuration snapshot from projected desired state;
2. compare it with the current snapshot, including access warnings;
3. validate the rendered Gateway configuration;
4. select the verified snapshot as current; and
5. observe Gateway reload or restart acknowledgement.

Only the final acknowledgement supports an `APPLIED` runtime claim. A successful
command or snapshot-pointer change alone is insufficient.

## Failure Handling

| Condition | Result |
| --- | --- |
| API version or Gateway is inactive | Reject before preview/publication. |
| Caller is not `admin`, `host-admin`, or `api-admin` | Reject without revealing unauthorized details. |
| Required source query fails | Reject; do not treat it as empty configuration. |
| Endpoint lacks rules or permission roles | Warn and require acknowledgement. |
| Preview digest changed | Conflict; require a new preview and confirmation. |
| Concurrent command created the association first | Conflict; refresh the winning association. |
| Target has no required path prefix | Warn; block replacement until routing is ready. |
| Routing conflict remains unresolved | Reject. |
| Dependent binding cannot be safely retired | Reject replacement. |
| Event append fails | No event batch is accepted. |
| Asynchronous projection fails after acceptance | Preserve command success; roll back the projection transaction, expose the failure in the DLQ, and recover through replay. |
| Accepted revision is ahead of projected revision | Reject another publication and snapshot creation until projection catches up. |
| Snapshot validation fails | Keep the current snapshot unchanged. |
| Gateway apply fails | Keep or restore the last known good runtime configuration. |

## Observability And Audit

Every preview and command exposes or logs:

- command correlation UUID and event transaction identity;
- trusted host, `instanceId`, `apiId`, `apiVersionId`, and `instanceApiId`;
- publication mode and selected retirement IDs;
- selected sections and acknowledged warnings;
- preview digest and source revisions;
- property and dependency action counts;
- requesting user and timestamp;
- event-append outcome; and
- separately, projection revision and DLQ outcome; and
- later snapshot/runtime identities where those systems expose them.

Audit views distinguish an operator decision to keep an old version from an
accepted replacement whose asynchronous projection is pending or failed.

## Implementation Readiness

This design has been implemented across Portal query, command, persistence, and
UI source. The command boundary,
authorization roles, warning behavior, UUID identity, event history, projection
failure handling, and snapshot/runtime boundary are settled.

The following are required implementation gates, not deferred enhancements:

- use the normal append-only command-handler behavior; do not enable
  synchronous projection for this command;
- validate `expectedTargetAcceptedRevision` under the target graph transaction
  lock so concurrent commands cannot append from the same stale baseline;
- register every emitted event for ordered transactional projection and DLQ
  replay, with all IDs and compiled values carried in the event payloads;
- block preview/command compilation when the target graph is not fully
  projected;
- block snapshot creation when accepted and projected graph revisions differ or
  an unresolved projection failure exists; and
- prove target routing readiness before accepting replacement events.

No publication status table, synchronous projection response, migration plan,
mandatory idempotency key, event-size redesign, or immutable publication
manifest is required to begin implementation.

## Implementation Plan

### Phase 1: Candidate, compiler, and preview

- Add the API Detail row action and dialog.
- Add the authorized Gateway candidate query.
- Show versions of the same API and dependency/path-prefix readiness.
- Show accepted/projected revision readiness and unresolved projection
  failures.
- Compile both access-control properties, warnings, diff, and preview digest
  without writing state.

### Phase 2: Append-only publication without replacement

- Add the compound command using the normal append-only command-handler path.
- Create, reuse, or reactivate the selected Instance API UUID.
- Reconcile `endpointRules` and `ruleBodies`, including active `{}` values.
- Return the accepted event transaction identity without waiting for
  projection.
- Reject compilation when the target graph projection is behind or failed.
- Keep the existing sync action temporarily as a repair fallback.

### Phase 3: Explicit replacement

- Add keep/replace selection and dependency review.
- Require target path-prefix readiness.
- Order the selected-version events before retirement events and project the
  complete transaction atomically.
- Keep Gateway Tool publication in its existing instance-level workflow; use
  `REPLACE_API_SCOPE` separately when API-version Tool bindings must change.

### Phase 4: Snapshot handoff

- Link successful commands to snapshot creation and comparison.
- Enforce accepted/projected revision equality and no unresolved projection
  failure before snapshot creation.
- Display snapshot and runtime-apply evidence through the existing snapshot
  workflow.
- Deprecate the manual sync path when publication has equivalent repair and
  recovery tooling.

## Validation Strategy

### Unit tests

- Compile permissions, filters, rules, and rule bodies deterministically.
- Distinguish source-query failure from a successful empty result.
- Generate and require acknowledgement for missing-rule and missing-role
  warnings.
- Create, update, reactivate, and unchanged reconciliation.
- Write canonical active `{}` for both empty access-control properties.
- Reject unauthorized Gateway and retirement IDs.
- Reject a stale preview digest.
- Reject a stale `expectedTargetAcceptedRevision`.

### Database and projection tests

- Create the first association with a server-generated UUID.
- Reuse an active association without a duplicate create.
- Reactivate an inactive association above projection and event-store versions.
- Return a clean conflict for concurrent first-publication attempts.
- Prove two commands compiled at the same graph revision cannot both append.
- Reject preview/command execution while the target graph projection is behind
  or failed.
- Project association creation before property creation.
- Roll back the whole projection when a later event fails.
- Replay appended events without querying current authoring tables.
- Deactivate the complete dependent graph during replacement.
- Prove that reactivating an old association does not revive stale children.

### UI tests

- Render **Publish to Gateway** on each API-version row, not Access Overview.
- Filter candidates to authorized eligible Gateway instances.
- Show only versions of the same API after Gateway selection.
- Display and require acknowledgement for access warnings.
- Prevent submission when preview validation fails or becomes stale.
- Report event acceptance without waiting or polling for projection.
- Distinguish event acceptance, projection, snapshot, and runtime application.

### End-to-end tests

- Publish a version to a Gateway with no existing association.
- Republish after adding an endpoint and verify updated `endpointRules`.
- Publish empty access data and prove stale values are replaced by `{}`.
- Keep two versions with non-conflicting path prefixes.
- Replace an old version and verify its complete dependent graph is inactive.
- Build, compare, validate, and activate a snapshot, then verify the Gateway
  loaded the expected configuration.
- Delay asynchronous projection and verify the command still returns accepted.
- Force asynchronous projection failure, verify the DLQ entry and no partial
  graph, block publication/snapshot creation, and recover the accepted batch
  through replay.

## Acceptance Criteria

The first complete release is accepted when:

- an authorized `admin`, `host-admin`, or `api-admin` can publish from the
  selected API-version row;
- the target dialog shows eligible Gateways and existing versions of the same
  API;
- preview distinguishes blocking errors from acknowledged access warnings;
- a missing Instance API is created with a server-generated UUID;
- active, inactive, missing, changed, unchanged, and empty properties reconcile
  correctly;
- empty access data writes active canonical `{}` values for both owned
  properties;
- stale previews and concurrent first creation return clean conflicts;
- stale target graph revisions are rejected atomically by event persistence;
- replacement requires target routing readiness and deactivates the complete
  selected old graph;
- the command reports success after the complete event transaction is accepted
  and does not wait for projection;
- publication and snapshot creation are rejected while the target graph's
  projection is behind or has an unresolved failure;
- unauthorized or cross-host identifiers are rejected server-side; and
- snapshot comparison, validation, activation, runtime evidence, and rollback
  remain separate from the publication command.
