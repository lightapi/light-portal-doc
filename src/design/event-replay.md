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

### Projection handler contract

Replayable projection handlers must:

- perform database projection work through the caller's transaction;
- be idempotent for the original event ID and ordering metadata;
- use monotonic aggregate-version or graph-revision checks when ordered;
- avoid network calls, email, message publication, payment submission, or any
  other non-transactional external side effect;
- produce the same projection outcome in `LIVE` and `REPLAY` modes.

An event whose handler cannot satisfy this contract belongs in
`excludedEventTypes`.

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

Approved or already-scheduled requests remain durable while paused. An in-flight
transaction finishes or rolls back under its existing database fence. Changing
`enabled` back to `true` and pushing the configuration resumes worker claims and
queued approved work. Removing gateway permission may prevent new operator
requests, but it is not a substitute for pausing an already-approved worker
queue.

`EventReplayConfig` must be a reloadable light-4j module. Config reload clears
the cached `event-replay` document, and command handlers read the current value
before every execute transition. The wake-up dispatcher and claimant read the
current value before starting or claiming work rather than retaining only the
startup snapshot. A transition from `false` to `true` triggers an immediate
recovery scan for queued approved work. The effective execution state is
exposed through health/status so an operator can verify that the push reached
every replica. A multi-instance pause is complete only after all target
instances report `enabled=false`.

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

An ordered failure blocks new commands for the affected aggregate or graph
scope until exact replay or repair restores projection continuity. This
prevents later versions from accumulating behind a known poison event. Before
classification, ordinary commands return `AGGREGATE_PROJECTION_BLOCKED` with a
safe failure reference. Once a validated repair proposal classifies the failure
as invalid data, they return `AGGREGATE_REPAIR_REQUIRED`; the operator uses the
repair flow instead of resubmitting through the stale projection UI. Waiver may
close the operator action for diagnostic or unordered failures, but it does not
unblock an ordered scope whose projection metadata still has a gap.

`notification_t` is the latest user-facing status, not the replay ledger. The
candidate APIs read canonical failure tables only.

## Payload Storage and Encryption

Application-level encryption is not required for replay correctness and is not
mandatory in the early-development design.

PostgreSQL deployments may retain a durable reference to the original
`event_store_t` or `outbox_message_t` payload, or copy the original payload into
the canonical event member. Kafka deployments persist the original value in
the canonical member because Kafka retention cannot be assumed to preserve the
only replay source.

In either case:

- the payload is immutable after capture;
- a SHA-256 digest is stored and verified before execution;
- the UI, list APIs, logs, metrics, and audit records never expose the payload,
  Kafka key, headers, or event JSON;
- database permissions restrict direct access;
- normal database and volume encryption at rest protect the development
  deployment.

Optional envelope encryption or object storage may be added for production
when retention, PII, regulatory, or storage requirements justify it. Enabling
that option must not change planning, fingerprints, ordering, or projection
behavior, and its key configuration must not be required for ordinary
development startup.

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

## Approval and Authorization

Light Gateway is the role-based authorization boundary for all replay service
IDs. Its endpoint rules map deployment-defined role names to the JWT `role`
claim. Replay code does not hard-code `admin`, `host-admin`, `replay-admin`, or
any other role name.

The minimum authorization model is one authorized role and two distinct users:

- user A creates the replay plan;
- user B, authorized for the same host, approves the exact plan hash;
- an authorized user requests execution after approval.

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

## Isolation and Execution

Replay must not race with newer live work for the same ordered scope.

Preferred barriers are:

- `GRAPH_ROOT` for graph-revision events;
- `AGGREGATE` for aggregate-version events;
- `TRANSACTION_ONLY` isolation when the transaction has no stronger ordering
  scope.

The worker installs a fenced barrier, waits for current work in that scope to
finish, and then applies the approved items through the shared executor. Live
transactions intersecting the barrier are deferred as complete transactions;
unrelated scopes continue normally. After repair, deferred transactions drain
in source order before the barrier is removed.

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

Each `hybrid-query` replica uses a lightweight virtual thread blocked on
`LISTEN event_replay_ready`. It does not run a one-second claim loop. The
listener may use a dedicated PostgreSQL connection or a shared internal
notification dispatcher that multiplexes application channels. A blocked
virtual thread consumes no polling CPU. When notified, it submits a drain task
that claims durable requests through the existing `SKIP LOCKED`, fencing, and
lease protocol. Several replicas may wake for the same notification, but only
one can claim a request.

PostgreSQL notifications are not durable. On startup, after listener reconnect,
and once every 60 seconds while execution is enabled, each replica performs a
recovery scan for an executable request. The 60-second interval is a reviewed
application default, not another development configuration property. After a
worker drains the available requests, it returns to the blocked listener. This
reduces an idle replica from one empty query per second to at most one recovery
query per minute while preserving immediate normal execution.

While `event-replay.enabled=false`, notifications may still wake the listener,
but no drain task may claim work. Changing it back to `true` triggers an
immediate recovery scan, so queued approved work does not wait for the periodic
fallback. Kafka deployments use the same PostgreSQL replay control plane and
therefore use this wake-up mechanism as well; it is independent of the live
Pub/Sub source.

Request states are:

```text
PLANNING -> READY -> AWAITING_APPROVAL -> APPROVED
         -> INSTALLING_BARRIER -> RUNNING -> SUCCEEDED
                                        \-> FAILED
READY/AWAITING_APPROVAL/APPROVED -> CANCELLED
READY/AWAITING_APPROVAL -> EXPIRED
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
- **Excluded event type:** retain diagnostic failure metadata and report
  `EVENT_NOT_REPLAYABLE` during planning.
- **Payload missing or digest mismatch:** reject planning or execution with
  `PAYLOAD_UNAVAILABLE` or `PAYLOAD_MISMATCH`.
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
- Database permissions restrict canonical payload access to the projection and
  replay services.
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
- active barriers, deferred transactions, quarantined scopes, and abandoned
  attempts;
- worker heartbeat and claim failures;
- replay listener connection/reconnection state, notification wake-ups, and
  recovery-scan claims.

Logs include request ID, failure ID, projection, consumer group, attempt,
counts, and safe result code. They exclude payloads and unbounded exception
messages.

## Deployment Behavior

The schema migration creates the canonical failure, repair, replay request,
item, attempt, lease, barrier, deferred-work, and audit tables. After both the
schema and updated services are present:

1. replay validation, capture, APIs, and worker startup are active;
2. `hybrid-query` starts canonical capture and the replay worker;
3. `hybrid-command` accepts plan and state-transition commands;
4. new failed transactions appear in Event Admin;
5. gateway endpoint roles determine who may operate them.

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

### Failure capture

- Fail one PostgreSQL transaction and verify one complete canonical candidate
  is committed with the notification and source progress.
- Fail canonical persistence and prove PostgreSQL or Kafka source progress does
  not advance.
- Redeliver the same transaction and verify idempotent failure observation.
- Verify historical legacy DLQ rows are ignored by candidate queries.

### Policy and planning

- Verify graph events derive `GRAPH_ROOT`.
- Verify events such as `UserDeletedEvent` derive `AGGREGATE_VERSION`.
- Verify ordinary complete unordered transactions derive `TRANSACTION_ONLY`.
- Verify an exact excluded event type is rejected as `EVENT_NOT_REPLAYABLE`.
- Select one member and verify the complete transaction is planned.
- Verify dependency closure, deterministic order, stale-plan rejection, and
  payload-digest enforcement.
- Verify inline corrected data is rejected and only an approved immutable
  repair ID can change the materialized replay input.

### Repair

- Fail an aggregate event at version `N` because of invalid data while its
  projection remains at `N-1`; verify ordinary submission is blocked with
  `AGGREGATE_REPAIR_REQUIRED` instead of appending `N+1`.
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

- Process the same transaction through `LIVE` and `REPLAY` and compare every
  projection and ordering row.
- Verify requester/approver separation and plan-hash binding.
- Verify unrelated scopes continue while a graph or aggregate barrier is
  active.
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
  reports the effective value without restart.
- Verify the execute endpoint returns `REPLAY_EXECUTION_PAUSED` and workers stop
  new claims without stopping capture, planning, approval, status, or an
  in-flight transaction.
- Push `event-replay.enabled=true` and verify queued approved work resumes
  immediately without waiting for the periodic scan or duplicating an attempt.

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
- failure-storm capacity controls;
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
