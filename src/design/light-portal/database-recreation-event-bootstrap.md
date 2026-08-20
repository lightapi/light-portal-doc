# Fast Snapshot-Derived Database Bootstrap

## Status

Implemented with a narrower ingestion-only boundary. The projection-aware
bootstrap proposal retained below records the review history, but its barrier,
materialization, convergence, DLQ, and database-ready requirements are
superseded by the decision below.

## Implemented Ingestion Boundary

For `--bootstrap-import`, success means only that every input event has been
durably inserted into `event_store_t`, `outbox_message_t`, and `notification_t`.
The importer does not invoke guarded graph command persistence and does not
wait for, inspect, or modify projection state. Projection, retry, DLQ handling,
identity materialization, terminal convergence, and user notification are the
responsibility of the asynchronous event-processing system.

The retained correctness contract is limited to the write itself:

- the destination event, outbox, and notification tables must be empty;
- one UUIDv7 logical transaction envelope is generated per event;
- nonce allocation, offset allocation, and all three table writes occur on the
  coordinator connection and roll back together;
- multiple singleton logical transactions may share one bounded physical
  commit, with a default and hard ceiling of 500 events;
- a session advisory lock prevents concurrent bootstrap importers;
- importer success does not imply projection readiness or an empty DLQ.

This document defines how Light Portal recreates an empty database quickly from
the `events.json` generated from a global projection snapshot. Those events are
new synthetic CreatedEvents. They are not an export of canonical event history
and cannot preserve the original business transaction IDs.

The first optimized implementation remains on the Java `event-importer` and
`light-portal` persistence path. The Rust importer may replace it only after it
passes the parity gates in this document.

Related designs are [Rust Event Importer](../importer-rust.md),
[Event Replay](../event-replay.md), and
[Light Portal Install](../light-portal-install.md).

## Problem

Database recreation currently imports `events.json` one event at a time. Each
event opens and commits a PostgreSQL transaction. Guarded graph appends also
commit and then poll projection convergence at 250 ms intervals before the next
input event. This protects failure, graph, and DLQ isolation, but a
baseline of approximately 17,000 events takes several minutes and the generated
event set will continue to grow.

The current implementation has not attributed that elapsed time reliably. The
candidate costs are:

- PostgreSQL transaction commits;
- nonce, aggregate-version, and offset queries;
- event-store, outbox, and notification writes;
- guarded append validation and graph metadata stamping;
- projection convergence and identity materialization barriers.

P0 must measure these costs separately before a default chunk size or primary
optimization is selected. Commit reduction is a useful proxy, not the outcome:
the optimization succeeds only when measured time-to-database-ready improves
without falsely claiming that adjacent snapshot-derived events belonged to one
original business transaction. Changing from Java to Rust or running outside a
container does not answer that measurement question.

## Source-Of-Truth Correction

`events.json` is produced in two distinct stages:

1. Global snapshot export reads current projection and read-model tables.
2. Snapshot conversion turns projection rows into new ordered CreatedEvents.

The global snapshot deliberately excludes infrastructure and operational tables
such as:

- `event_store_t`;
- `outbox_message_t`;
- `notification_t`;
- `dead_letter_queue`;
- `log_counter`;
- `consumer_offsets`.

The converter may also fold several child projection rows into one parent event,
derive a new aggregate version sequence, and generate a new event UUID. A
projection row can represent the result of many historical events, while
deleted or intermediate states may not appear in the snapshot at all.

Consequently, there is no reliable mapping from a converted event back to an
original `transaction_id`, `transaction_ordinal`, or `transaction_count`.
Querying `event_store_t` or joining `outbox_message_t` separately cannot restore
that relationship for synthetic snapshot events.

The importer must not attempt to enrich snapshot-derived `events.json` with
original transaction metadata. Original-history export is a separate problem
and is outside this design.

## Decision Summary

1. The existing top-level JSON array remains the canonical snapshot-derived
   `events.json` format.
2. Every generated event represents one new singleton logical transaction.
3. At import, each event receives its own newly generated UUIDv7
   `transaction_id`,
   `transaction_ordinal = 0`, and `transaction_count = 1`.
4. Adjacent events are never flattened under one logical `transaction_id`.
5. A physical PostgreSQL transaction may persist several singleton logical
   transactions while retaining a different logical transaction ID for every
   event.
6. Configured chunk size controls physical commit frequency only. It never
   defines business transaction membership.
7. Graph and validator read-model dependencies create commit barriers. The
   importer commits the barrier event before waiting for required projection
   state. It must never wait for a row produced by an open chunk.
8. The guarded Java append path remains authoritative during the first phase.
   Direct SQL that bypasses `GraphCommandPersistence`, `EventAppendValidator`,
   recovery projection markers, or identity materialization is not an accepted
   optimization.
9. Public installation should normally restore a release-built, validated
   PostgreSQL bootstrap archive and import only later event deltas. Complete
   snapshot-event import remains the portable fallback and qualification
   oracle.
10. Container versus host execution is an operational choice, not the primary
    performance design.
11. The Rust importer is not selected for database recreation until it
   implements singleton logical transactions, guarded bootstrap behavior, and
   Java-versus-Rust differential tests.
12. The first implementation is a single writer, enforced by a session-level
    advisory lock, and uses `READ COMMITTED` transactions.
13. Barrier latency is a first-class optimization target. P0 starts with an
    adaptive low-latency poll and evaluates `LISTEN`/`NOTIFY` if polling remains
    material.

## Goals

- Reduce empty-database recreation time as snapshot event volume grows.
- Preserve the current one-event logical transaction and DLQ isolation
  semantics.
- Reduce physical PostgreSQL commits without creating false multi-event
  transactions.
- Preserve nonce, aggregate-version, outbox-offset, policy-version, graph, and
  projection behavior.
- Keep current snapshot generation and `events.json` consumption portable.
- Preserve exact failure diagnostics during bootstrap.
- Provide a fast, reproducible installation artifact tied to an exact schema
  and event baseline.
- Compare Java and Rust importers against the same fixtures and database
  postconditions.

## Non-Goals

- Recovering original history or adding original `transaction_id` metadata to
  the snapshot/event format.
- Treating chunk adjacency as business transaction membership, using one giant
  transaction, or parallelizing arbitrary events.
- Weakening validation and graph/identity guards or bypassing them with direct
  `COPY` into canonical tables.
- Making a physical PostgreSQL volume the portable public artifact.
- Removing snapshot-event import as the recovery/conformance path or treating
  successful append as database readiness.

## Terminology

| Term | Meaning |
| --- | --- |
| Projection snapshot | Current state exported from projection and read-model tables. |
| Synthetic event | A new CreatedEvent generated from a projection row or folded group of rows. |
| Logical transaction | The event-processing and replay unit identified by `transaction_id`. Every snapshot-derived event has its own singleton logical transaction. |
| Physical commit chunk | One PostgreSQL transaction used to persist several singleton logical transactions. |
| Chunk target | A soft event-count and byte-size target used to construct a physical commit chunk. |
| Projection barrier | An event after which the importer must commit and wait before later events can be accepted safely. |
| Bootstrap archive | A release-built PostgreSQL archive containing canonical synthetic history and already-converged projection state. |
| Archive baseline ID | Immutable release-manifest coordinate identifying the exact schema, full `events.json`, and ordered release deltas already represented by an archive. It is not inferred from a maximum event UUID, nonce, or offset. |
| Database ready | Synthetic canonical history is present, required projections and identities are verified, and no bootstrap failure or pending convergence remains. |

## Current Behavior And Constraints

### Snapshot converter

The converter:

1. reads the snapshot's `tables` object;
2. removes tables excluded from export and conversion;
3. topologically sorts remaining tables;
4. folds selected child rows into parent event payloads;
5. derives aggregate identity and sequential aggregate versions;
6. generates a new UUID for every event;
7. writes nonce `0` as an import-time placeholder;
8. emits a top-level JSON array.

The generated events contain no transaction metadata. This is intentional, not
a legacy-format defect.

### Java importer

The Java importer currently validates, normalizes, and persists every generated
event independently. Each call creates:

- one PostgreSQL commit;
- one newly generated logical `transaction_id`;
- one outbox member with ordinal `0` and count `1`;
- one pending notification associated with that transaction.

The underlying persistence implementation already exposes connection-aware
`EventPersistenceImpl.insertEventStore(Connection, CloudEvent[], UUID)` and
`GraphCommandPersistence.append(Connection, CloudEvent[], UUID)` entry points,
as well as array inserts, append validation, nonce and offset allocation, and
JDBC batches. One array still becomes one logical transaction, so a physical
chunk cannot be passed as one arbitrary array without incorrectly turning
unrelated snapshot events into a multi-event DLQ and replay group.

Two concrete connection-level gaps remain. The public guarded connection-aware
append hardcodes ordinary projection behavior; there is no public
connection-aware bootstrap overload that sets `recoveryProjection=true`.
Also, the current non-guarded importer reserves the nonce through
`queryNonceByUserId` on a separate data-source connection before the append.
That reservation is committed independently and must be moved onto the chunk
connection.

### Guarded append constraints

The optimized path must retain:

- common trusted host and user identity validation;
- create-stream and semantic-identity guards;
- graph root and accepted-revision locking;
- policy registry and repair schema validation;
- recovery projection markers used by bootstrap;
- Category and Tag identity materialization;
- projection convergence waits;
- fail-fast empty-destination behavior.

### Rust importer

The current Rust importer generates one transaction ID for all events in its
configured batch. A batch of 500 therefore becomes one synthetic 500-event
logical transaction. That does not match this design.

The Rust implementation also writes canonical and outbox tables directly
without the complete guarded bootstrap, historical import, graph,
recovery-projection, policy registry, and identity-materialization behavior of
the Java path. It remains an experimental performance candidate until parity is
proven.

## Snapshot Event Contract

The canonical input remains:

```json
[
  {
    "specversion": "1.0",
    "id": "019ccccc-0000-7000-8000-000000000002",
    "type": "RefTableCreatedEvent",
    "subject": "019ccccc-0000-7000-8000-000000000003",
    "host": "019ccccc-0000-7000-8000-000000000004",
    "user": "019ccccc-0000-7000-8000-000000000005",
    "nonce": "0",
    "aggregateversion": 1,
    "data": {}
  }
]
```

For every array member, the importer derives a singleton append envelope:

```text
transaction_id      = UuidUtil.getUUID() // UUIDv7
transaction_ordinal = 0
transaction_count   = 1
```

Transaction identity is import infrastructure metadata. It is not added to the
CloudEvent or claimed to represent source history. Java uses the system-standard
`UuidUtil.getUUID()`, which generates a time-ordered epoch UUIDv7. Rust must
generate an RFC-compatible UUIDv7 through its shared UUID utility. UUIDv7 keeps
the transaction IDs aligned with other generated identifiers in the system,
but transaction processing order remains exclusively offset- and
ordinal-based; consumers must not infer ordering semantics from
`transaction_id`.

Before writes begin, each synthetic event is checked for:

- valid CloudEvent structure;
- a unique event ID within the file;
- a trusted host and user;
- a non-empty subject and aggregate type;
- a supported event type and policy version;
- a valid aggregate-version sequence;
- replacement and enrichment rule validity;
- bootstrap append-mode classification;
- hard event-size limits.

Duplicate input aggregate versions or an existing equal/higher target version
follow the existing importer rules. Empty-database bootstrap still requires a
complete, skip-free result.

## Import Planning

Import separates planning from execution:

```text
snapshot-derived events.json
  |
  v
parse, mutate, normalize, and validate events
  |
  v
assign one singleton logical transaction per event
  |
  v
classify append mode and projection barriers
  |
  v
pack compatible singleton appends into physical commit chunks
  |
  v
append -> commit -> wait at barriers -> verify
```

### Append-mode classification

Every event receives exactly one append mode:

- guarded command append;
- guarded bootstrap append;
- write-fenced bootstrap identity append;
- write-fenced historical append.

A physical chunk may contain different singleton append modes only if the
bootstrap coordinator can preserve each mode's validation and projection
behavior. The initial implementation should flush the chunk when mode changes.

### Projection barriers

The planner creates a barrier around work whose successor requires committed
projection state. Initial barriers include:

- guarded graph events whose projected revision must catch up;
- an event whose validator requires a read model produced by an earlier event;
- an explicit end-of-import convergence check.

Category and Tag birth events remain forced single-event physical chunks
because they cannot share an append batch with other events. Their identity
materialization is not a mid-import wait: the current importer runs
`materializeBootstrapIdentities()` once after the complete event loop, so it is
a terminal bootstrap step unless a future dependency proves otherwise.

Barrier classification is registry-driven and versioned with the importer. Its
source is the same contract that creates the dependency:

- graph barriers live beside `GraphEventRegistry.resolveRoot` and its
  projection-table root resolution;
- validator barriers live beside the validator read-model dependency registry.

This avoids a second hand-maintained event-type list drifting from the reads it
must protect. Classification is never inferred from timing or a failed retry.

### Physical commit chunk construction

The chunk builder follows these rules:

1. Preserve input order.
2. Keep every event as a distinct singleton logical transaction.
3. Never cross a projection barrier.
4. Flush when append mode or another guarded compatibility boundary changes.
5. Stop before the event-count or byte-size target would be exceeded.
6. Reject one event only when it exceeds the separate hard event-size limit.

Initial tuning candidates are 50, 100, 250, and 500 events per physical commit
chunk. A candidate must pass the lock-pressure test as well as performance and
correctness gates. The selected production default is based on qualification
results, not on language or container runtime.

### Transaction and barrier invariants

The coordinator enforces these named invariants:

1. **Never wait inside an open chunk.** `log_counter.next_offset` is advanced in
   the event write transaction, while the database consumer treats
   `next_offset - 1` as the claimable tip. Uncommitted rows are therefore
   intentionally invisible to the projector. A barrier event is appended and
   committed before any wait for its projection begins.
2. **Use `READ COMMITTED`.** Root resolution and validator dependencies read
   projection rows written by another process between chunks. A transaction
   must not retain a stale `REPEATABLE READ` snapshot across such a wait.
3. **One active bootstrap writer.** The coordinator acquires a well-known
   session-level PostgreSQL advisory lock before the empty-destination check and
   holds it through final verification. A second importer fails fast.
4. **Preserve append lock order.** A chunk repeats existing singleton append
   lock order on one connection. Locks last until commit, so chunk qualification
   records lock waits and distinct advisory locks and rejects sizes that create
   unsafe shared-lock-table, WAL, memory, or rollback pressure.

## Persistence Design

### Separate logical transactions inside one physical commit

The required shape is:

```text
PostgreSQL transaction
  event A -> transaction A / ordinal 0 / count 1
  event B -> transaction B / ordinal 0 / count 1
  event C -> transaction C / ordinal 0 / count 1
commit
```

The existing persistence APIs are already connection-aware, but each call
accepts one transaction ID with one event array. The optimized path therefore
needs a connection-aware bootstrap coordinator that accepts a sequence of
singleton append requests. Within one PostgreSQL transaction it processes each
request in input order through the same validation and stamping path, supplying
a new transaction ID and a one-event array for every request.

The coordinator must not flatten the chunk into one event array with one
generated transaction ID.

The first API change is a public connection-aware bootstrap guarded append, for
example `appendBootstrap(Connection, CloudEvent[], UUID)`, that preserves the
current recovery projection marker. The coordinator constructs and reuses one
`GraphCommandPersistence` with one loaded `GraphCommandConfig`; it must not
repeat the current `PortalDbProviderImpl.appendCommandEvents` behavior of
loading config and constructing the persistence object for every event.

### First optimization boundary

The first implementation reduces connection acquisition and commit/fsync cost
while retaining existing per-event validation, nonce stamping, offset
reservation, and persistence calls inside the shared PostgreSQL transaction.

This deliberately separates the highest-value change from later SQL
optimization. After correctness is proven, prepared statements, nonce ranges,
offset ranges, and notification inserts may be optimized without changing
logical transaction identity.

### Nonce and offset allocation

Nonce and offset allocation must become atomic with canonical and outbox writes
for every append mode. This is already true for guarded append because
`GraphCommandPersistence` calls the connection-taking nonce reservation. It is
not true today for direct bootstrap modes: `queryNonceByUserId` reserves and
commits through a separate connection before the event append.

- Preserve event order when assigning nonce values.
- Never trust nonce `0` from `events.json` as a persisted value.
- Add and use the connection-taking nonce reservation for direct append modes;
  never reserve or read a nonce outside the chunk transaction.
- Keep each outbox row's distinct transaction ID, ordinal `0`, and count `1`.
- Allocate gapless, commit-ordered outbox offsets across the physical chunk.
- Rollback returns the complete physical chunk to its pre-import state.

Until this gap is fixed, a rolled-back direct-mode chunk burns its already
committed nonces and does not satisfy the optimized bootstrap contract.

`EventAppendValidator` requires contiguous nonces inside one append array.
Singleton append calls satisfy that rule. This is an additional prohibition on
folding a physical chunk into one array unless the full multi-event logical
transaction contract is deliberately invoked.

Set-based range reservation is a later optimization and requires the same
locking and monotonicity proof as the current guarded path. Nonce or offset
ranges must never be reserved in a separate transaction: the consumer advances
its claim cursor to the committed counter tip, so publishing an offset tip
before its rows could cause permanently skipped events.

### SQL batching

Prepared statements should be reused within the physical chunk where the
validated persistence API permits it. Event-store, outbox, and notification
inserts may use JDBC batch or set-based execution after parity tests prove
identical validation, conflict, and notification behavior.

The implementation continues to write:

- `event_store_t` with validated policy and repair schema versions;
- `outbox_message_t` with one distinct singleton transaction per event;
- `notification_t` with the corresponding transaction ID and `PENDING` status.

### Failure behavior

Bootstrap import is fail-fast at the file level.

If a physical chunk fails:

1. roll back the complete physical chunk;
2. retain the failing chunk number and event IDs in diagnostics;
3. rerun the chunk one singleton event at a time in an isolated diagnostic
   attempt when enabled;
4. identify the first failing event and its validation or SQL code;
5. discard and recreate the destination, then restart from the verified empty
   state.

Diagnostic retry must not leave a partial database that an installer can
mistake for success.

The initial design has no resumable import checkpoint. That is consistent with
the existing `requireEmptyBootstrapDestination` guard and with bootstrap's hard
failure when any duplicate or existing aggregate version is skipped. A future
checkpoint design would need its own durable cursor, chunk checksum, idempotency
contract, and a deliberate relaxation of the empty-destination rule.

### Disposable durability optimization

The importer may expose an empty-database-only option that executes
`SET LOCAL synchronous_commit = off` inside each physical chunk. Transaction
scope is preferred to a session GUC so the relaxed durability cannot leak into
unrelated work if connection handling changes. It does not disable `fsync`,
constraints, or transactional rollback globally. If the host fails during
bootstrap, installation restarts from an empty destination.

This option is never enabled for incremental imports or existing databases.

P0 also benchmarks, and records an explicit accept or reject decision for:

- bootstrap-window `max_wal_size` and checkpoint tuning;
- deferring non-essential projection indexes and rebuilding them before ready;
- temporarily setting projection-only tables `UNLOGGED`, including the
  `SET LOGGED` rewrite and crash-restart cost.

Canonical event, outbox, nonce, offset, constraint, and guard tables remain
logged and indexed. No tuning is accepted unless the ordinary released
configuration is restored and verified before database-ready is reported.

## Release-Built PostgreSQL Bootstrap Archive

Physical commit chunking improves recovery performance, but public installation
should not repeatedly pay the full synthetic-event import and projection cost.
The release pipeline performs that work once and publishes a validated archive.

### Archive generation

```text
canonical snapshot-derived events.json
  |
  v
fresh release-matched PostgreSQL
  |
  v
guarded singleton-logical / chunked-physical import
  |
  v
projection and identity convergence
  |
  v
correctness and checksum gates
  |
  v
pg_dump archive + signed manifest
```

The generator uses the same released schema, service artifacts, policies, and
projection handlers declared by the installation bundle.

### Archive contents

The archive contains:

- canonical synthetic `event_store_t` history;
- event-derived read models;
- identity and graph revision state;
- required reference and bootstrap tables;
- consistent nonce and offset counters;
- schema objects owned by the release.

`user_t.password` and `auth_client_t.client_secret` are credential verifiers in
the canonical projection schema. A public archive must not turn a release seed
into a reusable credential shared by every installation. The published archive
contains disabled placeholder verifiers. During first boot, the installer
generates installation-unique administrator and client credentials locally,
stores only their verifiers, and delivers clear values through the existing
one-time secret/enrollment boundary. No externally reachable listener starts
until that rotation is verified. The dedicated auth-client secret regeneration
contract is reused where applicable. Stable host, user, and client identifiers
may remain in the archive; they are identifiers, not authentication secrets.

Checksums and signatures prove artifact integrity and provenance; they do not
make embedded credentials secret.

Before capture, the generator quiesces projection work and normalizes
operational state:

- all required projection cursors equal the baseline watermark;
- no required projection transaction is pending or failed;
- transport queues are empty or recorded under one explicitly versioned
  archive policy;
- bootstrap notifications and transient diagnostics are removed unless the
  release contract explicitly retains them;
- the next nonce and outbox offset remain monotonic after restore.

### Manifest

The archive manifest includes:

```json
{
  "format": "lightapi.portal-postgres-bootstrap",
  "formatVersion": 1,
  "postgresMajor": 18,
  "portalDbCommit": "...",
  "eventsJsonSha256": "...",
  "eventCount": 17000,
  "singletonTransactionCount": 17000,
  "lastEventId": "...",
  "lastOutboxOffset": 17000,
  "archiveBaselineId": "portal-2026.08.0-baseline-1",
  "includedDeltaIds": [],
  "checksumProfile": "portal-bootstrap-v1",
  "canonicalizationSpecSha256": "...",
  "projectionChecksumSet": "...",
  "createdAt": "..."
}
```

The PostgreSQL major version is illustrative; generation records the actual
release version. The manifest also contains archive SHA-256, byte size, schema
digest, required extension versions, per-table verification counts, credential
sanitization policy, restore role mapping, and release signing identity.

`pg_dump` does not carry cluster roles and planner statistics are not a durable
restore contract. Archive generation therefore uses an ownership-neutral dump
and records the intended application role/grants separately. Restore uses
`pg_restore --no-owner --no-acl` (or an explicitly mapped restore role),
reapplies and verifies grants, and runs `ANALYZE` before the readiness timer can
succeed.

### Checksum canonicalization and reproducibility

UUIDv7 transaction IDs and database-generated operational timestamps differ
between valid rebuilds. Differential and archive checks therefore use a
versioned, machine-readable checksum profile, not an unspecified
"canonicalized" comparison. The `portal-bootstrap-v1` profile defines an exact
ordered column list and row sort key for every checksummed table; no wildcard
column exclusion is permitted.

The initial exclusion/normalization set is:

- exclude `outbox_message_t.transaction_id` and, if notifications are retained
  by archive policy, `notification_t.transaction_id`; verify UUIDv7 type,
  uniqueness, ordinal, count, and event association through separate queries;
- exclude archive/build timestamps such as manifest `createdAt`;
- normalize only database-wall-clock columns named by the table profile,
  initially `entity_aggregate_t.created_ts`,
  `entity_aggregate_t.retired_ts`,
  `entity_identity_t.created_ts`,
  `entity_identity_t.demoted_ts`,
  `entity_identity_materialization_t.completed_ts`,
  `instance_graph_revision_t.accepted_ts`,
  `instance_graph_revision_t.projected_ts`,
  `notification_t.process_ts`, `notification_t.read_ts`,
  `portal_event_delta_t.imported_ts`, and `dead_letter_queue.created_dt` when
  those operational tables are retained;
- retain source-event `event_ts`, event IDs, payloads, metadata, aggregate
  identity/version, nonces, offsets, graph revisions, policy versions, and all
  other business columns exactly.

If implementation shows that another database-generated column is
nondeterministic, the versioned profile and its digest must change explicitly;
the test harness must not silently drop it. Gate 1 compares canonical event
content, Gate 10 uses this profile for projections, and Gate 13 compares Java
and Rust after the same normalization while separately checking UUIDv7
transaction invariants.

A rebuilt `pg_dump` archive is not expected to be byte-identical to the
published archive. UUIDv7 values, operational timestamps, dump ordering,
compression, and planner statistics can differ. Installation verifies the
published object's exact SHA-256 and signature from the release manifest. An
independent rebuild verifies schema digest, the versioned canonical table
checksums, per-table counts, and the separate transaction/ordering invariants;
it does not verify dump-byte equality.

### Delta contract

The archive watermark is the manifest's `archiveBaselineId` plus its exact
ordered `includedDeltaIds`; it is not `MAX(c_offset)`, a maximum event UUID, or
a per-user nonce. Offsets and nonces are local consistency checks, not a
portable release coordinate.

Post-archive changes use the existing release event-delta shape: one ordered
JSON file per immutable delta, an ID derived from its release filename, a
SHA-256 recorded in the signed release manifest, and an effect-verification SQL
contract. `portal_event_delta_t(delta_id, checksum)` records successful
application. The delta importer continues aggregate versions from the restored
state, reserves nonces and offsets transactionally, and records the delta only
after the exact event or an explicitly accepted equivalent effect at that or a
later aggregate version is verified.

The archive manifest lists the first delta that may follow it and the ordered
set or release range accepted thereafter. Delta files, verification SQL, and
supersession metadata are covered by the same signed release manifest as the
archive. An unknown, missing, reordered, checksum-mismatched, or unverifiable
delta fails closed. Database-ready requires all selected deltas and their
projections to converge.

### Installation flow

For an empty destination, the installer:

1. downloads the version-matched archive and manifest;
2. verifies checksum, signature, PostgreSQL major version, schema identity, and
   `events.json` digest;
3. restores with `pg_restore --no-owner --no-acl`, an explicit
   restore/application role mapping, and safe parallel jobs where supported;
4. reapplies and verifies grants, runs `ANALYZE`, and verifies the archive's
   credential sanitization or pre-listener rotation contract;
5. runs post-restore counter, graph, identity, projection, and row-count gates;
6. imports only manifest-authorized event deltas after the archive baseline;
7. starts normal externally reachable services only after credential and delta
   gates pass;
8. reports database ready only after delta projection converges.

If compatibility or verification fails, the installer discards the incomplete
empty destination and falls back to canonical snapshot-event import. It never
mixes an unverified partial restore with replay.

### Why not a physical volume snapshot

A physical PostgreSQL data-directory or container-volume snapshot can restore
faster, but it is coupled to PostgreSQL binary version, architecture, storage
layout, and crash-recovery state. A PostgreSQL archive plus compatibility
manifest is the initial portable distribution choice. A physical snapshot may
be added later for tightly controlled hosted environments.

## Java And Rust Responsibilities

### Phase-one Java path

The Java path owns the first optimized implementation because it already has:

- graph-aware command append and revision guards;
- append validation and policy selection;
- bootstrap recovery projection markers;
- nonce reservation through the trusted persistence layer;
- identity materialization and projection convergence waits;
- the deployment flags used by current recreation scripts.

The implementation adds a dedicated connection-aware bootstrap coordinator
instead of changing ordinary live-command semantics.

### Rust qualification requirements

The Rust importer becomes eligible only when it:

- reads the existing top-level snapshot event array;
- assigns one distinct UUIDv7 singleton logical transaction per event;
- never creates a logical transaction from arbitrary chunk membership;
- supports guarded bootstrap, historical, and bootstrap identity modes;
- uses the same event-type, aggregate, policy, repair-schema, and graph
  validation contracts;
- preserves the recovery projection marker without modifying canonical event
  history;
- reserves nonce and offset values atomically;
- performs required identity materialization and convergence barriers;
- emits parity-compatible summaries and failure codes;
- passes database differential tests against the Java importer.

Running the Rust binary directly on the host remains supported after parity,
but that removes only container startup overhead. It is not a substitute for
physical commit chunking or the bootstrap archive.

## Concurrency

The first implementation uses one ordered importer and enforces exclusivity
with the session advisory lock defined above. Arbitrary parallel workers are
rejected because they contend on:

- per-user nonce allocation;
- the global outbox offset counter;
- aggregate-version streams;
- logical identity and graph advisory locks;
- projection dependencies between earlier and later events.

Future parallelism may partition proven-independent hosts, but the current
snapshot baseline normally uses one target host and one administrative user.
Parallelism is considered only after physical commit chunking and archive
restore are measured.

Chunking also extends transaction-scoped lock lifetime. Row locks do not each
consume a `max_locks_per_transaction` slot, but distinct advisory and relation
locks use the shared lock table and all retained locks can increase blocking and
rollback cost. Qualification at the maximum supported chunk size records
distinct advisory locks, relation locks, lock waits, transaction memory, WAL,
and any PostgreSQL `out of shared memory` failure. The default remains below the
smallest demonstrated safe ceiling on the reference runner.

## Observability

The importer emits structured progress and a final machine-readable summary:

- input event count;
- assigned singleton logical transaction count;
- physical chunk count and size distribution;
- database commit count;
- events and commits per second;
- parse, plan, validation, per-event database round-trip, append, commit,
  lock-wait, and final-verification duration;
- barrier count and total, mean, and p95 wait duration broken out by graph-root
  resolution, validator dependency, terminal identity materialization, and
  final convergence;
- barrier poll count and wake-up latency;
- skipped duplicate and existing aggregate-version counts;
- diagnostic fallback count;
- current outbox and projection lag;
- failed event ID and error code;
- final graph, identity, and projection verification result.

Logs include synthetic transaction IDs where useful but do not log secrets or
complete sensitive event payloads.

## Configuration

Initial options are explicit and bootstrap-scoped:

```text
--bootstrap-import                         # existing
--bootstrap-operator-id <uuid>             # existing
--bootstrap-materialization-timeout-seconds 120  # existing
--physical-chunk-events 100
--physical-chunk-bytes 16777216
--max-event-bytes 67108864
--diagnose-failed-chunk
--bootstrap-synchronous-commit-off
--physical-chunking-disabled
```

The first three flags already exist. The remaining names and default values are
provisional until implementation review. The existing materialization timeout
is a terminal Category/Tag convergence budget and currently also bounds each
graph projection wait. The implementation separates or explicitly documents
those budgets so a file with many graph barriers cannot silently multiply one
operator setting into an unbounded total wait.

`--physical-chunking-disabled` preserves the current one-commit-per-event path
as a field rollback and reference oracle. The important contract is that
physical chunk limits never create logical transaction membership.

Ordinary incremental imports retain their existing durability and
failure-isolation behavior unless separately designed and qualified.

## Correctness Gates

Every optimized import or archive qualification run must prove:

1. Exact canonical event ID, type, payload, metadata, aggregate identity,
   aggregate version, and policy-version parity with the one-event reference.
2. Every snapshot event has a distinct UUIDv7 outbox `transaction_id`.
3. Every outbox member has `transaction_ordinal = 0` and
   `transaction_count = 1`.
4. No two adjacent snapshot events are represented as one logical transaction.
5. For each user, nonces are contiguous within every successfully committed
   chunk; a rolled-back chunk restores `user_t.nonce` and introduces no gap.
6. Outbox offsets are gapless and commit-ordered; no counter tip is visible
   before every row through that tip is committed.
7. No physical chunk member is visible after rollback.
8. Database-ready returns no row from
   `instance_graph_revision_t WHERE projected_revision < accepted_revision`.
9. Required identity materialization rows are verified.
10. Projection table counts and checksums produced by the manifest-pinned
    canonicalization profile match the one-event reference import.
11. No unexpected `FAILED`, DLQ, replay-candidate, or pending-bootstrap rows
    remain.
12. Crash and retry tests never report a partial database as ready.
13. Java and Rust database postconditions match before Rust is selected.
14. A barrier wait cannot execute while the coordinator connection has an open
    transaction, and the barrier event is visible before the wait begins.
15. Projection rows committed by another process between chunks are visible to
    the coordinator under `READ COMMITTED`.
16. A second bootstrap importer fails on the session advisory lock before it
    mutates the destination.
17. Direct and guarded nonce changes roll back with their physical chunk.
18. Restored ownership, grants, credential sanitization/rotation, and planner
    statistics pass before externally reachable services start.

## Performance Gates

Performance is recorded on a named reference runner with PostgreSQL, storage,
CPU, memory, container runtime, `events.json` checksum, and service versions in
the result manifest.

Initial acceptance targets for the approximately 17,000-event baseline are:

- optimized import reaches database-ready state at least five times faster than
  the one-event reference without failing any correctness gate;
- physical commit chunking reduces PostgreSQL commits by at least 90%, recorded
  as a diagnostic proxy rather than a substitute for the readiness target;
- bootstrap archive restore reaches database-ready state within 60 seconds on
  the reference runner;
- p95 archive restore time across ten clean runs remains within 20% of the
  median;
- increasing the fixture to 50,000 events does not reintroduce one commit per
  event or superlinear planning behavior.

These are release qualification gates, not claims about every customer host.
The measured reference results determine the final default chunk targets. A
large commit reduction with only a 1.2x readiness improvement fails
qualification and redirects work to the measured barrier, round-trip,
validation, lock, or restore bottleneck.

## Rollout Plan

### P0: Baseline and instrumentation

- Attribute parse, validation, per-event round trips, append, commit, lock wait,
  each barrier type, projection, identity materialization, and total readiness
  time. No default chunk decision precedes this result.
- Capture the 17,000-event and 50,000-event fixtures and checksums.
- Add singleton transaction, nonce, offset, graph, identity, and projection
  verification queries.
- Keep current one-event import as the reference oracle.
- Benchmark adaptive graph polling starting at 2-5 ms with bounded backoff. If
  graph waits remain material, prototype a projection-advance `LISTEN`/`NOTIFY`
  channel using polling only as the lost-notification safety net.
- Benchmark and record decisions for transaction-local `synchronous_commit`,
  WAL/checkpoint tuning, deferred projection indexes, and unlogged projection
  tables.

P0 exits only when instrumented buckets reconcile to within 5% of wall-clock
readiness time and the selected workstreams have a measured path to the 5x
gate. Chunking proceeds as the primary P2 workstream only when avoided commit
and connection work predicts at least a 20% readiness reduction; otherwise the
measured barrier, validation, or round-trip workstream moves ahead of chunk-size
tuning. Chunking may still follow for scale and commit-count control.

### P1: Explicit singleton semantics

- Document the snapshot-to-synthetic-event boundary in converter and importer
  tests.
- Assert that generated `events.json` contains no source transaction metadata.
- Add a bootstrap plan that assigns one UUIDv7 singleton logical transaction
  per event.
- Reject any optimization that flattens a physical chunk under one transaction
  ID.

### P2: Java physical commit chunking

- Add import planning, barrier classification, and physical chunk construction.
- Add the connection-aware bootstrap overload and coordinator; reuse loaded
  graph configuration and persistence objects.
- Move direct-mode nonce reservation onto the coordinator connection.
- Enforce `READ COMMITTED`, the session advisory lock, and never-wait-in-open-
  chunk invariant.
- Preserve distinct singleton transaction IDs within every physical commit.
- Add failed-chunk rollback and per-event diagnostics.
- Run the 500-event lock-pressure test, then select a qualified default and hard
  ceiling.

### P3: Release-built bootstrap archive

- Generate the archive from a clean, release-matched database.
- Add manifest, checksum, signature, and post-restore gates.
- Add ownership-neutral restore, grant verification, disabled archive
  verifiers, forced installation-unique pre-listener credential rotation, and
  `ANALYZE` to the readiness gate.
- Publish immutable versioned archive objects.
- Make installation prefer restore and fall back to snapshot-event import.
- Import and verify only release-manifest deltas after the archive baseline.
- Pin the named reference runner in `light-portal-install` release CI and enforce
  the 60-second ready gate for every release archive.

### P4: Rust parity and optimization

- Correct Rust singleton transaction and guarded bootstrap semantics.
- Add Java-versus-Rust differential database tests.
- Optimize prepared statements, set-based range reservation, and inserts only
  after parity passes.
- Select Rust as the default only through an explicit qualification decision.

### P5: Optional partitioned import

- Evaluate host-level parallelism only if archive restore and ordered physical
  chunking still miss the installation objective.
- Retain one global offset allocator and prove event ordering.

## Test Matrix

| Scenario | Required result |
| --- | --- |
| Snapshot array with 1,000 events | 1,000 distinct UUIDv7 logical transaction IDs; every ordinal is 0 and count is 1. |
| Same snapshot imported into two clean databases | UUIDv7 transaction values may differ; manifest-pinned canonical checksums and separate transaction-shape gates match. |
| Physical chunk target 100 | Approximately 10 physical commits without changing singleton transaction metadata. |
| Event larger than chunk byte target but below hard limit | One-event physical chunk. |
| Event beyond hard size limit | Import rejected before writes. |
| Mode change inside planned chunk | Prior chunk flushed; next mode starts a new chunk. |
| Projection barrier between ordinary events | Prior chunk committed; required projection wait completes before continuation. |
| SQL failure on event 42 of a chunk | Whole physical chunk rolled back; diagnostic retry identifies event 42. |
| Crash before physical commit | No chunk member visible. |
| Crash after a non-final chunk commit | Destination is not reported ready; installer recreates the empty destination and restarts. |
| Two adjacent related CreatedEvents | Still receive different logical transaction IDs. |
| Barrier event at the end of a chunk | Chunk commits before wait; projector observes it and wait terminates. |
| Attempted barrier wait with open transaction | Coordinator test fails immediately rather than timing out. |
| Projection advances between chunks | Coordinator observes it under `READ COMMITTED`. |
| Direct-mode failure after nonce reservation | Chunk rollback restores nonce, event, outbox, and notification state. |
| Two concurrent bootstrap importers | Second importer fails before the empty check or any write. |
| Chunk target 500 with graph/identity-heavy fixture | No lock-table exhaustion; lock waits, WAL, memory, and rollback time remain within the qualified ceiling. |
| Rust `--batch-size 500` parity test | 500 singleton transaction IDs, not one 500-member transaction. |
| Archive schema or PostgreSQL mismatch | Restore refused; clean fallback to snapshot-event import. |
| Archive checksum mismatch | Restore refused before database mutation. |
| Archive rebuilt from the same baseline | Dump bytes may differ; schema digest, table counts, canonical checksums, and transaction invariants match. |
| Archive restore role absent from dump source | `--no-owner --no-acl` restore plus explicit grants succeeds and application-role access verification passes. |
| Restored archive before `ANALYZE` | Database-ready remains false. |
| Public archive with unchanged seed verifier | Publication or pre-listener readiness gate fails according to the credential policy. |
| Delta after archive baseline | Manifest order and checksum, aggregate effects, counters, and projection convergence pass before database-ready. |

## Rejected Alternatives

### Enrich snapshot events with original transaction IDs

The snapshot excludes canonical event and outbox history, and converted events
do not map one-to-one to historical events. Any inferred ID would be false.

### Run the Java JAR outside a container

This removes container startup and image-mount overhead but retains one commit
per event. It remains a useful development option, not the primary solution.

### Select Rust solely for speed

The current Rust path does not yet preserve singleton logical transaction,
guarded bootstrap, and projection semantics. Language selection cannot replace
parity.

### Arbitrary `--batch-size N` as one transaction

This invents business transaction membership from file adjacency and merges
unrelated failures into one DLQ/replay group. Chunk size may control physical
commits only.

### Parallel event workers

This introduces ordering, nonce, offset, aggregate, and graph races before the
measured serial bottlenecks and archive path are exhausted.

### One transaction ID for the entire file

This creates one false logical failure domain and changes replay semantics even
if the database write is fast.

### One physical transaction for the entire file

Even with singleton logical IDs, this creates excessive rollback scope, delayed
visibility, large lock and WAL pressure, and poor failure diagnostics.

### Reserve nonce or offset ranges in a separate transaction

This makes counter state visible before canonical/outbox rows. In particular,
the database consumer claims through `log_counter.next_offset - 1` and advances
its cursor to that tip. A separately committed range could therefore make it
skip uncommitted rows permanently. Any future set-based reservation remains on
the same physical connection and transaction as the rows it reserves.

### Direct `COPY` into canonical tables

Raw `COPY` is fast but bypasses append validation, policy selection, graph
stamping, nonce allocation, recovery projection markers, notification behavior,
and identity materialization. It is not a valid bootstrap import path.

### Preserve only a PostgreSQL physical volume

Physical storage snapshots are too tightly coupled for the initial public
installation artifact. The portable archive is slower than a physical copy but
has an explicit compatibility and verification contract.

### Assume a storage tuning lever without measurement

Transaction-local `synchronous_commit=off`, WAL/checkpoint tuning, deferred
projection indexes, and temporary unlogged projections may be useful on an
empty disposable destination, but each changes a different cost and some add a
rewrite or recovery penalty. P0 measures them independently. None may bypass
the canonical append path or remain active after the readiness gate.

## Open Questions

1. Which validator read-model dependencies, beyond graph-root resolution, need
   an initial barrier-registry entry?
2. Which operational tables and cursors are normalized versus retained in the
   bootstrap archive?
3. Do the P0 graph-barrier count, mean wait, p95 wait, and total barrier share
   show that adaptive polling meets the target, or do they justify a dedicated
   projection-advance notification channel?
4. After Java qualification, is Rust replacement still valuable, or is the
   release-built archive sufficient for installation performance?
