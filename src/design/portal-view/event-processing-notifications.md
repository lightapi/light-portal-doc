# Event Processing Notifications

Portal commands are event driven. After a command is submitted, one or more
CloudEvents are written to `event_store_t` and `outbox_message_t`. The
hybrid-query event consumer later processes the outbox rows and updates the
projection tables used by `portal-view`.

The notification page in the user profile is intended to show the user the
recent processing result for those events. Today the table and read path exist,
but `notification_t` is not populated consistently, so the page cannot provide
meaningful status.

## Current State

The command path already writes events through the common command handler:

1. The command handler validates and enriches the request.
2. It builds one or more CloudEvents.
3. It inserts those events into `event_store_t` and `outbox_message_t`.
4. The command returns before the query-side projection has necessarily run.

The query side can run through either event-processing pipeline, selected by
configuration:

- Pg-notify pipeline: `DbEventConsumerStartupHook` polls `outbox_message_t`,
  uses the table's gapless `c_offset`, groups rows by `transaction_id`, and
  writes failed transactions to the database `dead_letter_queue`.
- Kafka pipeline: a connector publishes rows from `outbox_message_t` to Kafka.
  `PortalEventConsumerStartupHook` consumes those records, groups records by the
  command-side `transaction_id`, and produces failed transactions to the Kafka
  DLQ topic when DLQ is enabled.

Both pipelines eventually call `PortalDbProvider.handleEvent(conn, event)`.
`handleEvent` dispatches the event to the projection method for that event type.
Because both pipelines process the same outbox-backed events, they should share
the same user-facing notification status model.

The notification pieces are partially present:

- `notification_t` exists in `portal-db`.
- `NotificationDataPersistenceImpl` can query `notification_t`.
- `NotificationServiceImpl` can insert a notification row.
- `user-query` exposes `getNotification`.
- `portal-view` has a notification table page.

The current gap is that notification rows are not created at the central event
processing boundary.

There is also a separate UI error in `MailMenu`: it calls `getPrivateMessage`,
whose handler currently returns an empty response. That explains the browser
error `Unexpected end of JSON input`, but it is separate from the notification
status design.

## Goals

- Show the current user the latest event processing results in the profile
  notification page.
- Record both successful and failed projection processing.
- Preserve event processing correctness even if notification insertion fails.
- Keep notification creation centralized instead of adding calls to every
  projection method.
- Support commands that emit multiple events.
- Make the read API filter by host and user by default.
- Keep enough diagnostic data to debug failed projections.
- Keep notification writes idempotent so event replay is safe.

## Non-Goals

- Do not replace `event_store_t`, `outbox_message_t`, or `dead_letter_queue`.
- Do not use notifications as the source of truth for projection state.
- Do not build a real-time push channel in the first phase.
- Do not add notification logic manually to every projection method.
- Do not expose other users' processing history to non-admin users.

## Recommended Design

Use `notification_t` as an operational projection-status table. The command
side creates `PENDING` rows at the central event publication boundary, and the
hybrid-query event consumer updates those rows with the processing result.

The primary processing-result write point should be the centralized outbox
consumer path, around the call to `PortalDbProvider.handleEvent(conn, event)`.

Recommended lifecycle:

```text
command handler
  -> event_store_t
  -> outbox_message_t
  -> notification_t PENDING row
  -> response to caller

hybrid-query consumer
  -> read outbox_message_t
  -> handleEvent(conn, event)
  -> projection table write
  -> notification_t status row
```

For command-side publication, insert or update one notification row for each
CloudEvent with status `PENDING` in the same transaction that writes
`event_store_t` and `outbox_message_t`. Leave `event_partition` and
`event_offset` null for this first insert, because the consumer has not observed
the event position yet.

For successful projection processing, update the notification row for the
CloudEvent to status `SUCCEEDED` and populate `event_partition` and
`event_offset` from the active processor's outbox position.

For failed projection processing, insert or update one notification row for each
failed CloudEvent with status `FAILED` or `DLQ`, and store the exception
message. Populate `event_partition` and `event_offset` when the processor has
that information.

## Status Model

Use one explicit `status` field. Do not keep `is_processed`; this feature is
being implemented for the first time, and a boolean cannot distinguish pending,
success, retry, DLQ, and skipped outcomes.

Recommended statuses:

| Status | Meaning |
| --- | --- |
| `PENDING` | Event accepted into `event_store_t` and `outbox_message_t`, but the active event consumer has not recorded a processing result yet. |
| `SUCCEEDED` | Event was applied to projection tables and the projection transaction committed. |
| `FAILED` | Event processing failed before the failed transaction was durably written to the configured DLQ, or the DLQ write itself failed. |
| `DLQ` | Event transaction failed in fallback mode and was durably written to the configured DLQ. |
| `SKIPPED` | Event was read by the active event consumer but intentionally ignored, such as an unhandled event type. |

The UI should show the status labels, not the underlying event pipeline. The
same status meanings apply to both pg-notify and Kafka processing.

## Schema

The existing table is close, but it is too small for operational status and has
`nonce` as `INTEGER` while event tables use `BIGINT`.

Recommended table shape:

```sql
CREATE TABLE notification_t (
    id                  UUID NOT NULL,
    host_id             UUID NOT NULL,
    user_id             UUID NOT NULL,
    nonce               BIGINT NOT NULL,
    event_class         VARCHAR(255) NOT NULL,
    event_json          TEXT NOT NULL,
    event_ts            TIMESTAMP WITH TIME ZONE NULL,
    process_ts          TIMESTAMP WITH TIME ZONE NOT NULL,
    status              VARCHAR(16) NOT NULL,
    error               VARCHAR(2048) NULL,
    aggregate_id        VARCHAR(255) NULL,
    aggregate_type      VARCHAR(255) NULL,
    aggregate_version   BIGINT NULL,
    event_partition     INTEGER NULL,
    event_offset        BIGINT NULL,
    transaction_id      UUID NULL,
    read_ts             TIMESTAMP WITH TIME ZONE NULL,
    PRIMARY KEY (host_id, id),
    FOREIGN KEY (host_id) REFERENCES host_t(host_id) ON DELETE CASCADE
);
```

`user_id` is intentionally not a foreign key to `user_t`. `PENDING` rows are
inserted on the command side before projection tables are updated, so enforcing
that projection FK would break commands such as user creation before the
projection catches up.

Recommended indexes:

```sql
CREATE INDEX idx_notification_user_process_ts
    ON notification_t (host_id, user_id, process_ts DESC);

CREATE INDEX idx_notification_status_process_ts
    ON notification_t (host_id, status, process_ts DESC);

CREATE INDEX idx_notification_transaction
    ON notification_t (host_id, transaction_id);

CREATE INDEX idx_notification_event_position
    ON notification_t (host_id, event_partition, event_offset);

CREATE INDEX idx_notification_unread_failure
    ON notification_t (host_id, user_id, process_ts DESC)
    WHERE read_ts IS NULL AND status IN ('FAILED', 'DLQ');
```

`event_partition` and `event_offset` are intentionally generic processing
position fields. They are useful for operator diagnostics, but the UI should not
label them as pg-notify or Kafka details. In the pg-notify processor,
`event_partition` is the configured logical consumer partition and
`event_offset` is `outbox_message_t.c_offset`. In the Kafka processor,
`event_partition` and `event_offset` are the consumed Kafka record partition and
offset.

Both columns are nullable. `PENDING` rows should leave them empty at initial
insert time. They are filled later by the pg-notify or Kafka processor when the
processing result changes the row to `SUCCEEDED`, `FAILED`, `DLQ`, or `SKIPPED`.

`transaction_id` remains a UUID because it is generated by the command side and
used by both event processors.

Do not store pipeline name, source topic/channel name, or DLQ destination in
`notification_t`. Those are implementation details of the configured event
pipeline. Operators can use service configuration and logs when they need
pipeline-specific diagnostics.

For existing installations, ship this as a patch:

```sql
ALTER TABLE notification_t ALTER COLUMN nonce TYPE BIGINT;
ALTER TABLE notification_t ADD COLUMN IF NOT EXISTS status VARCHAR(16);
ALTER TABLE notification_t ADD COLUMN IF NOT EXISTS event_ts TIMESTAMP WITH TIME ZONE;
ALTER TABLE notification_t ADD COLUMN IF NOT EXISTS aggregate_id VARCHAR(255);
ALTER TABLE notification_t ADD COLUMN IF NOT EXISTS aggregate_type VARCHAR(255);
ALTER TABLE notification_t ADD COLUMN IF NOT EXISTS aggregate_version BIGINT;
ALTER TABLE notification_t ADD COLUMN IF NOT EXISTS event_partition INTEGER;
ALTER TABLE notification_t ADD COLUMN IF NOT EXISTS event_offset BIGINT;
ALTER TABLE notification_t ADD COLUMN IF NOT EXISTS transaction_id UUID;
ALTER TABLE notification_t ADD COLUMN IF NOT EXISTS read_ts TIMESTAMP WITH TIME ZONE;

ALTER TABLE notification_t DROP CONSTRAINT IF EXISTS notification_t_user_id_fkey;
ALTER TABLE notification_t DROP COLUMN IF EXISTS is_processed;
ALTER TABLE notification_t ALTER COLUMN status SET NOT NULL;

CREATE INDEX IF NOT EXISTS idx_notification_unread_failure
    ON notification_t (host_id, user_id, process_ts DESC)
    WHERE read_ts IS NULL AND status IN ('FAILED', 'DLQ');
```

## Write Path

Notification writes need an explicit transaction policy. A single rule cannot
cover every status:

- Failure and DLQ notifications must be durable even when projection writes are
  rolled back.
- Success notifications must not claim success until the projection write has
  committed.
- Notification write failures should not break projection processing.

Use a `REQUIRES_NEW` style helper for notification writes that must survive a
projection rollback. In plain JDBC, this means opening a separate connection
with its own commit/rollback boundary.

For success rows, there are two safe options:

1. Commit the projection transaction first, then write `SUCCEEDED` in a separate
   notification transaction.
2. Write `SUCCEEDED` inside the projection transaction, but wrap it in a
   savepoint and treat notification insert failure as non-fatal.

The first option is the recommended default because notification failures cannot
roll back projection updates. The tradeoff is a small window where projection
has committed but the success notification is missing. That is acceptable
because `event_store_t` remains the source of truth and success notifications
are user feedback, not projection correctness.

Recommended service methods:

```java
void recordPending(Map<String, Object> event, UUID transactionId);

void recordSuccess(Map<String, Object> event, EventMetadata metadata);

void recordFailure(Map<String, Object> event, EventMetadata metadata, String error, String status);
```

`recordPending` should participate in the command-side transaction that writes
`event_store_t` and `outbox_message_t`. It may store `transaction_id`, because
that value is generated by the command side, but it must leave
`event_partition` and `event_offset` null. `recordSuccess` and `recordFailure`
should use the event-processing transaction policy described below.

`EventMetadata` should carry only pipeline-neutral data that is not inside the
CloudEvent map:

- `eventPartition`: the active processor's partition value. For pg-notify this
  is the configured logical consumer partition; for Kafka this is the consumed
  Kafka record partition.
- `eventOffset`: the active processor's offset value. For pg-notify this is
  `outbox_message_t.c_offset`; for Kafka this is the consumed Kafka record
  offset.
- `transactionId`: the command-side transaction UUID used by both processors.

Both consumers should build this metadata before calling `handleEvent`, so the
failure path still has offset and transaction context after the projection
transaction is rolled back.

Use an idempotent upsert:

```sql
INSERT INTO notification_t (...)
VALUES (...)
ON CONFLICT (host_id, id) DO UPDATE SET
    process_ts = EXCLUDED.process_ts,
    status = EXCLUDED.status,
    error = EXCLUDED.error,
    event_partition = EXCLUDED.event_partition,
    event_offset = EXCLUDED.event_offset,
    transaction_id = EXCLUDED.transaction_id;
```

This makes replay and fallback processing safe.

### Success Handling

In the normal batch path:

```text
begin projection transaction
for each event from the active pipeline:
  parse CloudEvent
  handleEvent(conn, event)
commit projection transaction

for each successfully committed event:
  recordSuccess(event, metadata) in separate notification transaction
```

Do not write `SUCCEEDED` before the projection transaction commits unless it is
part of the same transaction. If it is written in the same transaction, a
projection rollback must roll back the success row too.

The implementation can keep an in-memory list of successfully applied events
while processing the batch. After commit, loop through that list and upsert the
success notifications. If a success notification write fails, log it and
continue; do not retry the projection.

### Failure Handling

Failure rows must be written outside the failed projection transaction.

In fallback mode, processing is retried per transaction. For a failed transaction:

```text
begin projection transaction
savepoint projection_attempt
  process transaction events
on exception:
  rollback to projection_attempt or rollback projection transaction
  write failed events to database DLQ or Kafka DLQ topic
  recordFailure(event, metadata, error, "DLQ") in separate notification transaction
```

For pg-notify, the DLQ destination is the database `dead_letter_queue` table.
For Kafka, the DLQ destination is the configured Kafka DLQ topic. The failure
notification can be committed with the database DLQ transaction for pg-notify,
or in a separate notification transaction immediately after the Kafka DLQ
produce request is accepted. The key requirement is that it must not be part of
the projection work that is being rolled back.

If the database connection enters an unrecoverable error state, close it and
open a fresh connection for the DLQ and failure notification writes.

If the payload cannot be parsed as a CloudEvent, the consumer may not know the
CloudEvent id or event type. In that case, the DLQ remains the primary failure
record. If the consumer metadata still has host, user, partition, offset, and
transaction id, the consumer can create a diagnostic notification with a
generated id, but this should be treated as a best-effort operational row.

### Pending Handling

`PENDING` is part of phase one. Add pending rows at the central command-side
publication boundary that writes `event_store_t` and `outbox_message_t`.

The pending notification should be written in the same command-side transaction
as the event-store and outbox rows. If the command rolls back, the pending
notification must roll back too. Do not add pending writes to individual command
handlers.

At this stage, the notification row should contain command-known fields only:
CloudEvent id, host id, user id, nonce, event class, event JSON, event timestamp,
and transaction id. The processor-owned `event_partition` and `event_offset`
fields remain null until event processing updates the row.

## Read API

Keep `getNotification` as the main query endpoint, but tighten its contract.

Recommended request fields:

```json
{
  "hostId": "uuid",
  "userId": "uuid",
  "offset": 0,
  "limit": 25,
  "status": "SUCCEEDED",
  "eventClass": "ClientCreatedEvent",
  "nonce": "123",
  "fromTs": "2026-05-08T00:00:00Z",
  "toTs": "2026-05-08T23:59:59Z",
  "error": "duplicate key"
}
```

Recommended response:

```json
{
  "total": 1,
  "notifications": [
    {
      "id": "uuid",
      "hostId": "uuid",
      "userId": "uuid",
      "nonce": 123,
      "eventClass": "ClientCreatedEvent",
      "status": "SUCCEEDED",
      "processTs": "2026-05-08T16:12:00Z",
      "aggregateId": "host|client",
      "aggregateType": "Client",
      "aggregateVersion": 2,
      "transactionId": "uuid",
      "eventPartition": 0,
      "eventOffset": 1001,
      "error": null,
      "eventJson": "{...}"
    }
  ]
}
```

`eventPartition` and `eventOffset` are intentionally displayed as generic
position fields regardless of which event pipeline is configured. The main list
can hide them by default and show them in the detail view.

`userId` is a filter on `getNotification`, not a separate endpoint contract. The
profile notification page should always send the logged-in user's `userId`. The
admin notification page can omit `userId` to request host-wide results, or pass a
specific `userId` to narrow the host-wide view to one user.

Authorization rules:

- Normal users can query only their own token `user_id` within the selected
  `hostId`. If the request omits `userId`, the backend should apply the token
  `user_id`; if the request supplies another `userId`, the backend should reject
  it or override it with the token `user_id`.
- Admin users can query all users for the host by omitting `userId`, or filter
  to a specific user by providing `userId`.
- The backend should enforce this using token claims, not only UI filters.

## Portal View

The profile notification page should become a processing-status view.

Recommended columns:

- Time
- Status
- Event
- Aggregate
- Nonce
- Error
- Details

Recommended default filters:

- `hostId` from the selected host.
- `userId` from the logged-in user.
- No default `status` filter.
- Most recent first.
- Last 25 rows.

The UI should display concise summaries and keep full `eventJson` behind an
expandable detail row or dialog.

Show all events associated with the user, including successful, failed, and
derived events. Derived events should be visible as their own rows instead of
being collapsed under the original command transaction.

The current `processFlag` filter should be replaced by `status`. No
`is_processed` compatibility mapping is needed because this feature has not yet
started populating `notification_t`.

The header `MailMenu` should not call `getPrivateMessage` unless that handler is
restored. For notification status, add a small notification badge endpoint or
reuse `getNotification` with `limit = 5`.

The header badge should count only unread failure notifications, such as
`FAILED` and `DLQ`, and display the count in red when the count is greater than
zero.

In the list, `FAILED` and `DLQ` status badges should also use red styling.

Phase 2 adds two narrow user-query RPCs:

- `getUnreadNotificationCount`: returns unread `FAILED` and `DLQ`
  notifications for the current `hostId` and `userId`.
- `markFailureNotificationsRead`: sets `read_ts` on unread `FAILED` and `DLQ`
  notifications for the current `hostId` and `userId`.

The header uses the count endpoint for its badge and marks failures read when
the user opens the notification menu. The notification page also marks failures
read when it is opened.

### Admin Notification Page

Phase 3 should add a separate admin notification page instead of overloading the
profile notification page. The recommended location is:

- Route: `/app/event/notifications`
- Menu: `Administration` -> `Event Admin` -> `Notifications`

This page should reuse the same notification table and `getNotification` read
API, but with admin defaults:

- `hostId` from the selected host.
- No default `userId` filter, so admins see host-wide results.
- Default status filter for `FAILED` and `DLQ`, with an option to show all
  statuses.
- Filters for `userId`, `eventClass`, `status`, `transactionId`, `aggregateId`,
  processing position, time range, and error text.
- No unread badge behavior and no call to `markFailureNotificationsRead`.

The page should clearly identify itself as an admin view, such as "Admin View:
Host Notifications". Host-wide access must still be enforced by the backend
using token roles.

## Operational Cleanup

Notifications are operational history. They should not grow forever.

Recommended retention:

- Keep successful notifications for 30 to 90 days.
- Keep failed and DLQ notifications longer, such as 180 days.
- Allow host-level configuration later if needed.

Cleanup should be implemented as a generic operational cleanup process, not as
notification-specific UI or command-handler logic. The first cleanup target is
`notification_t`, but the same framework should also support other operational
tables such as `message_t` for private messages.

Recommended implementation:

- Add an `OperationalCleanupStartupHook` on the query side.
- Run cleanup on a fixed interval, such as daily, with config-driven enablement,
  interval, batch size, and per-target retention days.
- Use a single cleanup coordinator that owns multiple cleanup targets. Each
  target defines its table, timestamp column, status/type conditions if needed,
  retention duration, and batch delete SQL.
- Use a database lock, such as a PostgreSQL advisory lock or a dedicated cleanup
  lock row, so only one service instance performs cleanup at a time.
- Delete in bounded batches to avoid long table locks and large transactions.
- Use a separate database connection and transaction for cleanup work.
- Log cleanup failures and continue service startup; cleanup failure must not
  block query APIs or event processing.

Do not use `schedule_t` directly for this cleanup. That scheduler is business
workflow infrastructure that emits events into `event_store_t` and
`outbox_message_t`. Operational cleanup is local maintenance and should stay out
of the event-processing path.

Example notification cleanup:

```sql
WITH doomed AS (
    SELECT host_id, id
    FROM notification_t
    WHERE (status IN ('SUCCEEDED', 'SKIPPED') AND process_ts < ?)
       OR (status IN ('FAILED', 'DLQ') AND process_ts < ?)
    ORDER BY process_ts
    LIMIT ?
)
DELETE FROM notification_t n
USING doomed d
WHERE n.host_id = d.host_id
  AND n.id = d.id;
```

Private-message cleanup can be another target using `message_t.send_time`:

```sql
WITH doomed AS (
    SELECT host_id, from_id, nonce
    FROM message_t
    WHERE send_time < ?
    ORDER BY send_time
    LIMIT ?
)
DELETE FROM message_t m
USING doomed d
WHERE m.host_id = d.host_id
  AND m.from_id = d.from_id
  AND m.nonce = d.nonce;
```

Recommended default cleanup targets:

| Target | Table | Retention |
| --- | --- | --- |
| Successful notification history | `notification_t` where `status IN ('SUCCEEDED', 'SKIPPED')` | 90 days |
| Failed notification history | `notification_t` where `status IN ('FAILED', 'DLQ')` | 180 days |
| Private messages | `message_t` | 180 days |

Do not delete recent `PENDING` notifications. Old `PENDING` rows should be
treated as an operational signal first because they may indicate that the event
consumer is stopped or lagging. If a hard cap is needed later, make it a
separate, longer retention policy.

## Snapshot and Promotion

`notification_t` should be treated as an operational table, not a promoted
projection table.

It should be excluded from global snapshot export and conversion alongside
`event_store_t`, `outbox_message_t`, `dead_letter_queue`, `log_counter`, and
`consumer_offsets`.

## Rollout Plan

### Phase 1: Make Notifications Useful

- Add `status` and diagnostic columns to `notification_t`.
- Add pipeline-neutral `event_partition`, `event_offset`, and
  `transaction_id` metadata.
- Change `NotificationService` to support separate notification transactions.
- Insert `PENDING` rows at the central command-side outbox publication boundary.
- Insert `SUCCEEDED` rows after successful `handleEvent`.
- Insert `DLQ` rows in fallback failure handling.
- Update `getNotification` to support `status` and correct timestamp fields.
- Update `portal-view` to use `status`, default to the current user, and show
  all user-associated events including derived events.

### Phase 2: Improve User Feedback

- Add an unread marker with `read_ts`.
- Add a small header badge query for unread `FAILED` and `DLQ` notifications
  and render the badge in red.
- Mark unread failure notifications as read when the user opens the header menu
  or the notification page.

### Phase 3: Operations

- Add a generic operational cleanup startup hook with retention targets for
  `notification_t` and `message_t`.
- Make cleanup configurable by enablement, interval, batch size, and per-target
  retention days.
- Add a database lock so only one service instance runs cleanup at a time.
- Add an admin notification page under Event Admin that uses `getNotification`
  without a `userId` filter for host-wide failures.
- Add dashboards or alerts for repeated DLQ statuses.

## Risks and Mitigations

| Risk | Mitigation |
| --- | --- |
| Notification write failure breaks event processing | Write notifications in a separate transaction after projection commit, or use savepoints for same-transaction success rows. |
| Failure notifications are rolled back with projection failures | Write `FAILED` and `DLQ` rows outside the failed projection transaction. |
| False success rows after projection rollback | Write `SUCCEEDED` only after projection commit, or keep same-transaction success rows rollback-safe. |
| Duplicate rows on replay | Use `ON CONFLICT (host_id, id) DO UPDATE`. |
| Users see other users' events | Enforce token-based authorization in `getNotification`. |
| Operational tables grow without bound | Add generic operational cleanup targets and supporting indexes. |
| Cleanup runs concurrently on multiple instances | Use a database lock so only one instance runs cleanup at a time. |
| Cleanup failure blocks query service startup | Log cleanup failures and continue startup; cleanup is maintenance, not correctness-critical. |
| Status meaning stays ambiguous | Use `status` as the only outcome field for both pg-notify and Kafka processing. |
