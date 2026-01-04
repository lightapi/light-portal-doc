# Distributed Scheduler Design

## Introduction

The Distributed Scheduler is a robust, highly available component of the light-portal architecture that manages the periodic execution of tasks across a cluster of application instances. It ensures that scheduled tasks are executed exactly as defined, even in a distributed environment, by using a database-backed leader election and locking mechanism.

## Architecture

The scheduler follows a **Leader-Follower** pattern to prevent redundant executions and ensure consistency.

1.  **Leader Election**: All scheduler instances compete for a global lock in the `scheduler_lock_t` table.
2.  **Lock Heartbeat**: The leader periodically updates its heartbeat to maintain ownership. If the leader fails, another instance will eventually claim the lock after a timeout.
3.  **Polling Loop**: Only the leader performs the polling of the `schedule_t` table for due tasks.
4.  **Task Execution**: When a task is due, the scheduler generates the corresponding event into the `event_store_t` and `outbox_message_t` tables and updates the `next_run_ts` for the next occurrence.

## Database Schema

### `schedule_t`
Stores the definitions and state of all scheduled tasks.

```sql
CREATE TABLE schedule_t (
    schedule_id          UUID NOT NULL,
    host_id              UUID NOT NULL,
    schedule_name        VARCHAR(126) NOT NULL,
    frequency_unit       VARCHAR(16) NOT NULL, -- e.g., 'MINUTES', 'HOURS', 'DAYS'
    frequency_time       INTEGER NOT NULL,
    start_ts             TIMESTAMP WITH TIME ZONE NOT NULL,
    next_run_ts          TIMESTAMP WITH TIME ZONE NOT NULL,
    event_topic          VARCHAR(126) NOT NULL,
    event_type           VARCHAR(126) NOT NULL,
    event_data           TEXT NOT NULL,
    aggregate_version    BIGINT DEFAULT 1 NOT NULL,
    active               BOOLEAN NOT NULL DEFAULT TRUE,
    PRIMARY KEY(schedule_id)
);
CREATE INDEX idx_schedule_active_next_run ON schedule_t (active, next_run_ts);
```

### `scheduler_lock_t`
Facilitates distributed locking and leader election.

```sql
CREATE TABLE scheduler_lock_t (
    lock_id              INT PRIMARY KEY, -- Static ID for the global scheduler lock
    instance_id          VARCHAR(255) NOT NULL, -- ID of the holding instance
    last_heartbeat       TIMESTAMP WITH TIME ZONE NOT NULL
);
```

## Implementation Details

### Leader Election and Heartbeat
Instances attempt to acquire the lock by updating the `last_heartbeat` if the existing heartbeat has expired (e.g., more than 60 seconds ago).

```sql
UPDATE scheduler_lock_t 
SET instance_id = ?, last_heartbeat = CURRENT_TIMESTAMP 
WHERE lock_id = 1 AND (instance_id = ? OR last_heartbeat < ?);
```

### Polling Mechanism
The leader queries for tasks where `next_run_ts <= CURRENT_TIMESTAMP` and `active = true`.

```sql
SELECT * FROM schedule_t 
WHERE active = true AND next_run_ts <= CURRENT_TIMESTAMP 
ORDER BY next_run_ts ASC 
LIMIT ?;
```

### Next Run Timestamp Calculation
After a task is executed, the `next_run_ts` is incremented based on the `frequency_unit` and `frequency_time`.

- **Interval-based**: Adds the specified amount of time to the `next_run_ts`.
- **Drift Correction**: To prevent cumulative drift, the calculation is based on the original `start_ts` or the previous `next_run_ts` rather than the actual execution time.

### Execution Flow
1.  Leader polls for due tasks.
2.  For each task:
    -   Starts a database transaction.
    -   Inserts the specified event into the event store and outbox message.
    -   Updates `next_run_ts` in `schedule_t`.
    -   Commits the transaction.
3.  The event is then picked up and processed by the Event Consumer (Kafka or Postgres).

## Conclusion

The Distributed Scheduler provides a reliable and scalable way to handle periodic activities within the light-portal, ensuring that tasks are executed predictably and exclusively by a single active leader at any given time.
