# Direct Event Replay Execution

## Status

Implemented on 2026-08-19 as the replacement for the asynchronous
replay-worker execution path in [Event Replay](../event-replay.md).

This design changes only the trigger and invocation path for an approved replay.
The existing replay processor, durable state, approval, fencing, barriers,
repairs, audit, and projection correctness rules remain in place.

## Decision

An authorized Portal user starts the exact replay request synchronously:

```text
Portal UI
   |
   | executeEventReplay
   v
hybrid-command
   | authorize and commit execution intent
   | forward the user's bearer token
   v
HybridQueryClient
   | POST processEventReplay; no automatic retry
   v
hybrid-query
   | process(hostId, replayRequestId, planHash)
   | on the RPC request thread
   v
hybrid-command -> Portal UI
```

There is no replay queue consumer, PostgreSQL `LISTEN`/`NOTIFY`, recovery scan,
or permanent replay execution thread. The UI action is the trigger. If the call
fails, the UI reads the durable request state and the user may try again.

`hybrid-query` remains the execution owner because it already owns the live
projection runtime and `ProjectionTransactionExecutor`. Although the database
provider is also present in current `hybrid-command` deployments, duplicating
projection execution configuration in command is unnecessary when the existing
`HybridQueryClient` path can call query directly.

## Why Change It

Replay is an exceptional operator action that occurs only a few times per
month. The current `PostgresEventReplayDispatcher` keeps a listener connection,
listener task, drain executor, and recovery executor alive on every query
replica. A notification only means that some work may exist; the worker's
`processOne()` then claims the oldest eligible request rather than the request
that caused the notification.

Direct execution is both smaller and more precise: the command names one
approved request and query processes that request only. Removing the idle
dispatcher machinery also removes its shutdown delay from `hybrid-query`.

## Goals

- Execute only the `(hostId, replayRequestId)` submitted by the user.
- Pass the user's existing bearer token from command to query.
- Reuse the existing replay processor and database safety checks.
- Preserve durable status so an ambiguous response is safe to inspect and retry.
- Perform no automatic retry in the client, command handler, query handler, or
  gateway route.
- Remove permanent threads and database sessions that exist only to wait for
  replay work.

## Non-Goals

- No queue, scheduler, workflow, Kafka topic, or outbox consumer is added.
- No machine or bootstrap token is introduced for this call.
- No background continuation or automatic recovery is added.
- No replay schema is removed in the first implementation.
- Failure capture, planning, approval, repairs, barriers, attempts, audit, and
  terminal history are unchanged.
- Live projection remains deferred for a barriered scope while its replay is
  non-terminal. Operators must be alerted if that condition becomes stale.

## RPC Contract

### Public command

Keep the existing public service:

```text
lightapi.net/user/executeEventReplay/0.1.0
```

The request remains:

```json
{
  "hostId": "019...",
  "replayRequestId": "019...",
  "planHash": "sha256:...",
  "reason": "Operator supplied reason"
}
```

The command handler remains responsible for user authorization, host scope,
plan-hash validation, reason capture, and requester/approver separation.

### Query command

Add a query-side hybrid handler:

```text
lightapi.net/user/processEventReplay/0.1.0
```

`HybridQueryClient.processEventReplay(...)` sends a POST with:

```json
{
  "host": "lightapi.net",
  "service": "user",
  "action": "processEventReplay",
  "version": "0.1.0",
  "data": {
    "hostId": "019...",
    "replayRequestId": "019...",
    "planHash": "sha256:..."
  }
}
```

The command passes the incoming user bearer token exactly as other
`HybridQueryClient` calls do. The new method must not fall back to a bootstrap
token. Query independently validates the user token, host scope, and replay
execute permission.

Register the new service in `user-query` `schema.json` and `spec.yaml` with
`scope: portal.w` and `skipAuth: false`. Add the exact endpoint to the Portal
endpoint-to-role configuration used by light-gateway. Add
`PROCESS_EVENT_REPLAY("processEventReplay", false, false)` to
`ReplayAuthorizationPolicy.Operation`. The `mutation=false` policy flag does
not mean the processor is read-only; it means this internal operation applies
intent that command already authorized and persisted, so it does not require a
new reason field in the RPC. Query loads and validates the stored reason.

This is intentionally the first `portal.w` service in `user-query`; the other
query registrations are read operations and use `portal.r`. Processing replay
applies already-approved projection mutations, and the forwarded user token
already needs `portal.w` to invoke `executeEventReplay`. Do not normalize this
registration back to `portal.r` merely because it resides in `user-query`.

`RUN_REPLAY_WORKER` machine-token authorization is not used by this path and can
be retired when the background worker is removed. A direct call to the query
handler cannot create execution intent: query accepts only the exact request
already moved by command to `INSTALLING_BARRIER`, or a resumable `RUNNING`
request. The durable request supplies the approved plan, actor, and reason.

Return metadata sufficient for the UI to refresh status:

```json
{
  "replayRequestId": "019...",
  "status": "SUCCEEDED",
  "retryable": false,
  "failureCode": null
}
```

`status` is the durable request status. A partially completed request never
claims that the whole projection was committed. The response contains no event
or repair payload.

## Execution Flow

### 1. Command commits intent

For a request in `APPROVED`, `JdbcEventReplayCommandProvider` keeps its current
transactional validation and transition to `INSTALLING_BARRIER`, including the
execution audit record. It stops calling `pg_notify`.

For a manual retry, the command handler may accept the same request in
`INSTALLING_BARRIER` or `RUNNING` without repeating the intent transition. It
still checks the authenticated user, host scope, plan hash, stored approval,
and original reason before calling query. A retry writes a distinct
`EVENT_REPLAY_EXECUTION_RETRIED` audit event.

If replay is disabled, command rejects a new execution before committing
intent. Query checks the flag again before installing a barrier or starting a
new item. Disabling replay during an item does not roll back committed work;
query stops before the next item and leaves the request resumable. Re-enabling
replay does not start work automatically—the user must retry.

### 2. Command calls query

After intent commits, `ExecuteEventReplay` calls
`HybridQueryClient.processEventReplay(...)` synchronously. No layer
automatically retries the POST.

The existing runtime maximum is 1,800 seconds. The internal command-to-query
HTTP/2 call is bounded to 1,830 seconds and may therefore keep a command worker
thread and a query worker thread occupied for up to 30 minutes. This is an
explicit tradeoff for a rare operator operation and avoids adding another
execution mechanism. The call resolves query directly through `Cluster`; it
does not traverse light-gateway. A borrowed HTTP/2 connection remains valid for
the in-flight call and is closed rather than returned idle to the pool if the
client deadline expires.

The browser-facing command request keeps the existing global
`router.maxRequestTime: 5000`. All hybrid commands share `/portal/command`, so
raising that global timeout would weaken the hung-backend protection for every
Portal command. The expected UI path is therefore:

1. gateway ends the browser request after about five seconds;
2. command's direct query call continues synchronously on its request thread;
3. query continues the replay on its request thread; and
4. Portal View treats the browser result as transport-ambiguous and uses its
   existing `getEventReplay` polling to display durable progress and completion.

This is not background execution: the original command-to-query request still
owns the replay. The gateway timeout only closes the outer browser leg. No
automatic retry occurs.

### 3. Query claims the exact request

Refactor the worker entry point from untargeted `processOne()` to a targeted
method such as:

```java
process(UUID hostId, UUID replayRequestId, String planHash)
```

The targeted claim must preserve the current claim semantics:

- lock and validate the exact request row;
- verify `INSTALLING_BARRIER` or resumable `RUNNING` state;
- reject a different host or plan hash;
- advance the fencing token with the existing compare-and-set update;
- abandon interrupted `RUNNING` attempts and reset their `RUNNING` items to
  `PENDING` before resuming; and
- keep every fenced write's existing `LEASE_LOST` row-count check.

Keep `event_replay_lease_t` for the first implementation. Use the existing
lease to reject a concurrent invocation. At claim time, set its expiry to the
remaining per-attempt execution budget; do not create a heartbeat executor. A
process failure leaves the lease to expire, after which a user may retry and
advance the fencing token. The accepted tradeoff is a worst-case recovery wait
of about 30 minutes after an early process failure, rather than today's roughly
30-second heartbeat lease recovery. Show the lease expiry in operator status
and document that wait in the runbook. No new advisory-lock design or schema
migration is required.

The execution budget is per attempt. Do not calculate a retry's remaining time
from the request's original `started_ts`. Use the existing in-memory
`Claim.started` as the deadline origin for the single request thread, but
populate it with the targeted claim time (`Instant.now()`) instead of the
currently selected request `started_ts`. This needs no schema migration; the
request's `started_ts` remains the original execution-intent audit timestamp.
Update `lockAndVerifyRequest(...)` to compare the execution deadline against
`claim.started`; changing only the `Claim` value while that method continues to
compare the request-row `started_ts` would leave retries permanently expired.

Keep `workerHeartbeatSeconds` and `workerLeaseSeconds` in the positional
`EventReplayRuntimePolicy.Limits` contract for the first release.
`PortalEventConsumerStartupHook` independently uses `workerHeartbeatSeconds`
as its live-consumer backoff, and tests such as
`JdbcProjectionFailureRepositoryPostgresTest` construct `Limits` positionally.
Remove only the `Limits.validate()` rule requiring
`workerLeaseSeconds > workerHeartbeatSeconds`; replay lease expiry is now
derived from the attempt deadline. Renaming the live-consumer backoff and later
removing obsolete fields is a separate cleanup.

### 4. Query executes on the request thread

The RPC request thread calls the existing processor phases: install the
barrier, validate immutable state, replay items through
`ProjectionTransactionExecutor`, drain deferred work, resolve failures, release
the barrier, and commit the terminal state. It does not create a worker thread.

When query returns, command returns the durable status to the UI. If the
connection is lost, query may still finish the current request; the UI resolves
that ambiguity by refreshing status, not by an automatic resubmission.

## Failure and Retry Semantics

| Durable state | User action |
| --- | --- |
| `APPROVED` | Command commits intent and calls query. |
| `INSTALLING_BARRIER` or `RUNNING`, active lease | Show current status and lease expiry; do not start a second execution. After a crashed process, expiry may take up to about 30 minutes. |
| `INSTALLING_BARRIER` or `RUNNING`, expired/no lease | An authorized manual retry resumes the exact request with a new attempt budget and fencing token. |
| `SUCCEEDED` | Return the stored success without replaying again. |
| Terminal failure/cancellation/expiry | Show the stable failure; require the existing plan, repair, or release procedure as applicable. |

Projection failures retain their existing domain status and failure code.
Network failures are not stored as projection failures. The response's
`retryable` value is derived by the server from durable state so the UI does not
classify status strings itself.

Command maps a query connection failure or lost internal response to the stable
public code `REPLAY_EXECUTION_UNAVAILABLE`. The error catalog marks it
retryable and the UI refreshes `getEventReplay` before offering Retry. Do not
return raw `ERR11000` exception text for this case.

If another invocation already owns the targeted lease, query returns the
non-retryable domain code `REPLAY_EXECUTION_IN_PROGRESS`. Command preserves
that query result, and the UI displays it after refreshing durable state.

Because there is no automatic recovery, stale barriers require explicit
operations visibility. Retain the existing `active_barriers`,
`oldest_blocked_scope_age_seconds`, and `deferred_transactions` metrics and
alert when a blocked scope reaches the existing
`blockedScopeIncidentSeconds = 900` threshold. The two-person
`releaseEventReplayBarrier` operation remains the escalation path.

## Threads, Hooks, and Observability

Remove replay execution infrastructure:

- `EventReplayWorkerStartupHook` and `EventReplayWorkerShutdownHook`;
- `PostgresEventReplayDispatcher`;
- the PostgreSQL listener connection;
- listener, drain, recovery, and lease-heartbeat executors; and
- notification and recovery-scan health fields.

Keep `EventReplayConfigStartupHook`; it validates configuration without waiting
for work.

Do not delete capture and capacity observability with the dispatcher.
`EventReplayOperationsMonitor` covers failure capture, deferred bytes, archive
capacity, publication backlog, quarantined scopes, and barrier health. Re-home
its snapshot refresh, gauges, alerts, and retention work under the existing
`OperationalCleanupStartupHook`, which is already registered in the query
deployment mirrors. It must not own a replay execution thread. Preserve the
current refresh and retention cadences rather than running the full operational
query on every metrics scrape. Schedule health refresh independently from
retention and general cleanup so a long cleanup cannot delay a stale-barrier
alert past its threshold.

## Deployment Changes

Remove the replay worker and dispatcher hook registrations from every
`hybrid-query` deployment mirror, including all nodes under:

- `portal-config-loc/all-in-lt`;
- `portal-config-loc/all-in-pg`;
- `portal-config-loc/all-in-one`;
- `portal-config-dev`;
- `light-portal-install`; and
- `implementation/light-gateway/bedrock-converse/replay-query-config`.

Keep the existing hybrid-query direct-registry mapping used by
`HybridQueryClient`. No new service, listener port, PostgreSQL channel,
advisory-lock requirement, or container is introduced.

The first release leaves `event_replay_lease_t`, schema verification, snapshot
persistence, operations repository queries, DDL, init mirrors, and schema gates
unchanged. A later cleanup may remove unused lease artifacts only after the
runtime no longer depends on them.

## Implementation Plan

### P1: Targeted processor

- Add the request/response schema, service specification, `portal.w` scope,
  endpoint-to-role mapping, error-catalog entry, and contract fixtures for
  `processEventReplay` and `REPLAY_EXECUTION_UNAVAILABLE`.
- Add `process(hostId, replayRequestId, planHash)`.
- Preserve targeted lease claim, fencing-token advancement, interrupted-attempt
  cleanup, per-attempt timing, barriers, repairs, and terminal audit behavior.
- Add `PROCESS_EVENT_REPLAY` and the query hybrid handler with user-token
  authorization and stored-reason validation.
- Update the shared authorization fixture, its Portal View copy, and the
  phase-zero contract tests in both `user-command` and `user-query`; remove
  `RUN_REPLAY_WORKER` coverage with the worker identity.

### P2: Direct command-to-query call

- Remove `pg_notify` from command execution.
- Add the bounded POST method to `HybridQueryClient` with exact user-token
  forwarding and no retry.
- Make command submission and manual retry idempotent by durable state.

### P3: Remove idle execution machinery

- Delete the dispatcher, listener, execution hooks, and replay execution
  executors.
- Retain the positional runtime-policy fields and remove only their replay-lease
  comparison so `PortalEventConsumerStartupHook` and positional test
  construction continue to compile.
- Update every deployment mirror.
- Preserve capture/capacity metrics and stale-barrier alerting outside the
  dispatcher.

### P4: UI and documentation

- Treat the expected five-second browser/gateway timeout as the primary flow:
  continue the existing three-second `getEventReplay` polling until terminal.
- Use server-provided `status`, `retryable`, and `failureCode`.
- Update the main replay design and runbook to remove worker, notification,
  automatic recovery, and listener-health instructions.

## Verification

- An approved exact replay and repair replay execute through the public command.
- Query processes only the named request, never another eligible row.
- The user bearer token and host scope reach query; a bootstrap token is not
  substituted.
- A direct query call cannot execute an `APPROVED` request or alter its stored
  actor, reason, approval, or plan.
- Two concurrent calls produce one active execution; stale writes fail their
  fencing checks.
- A retry after more than 30 minutes receives a fresh attempt budget.
- Disabling replay prevents new work and does not auto-resume on re-enable.
- No client, gateway route, command handler, or query handler retries the POST.
- An ambiguous HTTP result is resolved through durable status without a second
  projection commit.
- The gateway remains at `router.maxRequestTime: 5000`; after that expected
  browser timeout, the internal command-to-query request completes the replay
  and the UI polling reaches the terminal state.
- `REPLAY_EXECUTION_UNAVAILABLE` is returned for an internal query transport
  failure that reaches command before the browser leg closes.
- A killed query process exposes the lease expiry and rejects retry until that
  expiry, with a worst-case wait of about 30 minutes.
- Stale barriers alert at 900 seconds and retain the two-person release path.
- Capture, deferred-byte, archive-capacity, publication, and quarantine metrics
  remain available after dispatcher removal.
- An idle query JVM has no replay listener, polling scan, or replay execution
  thread and stops gracefully without waiting for Compose's 30-second kill
  timeout.

## Documentation Reconciliation

After implementation, update [Event Replay](../event-replay.md), its operations
runbook, and rollout tests. The durable database state remains authoritative;
only the trigger changes from background discovery to the explicit user request.
