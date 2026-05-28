# Rust Event Importer Design

## Overview

The `importer` repository is the Rust replacement for the current Java
`event-importer` CLI. It must preserve the operational workflows that are
already used for portal migrations:

1. Import a JSON array of CloudEvents into `event_store_t`, `outbox_message_t`,
   and pending `notification_t` records.
2. Convert a global snapshot JSON file into an ordered JSON array of
   CreatedEvents that can be imported by the same event import path.

The Rust version should be a standalone command-line tool. It should not start a
service, and it should not depend on Java runtime configuration. It should
connect directly to PostgreSQL and use the same event-store contract as
`light-portal`.

## Existing Java Behavior To Preserve

The Java `event-importer` exposes two modes.

### Import Mode

Default mode:

```bash
event-importer --filename events.json
```

Supported flags:

- `--filename`, `-f`: JSON array of CloudEvents.
- `--replacement`, `-r`: JSON array of replacement rules.
- `--enrichment`, `-e`: JSON array of enrichment rules.

Per event, the current importer:

1. Parses the input event as JSON.
2. Applies replacement and enrichment rules with `EventMutator`.
3. Deserializes the mutated JSON as a CloudEvent.
4. Reads or defaults `aggregateversion`.
5. Adds missing `aggregatetype` from event type.
6. Recomputes `subject` from event data when the subject is missing or
   replacement rules were applied.
7. Skips duplicate `(subject, aggregateversion)` pairs inside the input batch.
8. Skips events when the target database already has the same or a higher
   aggregate version for that subject.
9. Reserves a fresh nonce from `user_t` for the event user.
10. Inserts one event at a time so one bad event does not abort the whole file.

The insert path writes the event to:

- `event_store_t`
- `outbox_message_t`
- `notification_t` with `PENDING` status

### Snapshot Conversion Mode

Conversion mode:

```bash
event-importer --convert \
  --filename snapshot.json \
  --targetHostId 01964b05-552a-7c4b-9184-6857e7f3dc5f \
  --adminUserId 01964b05-5532-7c79-8cde-191dcbd421b8 \
  --output events.json
```

The current converter:

1. Reads snapshot JSON with a top-level `tables` object.
2. Sorts snapshot tables topologically from database FK metadata.
3. Skips runtime/projection-owned tables.
4. Maps each table to a CreatedEvent type.
5. Merges projection-owned child data into parent event payloads where required:
   - `auth_provider_key_t` into `auth_provider_t`
   - `auth_client_owner_t` into `auth_client_t`
   - `user_host_t`, `customer_t`, and `employee_t` into `user_t`
   - `api_endpoint_t` and endpoint scopes into `api_version_t`
6. Rewrites the source host id to the target host id recursively.
7. Emits CloudEvent-compatible JSON with:
   - new event id
   - target host
   - admin user
   - `nonce` placeholder
   - `subject` derived from event type and data
   - `aggregatetype`
   - `aggregateversion` set to `1`

The generated JSON is then imported through import mode.

## Goals

- Preserve Java CLI compatibility for existing scripts and runbooks.
- Preserve event-store, outbox, notification, nonce, offset, and transaction
  semantics.
- Keep migration behavior deterministic and testable with golden files.
- Make the Rust implementation easier to deploy as a single static binary.
- Keep snapshot conversion and import logic in one repository, but isolate them
  into testable modules.
- Support large migration workflows with stdin/stdout piping, bounded-memory
  conversion options, aggregate-version caching, and configurable batch imports.

## Non-Goals

- No online REST service in the first version.
- No schema migration management.
- No reconciliation or diff-based promotion logic.
- No attempt to replay projections directly. Import writes events and outbox
  rows; existing consumers rebuild projections.

## Command Line Interface

Use `clap` with two subcommands while also accepting Java-compatible flags.

Preferred Rust CLI:

```bash
importer import --filename events.json
importer convert --filename snapshot.json --target-host-id ... --admin-user-id ... --output events.json
importer convert --filename snapshot.json --target-host-id ... --admin-user-id ... --output - \
  | importer import --filename -
```

Compatibility CLI:

```bash
importer --filename events.json
importer --convert --filename snapshot.json --targetHostId ... --adminUserId ... --output events.json
```

### Import Options

- `--filename`, `-f`: required event list JSON file.
- `--filename -`: read event JSON from stdin.
- `--replacement`, `-r`: JSON string or `@file` containing replacement rules.
- `--enrichment`, `-e`: JSON string or `@file` containing enrichment rules.
- `--dry-run`: parse, mutate, validate, and report without writing.
- `--fail-fast`: stop on the first failed event. Default is continue.
- `--batch-size`: number of events per transaction. Default is `1` for Java
  compatibility. Snapshot imports should use a larger value, such as `500`,
  after validation passes.
- `--summary-json`: print machine-readable summary.

### Convert Options

- `--convert`, `-c`: compatibility flag for conversion mode.
- `--filename`, `-f`: required snapshot JSON file.
- `--targetHostId`, `--target-host-id`, `-t`: required target host id.
- `--adminUserId`, `--admin-user-id`, `-u`: required user id stamped on events.
- `--output`, `-o`: optional output file. If absent or `-`, write JSON to stdout
  and diagnostics to stderr.
- `--schema-source embedded|database`: default `embedded`. Embedded mode uses a
  checked-in dependency graph generated from portal DDL. Database mode uses
  PostgreSQL metadata and is useful for parity checks and dependency-graph
  refresh validation.

### Configuration

Use environment-first configuration:

```bash
DATABASE_URL=postgres://postgres:secret@localhost:5432/configserver importer import -f events.json
```

Optional config file support can mirror local compose usage:

```yaml
database:
  url: postgres://postgres:secret@localhost:5432/configserver
  max_connections: 3
```

Precedence:

1. CLI flags
2. Environment variables
3. Config file
4. Defaults

Use a config resolver such as `figment` or `config` so this precedence is
centralized and testable instead of open-coded through the CLI.

### Rust Crates And Observability

Recommended crates:

- `clap`: CLI parsing for subcommands and compatibility flags.
- `serde` and `serde_json`: strongly typed rule/config parsing plus flexible
  event payload handling.
- `sqlx`: PostgreSQL access with explicit SQL.
- `tracing` and `tracing-subscriber`: structured logs with event indexes,
  aggregate ids, table names, and transaction ids attached as fields.
- `anyhow` for internal error propagation and `miette` for user-facing
  validation/conversion diagnostics.
- `figment` or `config`: CLI/env/file/default configuration merging.
- `uuid`, `time`, and `indexmap`: deterministic IDs, timestamps, and stable
  output ordering where needed.

Logs must go to stderr when stdout is used for generated JSON. Long-running
imports should log periodic progress with totals for imported, skipped, and
failed events.

## Module Design

Proposed Rust modules:

```text
src/
  main.rs
  cli.rs
  config.rs
  db.rs
  event/
    mod.rs
    cloud_event.rs
    event_type.rs
    mutator.rs
    normalize.rs
  import/
    mod.rs
    aggregate_cache.rs
    batch.rs
    importer.rs
    report.rs
  snapshot/
    mod.rs
    converter.rs
    dependency_graph.rs
    stream.rs
    table_rules.rs
    topology.rs
    row_merge.rs
  sql/
    mod.rs
    event_store.rs
    nonce.rs
    offset.rs
    notification.rs
```

### `cli`

Parses both the new subcommand form and the legacy Java flags. The CLI layer
should only validate argument presence and resolve files. It should not contain
event mutation, conversion, or SQL logic.

### `db`

Owns the connection pool and transaction helper. Use `sqlx` with PostgreSQL.
Queries should be explicit SQL, not generated dynamically except for metadata
inspection in snapshot conversion.

### `event::cloud_event`

Represents CloudEvents as structured JSON plus typed helpers for required
fields and extensions. The implementation may use a Rust CloudEvents SDK if it
matches the portal payload exactly. If not, use a `serde_json::Value` backed
model so the serialized payload stays byte-compatible with existing Java
CloudEvents.

Required fields/extensions:

- `id`
- `source`
- `type`
- `time`
- `subject`
- `specversion`
- `datacontenttype`
- `data`
- `host`
- `user`
- `nonce`
- `aggregatetype`
- `aggregateversion`

The importer must preserve unknown CloudEvent extensions in the stored payload
and metadata. The metadata JSON should exclude the core portal extensions just
like Java `EventPersistenceImpl` excludes `host`, `user`, `nonce`,
`aggregatetype`, and `aggregateversion`.

### `event::event_type`

Rust parity for `EventTypeUtil`.

Responsibilities:

- Derive aggregate type from event type suffixes.
- Derive aggregate id from event type and event `data`.
- Keep table-to-event overrides aligned with `GlobalSnapshotPersistenceImpl`.

This module is a high-risk drift point. Every new portal event type that can be
exported or imported must have a test case here.

### `event::mutator`

Rust parity for `EventMutator`.

Rules should be parsed into strongly typed `serde` structs during startup. Bad
rule JSON should fail before the importer opens the input event file or starts a
long-running import.

Replacement rules:

```json
[
  {"field":"hostId","from":"OLD_HOST_UUID","to":"NEW_HOST_UUID"}
]
```

Behavior:

- If `from` and `to` are UUID-looking strings, recursively replace string
  occurrences anywhere in the event JSON.
- If `field` is present, recursively replace exact field values matching
  `from`.
- Accept legacy aliases `fieldName`, `fromValue`, and `toValue`.

Enrichment rules:

```json
[
  {"field":"id","action":"generateUUID"},
  {"field":"originalUserId","action":"mapGenerate","sourceField":"userId"}
]
```

Behavior:

- `generateUUID`: generate a new UUID for the target field.
- `mapGenerate`: use a stable in-memory map keyed by `field + source value`.
- Accept Java README-style aliases `field` and `mapAndGenerate` in addition to
  Java implementation names `fieldName` and `mapGenerate`. This keeps old
  scripts and docs working even though the Java implementation is stricter than
  the README examples.

The first Rust release should accept unversioned Java-compatible arrays and
versioned rule documents. The normalized internal representation should always
include a schema version so future rule changes are explicit.

Versioned rule document example:

```json
{
  "schemaVersion": 1,
  "replacement": [
    {"field":"hostId","from":"OLD_HOST_UUID","to":"NEW_HOST_UUID"}
  ],
  "enrichment": [
    {"field":"id","action":"generateUUID"}
  ]
}
```

## Import Flow

```text
read file
  -> parse JSON array from file or stdin
  -> for each raw event:
       mutate JSON
       normalize CloudEvent
       derive/default aggregate version
       derive missing aggregate type
       recompute subject if needed
       skip duplicate input aggregate version
       skip existing target aggregate version using cache-backed lookup
       reserve nonce
       insert event + outbox + pending notification in one transaction
       update summary
```

### Aggregate Version Rules

Input may contain either `aggregateversion` as a CloudEvent extension or
`aggregateVersion` as a raw compatibility field. Normalize to
`aggregateversion`.

Default is `1` when missing.

Skip rules:

- Skip duplicate `(subject, aggregateversion)` inside the input file.
- Cache target max versions in memory by `aggregate_id`.
- On first sight of an aggregate id, query target `MAX(aggregate_version)` and
  populate the cache.
- After a successful insert, update the cached max version.
- Skip if target max version is greater than or equal to the event version.

This avoids an N-query import path for aggregates with many events in the same
file. The cache is scoped to one importer run and is safe because the importer
still relies on database constraints as the final authority.

### Nonce Rules

Nonce must be reserved from `user_t` in the same transaction as the event insert:

```sql
UPDATE user_t
SET nonce = nonce + 1
WHERE user_id = $1
RETURNING nonce
```

Do not trust imported nonce values. They are placeholders only.

### Offset And Transaction Rules

For each transaction, reserve outbox offsets from `log_counter`:

```sql
UPDATE log_counter
SET next_offset = next_offset + $1
WHERE id = 1
RETURNING next_offset - $1
```

For import mode, keep Java's isolation behavior by default: one event per
transaction and one `transaction_id` per event. When `--batch-size` is greater
than `1`, reserve enough offsets for the batch and write the batch in one
transaction with one `transaction_id`.

If a batched transaction fails because of a validation or constraint error, roll
back the batch and retry its events one at a time unless `--fail-fast` is set.
This keeps fast-path imports efficient without losing the Java tool's ability to
identify the bad event and continue later events.

### Insert SQL

Write both event rows in one transaction:

```sql
INSERT INTO event_store_t
  (id, host_id, user_id, nonce, aggregate_id, aggregate_version,
   aggregate_type, event_type, event_ts, payload, metadata)
VALUES
  ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10::jsonb, $11::jsonb)
```

```sql
INSERT INTO outbox_message_t
  (id, host_id, user_id, nonce, aggregate_id, aggregate_version,
   aggregate_type, event_type, event_ts, payload, metadata, c_offset,
   transaction_id)
VALUES
  ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10::jsonb, $11::jsonb, $12, $13)
```

Also insert a pending notification row:

```sql
INSERT INTO notification_t
  (id, host_id, user_id, nonce, event_class, event_json, event_ts, process_ts,
   status, error, aggregate_id, aggregate_type, aggregate_version,
   event_partition, event_offset, transaction_id)
VALUES
  ($1, $2, $3, $4, $5, $6::jsonb, $7, now(), 'PENDING', NULL,
   $8, $9, $10, NULL, NULL, $11)
ON CONFLICT (host_id, id) DO NOTHING
```

The pending notification keeps admin visibility consistent with Java imports and
the event processor cleanup flow.

### Constraint Collisions And Idempotency

Do not add `ON CONFLICT DO NOTHING` to `event_store_t` or `outbox_message_t`.
Their primary keys and unique constraints are part of the import safety model.
The importer should catch PostgreSQL unique-violation errors, inspect the
existing row, and categorize the result:

- Exact duplicate event id and aggregate version with equivalent payload:
  report as skipped exact duplicate.
- Existing aggregate id/version with different payload, event type, or metadata:
  report as failed conflict.
- Event id collision pointing at a different aggregate: report as failed
  conflict.
- Outbox insert collision: roll back the transaction and report as failed
  conflict unless the corresponding event-store row proves this was an exact
  duplicate import.

The `notification_t` insert is different. It may use `ON CONFLICT DO NOTHING`
because it is a derived admin visibility record and should not make an otherwise
valid idempotent event import fail.

## Snapshot Conversion Flow

```text
read snapshot
  -> parse top-level object from file or stdin
  -> read tables map
  -> compute table order
  -> build child-row lookup maps
  -> for each table in order:
       skip runtime/projection-owned tables
       derive CreatedEvent type
       merge child row payloads when needed
       recursively replace source host with target host
       set aggregateVersion/newAggregateVersion compatibility fields
       derive subject
       emit CloudEvent JSON
  -> write array to output or stdout
```

### Memory Strategy

The simple implementation can parse the full snapshot into `serde_json::Value`
when the input is known to fit comfortably in memory. This is easiest for parity
work and golden tests, but it should be documented as roughly multiple times the
JSON file size because parsed JSON objects, strings, and maps add overhead.

For production-sized global snapshots, implement a streaming converter:

1. Stream the `tables` object from the input file.
2. Materialize only rows required for child merge rules, such as
   `auth_client_owner_t`, `auth_provider_key_t`, `user_host_t`, `customer_t`,
   `employee_t`, `api_endpoint_t`, and `api_endpoint_scope_t`.
3. Stream parent table rows in dependency order and write output events
   incrementally.
4. Preserve JSON array syntax by writing `[` once, then comma-separated events,
   then `]`.

If strict dependency ordering requires parent rows after later child tables, the
converter may use temporary spill files under a configured work directory. The
default design should avoid holding gigabyte-scale snapshots as a single JSON
tree.

### Snapshot Format

Expected top-level fields:

- `exportVersion`
- `sourceHostId`
- `exportScope`
- `exportTs`
- `tables`

Each table entry contains `rows`, where row keys are already camelCase.

### Table Ordering

Embedded mode should use a checked-in table dependency graph generated from the
portal DDL. Database mode should query PostgreSQL metadata and perform the same
Kahn topological sort used by Java:

- parent tables before child tables
- only dependencies between tables present in the snapshot matter
- if a cycle is found, append remaining tables deterministically and warn

The embedded graph should be the default so CI, offline conversion, and local
testing do not require a running PostgreSQL instance. Add a validation command
or test that compares the embedded graph with database metadata to catch DDL
drift.

### Table Skip Rules

Keep these sets centralized in `snapshot::table_rules`.

Auth runtime state skipped in both export/conversion logic:

```text
auth_session_audit_t
auth_session_t
auth_refresh_token_t
auth_code_t
auth_ref_token_t
auth_client_token_t
```

Projection-owned/runtime tables skipped in conversion:

```text
employee_t
customer_t
notification_t
user_host_t
user_crypto_wallet_t
auth_provider_key_t
auth_client_owner_t
api_endpoint_t
api_endpoint_scope_t
private_conversation_t
private_message_t
private_message_state_t
agent_memory_*
agent_session_history_t
snapshot_*
```

The exact skip sets must stay aligned with `GlobalSnapshotPersistenceImpl`. A
test should compare the Rust list against a fixture extracted from the Java
source until the Java importer is retired.

### Table-To-Event Overrides

Most tables map from snake case to PascalCase plus `CreatedEvent`, but several
tables require explicit overrides:

```text
environment_property_t             -> ConfigEnvironmentCreatedEvent
instance_api_property_t            -> ConfigInstanceApiCreatedEvent
instance_app_property_t            -> ConfigInstanceAppCreatedEvent
instance_app_api_property_t        -> ConfigInstanceAppApiCreatedEvent
instance_file_t                    -> ConfigInstanceFileCreatedEvent
deployment_instance_property_t     -> ConfigDeploymentInstanceCreatedEvent
instance_property_t                -> ConfigInstanceCreatedEvent
product_property_t                 -> ConfigProductCreatedEvent
product_version_property_t         -> ConfigProductVersionCreatedEvent
value_locale_t                     -> RefLocaleCreatedEvent
relation_type_t                    -> RefRelationTypeCreatedEvent
relation_t                         -> RefRelationCreatedEvent
auth_client_t                      -> ClientCreatedEvent
wf_definition_t                    -> WorkflowDefinitionCreatedEvent
```

### Child Row Merge Rules

Some tables are not standalone aggregates. Their rows must be embedded into the
parent event payload.

Required merge rules:

- `auth_provider_key_t`: group by `providerId`; attach key payloads to the
  matching `auth_provider_t` row.
- `auth_client_owner_t`: group by `ownerId`; merge owner data into the matching
  `auth_client_t` row so `ClientCreatedEvent` has the replay contract it needs.
- `user_host_t`, `customer_t`, `employee_t`: group by `userId`; merge dependent
  user state into `UserCreatedEvent`.
- `api_endpoint_t` and `api_endpoint_scope_t`: group endpoint payloads by
  `apiVersionId`; attach to `ApiVersionCreatedEvent`.

This is the most important conversion parity area. Missing merge logic can
produce an apparently valid event list that later fails replay or silently loses
projection state.

### Host Rewrite

When `sourceHostId` exists, recursively replace all exact string occurrences of
the source host id with `targetHostId` before deriving `subject`.

This order is required. If the subject is derived before replacement, old-host
aggregate ids survive and can collide on `(aggregate_id, aggregate_version)`.

## Reports And Exit Codes

Import summary should include:

```json
{
  "file": "events.json",
  "total": 100,
  "imported": 97,
  "skippedDuplicateInput": 1,
  "skippedExistingTarget": 1,
  "failed": 1
}
```

Exit code policy:

- `0`: completed; no failed events
- `2`: completed with skipped events only
- `3`: completed with failed events and `--fail-fast` was not set
- `4`: validation/config/connection error
- `5`: conversion failed

The Java tool currently exits successfully after per-event failures because it
logs and continues. The Rust tool should preserve continue behavior by default,
but explicit exit codes make automation safer.

## Testing Strategy

### Unit Tests

- CLI parsing for new and compatibility forms.
- Replacement and enrichment rules, including alias support.
- Versioned rule document parsing and fail-fast validation.
- CloudEvent normalization and metadata extraction.
- Aggregate type and aggregate id derivation.
- Aggregate max-version cache behavior.
- Table skip rules.
- Table-to-event override mapping.
- Child row merge rules.

### Golden File Tests

Use committed fixtures from `event-importer`:

- `events/bootstrap/*.json`
- `events/local/*.json`
- representative snapshot JSON files

Golden assertions:

- Java-converted snapshot and Rust-converted snapshot produce equivalent event
  arrays after ignoring nondeterministic fields (`id`, `time`).
- Rust import dry-run summary matches expected counts.
- `convert --output - | import --filename -` works without an intermediate
  events file.
- Host rewrite happens before subject derivation.
- `auth_client_t` conversion includes owner payload.
- PII token tables convert only when event/replay support exists.

### Database Integration Tests

Use disposable PostgreSQL. H2 is not recommended for Rust because the runtime
target is PostgreSQL-specific SQL and JSONB.

Test cases:

1. Import one event and verify `event_store_t`, `outbox_message_t`, and
   `notification_t`.
2. Import duplicate input aggregate version and verify skip count.
3. Import when target already has equal/higher aggregate version and verify skip.
4. Verify nonce increments from `user_t`.
5. Verify outbox offsets are gapless for successful inserts.
6. Verify failed event rolls back without blocking later events.
7. Verify unique-constraint collisions are categorized as exact duplicate or
   failed conflict.
8. Verify `--batch-size` imports multiple events in one transaction and falls
   back to one-event isolation when a batch fails.
9. Convert a snapshot and import the resulting event list into an empty DB.
10. Compare embedded table dependency order against live PostgreSQL metadata.

## Rollout Plan

### Phase 1: Rust Project Skeleton

- Add Cargo project in `importer`.
- Add CLI, config loading, logging, and database connection.
- Add dry-run import that parses and normalizes events.

### Phase 2: Import Parity

- Implement mutator and aggregate utilities.
- Implement event-store/outbox/notification transaction.
- Add duplicate/existing skip logic and aggregate max-version cache.
- Add `--batch-size` with failed-batch fallback to one-event isolation.
- Validate against existing `events/bootstrap` and `events/local` files.

### Phase 3: Snapshot Conversion Parity

- Port table ordering, skip rules, event overrides, and merge rules.
- Add embedded table dependency graph generated from portal DDL.
- Generate ordered CloudEvent JSON.
- Support `--filename -` and `--output -` so conversion can pipe directly into
  import.
- Compare Rust output with Java output using golden fixtures.
- Add streaming conversion or bounded-memory spill-file support before using the
  tool for multi-gigabyte snapshots.

### Phase 4: Operational Hardening

- Add release build and static binary packaging.
- Add wrapper scripts equivalent to `importer.sh` and `converter.sh`.
- Add README migration notes.
- Deprecate Java `event-importer` after the Rust importer passes the same
  snapshot conversion and import scenarios.

## Design Decisions

- Include an embedded table dependency graph in the first release and keep
  database metadata mode as a validation/refresh path.
- Implement `--batch-size` during import parity work. Default to `1` for Java
  behavior, but support larger batches for initial snapshot imports.
- Support stdin/stdout in both modes so operators can run
  `importer convert ... --output - | importer import --filename -`.
- Formalize replacement/enrichment as versioned `serde` schemas while accepting
  Java-compatible unversioned arrays for migration compatibility.
