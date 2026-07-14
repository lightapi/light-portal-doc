# Config Snapshot Output and Comparison

The `/app/config/configSnapshot` page lists effective configuration snapshots
and links to the raw snapshot tables, but it does not show the final
`values.yml` represented by a snapshot. It also requires users to inspect
snapshots one at a time. This document adds a deterministic `values.yml`
output for each row and a comparison workflow for two to four snapshots. The
same comparison engine supports historical selection from the snapshot page
and current-snapshot selection across instances from
`/app/instance/instanceAdmin`.

## Decision Summary

- Add a `View values.yml` row action. It opens a read-only preview with Copy
  and Download actions.
- Generate the YAML on the server from the complete snapshot. Do not assemble
  it from the paginated property table in the browser.
- Select historical data by explicit `hostId + snapshotId`; do not reuse the
  runtime query that implicitly selects only the snapshot marked `current`.
- Add `Compare current snapshots` to `InstanceAdmin`. It resolves the current
  snapshot for each selected instance, then opens the same comparison route
  with exact snapshot ids.
- Define one canonical YAML contract for the portal query and both the Java and
  Rust config servers. The Java services share one codec; the Rust service
  implements the same contract against the same golden test vectors.
- Let users compare two, three, or four snapshots in a semantic property
  matrix. Two snapshots remain the normal and simplest case.
- Offer a literal side-by-side YAML diff only when exactly two snapshots are
  selected. Three or four full YAML panes are too narrow to read reliably.
- Compare effective typed values by default and show source-only changes
  separately.

## Current Implementation

`portal-view/src/pages/snapshot/ConfigSnapshot.tsx` renders a server-paginated
Material React Table. It calls
`lightapi.net/config/getConfigSnapshot/0.1.0`, defaults the `current` filter to
`true`, and identifies each row by `instanceId + snapshotId`. Existing row
actions update or delete the header and navigate to the effective property,
file, deployment, API, app, app-api, instance, environment, product, and
product-version snapshot tables.

`portal-view/src/pages/instance/InstanceAdmin.tsx` is also server-paginated. Its
rows already contain `hostId`, `instanceId`, `instanceName`, `serviceId`, and
`envTag`, and each row has a Snapshot action that opens the snapshot page for
that instance. It does not currently support row selection. Its `current`
field belongs to the instance record and is not a config snapshot id or proof
that `config_snapshot_t` contains a current row.

Snapshot creation calls the PostgreSQL `create_snapshot` procedure. The
procedure copies the raw override levels and materializes one effective row per
`snapshotId + configPhase + configId + propertyId` in
`config_snapshot_property_t`. Each effective row records:

- `config_phase`
- `config_id` and `property_id`
- `property_name` and `property_type`
- `property_value` and `value_type`
- `source_level`

The Java `light-config-server` already turns current snapshot rows into YAML.
Its snapshot query joins `config_snapshot_property_t` to `config_t`, emits the
key as `configName.propertyName` for `Config` properties, orders by the emitted
key, parses values according to `value_type`, and writes a `# source_level`
comment before each entry. However, that query locates a snapshot indirectly
with `current = true`, `serviceId`, and environment. It cannot output a
specific historical row selected in `portal-view`.

The Rust config server in `portal-service/apps/config-server` independently
exposes `/config-server/configs`. It loads current snapshot rows through
`portal-service/crates/portal-core`, then currently formats each
`property_value` directly into YAML without using the returned `value_type`.
It cannot consume a Java shared utility class, so it requires a Rust canonical
codec and cross-language parity fixtures if both config-server implementations
are supported.

The current PostgreSQL schema does not enforce the resolver's cardinality
assumption. `config_snapshot_t` has no index beginning with
`(host_id, instance_id, current)` and no partial uniqueness constraint for
current rows. Its broader scope index begins with `host_id, environment`, so it
does not directly cover a host/instance/current lookup. The Java persistence
path attempts to clear an older current row, but its update is scoped by
`instance_id` rather than the full `host_id + instance_id` identity. The
database can therefore contain duplicate current rows and the resolver must not
depend on application convention alone.

The existing `getConfigSnapshotProperty` action is not an appropriate export
API. It is paginated, accepts only `snapshotId`, returns stored strings rather
than typed values, and does not enforce the full YAML serialization contract.
Using it from the browser could silently omit properties or produce values
whose YAML types differ from runtime configuration.

## Goals

- Let an authorized user view, copy, and download the runtime `values.yml` for
  any current or historical configuration snapshot.
- Make output deterministic so two semantically identical snapshots generate
  identical YAML and the same digest.
- Make effective configuration drift visible without requiring users to open
  every snapshot property page.
- Let users compare the current effective configuration of two to four
  same-service instances directly from `InstanceAdmin`.
- Support the common two-snapshot comparison and useful three- or four-snapshot
  comparisons without making the page unreadable.
- Keep snapshot metadata visible so users know which instance, environment,
  timestamp, and current state each value belongs to.
- Preserve value types, nested maps, and list order.
- Prevent cross-host snapshot access and avoid persisting sensitive output in
  browser storage.

## Non-Goals

- Do not compare raw override tables in the first release. The comparison is of
  the effective `values.yml` materialized in `config_snapshot_property_t`.
- Do not include `File` or `Cert` snapshot rows in `values.yml`. The existing
  Snapshot Files action remains the inspection path for those artifacts.
- Do not compare more than four snapshots on screen.
- Do not edit or restore configuration from the comparison page.
- Do not treat YAML formatting differences as configuration changes.
- Do not replace the existing snapshot property pages.
- Do not turn the feature into a general instance-drift comparison for files,
  certificates, deployments, APIs, apps, or other instance state.
- Do not compare instances with different `serviceId` values in the first
  release.

## Repository Scope

- `portal-db` for current-snapshot integrity audits, remediation tooling, and
  the database-enforced current-row invariant
- `light-portal` for the Java canonical codec and snapshot persistence contract
- `config-query` for the historical snapshot output/comparison query
- `light-config-server` for Java runtime `values.yml` parity
- `portal-service` for Rust runtime `values.yml` parity
- `portal-view` for snapshot-page and `InstanceAdmin` selection plus the shared
  output/comparison experience
- deployment/config repositories for packaging and live verification

## Why Support More Than Two Snapshots

Two snapshots answer the most common question: "what changed?" Three snapshots
also have clear operational uses:

- before, candidate, and current
- dev, QA, and production
- last known good, failed rollout, and repaired rollout

Four columns are still usable in a full-width property matrix and cover a
typical staged rollout. Beyond four, value columns become too narrow and users
lose the baseline while horizontally scrolling. Larger comparisons are better
handled later as a downloadable report or drift dashboard.

The initial limit should therefore be:

| View | Supported snapshots | Reason |
| --- | ---: | --- |
| Effective property matrix | 2–4 | Values remain scannable as dynamic table columns. |
| Side-by-side YAML diff | 2 | Raw text needs enough horizontal width and has a natural left/right baseline. |
| Download one `values.yml` | 1 | Produces the exact artifact for one snapshot. |

## `values.yml` Row Action

Add a row action with tooltip `View values.yml`. Selecting it requests the
snapshot by its explicit `hostId` and `snapshotId` and opens a large dialog or
right-side drawer containing:

- snapshot timestamp, snapshot id, instance name/id, environment, service id,
  and whether it is current
- configuration phase, initially fixed to runtime phase `R`
- property count and SHA-256 digest
- a read-only monospace YAML preview
- Copy and Download buttons
- a link back to Snapshot Properties for source-level inspection

The preview must show the entire output, not only the current table page. While
loading, disable Copy and Download. If the snapshot contains no runtime
`Config` properties, show an explicit empty-state message rather than an empty
dialog that looks like a failed request.

Use a stable, filesystem-safe download name such as:

```text
values-<instanceName>-<snapshotTs>-<snapshotId>.yml
```

The downloaded media type should be `application/yaml;charset=utf-8`. The file
should end with one newline.

The download helper must remove its temporary anchor and call
`URL.revokeObjectURL(...)` in a `finally` block after triggering the download.
This follows the cleanup pattern already used by `portal-view`'s
`downloadJson` helper and prevents repeated exports from retaining Blob URLs in
the single-page application.

The snapshot procedure captures both runtime and promote phases, but
`values.yml` is the runtime startup artifact. Phase `R` is therefore the first
release contract. A later phase selector can expose `P` if operators establish
a concrete promote-time verification use case.

## Canonical YAML Contract

The output and comparison API must use the same typed conversion rules as the
config server:

| `valueType` | Typed representation |
| --- | --- |
| `string` | YAML string |
| `boolean` | YAML boolean |
| `integer` | YAML integer |
| `float` | YAML number |
| `map` | Parse stored JSON into a YAML mapping. |
| `list` | Parse stored JSON into a YAML sequence. |

Canonicalization rules are:

1. Include only `config_phase = 'R'` and `property_type = 'Config'`.
2. Form the top-level key as `configName.propertyName`, matching the current
   config-server behavior.
3. Sort top-level entries by that complete emitted key, not by
   `property_name` alone.
4. Sort keys recursively inside map values.
5. Preserve list order because sequence order can be semantically significant.
6. Preserve the effective `source_level` as the comment immediately before its
   property.
7. Use fixed block style, two-space indentation, stable quoting rules, UTF-8,
   and a single final newline.
8. Reject an invalid stored value for its declared type. Do not quietly coerce
   it to a string or omit it.
9. Reject duplicate emitted keys instead of letting one overwrite another.

Map key order does not change YAML meaning, but recursive sorting prevents
nested map insertion order from creating noisy diffs. Source comments are
useful diagnostics, but a source-comment change alone is not an effective value
change.

Move or extract the current Java typed YAML conversion in
`ServiceConfigurationUtil` into a shared canonical serializer that both
`light-config-server` and `config-query` can call. A suitable home is the
shared `light-portal` utility/domain layer already used by both Java services.

Implement the same contract in Rust, preferably beside `ConfigEntry` and the
snapshot query in `portal-service/crates/portal-core`, and make
`portal-service/apps/config-server` call it instead of formatting raw values.
Because Java and Rust cannot share a runtime class, both codecs must consume
the same language-neutral input/output test vectors, including expected UTF-8
YAML bytes and digest.

The fixture corpus has an explicit contract version and a machine-readable
manifest containing the SHA-256 of the raw rows and expected YAML. Vendored
copies live in the Java and Rust test suites so unit tests remain hermetic. A
cross-repository CI job checks the copies from explicitly checked-out revisions
for byte equality. Tests must not download fixtures from a mutable branch or a
`latest` raw URL because that would make an otherwise unchanged build depend on
network availability and moving remote state.

For a current snapshot, add parity tests proving the portal output and the Java
and Rust config-server outputs are byte-for-byte identical. This is the
strongest check that the preview represents the artifact a runtime service
receives regardless of which supported config server is deployed.

## Query API

Add a read action:

```text
lightapi.net/config/getConfigSnapshotValues/0.1.0
```

It should retain the existing `portal.r` scope and use a batch-shaped request
for both output and comparison:

```json
{
  "hostId": "019...",
  "snapshotIds": ["019...", "019..."],
  "configPhase": "R",
  "include": ["entries"]
}
```

`snapshotIds` must contain between one and four unique ids. `include` may
contain `entries`, `yaml`, or both. The output dialog requests `yaml`; the
comparison matrix requests `entries`; the two-pane YAML tab loads `yaml` only
when opened. This avoids sending both a large structured representation and a
duplicate YAML string when only one is needed.

The response preserves request order:

```json
{
  "configPhase": "R",
  "snapshots": [
    {
      "snapshotId": "019...",
      "snapshotTs": "2026-07-13T14:30:00Z",
      "instanceId": "019...",
      "instanceName": "light-gateway-dev",
      "environment": "dev",
      "serviceId": "com.networknt.light-gateway-1.0.0",
      "current": false,
      "propertyCount": 2,
      "sha256": "sha256:...",
      "entries": [
        {
          "key": "server.enableHttp",
          "value": true,
          "valueType": "boolean",
          "sourceLevel": "instance"
        },
        {
          "key": "server.httpPort",
          "value": 8080,
          "valueType": "integer",
          "sourceLevel": "default"
        }
      ]
    }
  ]
}
```

When `yaml` is requested, each snapshot object also contains the canonical
`yaml` string. The digest is calculated from the exact UTF-8 YAML bytes.

The persistence query should join `config_snapshot_t`,
`config_snapshot_property_t`, and `config_t`, and scope every selected id by
`cs.host_id = ?`. It must not require `current = true`. Load all requested
metadata and properties in bounded batch queries rather than one query per
snapshot.

Reject the whole request if any selected snapshot is missing, belongs to
another host, has malformed typed data, or exceeds the configured response
limit. A partial comparison can look authoritative while silently omitting a
column, so partial success is unsafe here.

## Snapshot-Page Selection

Enable row selection on `ConfigSnapshot.tsx` and add a `Compare selected`
toolbar button. It is disabled until at least two snapshots are selected.

The current `getConfigSnapshot` response does not contain a property count.
Extend it additively with `propertyCount`, defined as the count of phase `R`,
type `Config` rows for that snapshot, and a response-level
`comparisonLimits.maxProperties` sourced from the same backend configuration
used by `getConfigSnapshotValues`. Load page counts in one aggregate query, not
one count query per row.

The selection state retains `propertyCount`. Disable `Compare selected` when
the sum across selected snapshots exceeds `maxProperties` and explain the
configured limit in the button tooltip. This check is advisory: the API still
enforces both property and serialized-byte limits and remains authoritative.
If it returns `413` because the byte limit is exceeded or metadata changed,
show an actionable error that suggests selecting fewer snapshots or
downloading them individually.

The page uses server-side pagination, so selected snapshot metadata must be
stored independently of the currently loaded `data` array. Selection should
survive paging and sorting and should be cleared explicitly by the user or when
the host changes. Reject a fifth selection with a short explanation.

The page currently defaults `current` to `true`, which often exposes only one
snapshot per instance. When compare mode is activated with fewer than two
visible candidates, show a `Show snapshot history` action that removes the
`current` filter. Do not silently change a filter merely because one checkbox
was selected.

Same-instance history is the default use case. Cross-instance comparison is
also valuable for environment drift, so permit it when all selected snapshots
have the same `serviceId`. Show a `Cross-instance comparison` banner and keep
instance and environment metadata pinned above each column. Reject snapshots
with different service ids in the first release; comparing unrelated services
mostly produces missing-key noise and is better handled as separate exports.

All selected snapshots must belong to the signed-in host. This is enforced by
the server even though the list query is already host-scoped.

## `InstanceAdmin` Current-Snapshot Entry Point

Add controlled row selection and a `Compare current snapshots` toolbar action
to `/app/instance/instanceAdmin`. This is a second selector for the shared
comparison page, not a separate comparison implementation.

Selection rules are:

- select two to four unique instances
- preserve selection across server-side pagination and sorting
- clear selection when the authenticated host changes
- require a non-empty, identical `serviceId` across all selected instances
- use only rows visible under the existing `InstanceAdmin` read/ownership scope
- do not infer config snapshot availability from the instance row's `current`
  field

Reject a fifth instance and mixed-service selections before making a resolver
request. Show selected instance names, environments, and a Clear action in the
toolbar. Do not silently change the page's active/current filters when compare
mode is enabled.

### Current-Snapshot Resolver API

Add a read action:

```text
lightapi.net/config/getCurrentConfigSnapshotsByInstances/0.1.0
```

Request:

```json
{
  "hostId": "019...",
  "instanceIds": ["019...", "019..."],
  "configPhase": "R"
}
```

`instanceIds` must contain two to four unique ids. The handler validates the
authenticated host and instance-read scope, then resolves all ids in one
bounded query against `config_snapshot_t` and `instance_t`. It requires
`cs.current = true`, phase `R` property counts, and one current config snapshot
per selected instance. It must preserve request order and must not issue one
query per instance.

Response:

```json
{
  "resolvedAt": "2026-07-13T18:30:00Z",
  "comparisonLimits": {
    "maxProperties": 10000,
    "maxResponseBytes": 5242880
  },
  "snapshots": [
    {
      "instanceId": "019...",
      "instanceName": "light-gateway-dev",
      "serviceId": "com.networknt.light-gateway-1.0.0",
      "environment": "dev",
      "snapshotId": "019...",
      "snapshotTs": "2026-07-13T18:00:00Z",
      "propertyCount": 125
    }
  ]
}
```

The server revalidates that all resolved snapshots have the same non-empty
`serviceId`; the UI check is only an early usability check. Resolution is
all-or-nothing. A missing instance, missing current snapshot, multiple current
snapshots, mixed service ids, ownership failure, or property-limit violation
must not produce a partial set. Error responses contain ids and counts only,
never configuration values.

Before enabling the resolver, add a partial unique index matching the intended
identity and access path:

```sql
CREATE UNIQUE INDEX uq_config_snapshot_current_instance
ON config_snapshot_t (host_id, instance_id)
WHERE current IS TRUE;
```

This both supports the resolver query and guarantees at most one current
snapshot per host/instance. Deployment must first audit every target database
for duplicate current rows and for current snapshot rows whose `service_id`
does not match the authoritative `instance_t.service_id`. Any current-row
violation blocks rollout until an operator reviews and applies an idempotent,
recorded remediation. Historical service-id mismatches are reported
separately and are not rewritten automatically: historical snapshot metadata
is evidence of the captured state and needs an explicitly approved migration
if the product decides it is corrupt. Verify the final resolver with
`EXPLAIN (ANALYZE, BUFFERS)` on representative data and require an index-backed
plan without per-instance queries.

After successful resolution, navigate to:

```text
/app/config/configSnapshotCompare?snapshotIds=<id1>,<id2>[,<id3>,<id4>]&source=current-instances
```

The comparison request continues to use explicit snapshot ids. This freezes
the result to the snapshots that were current when the user started the
comparison and keeps refresh/deep links reproducible. If one becomes
non-current before or after the values request, show its normal current badge
as false and offer `Refresh current snapshots`, which resolves the instance ids
from the loaded snapshot metadata again. Never silently replace a comparison
column while the user is inspecting it.

## Comparison Page

Add a route such as:

```text
/app/config/configSnapshotCompare?snapshotIds=<id1>,<id2>[,<id3>,<id4>]
```

Keeping the ids in the URL makes refresh and task-aware navigation reliable.
The host continues to come from authenticated user context and is not trusted
from the URL.

The page header contains ordered snapshot cards. Each card shows:

- a short label (`A`, `B`, `C`, or `D`)
- instance and environment
- snapshot timestamp and id
- description, snapshot type, and current badge
- property count and digest

The snapshot list continues to show the stored `userId` as the authoritative
audit identity. The first release does not resolve it through a user-profile
service: display names can change, and profile availability must not affect
snapshot inspection. A later enhancement may show a human-readable name
alongside the raw `userId`, but must not replace or obscure the identifier.

The user can choose any selected snapshot as the baseline and reorder the
cards. The initial baseline is the oldest selected snapshot, using
`snapshotTs` and then `snapshotId` as a deterministic tie-breaker.

### Effective Property Matrix

The default view is a table built from the union of every emitted key:

| Configuration key | Snapshot A | Snapshot B | Snapshot C | Status |
| --- | --- | --- | --- | --- |
| `server.enableHttp` | `true` | `false` | `false` | Value changed |
| `server.httpPort` | `8080` | `8080` | `8080` | Same |
| `oauth.tokenKeyUrl` | Missing | Present | Present | Added after baseline |

Each value cell renders scalars compactly and maps/lists in an expandable
formatted block. It also shows `valueType` and `sourceLevel` as secondary text.
Use typed deep equality after canonicalizing map keys; never compare JSON or
YAML strings. Equal-looking values with different types remain changes: for
example, integer `1` differs from float `1.0`, and string `"true"` differs from
boolean `true`.

Status rules are:

- `Same`: the key exists in all snapshots with the same type and value.
- `Value changed`: at least two selected snapshots have different typed
  values or value types.
- `Missing`: the key is absent from at least one selected snapshot.
- `Source changed`: all effective values match but `sourceLevel` differs.

For three or four snapshots, the row status describes the selected set and
each non-baseline cell additionally receives a same/changed/missing marker
relative to the baseline.

Provide filters for All, Changed, Missing, Source changed, and Same, plus a key
search. Default to Changed + Missing so the first view focuses on drift. Keep
unchanged rows available because users also need to prove that a critical
property did not change.

### Two-Snapshot YAML Diff

When exactly two snapshots are selected, add a `YAML diff` tab with synchronized
left and right panes. Both panes use canonical YAML, so line differences are
meaningful. Support wrapping, next/previous difference, copy, and download.

Use the official [CodeMirror `MergeView`
API](https://codemirror.net/docs/ref/#merge.MergeView) from
`@codemirror/merge` as the preferred implementation because the application
already uses CodeMirror 6 and the YAML language extension. Configure both
editors as read-only, set bounded `scanLimit` and `timeout` diff options for
large or highly divergent files, lazy-load the merge module with the YAML tab,
and call `destroy()` when the tab unmounts. Phase 0 still verifies
accessibility, license, bundle impact, and compatibility before freezing the
dependency.

Do not show this tab for three or four snapshots. The property matrix is the
side-by-side representation for those counts.

## Security and Privacy

Snapshot values can contain credentials and other sensitive configuration.

- Authorize the query with `portal.r` and validate authenticated host access
  for every requested snapshot.
- Return `Cache-Control: no-store` through the portal query path.
- Do not write YAML, typed values, or comparison responses to application logs.
- Do not store selected values or YAML in `localStorage`, `sessionStorage`, task
  context, or analytics events.
- Store only snapshot ids in the URL.
- Make Copy and Download explicit user actions.
- Preserve normal portal session expiry and CSRF behavior.

If fine-grained config-read permissions are introduced later, this endpoint
must use the same effective permission as the runtime snapshot property view,
not a weaker generic page permission.

## Performance and Limits

- Cap the request at four snapshots.
- Apply the proposed 10,000-property cap to the total entries across the
  request, not independently to each snapshot.
- Batch metadata and property loading.
- Return only requested representations through `include`.
- Enable HTTP compression for JSON/YAML responses.
- Virtualize or paginate the rendered comparison rows in the browser, but build
  the comparison from the complete server response.
- Abort an in-flight request when the user changes selection or leaves the
  page.
- Enforce a configurable property-count and serialized-response-size limit and
  return an explicit error instead of truncating.
- Build the sorted key union, typed deep comparisons, and row classifications
  in a module Web Worker. Use request generations, ignore stale replies, and
  terminate the worker when the request changes or the page unmounts.
- Keep React rendering, progress/error state, and the virtualized matrix on the
  main thread. `useTransition` may lower the priority of committing a completed
  result or changing filters, but it does not replace the worker for the
  comparison calculation itself.

The server must never paginate the data used to calculate a comparison. A
rendered table may paginate after the full key union is known.

## Implementation Areas

### `light-portal`

- Add a host-scoped persistence method that loads one to four snapshots by
  explicit id, including metadata and effective `Config` rows.
- Add the method to `PortalDbProvider` and `PortalDbProviderImpl`.
- Extract the canonical typed YAML serializer into a shared utility/domain
  class.
- Add a host-scoped batch resolver that maps two to four instance ids to exactly
  one current snapshot each and returns runtime property counts in request
  order.
- Scope current-snapshot reset/update statements by both `host_id` and
  `instance_id` so the write path matches the database identity.

### `portal-db`

- Add pre-deployment audits for duplicate current rows and current/historical
  snapshot-to-instance `service_id` mismatches.
- Add an operator-reviewed, idempotent remediation path for blocking current
  rows; do not silently choose a duplicate winner or rewrite history.
- Add the partial unique current-snapshot index to baseline DDL and an additive
  patch, with a deployment choice between concurrent creation and a maintenance
  window based on table size and patch-runner transaction constraints.
- Add schema and query-plan gates proving duplicate current rows are rejected
  and the resolver lookup uses the new index.

### `light-config-server`

- Update the Java config-server path to use the shared Java serializer.
- Run the shared golden test vectors through the Java runtime path.

### `portal-service`

- Add the Rust implementation of the canonical typed YAML contract, preferably
  in `crates/portal-core` beside the snapshot row model.
- Update `apps/config-server` to use the Rust codec instead of interpolating raw
  `property_value` strings.
- Run the same golden test vectors through the Rust runtime path.

### `config-query`

- Add `GetConfigSnapshotValues` and register
  `lightapi.net/config/getConfigSnapshotValues/0.1.0` in `spec.yaml`.
- Validate snapshot count, duplicates, phase, `include`, and host ownership.
- Return ordered snapshot objects and stable error responses.
- Add `GetCurrentConfigSnapshotsByInstances`, reuse the comparison limit model,
  enforce host/instance-read scope, and return only resolver metadata.

### `portal-view`

- Add a `values.yml` row action, preview component, copy helper, and YAML
  download helper.
- Add cross-page row-selection state with a four-snapshot cap.
- Add the Compare selected toolbar action and Show snapshot history helper.
- Add `ConfigSnapshotCompare.tsx`, its route, task/page registry metadata, and
  contextual help registration.
- Add reusable typed-value and source-change comparison helpers.
- Add cross-page `InstanceAdmin` selection, same-service validation, the
  current-snapshot resolver call, and navigation into the shared comparison
  route.

No new table or column is required because effective typed values and snapshot
metadata are already materialized. The dependent cross-instance workflow does
require the partial unique current-snapshot index above; the per-snapshot
output/comparison workflow can ship independently of that index.

## Testing

### Backend

- An explicit historical `snapshotId` is returned even when `current = false`.
- A snapshot outside `hostId` is rejected.
- One to four ids are accepted in request order; zero, five, duplicates, and
  unknown ids are rejected.
- Only runtime `Config` rows are emitted.
- Top-level and nested map keys are stable and sorted while list order is
  preserved.
- String, boolean, integer, float, map, and list values retain their types.
- Integer `1` and float `1.0`, and string `"true"` and boolean `true`, remain
  distinct typed values.
- Invalid typed values and duplicate emitted keys fail loudly.
- Source comments are emitted deterministically.
- The current snapshot output is byte-for-byte equal to both supported
  config-server implementations' `values.yml` output.
- Batch loading does not execute one property query per selected snapshot.
- Snapshot list counts include only phase `R` `Config` rows and are loaded
  without an N+1 query.
- The instance resolver returns one ordered current snapshot per selected
  instance and rejects missing, duplicate-current, mixed-service, cross-host,
  and unauthorized selections without partial output.
- The database rejects a second current snapshot for the same host/instance
  while allowing current rows for different host/instance pairs.
- The resolver's representative `EXPLAIN (ANALYZE, BUFFERS)` plan uses the
  partial current-snapshot index and the resolver remains free of N+1 queries.
- Pre-deployment audits classify duplicate current rows and current versus
  historical service-id mismatches without mutating data by default.

### Frontend

- The row action requests the clicked snapshot id, including a historical row.
- Preview loading, empty, error, Copy, and Download states work.
- The download has the expected filename, MIME type, and bytes.
- Selection survives server-side paging and rejects a fifth snapshot.
- Selection proactively blocks a total over the server-provided property cap,
  while a later authoritative `413` still produces actionable guidance.
- Show snapshot history removes only the `current` filter.
- Different-service selections are rejected; same-service cross-instance
  selections show a warning.
- Two, three, and four snapshot matrices use the complete key union.
- Value, missing, and source-only changes are classified correctly.
- Map key order does not create a false change and list order does.
- Equal-looking cross-type values are marked changed and display their types.
- Worst-case permitted comparison computation runs in the worker, ignores stale
  replies, and terminates on selection change or unmount.
- The YAML diff tab appears only for exactly two snapshots.
- The merge view is read-only, uses bounded diff work, and is destroyed on
  unmount.
- Every download revokes its Blob URL and removes its temporary anchor on
  success or failure.
- A comparison URL restores selection after refresh without storing values.
- `InstanceAdmin` selection survives paging, rejects mixed services and a fifth
  instance, and never treats the instance `current` flag as snapshot state.
- Current-instance resolution navigates with exact snapshot ids and an
  `source=current-instances` marker.
- A snapshot that becomes non-current remains visible as the resolved artifact;
  refresh requires an explicit user action.

## Acceptance Criteria

- Every row on `/app/config/configSnapshot` can output a complete, sorted,
  type-correct runtime `values.yml` for that exact snapshot.
- Output for a current snapshot matches what both supported config-server
  implementations serve for the same service and environment.
- Users can select two to four snapshots and compare all effective keys in one
  view.
- Oversized selections are rejected proactively when counts prove they exceed
  the property cap, without weakening the API's count and byte-limit checks.
- Users can select two to four same-service instances in `InstanceAdmin` and
  compare the snapshots that were current when comparison started.
- The database enforces at most one current config snapshot per
  `host_id + instance_id`, and resolver rollout is blocked by unresolved
  current-row integrity violations.
- Two selected snapshots can also be inspected as a canonical side-by-side
  YAML diff.
- The comparison clearly distinguishes value changes, missing keys, and
  source-only changes.
- Requests cannot read snapshots from another host and no sensitive value is
  persisted in browser storage.

## Rollout

1. Freeze the canonical contract and cross-language golden test vectors.
2. Add the shared Java serializer, equivalent Rust serializer, explicit
   snapshot query, parity tests, and the `getConfigSnapshotValues` action.
3. Add the per-row `values.yml` preview, Copy, and Download actions.
4. Add selection and the two-snapshot property matrix/YAML diff.
5. Enable the already-designed third and fourth matrix columns after the same
   comparison tests pass with dynamic columns.
6. Audit current-snapshot integrity in each target database, apply reviewed
   remediation for blocking current rows, deploy the partial unique index, and
   verify the resolver query plan.
7. Add `InstanceAdmin` current-snapshot resolution and selection after the
   shared comparison route, backend values API, and database gates have passed.

The API and selection cap support four snapshots from the beginning, even if
the UI rollout enables two first. This avoids an API redesign while still
allowing the simpler two-snapshot experience to be validated independently.
