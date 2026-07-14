# Event Replay Backfill and Rollout Runbook

This runbook activates event replay in bounded stages. The shipped configuration
remains `rollout.mode: DISABLED` with every feature gate off. Production
activation requires an approved change ticket, an allowlisted host, two human
operators, and retained rollout evidence.

## Safety Rules

- Apply the additive schema before deploying code that reads replay tables.
- Use `ALLOWLIST` for every canary. `ALL` is an expansion action, not a shortcut.
- Never remove a host from the allowlist while it owns an active request,
  barrier, pause, deferred transaction, or quarantine.
- Disable `executionEnabled` before rolling back worker or command code.
- Do not drop replay tables during application rollback.
- Do not rewind database/Kafka offsets, edit graph revisions, or delete
  canonical failures to make a canary pass.
- Keep legacy DLQ publication until every external consumer accepts the
  canonical compatibility envelope.

## Configuration Boundary

The global feature gate and rollout boundary must both allow an operation. A
database capture canary for one host is configured as follows:

```yaml
featureGates:
  captureEnabled: true
  kafkaPublicationEnabled: false
  planningEnabled: false
  rollbackDryRunEnabled: false
  executionEnabled: false
  breakGlassReleaseEnabled: false

rollout:
  mode: ALLOWLIST
  sourceProcessors: DATABASE
  projectionNames: portal-projection
  consumerGroups: user-query-group
  hostIds: 10000000-0000-0000-0000-000000000001
  changeTicket: CHG-000000
```

Add `KAFKA`, `portal-query`, and the Kafka group only at the Kafka capture
stage. Read, plan, dry-run, and execution APIs reject requests outside this
exact boundary. The worker claim query independently matches the host,
projection, and consumer group before it can claim an existing request.

## Ordered Rollout

1. **Schema:** Apply the fresh DDL or all dated patches through Phase 11 twice
   in a disposable database, then once in the target environment. Record
   `SCHEMA/VERIFIED` evidence.
2. **Dormant code:** Deploy both adapters, worker, APIs, UI, and operations hooks
   with all gates off and `rollout.mode: DISABLED`.
3. **Database capture:** Enable `captureEnabled` for one database projection
   group and one non-production host. Compare canonical transaction membership,
   digests, and errors with `dead_letter_queue`.
4. **Kafka capture:** Add `KAFKA` and enable `kafkaPublicationEnabled`. Prove
   canonical commit precedes offset commit and publication outage loses no
   canonical failure.
5. **Backfill:** Run bounded database backfill batches. Resolve or explicitly
   accept every open `event_replay_backfill_issue_t` row before expansion.
6. **Read-only:** Enable `planningEnabled`; verify metadata-only candidate,
   failure, plan, and status responses in Event Admin.
7. **Dry run:** Enable `rollbackDryRunEnabled` only for reviewed graph events.
   Projection rows and source offsets must remain unchanged.
8. **Non-production execution:** Enable `executionEnabled` for one host. Exercise
   lease loss, pod termination, publication and object-store outages, deferred
   capacity, and cleanup concurrency.
9. **Production canary:** Allow one approved production host. Require separate
   requester and approver identities and record the exact plan hash.
10. **Expansion:** Add handlers and hosts only after handler-specific replay,
    outage, and idempotency evidence is attached to the change ticket.
11. **Runbook cutover:** Remove offset rewind and manual graph-ledger edits from
    the supported procedure.
12. **Legacy decision:** Decide separately whether `dead_letter_queue` remains
    retained or becomes a compatibility view. Phase 11 does not delete it.

## Bounded Legacy Backfill

Backfill is an explicit CLI job and is never an application startup hook. It
uses a composite `(offset, host, group, transaction)` cursor, locks one durable
checkpoint, and refuses incomplete DLQ/outbox membership.

```bash
export EVENT_REPLAY_BACKFILL_JDBC_URL='jdbc:postgresql://db/portal'
export EVENT_REPLAY_BACKFILL_DB_USER='replay-operator'
export EVENT_REPLAY_BACKFILL_DB_PASSWORD='...'
export EVENT_REPLAY_BACKFILL_JOB_NAME='legacy-db-2026-07'
export EVENT_REPLAY_BACKFILL_CHANGE_TICKET='CHG-000000'
export EVENT_REPLAY_BACKFILL_WORKER_ID='operator@example.com'
export EVENT_REPLAY_BACKFILL_BATCH_SIZE='100'
export EVENT_REPLAY_BACKFILL_MAX_BATCHES='10'

mvn -q -pl db-provider exec:java \
  -Dexec.mainClass=net.lightapi.portal.db.replay.EventReplayBackfillMain \
  -Dexec.args=--apply
```

Use the reviewed external light-4j configuration containing replay keys,
object-store settings, capacity floors, rollout scope, and feature gates. An
evidence defect is recorded with its specific code, including
`TRANSACTION_INCOMPLETE`, `PAYLOAD_UNAVAILABLE`, or
`UNSUPPORTED_PAYLOAD_VERSION`; restore provable source evidence or leave the
item non-executable. Storage, database, crypto, and other transient failures
fail the batch without advancing the checkpoint, so the same item is retried
after the dependency is restored.

There is no coordinate-only Kafka backfill command. Legacy Kafka envelopes are
eligible only when transaction identity, complete membership, member order, and
source coordinates are independently proven; otherwise keep the DLQ evidence
and classify the item as non-executable.

## Canary and Motivating Incident

Capture the database offset and projection baseline before replay:

```bash
implementation/light-portal/scripts/event-replay-canary-snapshot.sh capture \
  "$POSTGRES_URL" "$HOST_ID" user-query-group /secure/replay-before.json
```

Then:

1. Confirm accepted graph revision is ahead of projected revision and
   `planInstanceClone/0.1.0` is absent.
2. List the canonical `ConfigInstanceApiUpdatedEvent` failure.
3. Create a `DEPENDENCY_CLOSURE` plan and verify every missing earlier revision
   and complete transaction was added.
4. Run `VALIDATE_ONLY`, then `ROLLBACK_DRY_RUN` if allowed.
5. Have a second operator approve the exact plan hash and execute it.
6. Confirm projected revision is contiguous and the endpoint rule is present.
7. Verify no database offset regressed and no request/barrier remains:

```bash
implementation/light-portal/scripts/event-replay-canary-snapshot.sh verify \
  "$POSTGRES_URL" "$HOST_ID" user-query-group /secure/replay-before.json
```

Capture Kafka offsets before and after with the platform Kafka admin tool. Every
after offset must be at least its baseline; `--reset-offsets` is prohibited.

## Preflight and Immutable Evidence

The control script checks active isolation, terminal publication failures, and
unresolved backfill issues for the target stage. It inserts append-only evidence
containing the reviewed config digest.

```bash
implementation/light-portal/scripts/event-replay-rollout-control.sh \
  "$POSTGRES_URL" "$HOST_ID" portal-query user-query-group \
  PRODUCTION_CANARY PRECHECK_PASSED "$CHANGE_TICKET" "$ACTOR" event-replay.yml
```

Record `VERIFIED` only after dashboards, APIs, offsets, audit, and alerts are
reviewed. Stage `ROLLBACK` refuses to proceed while requests, barriers, pauses,
or deferred work remain.

## Rollback

1. Stop new execute requests and set `executionEnabled: false`.
2. Run the `ROLLBACK` preflight. If blocked, retain the current worker and give
   every active scope an operator-owned recovery plan.
3. Disable dry-run, planning, Kafka publication, and capture in that order.
4. Preserve canonical tables, payload keys, objects, attempts, audit, backfill
   issues, and rollout evidence.
5. Keep the legacy compatibility path until source progress is verified.
6. Record `ROLLBACK/ROLLED_BACK` with the deployed config digest.

## Acceptance Checklist

- Database and Kafka canaries prove archive-before-progress ordering.
- Soft spill and every hard capacity stop are exercised.
- Publication/object outages, lease expiry, pod crash, stuck pause, deferred
  quarantine, and cleanup races have evidence.
- Metrics contain no host, event, transaction, request, or failure labels.
- The motivating incident is repaired without offset rewind or ledger edits.
- Operations accepts alerts, retention, recovery, and rollback procedures.
- Security accepts encryption, authorization, two-person approval, immutable
  audit, and break-glass evidence.
