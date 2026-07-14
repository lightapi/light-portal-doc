# Event Replay

## Status and Motivation

The portal has two projection processors:

- `DbEventConsumerStartupHook` reads `outbox_message_t` directly, tracks progress
  in `consumer_offsets`, and stores failed transactions in the PostgreSQL
  `dead_letter_queue` table.
- `PortalEventConsumerStartupHook` in `user-query` reads Debezium-published
  Kafka records, commits Kafka consumer offsets, and publishes failed
  transactions to the configured Kafka DLQ topic.

Both processors group events by the command-side `transaction_id`, use JDBC
savepoints to isolate a failed transaction, and ultimately call
`PortalDbProvider.handleEvent(conn, event)`. Both also advance past a failed
transaction after it has been sent to their DLQ. This keeps the live consumer
available, but there is no supported way to put a repaired transaction back
through the projection path.

The present operational workarounds are unsafe:

- rewinding a database or Kafka consumer offset also reprocesses unrelated
  transactions in the same partition;
- replaying one DLQ row can split a multi-event business transaction;
- republishing a Kafka DLQ record to the original topic changes ordering and
  may lose the original `transaction_id` and other headers;
- setting a projection revision manually can mark events as projected when
  their projection transaction actually rolled back;
- rebuilding code does not revisit offsets that the consumer already
  committed.

A concrete example is an instance graph whose accepted revisions reached 18
while its projected revision remained 0. Selecting only revision 18 cannot
succeed: revisions 1 through 17 form a mandatory dependency closure and every
multi-event transaction in that closure must remain atomic.

This design adds a transport-neutral replay control plane. The original live
processors still consume from PostgreSQL or Kafka, but failure capture,
planning, execution, status, authorization, and audit use one shared contract.

## Goals

- Replay a failed business transaction without rewinding a shared consumer
  offset.
- Preserve the original transaction boundary and event order.
- Support both the PostgreSQL and Kafka event processors with the same replay
  semantics.
- Detect and include prerequisite transactions, especially contiguous instance
  graph revisions.
- Execute replay through exactly the same projection logic as live processing.
- Keep an immutable record of the original failure and every replay attempt.
- Prevent concurrent live processing from racing with replay.
- Isolate ordered replay to proven dependency scopes so unrelated tenants and
  aggregates continue projecting.
- Provide plan, approval, execution, status, and cancellation operations for an
  admin UI.
- Preserve payload confidentiality and avoid placing sensitive values in logs,
  lists, metrics, or approval screens.
- Make execution crash-safe and idempotent.
- Bound archive and publication-outbox growth during a failure storm without
  discarding the only replayable payload.

## Non-Goals

- Replay is not an event editor. Operators cannot change an event payload,
  event ID, aggregate version, graph revision, or transaction ID.
- Replay does not replace event import, promotion, snapshot restore, or a full
  projection rebuild.
- Replay does not make non-idempotent projection handlers safe automatically.
- Replay does not provide arbitrary topic browsing or a general Kafka
  administration console.
- Replay does not delete DLQ history automatically.
- The first version does not replay successful historical transactions merely
  to reconstruct an empty projection database. That remains a separate rebuild
  workflow.

## Current Processing Contracts

| Concern | PostgreSQL processor | Kafka processor |
| --- | --- | --- |
| Live source | `outbox_message_t` | Debezium-derived Kafka topic |
| Transaction identity | `outbox_message_t.transaction_id` | `transaction_id` Kafka header, with legacy key fallback |
| Source position | logical partition plus `c_offset` | Kafka topic, partition, and offset |
| Failure destination | `dead_letter_queue` | `{topic}{deadLetterTopicExt}` |
| Progress | `consumer_offsets` | Kafka consumer-group offsets |
| Projection dispatch | `PortalDbProvider.handleEvent` | `PortalDbProvider.handleEvent` |
| Failure isolation | JDBC savepoint | JDBC savepoint |
| Current replay | manual offset rewind | external re-driver suggested, but not implemented |

There are important gaps to close before replay can be safe:

1. The database consumer's graph-revision and clone-outcome completion logic is
   private to `DbEventConsumerStartupHook`. The Kafka path calls
   `handleEvent(...)` but does not share that completion boundary.
2. The Kafka DLQ producer copies the key and value but does not preserve the
   original record headers or source coordinates in the replayed record.
3. Kafka DLQ publication is asynchronous, while fallback processing can commit
   the source offsets without a durable replay record proving that publication
   succeeded.
4. `notification_t` shows the latest processing result but is not a durable
   replay ledger and must not be used as one.
5. A DLQ contains events, while correctness usually requires selecting whole
   transactions and sometimes an ordered chain of transactions.

## Design Principles

### Transaction is the minimum replay unit

The UI and API may start from one failed event, but the planner immediately
expands that selection to its complete original transaction. Execution never
applies an individual event from a multi-event transaction.

### Plan before execute

Replay has two distinct phases:

1. **Plan** resolves complete transactions, dependency closure, ordering,
   handler compatibility, payload availability, limits, and impact.
2. **Execute** applies the immutable plan only if its fingerprints and
   projection preconditions still match.

The plan has a digest and an expiry. Approval binds to that digest so an
approved plan cannot silently gain more events later.

### Replay projection state, not transport offsets

The replay worker reads a durable failure archive and calls the shared
projection transaction executor directly. It does not seek the live database
consumer, alter Kafka consumer-group offsets, or republish records to the
original live topic.

### Keep original failures immutable

A successful replay resolves a failure but does not erase it. Failure rows,
payload digests, errors, source positions, approvals, and attempt results remain
available for audit and incident analysis.

### Fail closed on uncertainty

Missing transaction members, revision gaps, payload hash mismatches, unsupported
event types, stale plans, and an incomplete barrier or fallback pause all block
replay.
An operator can waive a failure from further action, but a waiver is not a
successful replay and does not advance projection metadata.

### Use scoped barriers before pausing a projection

The planner installs a `GRAPH_ROOT` or `AGGREGATE_VERSION` barrier when every
event in the plan has a proven dependency scope. Live transactions for other
scopes continue normally. Partition-level or projection-level pause is a
fallback for transactions whose isolation cannot be proven, not the default
replay mechanism.

### Leases provide liveness; database locks provide correctness

A lease lets another worker recover abandoned work, but lease expiry alone
never authorizes concurrent execution. Item row locks, monotonic fencing tokens,
and dependency-scope advisory locks prevent two workers from applying the same
transaction at once, including when one transaction legitimately runs longer
than its lease interval.

## Chosen Architecture

```text
                         shared PostgreSQL control plane
                       +-------------------------------+
DB outbox consumer --->| durable failure archive       |
Kafka consumer -------->| replay plans and attempts     |
                       | replay barriers and fencing   |
                       | Kafka DLQ publication outbox  |
                       +---------------+---------------+
                                       |
                              approved immutable plan
                                       |
                                       v
                         +-----------------------------+
                         | projection replay worker    |
                         | shared transaction executor |
                         +--------------+--------------+
                                        |
                                        v
                              projection tables and
                              projection metadata

Kafka failure publication:

failure archive -> failure publication outbox -> Kafka DLQ topic
```

The control plane lives in the projection database because both processors
already require that database to apply events. The Kafka DLQ topic remains a
useful external forensic stream, but it is no longer the only durable recovery
source.

The architecture has four shared components:

1. `ProjectionTransactionExecutor` applies one ordered business transaction.
2. `ProjectionFailureRepository` records an immutable transaction envelope
   after projection rollback.
3. `EventReplayPlanner` creates and validates dependency-complete plans.
4. `EventReplayWorker` installs the approved isolation barrier, claims plan
   items with fencing, and invokes the common executor.

Transport adapters supply source metadata but do not implement separate replay
semantics.

## Shared Projection Transaction Executor

Move the transaction-level projection behavior out of both startup hooks into
`light-portal` `db-provider`:

```java
ProjectionResult execute(
    Connection connection,
    ProjectionTransaction transaction,
    ProjectionExecutionMode mode
) throws Exception;
```

`ProjectionExecutionMode` is `LIVE` or `REPLAY`; it may alter telemetry and
audit fields, but it must not select a different projection handler.

The executor owns this sequence:

1. validate the transaction envelope and ordered event count;
2. call `PortalDbProvider.handleEvent(conn, event)` for every event;
3. run graph-revision completion for every `rootinstanceid` in the transaction;
4. update clone outcome state when `clonerequestid` is present;
5. return event-level notification outcomes;
6. leave commit or rollback to the caller.

This extraction makes live PostgreSQL processing, live Kafka processing, and
replay use the same graph-continuity and transaction-completion contract. The
Kafka processor must adopt the executor before Kafka replay is enabled.

Phase 2 implements this boundary in
`light-portal/db-provider/src/main/java/net/lightapi/portal/db/projection/`.
Both live startup hooks now construct the shared models and invoke the same
executor in batch and savepoint fallback paths. Notification result writes use
the caller's projection connection, and the former database-only graph/clone
completion methods no longer exist. All replay feature gates remain disabled.

The executor accepts replay metadata out of band. It never injects replay
fields into the original CloudEvent payload because changing the payload would
change its digest and could alter handler behavior.

## Canonical Failure Envelope

Both processors persist the same logical transaction envelope. Required
transaction fields are:

- envelope version, initially `portal-event-replay-v1`;
- `hostId`;
- projection name and consumer group;
- first observed source processor: `DB` or `KAFKA`, with every delivery stored
  separately;
- original `transactionId`;
- ordered event count;
- content fingerprint and delivery fingerprint;
- first failure timestamp and most recent failure timestamp;
- bounded error type, code, and message;
- extracted dependency scopes;
- current lifecycle status.

Each event member contains:

- ordinal within the original transaction;
- original CloudEvent ID and type;
- aggregate ID, aggregate type, and aggregate version when present;
- `rootinstanceid`, `instancegraphrevision`, and `clonerequestid` when present;
- original source coordinates;
- original key and headers for Kafka;
- payload format and payload digest;
- encrypted original payload;
- sensitivity marker.

The design deliberately uses two fingerprints:

- `content_fingerprint` is a SHA-256 digest over the projection name, consumer
  group, original transaction ID, ordered event IDs, and ordered payload
  digests. It excludes transport coordinates and identifies the logical
  transaction that can be replayed.
- `delivery_fingerprint` adds processor type and source coordinates. It
  identifies one database or Kafka delivery of that logical transaction.

The same event IDs and payloads delivered again at new offsets therefore add a
delivery observation to one failure candidate instead of creating a second
replay candidate. If an upstream retry generates new event IDs, the system may
flag a possible semantic duplicate using aggregate identities and versions, but
it does not merge or suppress it automatically.

Phase 3 implements these dormant primitives in
`light-portal/db-provider/src/main/java/net/lightapi/portal/db/replay/`.
`FailureEnvelopeFactory` uses a versioned length-delimited encoding rather than
map iteration order. `ReplayPayloadCipher` provides authenticated envelope
encryption and key rotation, while `JdbcProjectionFailureRepository` provides
connection-aware idempotent persistence and advisory-lock-fenced capacity
accounting. The Phase 3 retention migration permits only a one-way payload
transition to `DELETED`; immutable event/source metadata and payload digests
remain. Phase 4 integrates these primitives into the PostgreSQL granular
fallback behind `captureEnabled`: canonical rows, legacy DLQ rows,
connection-aware notifications, clone failure state, and claimed progress
commit together. Database delivery evidence includes the projection group,
logical partition, `c_offset`, and original transaction ID. A capture/key/quota
failure rolls back source progress. The Kafka processor remains unchanged until
its Phase 5 integration gate passes.

The event ordinal is assigned from the authoritative source order:

- database events sort by `c_offset`;
- Kafka events sort by topic, partition, and offset only after the planner has
  verified that the records carry one transaction identity. A transaction that
  spans Kafka partitions without an explicit event ordinal is blocked because
  Kafka does not define cross-partition order.

## Persistence Model

The following tables are the intended logical model. Column sizes and indexes
should follow the portal database conventions when the migration is written.
Phase 1 implements this model in
`portal-db/postgres/patch_20260713_event_replay.sql`, with the same replay block
in both fresh-install DDL sources. The implementation adds the envelope-key,
object-version, byte-accounting, fencing, retention, and trigger columns needed
to enforce the invariants described below.

### `event_failure_transaction_t`

One immutable failure identity per logical transaction content fingerprint:

```sql
CREATE TABLE event_failure_transaction_t (
    host_id                  UUID NOT NULL,
    failure_id               UUID NOT NULL,
    projection_name          VARCHAR(128) NOT NULL,
    consumer_group           VARCHAR(255) NOT NULL,
    first_source_processor   VARCHAR(16) NOT NULL,
    original_transaction_id  VARCHAR(255) NOT NULL,
    content_fingerprint      VARCHAR(64) NOT NULL,
    event_count              INTEGER NOT NULL,
    encrypted_payload_bytes  BIGINT NOT NULL DEFAULT 0,
    decrypted_payload_bytes  BIGINT NOT NULL DEFAULT 0,
    dependency_scopes        JSONB NOT NULL DEFAULT '[]'::jsonb,
    status                   VARCHAR(16) NOT NULL,
    error_type               VARCHAR(255),
    error_code               VARCHAR(128),
    error_message            VARCHAR(2048),
    failure_count            INTEGER NOT NULL DEFAULT 1,
    first_failed_ts          TIMESTAMPTZ NOT NULL,
    last_failed_ts           TIMESTAMPTZ NOT NULL,
    resolved_ts              TIMESTAMPTZ,
    resolved_by_request_id   UUID,
    created_ts               TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_ts               TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (host_id, failure_id),
    UNIQUE (host_id, projection_name, consumer_group, content_fingerprint),
    CHECK (status IN ('OPEN', 'RESOLVED', 'WAIVED'))
);
```

`WAIVED` means an operator deliberately chose not to replay one explicitly
identified failure transaction. It does not imply that projection state
includes the events, does not advance graph or aggregate versions, and does not
waive downstream transactions automatically. If a waived transaction is a
required dependency, downstream plans remain blocked. A bulk waiver must list
every transaction explicitly, show the dependency impact, and follow the same
approval policy as replay.

### `event_failure_delivery_t`

One row records each observed delivery of a logical failure. It stores the
`delivery_fingerprint`, processor type, database or Kafka source coordinates,
first and last observation times, and observation count. This preserves
transport evidence without making offsets part of replay identity.

### `event_failure_event_t`

One row per ordered event member:

```sql
CREATE TABLE event_failure_event_t (
    host_id             UUID NOT NULL,
    failure_id          UUID NOT NULL,
    event_ordinal       INTEGER NOT NULL,
    event_id            VARCHAR(255) NOT NULL,
    event_type          VARCHAR(255) NOT NULL,
    aggregate_id        VARCHAR(255),
    aggregate_type      VARCHAR(255),
    aggregate_version   BIGINT,
    root_instance_id    UUID,
    graph_revision      BIGINT,
    clone_request_id    UUID,
    source_processor    VARCHAR(16) NOT NULL,
    source_topic        VARCHAR(255),
    source_partition    INTEGER,
    source_offset       BIGINT,
    source_key          BYTEA,
    source_headers      JSONB NOT NULL DEFAULT '[]'::jsonb,
    payload_format      VARCHAR(32) NOT NULL,
    payload_digest      VARCHAR(64) NOT NULL,
    payload_storage     VARCHAR(16) NOT NULL,
    payload_ciphertext  BYTEA,
    payload_object_uri  VARCHAR(2048),
    payload_object_version VARCHAR(255),
    payload_key_id      VARCHAR(255) NOT NULL,
    payload_wrapped_key BYTEA NOT NULL,
    payload_iv          BYTEA NOT NULL,
    encrypted_payload_bytes BIGINT NOT NULL,
    decrypted_payload_bytes BIGINT NOT NULL,
    sensitive_payload   BOOLEAN NOT NULL DEFAULT FALSE,
    PRIMARY KEY (host_id, failure_id, event_ordinal),
    FOREIGN KEY (host_id, failure_id)
      REFERENCES event_failure_transaction_t(host_id, failure_id)
      ON DELETE RESTRICT,
    CHECK (
      (payload_storage = 'DATABASE' AND payload_ciphertext IS NOT NULL
        AND payload_object_uri IS NULL)
      OR
      (payload_storage = 'OBJECT' AND payload_ciphertext IS NULL
        AND payload_object_uri IS NOT NULL)
    )
);
```

`source_offset` is `outbox_message_t.c_offset` for the database processor and a
Kafka offset for the Kafka processor. `source_topic` is null for the database
processor. These columns preserve the first observed delivery coordinates for
the event member; subsequent delivery observations belong in
`event_failure_delivery_t`. Full payloads use application-level envelope
encryption. Small payloads may remain inline; a configured immutable object
store holds large payloads or absorbs a failure storm. The object URI is an
opaque server-side locator, never a caller-supplied URL. List and plan queries
read only the extracted metadata unless the caller has a separate
sensitive-diagnostic permission.

### Replay control tables

`event_replay_request_t` stores one immutable plan and its workflow state:

- request ID, host, projection, and consumer group;
- requested strategy and operator reason;
- plan hash and expiry;
- status;
- event, transaction, and byte counts;
- requested, approved, started, and completed identities and timestamps;
- failure code and bounded failure message;
- monotonic fencing token;
- isolation mode and installed barrier epoch.

Statuses are:

```text
PLANNING -> READY -> AWAITING_APPROVAL -> APPROVED
         -> INSTALLING_BARRIER -> RUNNING -> SUCCEEDED
                                        \-> FAILED
READY/AWAITING_APPROVAL/APPROVED -> CANCELLED
READY/AWAITING_APPROVAL -> EXPIRED
```

`event_replay_item_t` maps the request to ordered failure transactions and
stores the expected content fingerprint, dependency reason, item status,
attempt count, and current fencing token. Its statuses are `PENDING`, `RUNNING`,
`SUCCEEDED`, and `FAILED`.

`event_replay_attempt_t` is append-only. It stores the request, item, attempt
number, worker identity, start/completion times, result, pre- and
post-projection metadata, and bounded error. A crash may leave an attempt
`RUNNING`; lease recovery changes it to `ABANDONED` before another attempt.

`event_replay_lease_t` stores lease owner, lease epoch, heartbeat, and expiry on
a row separate from the immutable request/fence row. This lets a control
connection renew liveness while a long projection transaction holds the
request fence row.

### Replay barriers and pause fallback

`event_replay_barrier_t` stores an active barrier epoch for one of these scope
types:

```text
GRAPH_ROOT | AGGREGATE | HOST | DB_PARTITION | KAFKA_PARTITION | PROJECTION
```

The row also stores a lifecycle state (`INSTALLING`, `ACTIVE`, `DRAINING`, or
`QUARANTINED`), owner type (`REPLAY_REQUEST` or `FAILURE_QUARANTINE`), owner ID,
and the failure ID that caused quarantine when present. Barrier ownership and
state changes are fenced and audited; they are not inferred from a worker
lease.

`GRAPH_ROOT` and `AGGREGATE` are the preferred modes. The planner may choose
them only when every event in the plan has a registered, deterministic scope
extractor. A transaction touching several scopes acquires all scope locks in
canonical order and is deferred as a whole if any scope is blocked.

Live and replay workers use the same transaction-scoped PostgreSQL advisory
lock for each dependency scope. Barrier installation acquires that lock, waits
for any current transaction to finish, inserts the barrier with a new epoch,
and commits. Every subsequent live transaction acquires the scope lock and
checks the barrier before calling `ProjectionTransactionExecutor`.

If a live transaction intersects an active barrier, the processor writes its
complete immutable envelope to `event_projection_deferred_t` and advances its
normal source position. Disjoint transactions continue projecting. After the
approved repair transactions succeed, the replay worker drains deferred
transactions in original source order through the common executor before it
removes the barrier. Deferred transactions are already-authorized live work and
do not alter the approved repair plan; their counts and bytes are nevertheless
shown in status and bounded by separate limits.

Deferred payloads use the same encryption, content digest, inline/object-store
policy, and capacity circuit breaker as failure payloads, but they are not
labeled as DLQ failures. If a deferred envelope cannot be persisted durably,
the processor does not advance the database or Kafka source position.

This is the replay equivalent of shedding only the affected dependency scope.
It prevents one tenant's graph repair from pausing unrelated hosts and
aggregates.

If the planner cannot prove a complete scope, it falls back in this order:

1. pause the affected database logical partition or Kafka `TopicPartition`;
2. pause the host when all affected traffic is host-isolated;
3. pause the complete projection only for an explicitly approved, bounded
   maintenance operation.

`event_projection_control_t` and `event_projection_worker_t` coordinate these
fallback pauses by epoch. Only workers assigned to the affected partition or
projection must acknowledge. Kafka workers continue heartbeats while paused so
they retain their assignment. There is no unsafe force-acknowledge operation:
an unresponsive worker must lose its assignment, finish or roll back its
database transaction, or be terminated before replay can proceed.

The plan and UI state the selected isolation mode and its blast radius. A
projection-wide pause is always a high-impact warning and requires two-person
approval in production.

### Claiming, leases, and fencing

Workers claim requests with a compare-and-set that increments a monotonic
fencing token and creates or replaces the separate lease row. A control
connection renews that lease during a long-running item. Lease expiry indicates
that recovery may be needed; it does not by itself make the item concurrently
executable.

For each transaction, the worker opens the projection transaction, locks the
request fence row, and claims the item with `SELECT ... FOR UPDATE SKIP LOCKED`.
It keeps both row locks until the projection writes, replay attempt, graph
completion, and item outcome commit together. It also checks the request
fencing token and acquires the dependency-scope advisory locks. A second worker
skips the locked item even if the lease timestamp has expired. Recovery can
increment the request fence and claim the item only after the first database
transaction commits or rolls back.

The worker checks its fence before invoking the executor and again before
commit. Losing the fence causes rollback with `LEASE_LOST`. Lease heartbeat is
therefore a liveness optimization; row locks, fencing, and advisory locks are
the correctness boundary.

### Kafka DLQ publication outbox

`event_failure_publish_outbox_t` records that a canonical failure transaction
must be published to the Kafka DLQ topic. The Kafka processor inserts this row
in the same database transaction as the canonical failure archive. A separate
publisher follows the bounded retry policy until Kafka acknowledges the
complete transaction envelope or the row becomes `TERMINAL_FAILED`.

The outbox row references `failure_id`; it does not duplicate the encrypted
payload. Its states are `PENDING`, `RETRY_WAIT`, `PUBLISHED`, and
`TERMINAL_FAILED`, with attempt count, next-attempt time, first/last error time,
and bounded error code. Retries use exponential backoff with jitter. Exceeding
the configured attempt or age limit moves the row to `TERMINAL_FAILED`, raises
an alert, and stops automatic publication until an operator explicitly retries
or waives external DLQ delivery. It never deletes the canonical failure.
The publication identity (`host_id`, `publication_id`, `failure_id`, envelope
version, target topic, and creation timestamp) is immutable after insertion;
only retry and outcome fields may change.

Published outbox rows are deleted after a short audit retention period.
Terminal rows retain metadata for a bounded diagnostic period, then copy their
final outcome into the append-only replay audit record and are deleted from the
active outbox even if external DLQ delivery was waived. The canonical failure
still records that external publication never succeeded. Backlog count, age,
and table bytes have warning and hard thresholds so an unavailable Kafka
cluster cannot grow the active outbox without bound.

The original Kafka consumer offset may be committed after the failure archive
and publication-outbox transaction commits. It must not depend on an
unobserved asynchronous produce future. Kafka DLQ publication failure therefore
cannot lose the replay source.

## Failure Capture

### PostgreSQL processor

After `ProjectionTransactionExecutor` throws:

1. roll back to the transaction savepoint;
2. build the canonical envelope from the complete `EventData` list;
3. insert or observe the failure transaction and all members;
4. update notification status to `DLQ`;
5. commit the failure archive and claimed progress together;
6. continue with the next independent transaction.

The existing `dead_letter_queue` can remain as a compatibility sink during
migration. New replay uses the canonical failure tables. Once backfill and
operational tooling are complete, the old table can become a compatibility
view or be retired under a separate migration.

### Kafka processor

After projection rollback:

1. preserve the complete transaction's original key, value, headers, topic,
   partition, and offset;
2. insert the canonical failure transaction and publication-outbox row;
3. commit that database transaction;
4. commit source Kafka offsets only after step 3 succeeds;
5. let the failure publisher send a transaction envelope to the Kafka DLQ and
   retry independently until acknowledged.

If canonical failure persistence fails, the Kafka source offset is not
committed, so Kafka redelivers the original records. The fingerprint makes
failure capture idempotent.

The new Kafka DLQ envelope must retain:

- envelope version `portal-event-replay-v1`;
- original transaction ID;
- ordered event count and ordinal;
- original topic, partition, and offset;
- original key and headers;
- original value and payload digest;
- failure ID, error code, and failure timestamp;
- replay generation, initially zero.

Deploy the versioned envelope on a new topic or behind an explicit consumer
compatibility gate. Existing consumers of the legacy per-event DLQ shape must
not receive a transaction envelope without an advertised migration.

Legacy DLQ records without transaction headers or source coordinates are not
silently guessed into a multi-event transaction. A migration tool may correlate
them with `notification_t`, `event_store_t`, or `outbox_message_t`; unresolved
records remain `PAYLOAD_UNAVAILABLE` or `TRANSACTION_INCOMPLETE` candidates.

Replay execution does not publish a new Kafka DLQ envelope when the handler
fails again. It appends a failed attempt to the same canonical failure and stops
the ordered plan. `replayGeneration` is diagnostic lineage for externally
imported or future re-drive workflows, not an automatic feedback loop. The
initial implementation allows generation zero only and enforces a bounded
attempt count per failure. Another attempt requires a new or explicitly retried
approved plan, so a poison event cannot cycle indefinitely between replay and
the Kafka DLQ.

## Replay Planning

### Selection

The public selector accepts failure transaction IDs, not arbitrary event IDs.
If the user starts from a notification row, the server resolves its host,
consumer group, and transaction ID and returns the corresponding failure
transaction.

There is intentionally no unbounded **Replay All DLQ** operation. Bulk replay
requires explicit filters, result limits, and a generated plan.

Supported selection strategies are:

- `EXACT`: replay only the selected complete transactions when no earlier
  dependency is missing;
- `DEPENDENCY_CLOSURE`: add prerequisite failed transactions automatically.

Validation modes are orthogonal to the selection strategy:

- `VALIDATE_ONLY`: perform static planning and diagnostics but make the plan
  non-executable;
- `ROLLBACK_DRY_RUN`: optionally execute a statically valid plan inside
  rollback-only database transactions when every handler is registered as
  dry-run safe.

### Dependency closure

The planner extracts scopes from every event and delegates ordering to a replay
policy registry.

Initial policies are:

| Policy | Ordering and validation |
| --- | --- |
| `GRAPH_ROOT` | Group by `(host_id, rootinstanceid)`. Read accepted/projected revision state and include every failed transaction from `projected_revision + 1` through the selected highest revision. Reject any gap. |
| `AGGREGATE_VERSION` | Group by host, aggregate type, and aggregate ID. Use the registered projection-version resolver and include missing failed versions in ascending order. |
| `TRANSACTION_ONLY` | Replay the exact transaction only after proving that no registered ordering metadata requires an earlier transaction. |
| `NOT_REPLAYABLE` | Reject the plan and require data repair, migration, or a full rebuild. |

All members of one transaction must agree on compatible ordering. A
transaction touching multiple scopes is one node in a dependency graph. The
planner performs a deterministic topological sort and rejects cycles or
ambiguous order.

For `GRAPH_ROOT`, selecting revision 18 while the projection is at revision 0
adds revisions 1 through 17. Two rows carrying revision 2 and the same
transaction ID remain one replay item, not two.

### Replay policy registry

Every handled event type declares:

- replay policy;
- supported payload/schema versions;
- dependency extractor;
- projection-version resolver when required;
- whether the handler is idempotent under the original event ID and aggregate
  version;
- sensitivity classification;
- optional shared compatibility upgrader;
- maximum transaction and payload limits.

An event type absent from the registry is blocked even if it exists in the
large `handleEvent` dispatch switch. This makes replay support explicit and
testable.

A compatibility upgrader is disabled by default and must not be replay-only
business logic. It must be the same versioned, deterministic, side-effect-free
compatibility layer that live processing would use for the same historical
schema. The archived original never changes. The plan records the signed
upgrader artifact, registry version, original digest, and effective digest, and
approval binds to all four values.

Plans using an upgrader require `ROLLBACK_DRY_RUN` or a shadow-environment
rehearsal plus two-person approval. An upgrader cannot change event identity,
transaction identity, aggregate version, graph revision, or dependency scope.
Its tests include fixed input/output vectors and parity between live and replay
modes. If those constraints cannot be met, the handler must gain native
backward compatibility or the incident must use a migration/rebuild workflow.

### Validation modes

`VALIDATE_ONLY` is intentionally a static operation. It verifies transaction
completeness, dependency closure, ordering, fingerprints, payload availability,
handler and schema support, limits, authorization, and the proposed isolation
scope. It does not claim that projection SQL will commit successfully.

`ROLLBACK_DRY_RUN` is a separate, explicit mode. After installing the same
scoped barrier required for execution, it invokes
`ProjectionTransactionExecutor` in a database transaction and always rolls it
back. It is allowed only when every involved handler and database routine is
registered as database-only and dry-run safe. The result warns that sequences,
non-transactional extensions, external calls, and commit-time behavior cannot
be proven by rollback. Handlers with external side effects are ineligible.

A shadow database rehearsal is the strongest validation for large or upgraded
plans. It records the source snapshot/revision and resulting digests but remains
a rehearsal; production execution still rechecks all plan preconditions.

### Plan preconditions

The plan records:

- failure content fingerprints as execution preconditions and observed
  delivery fingerprints for audit only;
- current projection metadata for every scope;
- accepted/projected graph revisions when applicable;
- source high-water marks;
- handler registry version;
- compatibility-upgrader artifact and registry versions;
- transaction, event, and decrypted-byte counts;
- added dependency transactions and the reason each was added;
- required barrier or fallback pause scope and estimated operational impact;
- plan expiry.

Execution fails with `STALE_PLAN` if any material precondition changes before
the isolation barrier or fallback pause is established. The caller must
generate and approve a new plan.

## Approval and Authorization

Replay is host-scoped operational mutation, not a normal user retry.

- `admin` and `host-admin` may list and plan failures within their authorized
  host.
- Execution requires a dedicated replay permission in addition to the normal
  portal write group.
- Production can require approval by a second administrator who is not the
  requester.
- The reason is mandatory and retained in the audit record.
- Large plans, sensitive events, partition/host/projection-wide impact,
  compatibility upgrades, and `NOT_REPLAYABLE` overrides always require
  two-person approval.
- No API response exposes encrypted payloads by default.

Replay control operations write operational tables directly. They must not emit
ordinary portal domain events into the same projection stream, because a broken
projection must not be required to authorize or schedule its own repair. Audit
records are written through the separate audit path.

## API Contract

The implementation remains in the existing `user-command` and `user-query`
services, next to the notification operations. The service IDs intentionally
remain under `lightapi.net/user/...`; introducing a separate admin or operations
service solely for replay would add deployment and routing overhead without
creating a stronger security boundary. Dedicated endpoint permissions,
host-scoped authorization, approval separation, and audit provide the privilege
boundary.

| Operation | Type | Proposed service ID |
| --- | --- | --- |
| List replay candidates | Query | `lightapi.net/user/listEventReplayCandidate/0.1.0` |
| Get failure transaction | Query | `lightapi.net/user/getEventReplayFailure/0.1.0` |
| Create immutable plan | Command | `lightapi.net/user/createEventReplayPlan/0.1.0` |
| Get plan/status | Query | `lightapi.net/user/getEventReplay/0.1.0` |
| Approve plan | Command | `lightapi.net/user/approveEventReplay/0.1.0` |
| Execute approved plan | Command | `lightapi.net/user/executeEventReplay/0.1.0` |
| Cancel before execution | Command | `lightapi.net/user/cancelEventReplay/0.1.0` |
| Waive explicit failure transactions | Command | `lightapi.net/user/waiveEventReplayFailure/0.1.0` |
| Break-glass barrier release | Command | `lightapi.net/user/releaseEventReplayBarrier/0.1.0` |

Example planning request:

```json
{
  "hostId": "01964b05-552a-7c4b-9184-6857e7f3dc5f",
  "projectionName": "portal-query",
  "consumerGroup": "user-query-group",
  "failureIds": [
    "019f6000-0000-7000-8000-000000000018"
  ],
  "strategy": "DEPENDENCY_CLOSURE",
  "validationMode": "VALIDATE_ONLY",
  "reason": "Recover missing instance API projection after metadata parser fix"
}
```

Example plan response:

```json
{
  "replayRequestId": "019f6001-0000-7000-8000-000000000001",
  "status": "AWAITING_APPROVAL",
  "planHash": "sha256:...",
  "selectedTransactionCount": 1,
  "addedDependencyTransactionCount": 17,
  "eventCount": 27,
  "strategy": "DEPENDENCY_CLOSURE",
  "validationMode": "VALIDATE_ONLY",
  "isolationScope": {
    "mode": "GRAPH_ROOT",
    "projectionName": "portal-query",
    "consumerGroup": "user-query-group",
    "rootInstanceIds": [
      "019d2a45-4eb7-7e20-a6b6-9cc3261e89a1"
    ]
  },
  "warnings": [
    {
      "code": "DEPENDENCY_CLOSURE_EXPANDED",
      "message": "Graph revisions 1 through 17 were added before selected revision 18"
    }
  ],
  "expiresAt": "2026-07-13T18:00:00Z"
}
```

Approval and execution both require `replayRequestId` and `planHash`. This is an
optimistic-concurrency check over the complete plan.

`waiveEventReplayFailure` names every failure transaction explicitly, shows the
dependency impact, requires a reason and applicable approval, and uses an
expected current status to prevent a stale operator decision. A waiver does not
advance projection metadata, does not waive downstream failures automatically,
and leaves a downstream plan blocked when it requires the waived transaction.
Bulk waiver is only syntactic convenience over the same explicit per-failure
semantics; it is never a dependency-cascade operation.

`releaseEventReplayBarrier` is not part of normal replay completion. It requires
the barrier ID, expected epoch, owning failure ID, `RELEASE_WITH_GAP` reason,
dedicated break-glass permission, and two-person approval in production. It
does not resolve or waive the failure, advance projection metadata, or claim
that the affected scope is consistent.

Public failure codes include:

- `TRANSACTION_INCOMPLETE`;
- `REPLAY_GAP`;
- `PAYLOAD_UNAVAILABLE`;
- `PAYLOAD_DIGEST_MISMATCH`;
- `UNSUPPORTED_EVENT_TYPE`;
- `UNSUPPORTED_PAYLOAD_VERSION`;
- `STALE_PLAN`;
- `LEASE_LOST`;
- `PAUSE_TIMEOUT`;
- `ARCHIVE_CAPACITY_EXCEEDED`;
- `FAILURE_PUBLICATION_TERMINAL`;
- `REPLAY_LIMIT_EXCEEDED`;
- `PROJECTION_FAILED`;
- `DEFERRED_PROJECTION_FAILED`;
- `AUTHORIZATION_DENIED`.

## Execution Flow

1. The execute command atomically changes an approved request to
   `INSTALLING_BARRIER`.
2. The coordinator acquires the canonical dependency-scope advisory locks and
   installs the planned barrier epoch. If scoped isolation is unavailable, it
   requests the approved partition, host, or projection pause and waits only
   for the affected workers to acknowledge.
3. The coordinator rechecks the plan hash, content fingerprints, payload
   digests, registry version, projection metadata, and isolation epoch, then
   changes the request to `RUNNING`.
4. The replay worker claims the request with a compare-and-set that increments
   its fencing token and starts lease heartbeat on a separate control
   connection.
5. For each item in plan order, the worker opens a database transaction, locks
   the request fence row and item row, verifies its fencing token, and acquires
   deterministic advisory locks for all dependency scopes.
6. The worker invokes `ProjectionTransactionExecutor` in `REPLAY` mode.
7. The item result, replay attempt, projection writes, graph-revision
   completion, and failure resolution commit atomically with a final fencing
   check.
8. On success, the next repair transaction begins. Transaction boundaries are
   never split to meet a batch limit.
9. After repair items succeed, the worker drains live transactions deferred by
   the barrier in original source order using `LIVE` mode. If a deferred
   transaction fails, its projection transaction rolls back and one database
   transaction records the canonical failure, marks that deferred item failed,
   changes the request to `FAILED` with `DEFERRED_PROJECTION_FAILED`, and
   transfers the barrier to `FAILURE_QUARANTINE` ownership.
10. When repair and deferred work are complete, the request becomes
    `SUCCEEDED`, the barrier or fallback pause is removed, and normal processing
    continues without rewinding live source positions.

Replay execution is at-least-once. If a worker crashes after a database commit
but before acknowledging its lease, the next worker recognizes the committed
item or retries it safely. The original event ID, aggregate version, graph
revision, content fingerprint, and idempotent projection handlers make that
retry safe. The attempt table records both worker attempts.

A slow transaction may outlive one or more nominal lease intervals. The worker
renews its lease, but correctness does not depend on timely renewal. Its
database transaction holds the item row, request fence row, and scope advisory
locks. Another worker using `FOR UPDATE SKIP LOCKED` cannot execute that item or
increment the active fence until the first transaction commits or rolls back.
If the first worker loses ownership between items, its next fencing check fails
with `LEASE_LOST` before any projection handler runs.

If an ordered item fails, the request becomes `FAILED` and its isolation barrier
remains by default. Disjoint scopes continue processing. An administrator may
fix the cause and create a new plan. Removing the barrier while the scope is
still behind is a separate `RELEASE_WITH_GAP` emergency override with explicit
impact acknowledgement, two-person production approval, and audit; it is not a
normal replay cancellation. The worker does not skip ahead to a later revision.

A failed deferred transaction follows the same ordering rule. The scoped
barrier is not automatically removed merely because the immutable envelope is
safe in the failure archive: releasing it would let newer graph revisions or
aggregate versions overtake the failed transaction and recreate a projection
gap. Instead, the barrier becomes a durable `QUARANTINED` row owned by the new
failure, and later transactions intersecting that scope continue to enter
`event_projection_deferred_t`. Unrelated scopes remain live. The UI alerts on
the quarantine and offers a follow-up dependency-closure plan beginning with
the failed deferred transaction. That plan takes fenced ownership of the
existing barrier, drains the remaining deferred sequence, and removes the
barrier only after the ordered scope is complete. Quarantine age and deferred
capacity are monitored; reaching a hard capacity limit stops only the affected
source partition rather than releasing the barrier unsafely.

## Notification and UI Design

Extend the admin notification page with transaction-oriented replay controls:

- group failed notification rows by host, projection, consumer group, and
  transaction ID;
- show processor type, source coordinates, event types, event count, first and
  last failure time, bounded error, dependency scope, and replay status;
- selecting any row selects its complete transaction;
- **Plan Replay** opens a preview rather than executing immediately;
- the preview distinguishes explicitly selected transactions from dependency
  transactions added by the planner;
- graph revisions and detected gaps are displayed as an ordered sequence;
- warnings show barrier or fallback-pause scope, deferred or queued live work,
  sensitive events, compatibility upgrades, capacity limits, and approval
  requirements;
- quarantined scopes show the owning failure, quarantine age, deferred counts
  and bytes, capacity state, and the follow-up replay action;
- raw payload values are hidden unless the caller has sensitive-diagnostic
  permission;
- the detail view shows immutable attempts and links the resolved failure to
  its replay request.

There is no one-click **Replay All** button. The bulk workflow requires filters,
a bounded plan, a reason, and approval.

`notification_t` continues to represent the latest user-facing event status.
After replay succeeds it may return to `SUCCEEDED`, but the original error and
attempt history remain in the replay tables. The UI joins that history instead
of treating an overwritten notification row as the audit record.

## Limits and Retention

Configuration provides hard limits for:

- transactions per plan;
- events per plan;
- encrypted and decrypted bytes per transaction and plan;
- planning duration;
- pause acknowledgement duration;
- execution duration;
- attempts per transaction;
- plan TTL;
- worker lease and heartbeat periods;
- inline payload bytes per failure and per host;
- total archive bytes, object-store backlog, deferred bytes, and publication
  outbox rows;
- warning and hard database free-space thresholds.

Plans exceeding a hard limit are rejected rather than partially truncated.
Operators can create several dependency-independent plans, but one ordered
scope cannot be split at an unsafe boundary.

### Failure-storm circuit breaker

Failure capture is part of source progress, so capacity exhaustion must fail
closed. At a soft archive threshold, the system alerts, reduces diagnostic
sampling, and routes new encrypted payload blobs to the configured immutable
object store while retaining searchable metadata in PostgreSQL. It never drops
headers, transaction membership, payload digests, or the only replayable
payload.

At a hard per-host, per-projection, archive-byte, deferred-byte, or database
free-space threshold, the affected DB logical partition or Kafka
`TopicPartition` stops advancing. The Kafka processor does not commit the
source offset; the database processor rolls back the claim transaction. Health
reports `ARCHIVE_CAPACITY_EXCEEDED`, pages operators, and leaves the source as
the durable backlog. Unrelated partitions continue when isolation is safe.

If no object store is configured, the system moves directly from warning to
the hard stop before PostgreSQL reaches its reserved free-space floor. A
metadata-only capture mode is prohibited because it would commit past an event
that can no longer be replayed.

Failure metadata and replay attempts have a longer retention period than raw
payloads. Encrypted payload removal changes unresolved failures to
`PAYLOAD_UNAVAILABLE`; it does not delete their audit metadata. Resolved payloads
can be removed according to policy after their retention deadline and legal
hold checks.

Replay tables reference `host_t` with `ON DELETE RESTRICT`. Host teardown must
run an explicit, audited replay-retention purge after legal-hold checks; it must
not cascade through immutable attempts or audit history implicitly.

Kafka DLQ retention must be long enough for external incident tooling, but
replay correctness no longer depends on the topic retaining the only payload
copy.

## Security and Privacy

- Encrypt archived payloads with a rotatable application key and store the key
  ID per event.
- Require a non-empty password for the replay PKCS12 keystore; passwordless
  replay key stores are not supported.
- Store and compare SHA-256 payload digests before every replay.
- Never log payloads, Kafka keys, headers, or decrypted values.
- Redact error messages to a bounded safe form.
- Treat `sensitivepayload=true` as requiring sensitive-event approval and
  restricted diagnostics.
- Enforce host scope in every failure, plan, approval, and status query.
- Audit requester, approver, executor, reason, plan hash, counts, event types,
  scopes, result, and timestamps without auditing payload values.
- Do not allow payload download through the initial UI.
- Use constant-time digest comparison where application code compares payload
  fingerprints.

## Observability

Metrics should be labeled by projection, consumer group, processor type, event
type, and bounded result code, but never by host ID, transaction ID, event ID,
or error text.

Recommended metrics are:

- open failure transactions and oldest age;
- failure capture count and capture errors;
- encrypted archive bytes written per minute, total inline bytes, object-store
  bytes, deferred bytes, highest host-quota utilization, host-quota violation
  count, and database free-space ratio;
- Kafka failure-publication backlog, bytes, oldest age, retry count, and
  `TERMINAL_FAILED` count;
- replay plans by status;
- replay events, transactions, and bytes;
- replay duration and barrier/fallback-pause duration;
- replay successes and failures by safe error code;
- stale plans, dependency gaps, and unsupported event types;
- abandoned attempts and lease recoveries;
- active barriers by scope, fallback pause state, deferred backlog, and worker
  acknowledgement lag;
- quarantined scopes, oldest quarantine age, follow-up-plan count, and
  quarantine capacity stops.

Logs carry replay request ID, failure ID, attempt number, projection, consumer
group, processor type, counts, and safe result code. Payloads and exception
stack traces containing payload fragments are excluded.

## Failure Handling

- **Planner finds a gap:** keep the request non-executable and identify the
  missing revision, aggregate version, or transaction member.
- **Payload digest mismatch:** fail before projection and retain the barrier or
  fallback pause until an administrator responds.
- **Worker crashes before commit:** database rollback leaves the item pending;
  lease recovery starts a new attempt.
- **Worker crashes after commit:** the item and projection state committed
  together; retry is idempotent and recognizes the completed state.
- **Lease expires during a slow transaction:** the item row and scope locks
  prevent concurrent execution; recovery waits for commit or rollback and then
  applies the next fencing token.
- **A live worker does not acknowledge a fallback pause:** fail with
  `PAUSE_TIMEOUT`; do not start replay. There is no force-acknowledge shortcut.
- **Archive reaches a hard capacity limit:** stop the affected source partition
  before committing progress and report `ARCHIVE_CAPACITY_EXCEEDED`.
- **Kafka DLQ is unavailable:** retain the canonical failure and retry its
  publication outbox; source offsets may progress after the canonical record is
  durable. Exhausted publication policy becomes `TERMINAL_FAILED` and requires
  operator action instead of retrying forever.
- **Replay handler still throws:** stop the ordered plan at that transaction,
  record `PROJECTION_FAILED`, retain the same failure lineage, and keep the
  affected barrier. Do not publish another Kafka failure envelope
  automatically.
- **Deferred live transaction throws:** atomically capture
  `DEFERRED_PROJECTION_FAILED`, transfer the scoped barrier to durable failure
  quarantine, keep later intersecting transactions deferred, and alert for a
  follow-up dependency-closure plan. Never release an ordered scope merely
  because its failed envelope was archived.
- **Plan expires:** require a new plan and approval; never refresh it silently.
- **Administrator cancels before execution:** release the barrier or fallback
  pause if this request owns it and preserve the cancelled plan.

## Migration and Rollout

### Phase 1: schema and shared executor

1. Add the failure, delivery, replay, barrier, deferred-work, fallback-pause,
   worker, attempt, and publication-outbox tables.
2. Extract `ProjectionTransactionExecutor` and move graph/clone completion into
   it.
3. Make both live processors use the executor.
4. Keep replay execution disabled.
5. Run parity tests proving that DB and Kafka processing produce identical
   projection and notification outcomes.

### Phase 2: durable failure capture

1. Dual-write database failures to the existing DLQ and canonical archive.
2. Change Kafka failure handling to persist the canonical archive and
   publication outbox before committing source offsets.
3. Publish the enriched Kafka DLQ transaction envelope.
4. Enable archive quotas, disk-watermark circuit breakers, object-store spill,
   publication terminal states, and cleanup before enabling replay.
5. Monitor content/delivery fingerprints, archive bytes, counts, and
   publication lag.

### Phase 3: planning and validate-only UI

1. Add candidate, failure-detail, plan, and status APIs.
2. Backfill database DLQ rows by joining original outbox transactions.
3. Index legacy Kafka DLQ records where complete transaction identity can be
   proven.
4. Enable static `VALIDATE_ONLY` and approval workflows without execution.
5. Enable `ROLLBACK_DRY_RUN` only for the initial dry-run-safe allowlist.

### Phase 4: controlled execution

1. Enable scoped barriers, deferred live-work draining, fenced claims, and
   worker heartbeats.
2. Enable execution for a small allowlist of replay-safe event types.
3. Add graph-root dependency closure.
4. Enable partition/projection pause only as an approved fallback.
5. Expand the replay registry only after handler-specific idempotency and
   dry-run classification tests pass.

### Phase 5: operational completion

1. Add bounded bulk planning and two-person production approval.
2. Add retention and legal-hold jobs.
3. Retire manual offset-rewind runbooks.
4. Decide whether the legacy database DLQ table becomes a compatibility view.

## Validation Plan

### Common executor parity

- Process the same transaction through DB live, Kafka live, and replay modes and
  compare every projection row and completion side effect.
- Verify graph revisions and clone ledger outcomes advance identically in all
  three modes.
- Verify a multi-event transaction is committed or rolled back as one unit.

### PostgreSQL processor

- Fail one transaction between successful transactions and confirm progress,
  canonical failure capture, and unchanged source offset during targeted
  replay.
- Replay the failure without reprocessing unrelated outbox offsets.
- Crash before and after item commit and verify lease recovery.

### Kafka processor

- Preserve original keys, headers, topic, partition, offset, transaction ID,
  and event order in the canonical envelope and external DLQ envelope.
- Make Kafka DLQ publication unavailable and prove the canonical failure and
  publication-outbox record commit before the source offset advances.
- Make failure-archive persistence unavailable and prove the source Kafka
  offset is not committed.
- Redeliver the same logical transaction at a new offset and verify one content
  failure with two delivery observations.
- Exhaust DLQ publication retries and verify the outbox becomes
  `TERMINAL_FAILED`, alerts, and stops retrying without losing the canonical
  failure.
- Fail a replay attempt and verify it does not publish a new Kafka DLQ envelope
  or create an unbounded replay generation.
- Reject a legacy multi-record failure whose transaction boundary cannot be
  proven.

### Planning and ordering

- Select one event from a multi-event transaction and verify the complete
  transaction is selected.
- Select graph revision 18 when projected revision is 0 and verify revisions 1
  through 17 are added in order.
- Remove one prerequisite payload and verify `REPLAY_GAP` or
  `PAYLOAD_UNAVAILABLE` blocks execution.
- Verify topological ordering for a transaction touching several scopes.
- Change projection metadata after planning and verify `STALE_PLAN`.
- Verify `VALIDATE_ONLY` performs no projection SQL and
  `ROLLBACK_DRY_RUN` rejects handlers that are not dry-run safe.
- Verify compatibility-upgrader vectors and live/replay parity, and reject an
  upgrader that changes identity, version, revision, or dependency scope.
- Waive a prerequisite and verify downstream replay remains blocked.

### Concurrency, barriers, and fencing

- Install a graph-root barrier and verify unrelated hosts and roots continue
  projecting.
- Send new transactions for the blocked root and verify they are deferred and
  drained in source order after repair.
- Fail the first deferred transaction during drain and verify the request
  fails, the barrier atomically becomes failure-owned `QUARANTINED`, newer work
  for that scope stays deferred, and unrelated scopes continue. Then execute a
  follow-up closure plan and verify it drains the sequence before releasing the
  barrier.
- Expire a request lease during a deliberately slow transaction and verify a
  second worker skips the locked item and cannot execute concurrently.
- Kill a worker before and after commit and verify the fencing token and item
  row lock provide one committed outcome.
- Use an event with unprovable scope and verify the planner chooses the affected
  partition pause, then projection pause only as the final approved fallback.
- Partition a fallback-pause worker from the coordinator and verify replay does
  not start until assignment loss or transaction rollback provides a safe
  fence.

### Capacity and retention

- Drive a high-rate failure storm and verify object-store spill activates at
  the soft threshold.
- Cross the hard archive or database free-space threshold and verify the
  affected source position does not advance.
- Verify publication-outbox cleanup removes published rows after retention,
  copies terminal outcomes to append-only audit, and removes terminal rows from
  the active outbox after bounded diagnostic retention.
- Verify metrics report encrypted bytes written per minute, total inline and
  object bytes, deferred bytes, bounded quota summaries, and database free
  space without host-ID labels.

### Security and operations

- Verify host admins cannot inspect or replay another host's failures.
- Verify requester/approver separation when configured.
- Verify break-glass barrier release rejects a stale epoch or owner, requires
  its dedicated permission and approval, and leaves the failure open without
  advancing projection metadata.
- Verify sensitive payloads never appear in API lists, logs, metrics, or audit
  details.
- Verify payload tampering is detected before decryption output reaches a
  handler.
- Verify limits reject the complete plan instead of truncating an ordered
  closure.

## Open Questions

The following decisions can be settled during implementation without changing
the core architecture:

- which immutable object-store implementation backs large encrypted payloads
  and the threshold for inline PostgreSQL storage;
- which event types are safe for scoped barriers and which require a partition
  or projection fallback pause;
- the initial allowlist of replay-safe event types beyond instance/config graph
  events;
- the initial allowlist of `ROLLBACK_DRY_RUN` handlers;
- the production thresholds that trigger two-person approval;
- encryption-key ownership and payload retention periods;
- whether resolved legacy `dead_letter_queue` rows remain indefinitely or are
  represented by a compatibility view;
- whether a later full-rebuild service should reuse the transaction executor
  and replay policy registry while maintaining a separate workflow and safety
  model.

The non-negotiable contracts are transaction atomicity, dependency-complete
ordering, immutable payloads and content fingerprints, database-enforced replay
fencing, scoped isolation when it can be proven, durable failure capture before
source progress, bounded archive growth, a shared projection executor, and
replay without live offset rewind.
