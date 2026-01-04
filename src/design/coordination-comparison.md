# Comparison: Leader Election vs. Competing Consumer (Claiming)

The light-portal architecture employs two different distributed coordination strategies: **Leader Election** for the Scheduler and **Competing Consumers (Offset Claiming)** for the PostgreSQL Pub/Sub. Each approach is optimized for its specific use case.

## Summary Table

| Feature | Leader Election (`scheduler_lock_t`) | Host Partitioning (`consumer_offsets`) |
| :--- | :--- | :--- |
| **Primary Goal** | Exclusive Control (Safety) | Horizontal Scalability (Throughput) |
| **Mechanism** | Centralized "lock" with heartbeat. | Logical partitioning via `host_id` hash. |
| **Parallelism** | None (Single active instance). | High (N partitions, N consumers). |
| **Database Load** | Very Low (Heartbeat only). | Moderate (Per-partition updates). |
| **Failover** | Detection delay (Timeout-based). | Instant (One processor per partition). |
| **Complexity** | Simple. | Moderate (Hashing + Batching). |

---

## 1. Leader Election (Used in Distributed Scheduler)

### Why it's used for the Scheduler:
The "work" done by the scheduler is extremely lightweight: it simply checks if a task is due, inserts a one-line event into the outbox, and updates the next run time. However, the cost of **double execution** (starting the same job twice) is high.

*   **Efficiency**: Having one leader prevents multiple instances from redundant polling of the `schedule_t` table, which reduces database contention.
*   **Safety**: It provides a simple guarantee that only one controller is making decisions about what triggers and when.
*   **Scaling**: Since the scheduler doesn't do the actual "heavy lifting" (the work is done by event consumers), the leader bottleneck is rarely an issue.

## 2. Host-Based Partitioning (Used in Postgres Pub/Sub)

### Why it's used for Event Processing:
Event processing is the "Data Plane" of the system. By partitioning based on `host_id`, we emulate Kafka's partitioning behavior within PostgreSQL.

*   **Ordered Processing**: Ensures all events for a specific host (or user) are processed by the same partition sequence, avoiding race conditions on multi-tenant data.
*   **Throughput**: Multiple consumers can process different partitions in parallel. 8 partitions = 8 instances working concurrently.
*   **Implicit Load Balancing**: Distributes thousands of hosts across a fixed number of partitions.
*   **Resiliency**: Each partition's progress is independent. A failure in one host/partition doesn't block others.

## Conclusion: Which is "Better"?

Neither is universally better; they are **complementary**:

*   **Leader Election** is better for **orchestration and control**: Where you need a single "brain" to make consistent decisions and volume is manageable.
*   **Competing Consumers** is better for **workload distribution**: Where you need to process a high volume of independent tasks as quickly as possible.

In light-portal, we use the **Scheduler (Leader)** to reliably "kick off" tasks by emitting events, and the **Pub/Sub (Competing Consumers)** to at-scale process those events.
