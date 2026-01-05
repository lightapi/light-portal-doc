# PostgreSQL Pub/Sub Design

## Introduction

The PostgreSQL Pub/Sub mechanism provides an alternative to Kafka for event distribution within the light-portal architecture. It is designed for smaller deployments or environments where Kafka is not available, offering a reliable, low-latency, and strictly ordered event delivery system using native PostgreSQL features.

## Architecture

The system utilizes a hybrid **Polling + LISTEN/NOTIFY** approach to achieve both high reliability and low latency.

### 1. Logical Partitioning
To support horizontal scalability and ensure ordered processing for multi-tenant environments, the system uses logical partitioning based on the `host_id`.
- Events are distributed across a fixed number of partitions (e.g., 8 or 16).
- Partition index = `abs(hashtext(host_id::text)) % total_partitions`.
- Each partition has its own progress tracker in `consumer_offsets`.

### 2. Contiguous Offset Claiming
Within each partition, the consumer claims a batch of events using gapless logical offsets (`c_offset`).

### 3. Real-time Wake-up
To minimize latency without high-frequency polling, the system uses the PostgreSQL **LISTEN/NOTIFY** mechanism.
- A database trigger on the `outbox_message_t` table issues a `NOTIFY event_channel` whenever new messages are inserted.
- Consumers use `LISTEN event_channel` to subscribe to these real-time signals.
- The consumer loop calls `pgConn.getNotifications(timeout)` to wait for signals. This allows the consumer thread to sleep efficiently and wake up immediately when work is available, while still falling back to a poll-based check if no notification is received within the `waitPeriodMs`.

## Database Schema

### `log_counter`
Manages the global version/offset for the outbox.

```sql
CREATE TABLE log_counter (
    id INT PRIMARY KEY,
    next_offset BIGINT NOT NULL DEFAULT 1
);
INSERT INTO log_counter (id, next_offset) VALUES (1, 1);
```

### `consumer_offsets`
Tracks the progress of each consumer partition.

```sql
CREATE TABLE consumer_offsets (
    group_id VARCHAR(255),
    topic_id INT, -- 1 for global outbox
    partition_id INT, -- Logical partition index
    next_offset BIGINT NOT NULL DEFAULT 1,
    PRIMARY KEY (group_id, topic_id, partition_id)
);
```

### `outbox_message_t` (Modified)
Stores the events to be published.

```sql
ALTER TABLE outbox_message_t ADD COLUMN c_offset BIGINT UNIQUE;
CREATE INDEX idx_outbox_offset ON outbox_message_t (c_offset);
```

### Triggers and Functions
Enables the `NOTIFY` mechanism.

```sql
CREATE OR REPLACE FUNCTION notify_event() RETURNS TRIGGER AS $$
BEGIN
    PERFORM pg_notify('event_channel', 'new_event');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER event_trigger
AFTER INSERT ON outbox_message_t
FOR EACH STATEMENT EXECUTE FUNCTION notify_event();
```

## Implementation Details

### Offset Reservation
When inserting events, the system locks the `log_counter` row to reserve a range of offsets:
```sql
UPDATE log_counter SET next_offset = next_offset + ? WHERE id = 1 RETURNING next_offset - ?;
```

### Competing Consumer Pattern
To support multiple instances within the same consumer group, logical offsets are "claimed" in batches using an atomic `UPDATE ... RETURNING` statement. This ensures that each event is processed exactly once by one member of the group.

```sql
WITH counter_tip AS (
    SELECT (next_offset - 1) AS highest_committed_offset FROM log_counter WHERE id = 1
),
to_claim AS (
    SELECT group_id, next_offset, 
           LEAST(batch_size, GREATEST(0, (SELECT highest_committed_offset FROM counter_tip) - next_offset + 1)) AS delta
    FROM consumer_offsets 
    WHERE group_id = ? AND topic_id = 1 
    FOR UPDATE
),
upd AS (
    UPDATE consumer_offsets c SET next_offset = c.next_offset + t.delta
    FROM to_claim t 
    WHERE c.group_id = t.group_id AND c.topic_id = 1
    RETURNING t.next_offset AS start_offset, (c.next_offset - 1) AS end_offset
)
SELECT start_offset, end_offset FROM upd;
```

## Transactional User-Based Batching

To ensure that events generated from the same user are handled atomically and in order, the consumer employs a grouping strategy within its processing cycle:

1.  **Fetch Batch**: Read raw payloads from `outbox_message_t` for the assigned partition range.
2.  **Filter and Group**:
    - Filter messages by the partition hash: `abs(hashtext(host_id::text)) % ? = ?`.
    - Group the filtered messages by `host_id` and `user_id`.
3.  **Process by User**:
    - For each `(host_id, user_id)` group, execute all events in a single database transaction.

### Handling Large Atomic Transactions (Batch Extension)

If a business activity (e.g., "instance clone") generates more events than the configured `batchSize`, these events should still be processed in a single transaction to maintain system consistency.

The consumer handles this via **Atomic Batch Extension**:
1.  After fetching the initial batch (e.g., 100 events), the consumer peeks at the *next* available event in the outbox.
2.  If the next event belongs to the same `user_id` as the last event in the batch, the consumer continues fetching consecutive events for that user until the transaction boundary is found.
3.  The `consumer_offsets` are then atomically updated to reflect the true end of the extended batch.
4.  This ensures that even if 120 events were generated, all 120 are processed in a single transaction, regardless of the `batchSize` limit.

This approach ensures that even if events are processed in parallel across different partitions, events belonging to the same user are always handled in the same transaction, maintaining consistency across subsystems.

## Configuration

The consumer is configured via `db-event-consumer.yml` and runs in a Java 21 **Virtual Thread**. This ensures that the frequent `Thread.sleep` (during retries) and the blocking `pgConn.getNotifications()` (waiting for wake-ups) do not tie up native system threads, making the consumer extremely lightweight.

```yaml
groupId: user-query-group
batchSize: 100
totalPartitions: 8
partitionId: 0
waitPeriodMs: 10000
## Clean Shutdown

To ensure resources are released cleanly when the application stops, a `ShutdownHookProvider` is implemented:

- **DbEventConsumerShutdownHook**: Sets the `done` flag to stop the consumer loop and shuts down the `ExecutorService`. This ensures that the application doesn't hang on exit and that the database connections are properly returned to the pool.

## Conclusion

This native PostgreSQL implementation provides a robust alternative to Kafka, leveraging standard relational database features to maintain strict event ordering and delivery guarantees with minimal infrastructure overhead.
