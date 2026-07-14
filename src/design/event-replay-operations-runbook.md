# Event Replay Operations Runbook

This runbook covers the Phase 10 health, capacity, retention, and reconciliation
controls for both database and Kafka projection processors. Preserve the
canonical failure, replay attempt, barrier, and retention evidence while
responding. Never rewind a shared source offset as an incident shortcut.

## Health states

`HEALTHY` means the canonical archive has capacity and external publication has
no known terminal failure. `DEGRADED_EXTERNAL_PUBLICATION` means the Kafka DLQ
publication path is degraded but the PostgreSQL canonical archive remains
authoritative; live source progress can continue while the outbox remains below
its hard limit. `HARD_STOP` means archive, deferred-work, or database free-space
limits can no longer guarantee durable capture. The affected source must not
advance until capacity is restored.

The dashboard uses only global gauges. Do not add host IDs, event types,
transaction IDs, failure IDs, topic names, partitions, or replay request IDs as
metric labels.

## Alert actions

### Archive, object, or deferred quota warning

1. Check `event_replay.inline_bytes`, `object_bytes`, `deferred_bytes`,
   `object_store_backlog_bytes`, and `highest_host_quota_utilization`.
2. Verify the object store is healthy and immutable versioning/object lock are
   still enabled.
3. Drain publication or deferred backlog before raising a limit.
4. Do not delete an open failure payload. Use the Event Admin follow-up plan for
   quarantined work.

At a hard limit, keep source progress stopped. Restore disk/object capacity,
run one bounded cleanup iteration, refresh health, and resume only after the
hard condition clears.

### Database free-space floor

1. Confirm the filesystem measured by `databaseCapacity.dataPath` is the
   PostgreSQL data filesystem.
2. Stop unrelated disk growth and add capacity if needed.
3. Do not manually truncate replay tables or audit evidence.
4. Allow the retention worker to remove only eligible resolved payloads and
   aged metadata. Resume processors only after `database_free_ratio` exceeds
   the hard boundary.

### Publication `TERMINAL_FAILED`

1. Treat PostgreSQL canonical failure rows as authoritative; do not replay from
   the external DLQ merely because publication failed.
2. Repair Kafka connectivity/topic/ACL configuration.
3. Preserve the terminal row until its outcome has been copied to immutable
   audit evidence. The retention worker performs that copy before deletion.
4. Confirm backlog age and terminal-failure gauges fall after recovery.

### Stuck fallback pause acknowledgement

1. Inspect worker heartbeat and acknowledged epoch for the affected projection.
2. Identify the stuck transaction or partition without releasing the barrier.
3. Restart only the unhealthy worker if its current transaction is confirmed
   rolled back.
4. Use `RELEASE_WITH_GAP` only under the separate two-person break-glass
   procedure; it is not a repair and leaves the failure open.

### Old barrier or quarantine

1. Open Event Admin and confirm the owner failure, barrier epoch, deferred bytes,
   and immutable attempt history.
2. Build a dependency-closure follow-up plan containing the owner failure.
3. Execute the exact approved hash. Do not delete deferred rows or change the
   barrier owner manually.

### Repeated `STALE_PLAN` or `LEASE_LOST`

1. Stop approving the stale hash and create a new plan from current graph and
   source metadata.
2. For lease loss, verify the old transaction released its row/advisory locks.
3. Confirm the abandoned attempt and higher fencing token are present before
   retry. Never edit fencing tokens or leases directly.

### Payload-key unavailable

1. Restore the referenced historical KEK alias from the approved key backup;
   do not rotate or replace the key ID in archived rows.
2. Validate decryption with a dry run before execution.
3. Keep the failure open if the key cannot be recovered. Do not waive solely to
   hide key loss.

### Cleanup or object reconciliation failed

1. Check `event_replay.cleanup_failures` and `reconciliation_failures` plus the
   worker error type. Payload and identifiers are deliberately absent from logs.
2. Repair database/object connectivity and retry. Cleanup batches are
   resumable and use `SKIP LOCKED`.
3. An object is deleted as orphaned only when it uses the managed `replay/v1/`
   prefix, is older than the configured grace period, and has no exact
   locator/version reference in PostgreSQL.
4. Retention evidence is append-only. Never delete or modify
   `event_replay_retention_log_t`.

## Rollout and rollback

Keep `operations.enabled` false until canonical capture, database filesystem
measurement, object-store listing support, dashboards, and alerts are verified.
Enable one query node first. Multiple nodes are safe because cleanup candidates
are locked with `FOR UPDATE SKIP LOCKED`.

To roll back the worker, set `operations.enabled` false and restart. Do not roll
back schema additions or remove retention evidence. Capture, planning, and
execution gates remain independent.

