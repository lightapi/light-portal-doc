# Event Replay

## Status

This document defines the revised target design for event replay during the
early development stage of light-portal. The implementation still contains
legacy-backfill, staged-rollout, feature-gate, mandatory-encryption, and
allowlist machinery that does not yet match this design. That code will be
reviewed separately after this design is accepted.

The design deliberately optimizes for a new development deployment:

- replay works as soon as the code and replay database tables are deployed;
- only failures observed after deployment are replay candidates;
- historical DLQ rows are not migrated or replayed;
- one small configuration provides an execution circuit breaker and identifies
  exceptional event types that must not be replayed;
- event validity and replay safety are enforced in code;
- Light Gateway controls which roles may call each replay endpoint;
- application-level payload encryption is not required for replay correctness.

## Motivation

The portal has two projection processors:

- `DbEventConsumerStartupHook` reads `outbox_message_t`, tracks progress in
  `consumer_offsets`, and writes failed events to the PostgreSQL
  `dead_letter_queue` table.
- `PortalEventConsumerStartupHook` in `user-query` reads Debezium-published
  Kafka records, commits Kafka consumer offsets, and publishes failed records
  to the configured Kafka DLQ topic.

Both processors ultimately call `PortalDbProvider.handleEvent(conn, event)`.
They isolate a failed transaction and advance to later independent work, but a
DLQ row alone is not a safe replay instruction:

- one row may be only one member of a multi-event business transaction;
- aggregate versions or graph revisions may require earlier failed
  transactions first;
- replay can race with newer live projection work;
- rewinding a shared source offset reprocesses unrelated transactions.

Event replay therefore operates on complete canonical failure transactions,
not individual notification or DLQ rows. It invokes the same projection
executor as live processing without rewinding PostgreSQL or Kafka offsets.

## Goals

- Capture every new failed projection transaction in a replayable canonical
  form.
- Preserve the original transaction boundary, event order, payload, identity,
  aggregate version, graph revision, and source coordinates.
- Distinguish exact replay after a processor fix from controlled repair of an
  event whose business data is permanently invalid.
- Validate replay-required metadata when commands append events to
  `event_store_t` and `outbox_message_t`.
- Support PostgreSQL and Kafka through the same planning and execution model.
- Derive ordinary replay policy from validated event metadata instead of
  maintaining a large event allowlist.
- Permit an explicit exclusion list for exceptional, non-idempotent, or
  externally side-effecting projection events.
- Use the same projection handler path for live processing and replay.
- Keep unrelated hosts, aggregates, and graph roots processing while a failed
  scope is repaired.
- Require an immutable plan, a reason, authorization, and a distinct approver
  before execution.
- Start replay capture, APIs, and the asynchronous worker by default after the
  schema is present.
- Keep configuration small enough that a developer can understand the entire
  replay setup from one screen.

## Non-Goals

- Historical or legacy `dead_letter_queue` rows are not imported. They remain
  diagnostic history only.
- The replay planner is not an event editor. It can use the original payload or
  reference a separately validated and approved repair; it cannot create or
  modify that repair.
- A repair never overwrites the original event or changes event IDs,
  transaction membership, aggregate identity/version, graph revision, or
  source coordinates.
- Replay does not replay successful history to rebuild an empty projection.
- Replay does not make external side effects or non-idempotent handlers safe.
- Replay does not replace event import, promotion, snapshot restore, or a full
  projection rebuild.
- The initial design does not require an object store, application-managed
  encryption keys, production rollout stages, canary allowlists, or legacy
  migration jobs.

## Operating Model

```text
command validation
       |
       v
event_store_t + outbox_message_t
       |
       v
PostgreSQL or Kafka live projection processor
       |
       +---------------- success ----------------> projection tables
       |
       +---------------- failure
                              |
                              v
                  canonical failure transaction
                              |
                              v
                     classify failure
                        /       \
                       v         v
             exact replay    propose repair
                       \         /
                        v       v
                  plan -> approve -> execute
                              |
                              v
                    asynchronous replay worker
                              |
                              v
                       projection tables
```

The normal Pub/Sub configuration selects the live processor. Event replay must
not introduce another source-selection property. PostgreSQL deployments use
the database source metadata; Kafka deployments use the Kafka source metadata.

All of these components are standard, always-active platform behavior after the
replay schema and services are deployed:

1. command-side event validation;
2. canonical failure capture;
3. replay query and command APIs;
4. the built-in approval state machine;
5. the asynchronous replay worker.

Replay and repair are different operations. Exact replay is appropriate when
the event was valid and the projection handler was defective or temporarily
unable to process it. Repair is appropriate only when the persisted business
data itself is invalid and exact replay would deterministically fail again.

There are no independent capture, planning, rollout, source, projection,
consumer-group, or host switches in the development configuration. One
`enabled` property is retained solely as the replay-execution circuit breaker.

## Event Append Contract

Replayability begins when a command appends events, not after an event fails.
The command path must reject invalid transactions before committing
`event_store_t` or `outbox_message_t`.

### Transaction invariants

Every appended transaction must satisfy:

- `transaction_id` is present and uses the canonical UUID representation;
- `transaction_count` is positive and identical on every member;
- `transaction_ordinal` is contiguous from zero through
  `transaction_count - 1`;
- every member has the same host and transaction identity;
- event IDs are present and unique;
- the transaction does not contain duplicate ordinals;
- `event_store_t` and `outbox_message_t` are committed atomically;
- the persisted source order is deterministic.

Database constraints enforce uniqueness and basic ranges. Java validation
enforces cross-row completeness before commit. Tests must prove that a partial
transaction cannot become visible to either live processor.

### Event invariants

Every event must contain a structurally valid CloudEvent envelope, including:

- event ID and event type;
- host identity;
- schema/specification version;
- event timestamp;
- parseable data;
- aggregate ID, aggregate type, and positive aggregate version for aggregate
  events;
- root instance ID and positive graph revision for graph-ordered events;
- any handler-specific identity required to make the projection idempotent.

The command path also validates the event data against the registered schema
for that exact event type and schema version. It enforces required properties,
property types, bounded values, and domain invariants that can be evaluated
without projection state. A failure returns a command validation error and
appends nothing; it is not a DLQ or replay candidate.

The validation registry is shared by command append, live projection, failure
capture, planning, and replay. A handler must not interpret an event as one
policy during live processing and another policy during replay.

Every appended event records the exact registry and repair-schema version used
to validate it. Later live projection, capture, planning, repair, and replay use
that pinned version; a deployment may add a new version but must not remove a
version while an event, open failure, repair, or plan references it. Unknown
registry entries fail closed on portal/internal append. An external Kafka event
with an unknown entry is captured as diagnostic, non-executable evidence rather
than interpreted under the current default. This prevents a registry edit from
retroactively changing the meaning of already-committed events.

### Projection handler contract

Replayable projection handlers must:

- perform database projection work through the caller's transaction;
- be idempotent for the original event ID and ordering metadata;
- use monotonic aggregate-version or graph-revision checks when ordered;
- avoid network calls, email, message publication, payment submission, or any
  other non-transactional external side effect;
- produce the same projection outcome in `LIVE` and `REPLAY` modes.

An unordered event whose handler cannot satisfy this contract belongs in
`excludedEventTypes`. An aggregate- or graph-ordered handler cannot be excluded:
doing so would create a projection gap that cannot be replayed or safely waived.
Such a handler must be made transactionally idempotent, normally by moving its
external effect behind an outbox, before it can carry ordering metadata.

## Replay Eligibility Policy

The default policy is derived from validated metadata:

| Event evidence | Derived policy | Behavior |
| --- | --- | --- |
| Root instance ID and graph revision | `GRAPH_ROOT` | Order by root and require contiguous graph revisions. |
| Aggregate ID, type, and version | `AGGREGATE_VERSION` | Order by aggregate and require monotonic versions. |
| Complete transaction without stronger ordering metadata | `TRANSACTION_ONLY` | Replay the complete transaction as one unit. |
| Explicitly excluded event type | `NOT_REPLAYABLE` | Keep diagnostic failure evidence but reject planning. |
| Missing or contradictory required metadata | Invalid event | Reject at append; if received from an external Kafka producer, do not create an executable candidate. |

This removes the need to list hundreds of ordinary replayable events. A new
event is replayable when its append contract and projection handler satisfy the
derived policy. Exceptional events are excluded explicitly.

For example, `UserDeletedEvent` contains aggregate identity and version
metadata. Its projection handler must use the monotonic aggregate-version
guard; it then derives `AGGREGATE_VERSION` without a dedicated allowlist entry.

An exclusion is an exact event-type match. Unknown patterns, substrings, and
wildcards are not accepted because they make policy review ambiguous.
Configuration reload also rejects an exclusion whose registered policy is
`GRAPH_ROOT` or `AGGREGATE_VERSION`. Registry validation rejects an ordered
`NOT_REPLAYABLE` policy for the same reason. Exclusion is therefore available
only for transaction-only or explicitly unordered events and cannot brick an
ordered scope.

## Minimal Configuration

The complete development-facing `event-replay.yml` is:

```yaml
# Execution circuit breaker. This does not disable capture, queries, planning,
# approval, or durable replay state.
enabled: ${event-replay.enabled:true}

# Exact event type names whose projection handlers are not safe to replay.
excludedEventTypes: ${event-replay.excludedEventTypes:}
```

`enabled` defaults to `true` and controls execution only. Event validation,
canonical failure capture, candidate and status queries, planning, approval,
and durable replay state remain active when it is `false`. An empty exclusion
list means every event satisfying the append and projection-handler contracts
derives its replay policy from its metadata.

Limits, lease durations, plan expiry, retry counts, approval requirements, and
safe error sizes use reviewed application defaults. They do not need operator
properties during early development. They can become advanced production
configuration later without changing the public replay contract.

The worker identity is derived from the deployed service identity plus a
per-process instance identifier. Developers do not configure a separate replay
client ID merely to start the worker.

Gateway endpoint roles remain in Light Gateway access-control configuration,
not `event-replay.yml`.

### Execution circuit breaker

An emergency may require replay execution to pause while diagnosis continues.
Examples include a projection-handler regression, database overload, an
incompatible rolling deployment, repeated worker failures, or an authorization
incident. These conditions do not justify disabling event validation or
failure capture.

Execution pause is controlled by changing `event-replay.enabled` to `false` in
the config server and pushing the change to every `hybrid-command` and
`hybrid-query` instance. Config-server change history provides the actor,
timestamp, and change evidence. Pausing:

- makes the execute endpoint reject new execution requests with
  `REPLAY_EXECUTION_PAUSED`;
- prevents workers from claiming new replay requests;
- does not interrupt an already-running database transaction unsafely;
- does not stop command-side event validation or canonical failure capture;
- does not hide candidates, plans, attempts, or status APIs;
- does not prevent creating or approving a plan;
- does not delete or alter durable replay state;
- does not require a service restart.

Scheduled requests remain durable while paused; approved but unscheduled plans
remain available only until their immutable expiry. An in-flight transaction
finishes or rolls back under its existing database fence. Changing `enabled`
back to `true` and pushing the configuration resumes worker claims and queued,
non-expired work. Removing gateway permission may prevent new operator
requests, but it is not a substitute for pausing an already-approved worker
queue.

`EventReplayConfig` must be a reloadable light-4j module. Config reload clears
the cached `event-replay` document, and command handlers read the current value
before every execute transition. The wake-up dispatcher and claimant read the
current value before starting or claiming work rather than retaining only the
startup snapshot. Like `AuditConfig`, it compares the cached configuration-map
identity on each `load()`/`current()` access and rebuilds its immutable snapshot
after `ConfigReloadHandler` clears the cache. No replay-specific callback or
light-4j framework change is required. A transition from `false` to `true`
schedules a drain when it is observed by the next notification, command/status
read, or periodic recovery scan. With no other activity, queued approved work
resumes within the 60-second recovery interval. The effective execution state
is exposed through health/status together with the config-server version or
generation, reload timestamp, and process instance ID. The deployment health
aggregator reports the expected replicas, their effective values and
generations, and whether they agree. A multi-instance pause is complete only
when that single fleet view reports every expected command/query replica at the
same pushed generation with `enabled=false`; missing or stale replicas keep the
pause state unconfirmed.

## Shared Projection Transaction Executor

PostgreSQL live processing, Kafka live processing, and replay call one shared
executor:

```java
ProjectionResult execute(
    Connection connection,
    ProjectionTransaction transaction,
    ProjectionExecutionMode mode
) throws Exception;
```

`ProjectionExecutionMode` is `LIVE` or `REPLAY`. It may change telemetry and
audit context but must not select a different projection handler. Exact replay
passes the original CloudEvent. Repair replay passes a transaction materialized
by the approved repair resolver before the executor is called; the executor
itself never edits an event.

The executor:

1. validates transaction membership and event order;
2. calls `PortalDbProvider.handleEvent(conn, event)` for every member;
3. completes graph-revision and aggregate-version bookkeeping;
4. completes clone or other transactional projection outcomes;
5. records notification outcomes through the caller's connection;
6. leaves commit or rollback to the caller.

The same transaction must contain projection writes, ordering metadata, replay
attempt outcome, and failure resolution.

## Canonical Failure Capture

Canonical capture applies only to failures observed after the feature is
deployed. The legacy DLQ remains visible for diagnostics but is not queried by
the replay candidate API and is never backfilled.

### PostgreSQL processor

When a complete projection transaction fails:

1. roll back projection writes to the transaction savepoint;
2. construct a canonical envelope from the complete ordered transaction;
3. persist the failure transaction and all event members;
4. update the notification status to `DLQ`;
5. commit canonical failure capture and claimed source progress atomically;
6. continue with the next independent transaction.

If canonical capture fails, source progress does not advance. A failed event
must not be committed past unless the payload needed for replay is durable.

The existing PostgreSQL `dead_letter_queue` write may remain temporarily for
diagnostic compatibility, but replay correctness depends only on canonical
failure capture for new failures.

### Kafka processor

When a complete Kafka projection transaction fails:

1. roll back projection writes;
2. persist the canonical transaction with original keys, headers, topic,
   partition, offsets, transaction identity, count, and order;
3. commit the source Kafka offsets only after canonical persistence commits;
4. publish to the external Kafka DLQ independently when that integration is
   configured.

If canonical persistence fails, the source offset is not committed and Kafka
redelivers the records. Capture is idempotent by content fingerprint.

This is intentionally an at-least-once boundary across PostgreSQL persistence
and Kafka offset commit, not a distributed transaction. PostgreSQL capture
must commit first; Kafka may redeliver after a crash, and the deterministic
fingerprint must collapse that delivery into the existing failure. Reversing
or parallelizing this order is forbidden because it can lose the only durable
replay payload.

External Kafka producers that omit transaction count/order or required event
metadata are rejected as executable replay candidates. The system does not
guess transaction boundaries.

## Canonical Failure Model

One canonical failure represents one complete logical transaction. It records:

- host, projection, and consumer group;
- original transaction ID and ordered member count;
- original source processor and coordinates;
- content fingerprint;
- dependency scopes derived from event metadata;
- bounded error code and message;
- first and latest failure timestamps;
- lifecycle status: `OPEN`, `RESOLVED`, or `WAIVED`.

Each ordered event member records:

- ordinal, event ID, and event type;
- aggregate identity and version when present;
- graph root and revision when present;
- original source coordinates, key, and headers when applicable;
- original payload or a durable payload reference;
- payload format and SHA-256 digest.

The content fingerprint is deterministic over projection identity,
transaction identity, ordered event IDs, and ordered payload digests. A
redelivery at a different source offset observes the same logical failure
rather than creating another candidate.

Once an ordered failure is canonically captured, new commands for the affected
aggregate or graph scope are blocked until exact replay or repair restores
projection continuity. This bounds further accumulation behind a known poison
event, but it cannot guarantee that `N+1` is never appended: projection and
capture are asynchronous, so commands may append during the interval between
the original append and committed failure capture. The block is therefore a
prompt, eventually-visible guard after capture, not a synchronous projection
cursor.

Before classification, blocked commands return
`AGGREGATE_PROJECTION_BLOCKED` with a safe failure reference. Once a validated
repair proposal classifies the failure as invalid data, they return
`AGGREGATE_REPAIR_REQUIRED`; the operator uses the repair flow instead of
resubmitting through the stale projection UI. Waiver may close the operator
action for diagnostic or unordered failures, but it does not unblock an
ordered scope whose projection metadata still has a gap.

This is a deliberate consistency-over-availability decision. One failed
ordered transaction can deny commands for that scope until a fix and exact
replay or an approved repair succeeds. There is no generic break-glass that
advances ordering metadata without applying the missing projection. Health and
alerts report blocked-scope count, age, host, projection, and safe failure ID;
crossing the reviewed duration threshold is an operator incident. The existing
barrier release can recover worker isolation but cannot pretend an ordered gap
is resolved or make later versions safe.

`notification_t` is the latest user-facing status, not the replay ledger. The
candidate APIs read canonical failure tables only.

## Payload Storage and Encryption

Application-level encryption is not required for replay correctness and is not
mandatory in the early-development design.

Canonical and repaired payloads are stored as immutable bytes (`BYTEA` for the
plain database representation). The SHA-256 content digest is computed over
exactly those stored canonical bytes. Replay verifies and parses those same
bytes; it never recomputes a digest from a JSONB value or re-serialized object.

`event_store_t` and `outbox_message_t` currently store JSONB, which normalizes
representation and is not a stable raw-byte archive. A canonical failure may
therefore reference those rows for identity and audit, but not as the sole
digest-bound payload unless a future schema also stores the versioned canonical
bytes. For current PostgreSQL capture, serialize through the versioned canonical
JSON encoder once and copy the resulting bytes into the canonical member before
source progress commits. Kafka capture stores the received value bytes. Repair
creation likewise materializes and stores corrected canonical bytes once.

In either case:

- the payload is immutable after capture;
- a SHA-256 digest over the stored bytes is stored and verified before
  execution;
- the UI, list APIs, logs, metrics, and audit records never expose the payload,
  Kafka key, headers, or event JSON;
- the baseline schema revokes payload-column access from `PUBLIC`; production
  deployments use dedicated non-owner projection/replay roles with explicit
  column-scoped grants because owners and explicit table grants bypass that
  baseline;
- normal database and volume encryption at rest protect the development
  deployment.

Optional envelope encryption or object storage may be added for production
when retention, PII, regulatory, or storage requirements justify it. Enabling
that option must not change planning, fingerprints, ordering, or projection
behavior, and its key configuration must not be required for ordinary
development startup. A secure representation must retain the stable digest of
the canonical plaintext bytes separately from any digest of randomized
ciphertext or object-storage bytes; ciphertext digests are storage-integrity
evidence and must never define the corrected transaction fingerprint.

## Repair Model

Repair is an append-only amendment to a canonical failed transaction. It is
not an update to `event_store_t`, `outbox_message_t`, a Kafka record, or the
canonical failure payload. The original event remains available with its
original digest for audit and diagnosis.

The minimum repair persistence model is:

- `event_repair_t`: repair ID, host, target failure, lifecycle status, reason,
  requester, approver, timestamps, original transaction fingerprint, and
  corrected transaction fingerprint;
- `event_repair_event_t`: repair ID, original event ID and ordinal, original
  digest, corrected data or durable reference, corrected digest, schema
  version, and the names of changed fields.

Repair lifecycle states are `AWAITING_APPROVAL`, `APPROVED`, `APPLIED`,
`CANCELLED`, and `REJECTED`. Rows and corrected payloads become immutable when
the proposal enters `AWAITING_APPROVAL`; a change requires a new repair ID and
new approval.

### Repair proposal contract

A repair proposal always targets one complete canonical failure transaction.
It may correct the data of one or more members, but it preserves:

- event IDs, event types, transaction ID, count, order, host, and source
  coordinates;
- aggregate ID, aggregate type, and aggregate version;
- graph root and graph revision;
- unchanged transaction members byte-for-byte.

Editable fields come from an event-type-specific repair schema. The UI does not
provide a generic CloudEvent or JSON editor. The server exposes only authorized,
schema-approved business fields, applies field-level redaction, and revalidates
the complete corrected transaction with the same schema and domain validators
used by command append. Envelope, identity, authorization, and ordering fields
are server controlled.

Every event policy explicitly declares one repair disposition:
`SCHEMA_REPAIR`, `FIX_AND_EXACT_REPLAY_ONLY`, or `NOT_REPAIRABLE_UNORDERED`.
`SCHEMA_REPAIR` names a versioned repair schema and the registry coverage gate
requires that schema to exist. `FIX_AND_EXACT_REPLAY_ONLY` is allowed for an
ordered event only as an explicit decision: invalid external data keeps the
scope blocked until a deployment makes the original event processable or adds
a new repair-schema version. `NOT_REPAIRABLE_UNORDERED` cannot be used for an
ordered policy. There is no implicit empty repair schema.

The proposal stores both payload digests and a bounded audit summary of changed
field names. Payload values do not appear in audit messages, logs, metrics, or
ordinary replay APIs. The requester cannot approve the repair.

### Repair planning and execution

An approved repair is input to the planner, not output from it. A repair plan
binds the repair ID, approval, original fingerprint, corrected fingerprint,
schema version, dependency closure, and projection preconditions into the plan
hash. Any change makes the plan stale.

The replay worker installs the normal scope barrier and materializes the
corrected transaction using the original immutable envelope plus the approved
corrected data. The transaction executes at its original logical aggregate
version or graph revision through the shared projection handler. This avoids
trying to insert another `(aggregate_id, aggregate_version)` into
`event_store_t` and avoids generating version `N+1` while the projection is
still at `N-1`.

Projection writes, ordering metadata, repair status `APPLIED`, replay attempt
completion, and failure status `RESOLVED` with resolution code
`RESOLVED_BY_REPAIR` commit atomically. Failure leaves the repair approved and
retryable and keeps the scope quarantined. Waiver does not apply a repair and
never advances projection metadata.

Approved repairs are permanent canonical history. Exact replay of that failure
and any future projection rebuild must resolve the original event through the
approved repair record and verify both fingerprints. A deployment that loses
the repair tables cannot deterministically rebuild repaired projections and
must fail closed rather than fall back to the poison payload.

## Planning

The UI selects canonical failure transaction IDs. Selecting one member always
selects its complete transaction.

The planner:

1. loads complete immutable failure transactions;
2. loads any explicitly selected, approved repairs;
3. verifies original and corrected payload digests and availability;
4. rejects excluded event types;
5. derives graph, aggregate, or transaction-only scopes;
6. adds required failed dependency transactions;
7. deterministically orders the dependency graph;
8. records projection preconditions and isolation scope;
9. creates an immutable plan hash and expiry.

Supported selection strategies are:

- `EXACT`: use exactly the selected complete transactions when no earlier
  dependency is missing;
- `DEPENDENCY_CLOSURE`: add required failed predecessors automatically.

There is no unbounded **Replay All** operation. Bulk selection is bounded by
application defaults and always produces a preview before approval.

Execution rejects a stale plan when failure content, dependency state,
projection versions, repair approval, schema version, or payload digests change
after planning. The planner cannot accept inline corrected data.

Plan expiry continues after approval. `APPROVED` may transition to `EXPIRED`,
and execute compares the current time with the immutable `expiresAt` before
scheduling. Pausing execution does not extend the TTL; an expired approved plan
requires a new plan and approval instead of executing unexpectedly after a long
pause.

## Approval and Authorization

Light Gateway is the role-based authorization boundary for all replay service
IDs. Its endpoint rules map deployment-defined role names to the JWT `role`
claim. Replay code does not hard-code `admin`, `host-admin`, `replay-admin`, or
any other role name.

The minimum authorization model is one authorized role and two distinct users:

- user A creates the replay plan;
- user B, authorized for the same host, approves the exact plan hash;
- an authorized user requests execution after approval.

The early-development deployment therefore assumes that two test identities
can be created in the host. There is no single-user or development-mode bypass:
such a bypass would make the same artifact behave differently when promoted and
would weaken the audit evidence this feature exists to provide.

Existing `admin` or `host-admin` roles may be assigned to every replay endpoint,
or a deployment may create one dedicated role. `host-admin` remains host
scoped; endpoint permission never bypasses token-host validation.

The built-in state machine records requester, approver, executor, reason, plan
hash, and timestamps. It rejects requester-as-approver. It does not require
`light-workflow` or create a manual task. A future workflow integration may
drive the same transitions without weakening these invariants.

## API Contract

Replay remains in the existing `user-query` and `user-command` services:

| Operation | Type | Service ID |
| --- | --- | --- |
| List replay candidates | Query | `lightapi.net/user/listEventReplayCandidate/0.1.0` |
| Get failure transaction | Query | `lightapi.net/user/getEventReplayFailure/0.1.0` |
| Create immutable plan | Command | `lightapi.net/user/createEventReplayPlan/0.1.0` |
| Get plan/status | Query | `lightapi.net/user/getEventReplay/0.1.0` |
| Approve plan | Command | `lightapi.net/user/approveEventReplay/0.1.0` |
| Execute approved plan | Command | `lightapi.net/user/executeEventReplay/0.1.0` |
| Cancel before execution | Command | `lightapi.net/user/cancelEventReplay/0.1.0` |
| Waive explicit failure transactions | Command | `lightapi.net/user/waiveEventReplayFailure/0.1.0` |
| Release a quarantined barrier | Command | `lightapi.net/user/releaseEventReplayBarrier/0.1.0` |
| Get a repair proposal | Query | `lightapi.net/user/getEventReplayRepair/0.1.0` |
| Create a validated repair proposal | Command | `lightapi.net/user/createEventReplayRepair/0.1.0` |
| Approve a repair proposal | Command | `lightapi.net/user/approveEventReplayRepair/0.1.0` |

All request bodies are host-scoped and bounded. Host and actor identity come
from trusted token/audit context, not caller-supplied authorization fields.
The approve-repair command accepts `APPROVE` or `REJECT`. `CANCELLED` is a
system transition when the target failure reaches another terminal outcome;
there is no separate repair-cancel endpoint, so the public contract remains
exactly twelve endpoints.

Waiver remains a two-person operation without adding a thirteenth endpoint.
The requester first calls `waiveEventReplayFailure` with the exact failure IDs;
the response is `AWAITING_APPROVAL` and includes a `waiverRequestId` plus the
computed downstream impact. A different user approves by calling the same
endpoint with that `waiverRequestId`, the exact failure IDs, and the expected
downstream blocked failure IDs. Neither step advances projection metadata.

V2 inheritance is closed, not catch-all. Only sections named in
`inheritsFrom.inheritedSections` carry forward from v1. The shared LIVE/REPLAY
execution modes, validation-mode semantics, Kafka DLQ evidence contract,
replay policies, and failure/barrier/audit state remain inherited. V1
`featureGates`, mandatory `encryption`, required `objectStore`, operator-facing
`limits`, and fixed `retentionDays` are explicitly superseded and must not be
merged into v2.

## Isolation and Execution

Replay must not race with newer live work for the same ordered scope.

Preferred barriers are:

- `GRAPH_ROOT` for graph-revision events;
- `AGGREGATE` for aggregate-version events;
- `TRANSACTION_ONLY` isolation when the transaction has no stronger ordering
  scope.

A complete transaction may touch several aggregates or graph roots. Planning
derives the union of every member's ordering scopes, checks dependency
continuity for each scope, sorts the lock keys canonically, and acquires all
scope locks before executing any member. A gap or exclusion in one scope makes
the whole transaction non-executable; replay never applies the transaction to
only the unaffected scopes. Live work intersecting any member scope is deferred
as the same complete transaction. Canonical lock ordering prevents two
cross-scope transactions from deadlocking each other.

The worker installs a fenced barrier, waits for current work in that scope to
finish, and then applies the approved items through the shared executor. Live
transactions intersecting the barrier are deferred as complete transactions;
unrelated scopes continue normally. After repair, deferred transactions drain
in source order before the barrier is removed.

### R2 transitional plain-payload limitation

The preceding paragraph is the target isolation contract, but R2 does not yet
fully provide it for the default `DATABASE_PLAIN` codec. The legacy deferred
table stores only encrypted/object representations. R2 therefore returns
`PAUSED` when a live transaction intersects an active replay barrier under the
plain codec, holds the source position, and retries after barrier release. This
preserves ordering and prevents payload loss, but it creates a temporary
head-of-line stall: unrelated transactions sequenced later on that source do
not advance even when their scopes do not intersect the barrier. The legacy
encrypted codec still uses durable `DEFERRED` work and can advance the source.

This limitation is accepted only for the early R2 development phase. Repair
execution adds an exact-byte plain deferred representation, digest and
retention rules, then restores `DEFERRED` behavior before cross-repository
qualification. Tests must pin both the transitional behavior and the restored
target so the general goal that unrelated scopes continue is not weakened.

Replay requests use row locks, monotonic fencing tokens, leases, and advisory
scope locks. A lease provides liveness and abandoned-work recovery; it never
overrides a database lock or permits two workers to execute the same item.

The replay execution components are registered only in `hybrid-query` and start
automatically after the replay schema is available. The execute API durably
schedules work and returns; it does not run projection SQL on the HTTP thread.

### Worker wake-up and idle behavior

`event_replay_request_t` is the durable work queue. In the same database
transaction that changes an approved request to `INSTALLING_BARRIER`, the
execute command calls `pg_notify('event_replay_ready', replayRequestId)`. A
PostgreSQL notification is delivered only after commit, so a listener cannot
wake for work that later rolls back. The notification is only a wake-up hint;
the durable request row remains the source of truth.

Replay configuration follows the standard light-4j lazy reload contract used by
`AuditConfig`: `ConfigReloadHandler` clears the registered module's cached
document, and the next `EventReplayConfig.current()` observes the new map
identity and rebuilds the configuration. A replay notification observes the new
value immediately through `requestDrain`; when no notification or request
arrives, the 60-second recovery scan is the bounded config-observation path.
An observed `false -> true` transition schedules a coalesced drain. This avoids
both a one-second claim loop and a replay-specific change to the shared
light-4j config-reload framework.

Each `hybrid-query` replica uses a lightweight virtual thread blocked on
`LISTEN event_replay_ready`. It does not run a one-second claim loop. The
listener may use a dedicated PostgreSQL connection or a shared internal
notification dispatcher that multiplexes application channels. A blocked
virtual thread consumes no polling CPU. When notified, it submits a drain task
that claims durable requests through the existing `SKIP LOCKED`, fencing, and
lease protocol. Several replicas may wake for the same notification, but only
one can claim a request.

The current implementation reserves one connection from the application data
source for the lifetime of each query replica. Size the pool for peak ordinary
query/projection concurrency plus this listener connection; a pool size of one
is invalid for a query replica. Some PostgreSQL driver versions may pin the
listener virtual thread's carrier while `getNotifications` waits. This is
bounded to the single listener and is not a reason to fan out one listener per
channel.

`LISTEN` requires session affinity. The listener connection must reach
PostgreSQL directly or through a session-pooling endpoint; PgBouncer transaction
or statement pooling is unsupported for this connection even when ordinary
queries use it. Startup sends a uniquely identified self-test notification and
requires the listener to observe it within a bounded interval. Failure marks
listener health degraded and reports the connection/pool mode; the 60-second
scan preserves correctness but must not mask a permanently broken notification
path.

PostgreSQL notifications are not durable. On startup, after listener reconnect,
and once every 60 seconds while execution is enabled, each replica performs a
recovery scan for an executable request. The 60-second interval is a reviewed
application default, not another development configuration property. After a
worker drains the available requests, it returns to the blocked listener. This
reduces an idle replica from one empty query per second to at most one recovery
query per minute while preserving immediate normal execution.

While `event-replay.enabled=false`, notifications may still wake the listener,
but `requestDrain` intentionally drops those wake-up hints and no drain task may
claim work. Durable request rows are not dropped. Changing it back to `true` is
observed by the next notification or other config access, or within 60 seconds
by the periodic recovery scan. Kafka deployments use the same PostgreSQL replay
control plane and therefore use this wake-up mechanism as well; it is
independent of the live Pub/Sub source.

### Replay worker operational status

Each `hybrid-query` replica exposes the following replica-local administrative
endpoint:

```http
GET /adm/event-replay/status
```

The endpoint returns `application/json`. It is an observation endpoint only: it
does not list replay candidates, create or approve a plan, or start replay
execution. Its purposes are to confirm that a replica loaded the expected
execution-pause configuration, verify that its PostgreSQL `LISTEN/NOTIFY`
worker is healthy, and provide enough evidence to confirm a fleet-wide pause.

A healthy response has the following shape:

```json
{
  "status": "HEALTHY",
  "effectiveEnabled": true,
  "configGeneration": "6b68d2...",
  "configReloadTimestamp": "2026-07-23T18:20:31.123Z",
  "processInstanceId": "019...",
  "listenerConnectionRequirement": "DIRECT_OR_SESSION_POOLING",
  "dedicatedListenerConnections": 1,
  "listenerConnected": true,
  "selfTestPassed": true,
  "detail": "LISTEN/NOTIFY self-test passed",
  "lastConnectedTimestamp": "2026-07-23T18:19:02.456Z",
  "lastNotificationTimestamp": "2026-07-23T18:20:10.789Z",
  "lastRecoveryScanTimestamp": "2026-07-23T18:20:02.456Z",
  "reconnectCount": 0,
  "notificationCount": 4,
  "recoveryScanCount": 1,
  "drainRunCount": 5
}
```

The fields have these meanings:

| Field | Meaning |
| --- | --- |
| `status` | Dispatcher lifecycle or health: `STARTING`, `SELF_TESTING`, `HEALTHY`, `DEGRADED`, or `STOPPED`. |
| `effectiveEnabled` | Effective value of `event-replay.enabled` on this replica. `false` pauses execution and claiming only. |
| `configGeneration` | SHA-256-derived identity of the effective replay configuration. Replicas with the same intended config must report the same generation. |
| `configReloadTimestamp` | Time this process last observed the current configuration generation. |
| `processInstanceId` | Unique identity of this running query replica, used to distinguish reports across restarts and replicas. |
| `listenerConnectionRequirement` | Required PostgreSQL connection mode. The value is `DIRECT_OR_SESSION_POOLING`; transaction pooling cannot preserve `LISTEN` session affinity. |
| `dedicatedListenerConnections` | Number of JDBC connections permanently reserved by this replica's listener; currently `1`. |
| `listenerConnected` | Whether the dedicated PostgreSQL listener session is currently connected. |
| `selfTestPassed` | Whether the session-affinity `LISTEN/NOTIFY` self-test passed on the current listener session. |
| `detail` | Human-readable lifecycle or degradation detail, including the failure type when degraded. |
| `lastConnectedTimestamp` | Most recent successful listener connection time, or `null` before the first connection. |
| `lastNotificationTimestamp` | Most recent received replay-ready notification time, or `null` if none has been received. |
| `lastRecoveryScanTimestamp` | Most recent periodic durable-work recovery scan time, or `null` before the first scan. |
| `reconnectCount` | Number of listener reconnection attempts after listener failures. |
| `notificationCount` | Number of PostgreSQL replay-ready notifications received by this process. Notifications are coalescible wake-up hints, not the durable work record. |
| `recoveryScanCount` | Number of periodic recovery scans used to find work after a lost notification or listener failure. |
| `drainRunCount` | Number of coalesced worker drain runs scheduled by startup, notification, resume, reconnect, or recovery. It is not expected to equal `notificationCount`. |

Before the dispatcher is installed, the endpoint reports `status=STARTING`,
`listenerConnected=false`, `selfTestPassed=false`, and the configuration and
connection-requirement fields. Listener timestamps and counters are added once
the dispatcher exists. A `DEGRADED` status commonly means that the listener
connection failed, its self-test failed, or a transaction-pooling proxy broke
session affinity. The `detail` field identifies the observed condition.

For fleet-wide pause confirmation, an operator or aggregator polls every target
query replica and verifies all of the following:

- every expected `processInstanceId` is represented by a fresh response;
- every response has `effectiveEnabled=false`;
- every response has the intended `configGeneration`; and
- there are no missing or stale replicas.

A missing or stale response never confirms a pause. Listener health is separate
from pause confirmation: a replica can report `DEGRADED` while still finding
durable work through the 60-second recovery scan.

For that reason, listener degradation does not fail the service's normal
liveness endpoint. Restarting an otherwise healthy query service would disrupt
unrelated APIs without repairing an unsupported connection-pooling mode. The
administrative status endpoint must instead be monitored separately. It exposes
no event payload or PII, but it reveals internal execution state, so the gateway
or deployment ingress must protect it with the same administrative access
controls used for other `/adm` routes.

Request states are:

```text
PLANNING -> READY -> AWAITING_APPROVAL -> APPROVED
         -> INSTALLING_BARRIER -> RUNNING -> SUCCEEDED
                                        \-> FAILED
READY/AWAITING_APPROVAL/APPROVED -> CANCELLED
READY/AWAITING_APPROVAL/APPROVED -> EXPIRED
```

Attempts are append-only. Success resolves the canonical failure in the same
transaction as projection writes and attempt completion. A failed replay does
not create a new DLQ loop; it records another attempt against the same failure.

## Notification and UI

The Event Admin page provides:

- a list of open canonical replay candidates;
- transaction member count, event types, ordering scope, error, and failure
  time;
- explicit distinction between canonical candidates and legacy DLQ
  notifications;
- dependency-closure preview;
- plan hash, expiry, requester, approver, status, and attempts;
- approval, execution, cancellation, waiver, and quarantine controls according
  to gateway authorization.
- a separate **Repair** action when exact replay would repeat an invalid-data
  failure;
- a schema-driven repair form that exposes only authorized editable business
  fields and clearly states that the complete failed transaction is affected;
- repair status, changed field names, original/corrected digests, requester,
  approver, and linked replay plan without exposing payload values.

A legacy notification may remain visible in the lower notification table but
must not be described as replayable. The empty candidate state explains that
only newly captured canonical failures appear there.

Raw payloads, complete event JSON, Kafka keys, headers, and database payload
references are never returned to the browser. A repair endpoint may return only
the explicitly authorized and redacted business fields declared by the repair
schema.

## Failure Handling

- **Invalid command-side transaction:** reject the command before event-store
  or outbox commit.
- **Persisted event has permanently invalid data:** once a validated repair
  proposal classifies the failure, reject exact planning with
  `EVENT_REPAIR_REQUIRED`; block later commands in the ordered scope with
  `AGGREGATE_REPAIR_REQUIRED`; require an approved repair.
- **External Kafka transaction is incomplete:** do not create an executable
  candidate and do not commit the source offset when canonical evidence cannot
  be persisted safely.
- **Excluded unordered event type:** retain diagnostic failure metadata and
  report `EVENT_NOT_REPLAYABLE` during planning. Reject ordered exclusions at
  policy/configuration validation.
- **Payload missing or digest mismatch:** reject planning or execution with
  `PAYLOAD_UNAVAILABLE` or `PAYLOAD_DIGEST_MISMATCH`.
- **Dependency gap:** report the exact missing aggregate version, graph
  revision, or transaction and keep the plan non-executable.
- **Worker crashes before commit:** database rollback leaves the item pending;
  lease recovery starts a new fenced attempt.
- **Worker crashes after commit:** projection result and attempt outcome are
  already atomic; recovery observes completion.
- **Replay handler still fails:** stop the ordered plan, record the attempt,
  and keep the affected scope quarantined.
- **Plan expires or becomes stale:** require a new plan and approval.
- **Repair fails validation:** store no executable repair and report bounded
  field errors without changing the original failure.
- **Repair execution fails:** retain the approved repair, record the attempt,
  and keep the ordered scope quarantined for retry or cancellation.
- **Emergency execution pause:** push `event-replay.enabled=false` to all
  command and query instances, verify their effective health/status, and stop
  new execute transitions and worker claims while validation, capture, query
  APIs, planning, approval, and durable state remain available.

## Security and Privacy

- Light Gateway authorizes every replay endpoint.
- Every query and mutation validates token host against the requested host.
- Requester and approver must be distinct users.
- Repair requester and repair approver must also be distinct users; approval of
  a replay plan does not implicitly approve a repair.
- The reason and immutable plan hash are audited.
- Payload digests are verified immediately before projection execution.
- Repair APIs enforce event-type-specific editable fields and never accept
  caller-controlled envelope, tenant, identity, or ordering metadata.
- Payloads, keys, headers, event JSON, and direct storage locations never
  appear in API lists, browser state, logs, metrics, or audit details.
- Dedicated non-owner database roles and column-scoped grants restrict canonical
  payload access to the projection and replay services; revoking `PUBLIC` alone
  is only the schema baseline.
- Application-level encryption is an optional production hardening control,
  not a prerequisite for development replay.

## Observability

Recommended bounded-cardinality metrics are:

- canonical failures captured, open, resolved, repaired, and waived;
- capture failures by safe error code;
- replay plans and attempts by status;
- repair proposals and executions by safe status and event type;
- replay transaction and event counts;
- planning, approval-wait, execution, and barrier duration;
- stale plans, dependency gaps, excluded events, and payload mismatches;
- blocked ordered scopes by age bucket and safe failure code;
- capture rate, stored payload bytes, capacity-watermark state, and source
  backpressure activations;
- active barriers, deferred transactions, quarantined scopes, and abandoned
  attempts;
- worker heartbeat and claim failures;
- replay listener connection/reconnection state, notification wake-ups, and
  recovery-scan claims.

Logs include request ID, failure ID, projection, consumer group, attempt,
counts, and safe result code. They exclude payloads and unbounded exception
messages.

Always-on capture uses reviewed internal soft/hard capacity defaults even
though they are not development-facing configuration. A failure storm crossing
the soft threshold raises health/alerts. At the hard threshold, the affected
source stops before advancing past a failure whose replay bytes cannot be
stored; it does not discard payloads or silently downgrade to legacy DLQ-only
behavior. Blocked-scope age and failure-rate alerts make the resulting
availability impact visible during a bad deployment.

## Deployment Behavior

The schema migration creates the canonical failure, repair, replay request,
item, attempt, lease, barrier, deferred-work, and audit tables. After both the
schema and updated services are present:

1. replay validation, capture, APIs, and worker startup are active;
2. `hybrid-query` starts canonical capture and the replay worker;
3. `hybrid-command` accepts plan and state-transition commands;
4. new failed transactions appear in Event Admin;
5. gateway endpoint roles determine who may operate them.

`user-command` and `user-query` are source repositories/modules;
`hybrid-command` and `hybrid-query` are their deployed service bundles. This
document uses the module names for code ownership and the hybrid names for
runtime instances.

Deployment order remains schema, shared `light-portal` artifacts,
`hybrid-command`, then `hybrid-query`. Command-side schema validation is active
when command deploys, but the open-failure scope block is inert until the query
deployment is capturing canonical failures. Operators must not claim the block
is fleet-effective until capture health is green on every query replica.

Repair tables are required replay history, not an optional UI feature. Startup
must verify them together with the canonical failure and replay tables.

`event-replay.enabled` defaults to `true`. Config-server reload applies changes
without restart. `hybrid-command` enforces the current value at execute time;
every `hybrid-query` worker enforces it before claiming work. Health/status
reports the effective value for each instance.

The schema migration also installs the `event_replay_ready` notification
contract. `hybrid-query` establishes its listener before its startup recovery
scan so work committed during startup cannot be stranded. Listener loss marks
health degraded and reconnects with bounded backoff; the recovery scan remains
the correctness fallback.

Startup fails with a clear schema error when required replay tables are absent.
It must not silently downgrade to a partially working mode.

There is no rollout table, rollout stage, source/host allowlist, legacy
backfill job, or requirement to enable capture, planning, and execution
separately.

## Validation Plan

### Append validation

- Reject missing transaction IDs, duplicate ordinals, inconsistent counts,
  non-contiguous membership, and cross-host members.
- Reject aggregate and graph events missing their required ordering metadata.
- Reject event data that fails its registered event-type/schema-version
  validator, and prove no event-store, outbox, notification, or failure row is
  committed.
- Prove `event_store_t` and `outbox_message_t` commit atomically.
- Prove a newly registered projection handler declares or derives a replay
  policy and satisfies the idempotency contract.
- Prove every policy declares a repair disposition and every `SCHEMA_REPAIR`
  policy resolves to a versioned schema.
- Prove a pinned registry/schema version remains usable for an already-appended
  event after a newer version is deployed, and referenced versions cannot be
  removed.
- Reject ordered `NOT_REPLAYABLE` policies and configuration that excludes a
  graph- or aggregate-ordered event.
- Smoke-test registry misconfiguration and prove portal/internal appends fail
  closed without reserving offsets or writing partial rows.

### Failure capture

- Fail one PostgreSQL transaction and verify one complete canonical candidate
  is committed with the notification and source progress.
- Fail canonical persistence and prove PostgreSQL or Kafka source progress does
  not advance.
- Redeliver the same transaction and verify idempotent failure observation.
- Crash after PostgreSQL Kafka-failure capture commits but before Kafka offset
  commit; verify redelivery resolves to the same fingerprint and failure row.
- Round-trip equivalent JSON through JSONB with different key ordering and
  whitespace; verify replay still hashes the unchanged canonical `BYTEA`, not
  the re-serialized JSONB.
- Verify historical legacy DLQ rows are ignored by candidate queries.

### Policy and planning

- Verify graph events derive `GRAPH_ROOT`.
- Verify events such as `UserDeletedEvent` derive `AGGREGATE_VERSION`.
- Verify ordinary complete unordered transactions derive `TRANSACTION_ONLY`.
- Verify an exact excluded unordered event type is rejected as
  `EVENT_NOT_REPLAYABLE`, and ordered exclusions are rejected at reload.
- Select one member and verify the complete transaction is planned.
- Verify dependency closure, deterministic order, stale-plan rejection, and
  payload-digest enforcement.
- Approve a plan, let its immutable TTL expire, and verify execute rejects it;
  pausing execution must not extend the TTL.
- Verify inline corrected data is rejected and only an approved immutable
  repair ID can change the materialized replay input.

### Repair

- Fail an aggregate event at version `N` because of invalid data while its
  projection remains at `N-1`; after canonical capture commits, verify ordinary
  submission is blocked with `AGGREGATE_REPAIR_REQUIRED`. Separately race a
  command with asynchronous capture and document that an `N+1` append may win
  before the block becomes visible.
- Verify a repair cannot change envelope, identity, transaction membership,
  aggregate version, graph revision, or fields absent from the repair schema.
- Verify original and corrected digests, changed field names, reason,
  requester, and distinct approver are durable while payload values remain out
  of API, audit, log, and metric output.
- Apply an approved repair and verify projection writes, ordering metadata,
  repair status, attempt completion, and failure status `RESOLVED` with
  resolution code `RESOLVED_BY_REPAIR` commit atomically.
- Re-run exact replay and a projection rebuild and verify both resolve the
  approved repair deterministically instead of processing the poison payload.
- Verify waiver does not apply the repair or advance projection metadata.
- Verify waiver cannot unblock an ordered scope while its projection metadata
  still has a version or revision gap.

### Execution and concurrency

- In the R2 compatibility window, verify an intersecting barrier produces
  `PAUSED` for `DATABASE_PLAIN` and `DEFERRED` for the legacy encrypted codec;
  do not claim unrelated-scope concurrency for the plain path until its deferred
  representation lands.
- Process the same transaction through `LIVE` and `REPLAY` and compare every
  projection and ordering row.
- Verify requester/approver separation and plan-hash binding.
- Verify unrelated scopes continue while a graph or aggregate barrier is
  active.
- Replay a complete transaction spanning multiple aggregate/root scopes;
  verify canonical lock ordering and that a gap in one scope prevents every
  member from executing.
- Verify deferred work drains in source order.
- Kill a worker before and after commit and prove one committed outcome.
- Verify an execute commit emits `event_replay_ready`, wakes the listener, and
  begins execution without waiting for the recovery interval.
- Drop a notification and restart or reconnect the listener; verify the startup
  or 60-second recovery scan claims the durable request.
- Run several `hybrid-query` replicas, wake all of them, and prove
  `SKIP LOCKED` plus fencing permits one committed execution.
- Leave the system idle and verify there is no one-second claim loop and no more
  than one scheduled recovery query per minute per replica.
- Push `event-replay.enabled=false` and verify every command/query instance
  reports the effective value, config generation, reload timestamp, and
  instance ID without restart; verify the fleet aggregator refuses to confirm
  pause while a replica is missing or stale.
- Verify the execute endpoint returns `REPLAY_EXECUTION_PAUSED` and workers stop
  new claims without stopping capture, planning, approval, status, or an
  in-flight transaction.
- Push `event-replay.enabled=true` and verify queued approved work resumes
  immediately without waiting for the periodic scan or duplicating an attempt.
- Run the listener through a direct/session-pooled connection and verify the
  startup self-test. Route it through transaction pooling and verify health is
  degraded while the recovery scan still preserves correctness.
- Cross the internal capture soft and hard watermarks; verify alerting and that
  source progress stops before an uncaptured replay payload is lost.

### Security and UI

- Verify gateway roles can be configured independently for all twelve
  endpoints.
- Verify a host-scoped user cannot inspect or mutate another host.
- Verify no payload, event JSON, key, header, or storage reference reaches the
  browser, log, metric, or audit record.
- Verify legacy DLQ notifications and canonical candidates have unambiguous UI
  wording.

## Future Production Hardening

The following may be added later as advanced capabilities without changing the
core replay contract:

- application-level envelope encryption and key rotation;
- immutable object storage and payload lifecycle policies;
- configurable retention and legal holds;
- operator tuning of the mandatory baseline failure-storm capacity controls;
- staged rollout and canary scopes for an existing production deployment;
- legacy migration tooling if historical replay becomes a requirement;
- rollback dry-run support for handlers proven safe for transactional dry run;
- `light-workflow` manual approval tasks;
- production-specific limits and break-glass policy.

The non-negotiable contracts are complete transaction membership, deterministic
ordering, immutable original and repair payload digests, code-level event
validation, a planner that cannot edit data, shared live and replay projection
behavior, host-scoped authorization, distinct-user approval, database-enforced
fencing, durable repair history, and durable failure capture before source
progress.
