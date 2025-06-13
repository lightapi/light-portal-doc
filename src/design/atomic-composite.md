# Atomic Events vs Composite Events

## Event Design

This is a fundamental design decision in any Event Sourcing system, and the choice has significant long-term consequences for your system's flexibility, maintainability, and clarity.

The overwhelming consensus and best practice is to design **atomic events**.

Let's break down why, and then look at the trap of composite events.

---

### 1. Atomic Events (The Recommended Approach)

An atomic event represents a single, granular, immutable fact that has occurred in your system. It is the smallest possible unit of change that has meaning to the business domain.

**Example Scenario:** A user updates their profile by changing their name and their shipping address on the same form.

With atomic events, this single user action (the *Command*) would result in **two separate events** being written to the stream:

1.  `CustomerNameChanged { customerId: "123", newName: "Jane Doe" }`
2.  `CustomerAddressChanged { customerId: "123", newAddress: "..." }`

#### Why Atomic Events are Superior:

**a) Maximum Flexibility and Reusability:**
*   **Targeted Consumers:** You can have different parts of your system (projections, process managers, other microservices) subscribe to only the events they care about. The shipping department only needs to know about `CustomerAddressChanged`, while the marketing department might only care about `CustomerNameChanged`. With a composite event, both would have to subscribe and parse the larger event to see if the part they care about was updated.
*   **Future-Proofing:** Six months from now, you might need to build a new feature that triggers a welcome kit to be sent when a customer provides an address for the first time. It's trivial to add a new consumer for the `CustomerAddressChanged` event.

**b) Clear and Unambiguous Intent:**
*   Each event has a single, well-defined purpose. The name of the event, like `ItemAddedToCart`, tells you exactly what happened.
*   A composite event like `ProfileUpdated` is ambiguous. Did the name change? The address? The phone number? The password? You have to inspect the payload to understand the actual change, which makes the event stream harder to read and debug.

**c) Simplified Event Handlers (Projections):**
*   Your event handlers become small and simple. The logic for handling `CustomerAddressChanged` is focused purely on updating the address.
*   With a composite event, your handler becomes a complex series of `if` statements: `if (event.newName != null) { updateName(); } if (event.newAddress != null) { updateAddress(); } ...`. This is brittle and hard to maintain.

**d) Better for Versioning:**
*   Events are immutable and stored forever. Your system will evolve. It's much easier to version a small, focused event (e.g., add an optional field to `CustomerAddressChanged_v2`) than it is to version a large, complex composite event where any one of its dozen fields might change.

---

### 2. Composite Events (The Anti-Pattern)

A composite event attempts to bundle multiple state changes into a single, large event. It's often a result of developers mapping the event directly to the UI form or the incoming command.

Using the same scenario (updating name and address):

A composite event might look like this:

*   `CustomerProfileUpdated { customerId: "123", name: "Jane Doe", address: "...", phoneNumber: null }`

#### The Problems with this Approach:

*   **Loss of Granularity:** As explained above, you lose the ability to react to specific changes.
*   **Ambiguous Intent:** The event name doesn't tell the whole story.
*   **Sparse Payloads:** What if the user only changed their name? The `address` and `phoneNumber` fields in the event payload would be `null` or unchanged. Your consumers have to handle these sparse, optional fields, leading to more complex logic.
*   **False Cohesion:** It groups things together that only changed *at the same time* but are not necessarily part of the same *business fact*.

### 3. The Key Insight: The Role of the Aggregate

You might be thinking, "But the name and address change must be atomic! What if the system crashes after writing the first event but before the second?"

This is where the **Aggregate** from Domain-Driven Design (DDD) comes in. The Aggregate is the consistency boundary.

Here is the correct flow:

1.  **Command:** A single `UpdateCustomerProfileCommand` is sent to the system. It contains both the new name and the new address.
2.  **Aggregate:** The `Customer` Aggregate receives the command. It validates the business rules (e.g., the name isn't empty, the address is valid).
3.  **Event Generation:** If the rules pass, the Aggregate's method produces **a list of atomic events**: `[CustomerNameChanged, CustomerAddressChanged]`.
4.  **Atomic Persistence:** The Event Store then takes this list of events and persists them to the event stream **in a single, atomic transaction**. It's all or nothing. You will never have a `CustomerNameChanged` in the stream without the corresponding `CustomerAddressChanged` from the same command.

> **Key Takeaway:** The *Command* can be composite (representing a single user gesture), but it should be resolved into a set of *atomic Events*. The atomicity of *writing* these events is guaranteed by your Aggregate and Event Store, not by bundling them into a single event type.

---

### How to Design Good Atomic Events (A Checklist)

*   **Name it in the Past Tense:** `UserRegistered`, `OrderShipped`, `PasswordReset`. It's a fact that has already happened.
*   **Capture Business Intent:** Don't just record a CRUD-like change. `ProductPriceUpdated` is okay, but `PriceAdjustedForSale` is better because it captures the *why*.
*   **Ensure it's a Complete Fact:** Include all necessary data for a consumer to understand the event without having to look up previous state. For example, `ItemAddedToCart` should include `productId`, `quantity`, and `priceAtTimeOfAdding`, not just `productId`.
*   **Include Causation and Correlation IDs:** Add metadata to your events. Who triggered this change (`userId`)? What command caused it (`causationId`)? What overall business process is this part of (`correlationId`)?
*   **Think "What happened?" not "What changed?":** An event is a story. `OrderSubmitted` is a great event. A composite event like `OrderStateChanged { oldState: "Pending", newState: "Submitted" }` is far less expressive.

### Final Verdict

**Always design atomic events.**

Use the Aggregate pattern to ensure that multiple atomic events resulting from a single command are persisted transactionally. This approach gives you a system that is far more flexible, maintainable, readable, and ready for future evolution.

## Transaction

When using Kafka to handle the events, we need to handle the transactions on both producer side and consumer side along with database transation to ensure multiple events can be handled together. The choice you make here directly impacts the atomicity, ordering, and resilience of your entire system.

Let's break down the options and the correct way to handle transactions on both the producer and consumer side.

### The Correct Approach: Multiple Events, One Transaction

The best practice, by far, is to **push multiple, individual event messages per command, wrapped in a single Kafka producer transaction.**

This approach maintains the benefits of atomic events (flexibility, clarity) while guaranteeing the all-or-nothing atomicity you need.

#### How to Implement This (Producer Side)

Your service that processes the command and talks to the `Aggregate` will do the following:

1.  **Generate Events:** The `Customer` Aggregate generates the list of atomic events: `[CustomerNameChanged, CustomerAddressChanged]`.
2.  **Use Kafka Producer Transactions:** This is the key feature that makes it all work.

Here is a conceptual code flow (using Java-like syntax):

```java
// IMPORTANT: Configure your producer for transactions and idempotence
// props.put("transactional.id", "my-unique-transactional-id");
// props.put("enable.idempotence", "true");
KafkaProducer<String, Event> producer = new KafkaProducer<>(props);

// The list of events from your Aggregate
List<Event> events = customerAggregate.handle(updateProfileCommand);

// 1. Initialize the transaction
producer.initTransactions();

try {
    // 2. Begin the transaction
    producer.beginTransaction();

    // The Aggregate ID (e.g., "customer-123") is the Kafka Key
    String aggregateId = customerAggregate.getId();

    for (Event event : events) {
        // 3. Send EACH event as a SEPARATE message.
        // CRUCIAL: All events for this transaction MUST have the same key.
        // This ensures they all go to the same partition and are consumed in order.
        producer.send(new ProducerRecord<>("customer-events-topic", aggregateId, event));
    }

    // 4. Commit the transaction.
    // This makes all messages in the transaction visible to consumers atomically.
    producer.commitTransaction();

} catch (ProducerFencedException | OutOfOrderSequenceException | AuthorizationException e) {
    // These are fatal errors, we should close the producer
    producer.close();
} catch (KafkaException e) {
    // 5. If anything goes wrong, abort. None of the messages will be visible.
    producer.abortTransaction();
}

producer.close();
```

**Why this is the best way:**

*   **Atomicity Guaranteed:** Kafka guarantees that consumers will either see ALL the messages from `commitTransaction` or NONE of them (if you `abortTransaction`).
*   **Ordering Guaranteed:** By using the same key (`aggregateId`) for all events in the transaction, you ensure they are written to the same partition in the exact order you sent them. Your consumer will read them in that same order.
*   **Consumer Flexibility:** Your stream processors can now consume individual, meaningful events. A shipping-related processor can filter for and process only `CustomerAddressChanged` events, completely ignoring `CustomerNameChanged`.

---

### How to Process Events Transactionally (Consumer Side)

Now, how does your streams processor populate the database tables while maintaining consistency? This is often called the "Transactional Outbox" pattern, but in reverse—a "Transactional Inbox".

The goal is to **atomically update the database AND commit the Kafka offset**. You never want to commit an offset for a message whose database update failed.

Here is the standard, robust pattern for a custom consumer/streams processor:

1.  **Disable Kafka Auto-Commit:** This is the most important step. Your application must take manual control of committing offsets. In your consumer configuration, set `enable.auto.commit=false`.

2.  **Consume and Process in Batches:**

```java
// This is a conceptual loop for your consumer
while (true) {
    // 1. Poll for a batch of records. Kafka gives you a batch.
    ConsumerRecords<String, Event> records = consumer.poll(Duration.ofMillis(1000));

    if (records.isEmpty()) {
        continue;
    }

    // Get your database connection
    Connection dbConnection = database.getConnection();
    dbConnection.setAutoCommit(false); // Start manual DB transaction management

    try {
        // 2. Process each record in the polled batch
        for (ConsumerRecord<String, Event> record : records) {
            Event event = record.value();
            // Apply the change to the database based on the event type
            processEvent(event, dbConnection);
        }

        // 3. If all events in the batch were processed successfully, commit the database transaction
        dbConnection.commit();

        // 4. IMPORTANT: Only after the DB commit succeeds, commit the Kafka offset.
        // This tells Kafka "I have successfully and durably processed all messages up to this point."
        consumer.commitSync();

    } catch (SQLException e) {
        // 5. If the DB update fails, rollback the DB transaction...
        dbConnection.rollback();
        // ...and DO NOT commit the Kafka offset.
        // The consumer will re-poll and re-process this same batch of messages later.
        // This is why your processing logic MUST be idempotent.
        System.err.println("Database update failed. Rolling back. Will retry batch.");
        // You might want to seek to the beginning of the failed batch to be explicit
        // consumer.seek(record.topic(), record.partition(), record.offset());
    } finally {
        dbConnection.close();
    }
}
```

It is possible to handle transactions in a Kafka Streams processor, but it requires using the low-level Processor API and is significantly more complex than the standard consumer approach. You cannot achieve this with the high-level DSL (.map(), .filter(), etc.) alone. 

If your processor's only job is to read from Kafka and write to a database: Use the Plain Kafka Consumer. It is simpler, more direct, less error-prone, and purpose-built for this task. You are essentially building a custom, lightweight Kafka Connect sink.

#### The Critical Need for Idempotency

Because a failure can occur after the DB commit but *before* the Kafka offset commit, your application might restart and re-process the same batch of events.

Your database update logic **must be idempotent**. This means running the same update multiple times produces the same result as running it once.

**Examples of Idempotent Operations:**

*   **`INSERT` with a primary key:** `INSERT INTO customers (...) VALUES (...) ON DUPLICATE KEY UPDATE ...` (MySQL) or `INSERT ... ON CONFLICT ... DO UPDATE ...` (PostgreSQL).
*   **`UPDATE` statements:** `UPDATE customers SET name = 'Jane Doe' WHERE customer_id = '123'`. Running this 5 times is the same as running it once.
*   **Using Versioning:** Store a `version` or `last_processed_event_id` in your database table.
    ```sql
    UPDATE customers
    SET name = 'Jane Doe', version = 2
    WHERE customer_id = '123' AND version = 1;
    ```
    If the update tries to run again, the `WHERE` clause will not match, and no rows will be affected.

---

### Why Not Put a List of Events in One Message?

This is an anti-pattern that solves one problem (producer atomicity) by creating many more downstream.

*   **Loss of Meaning:** The fundamental unit is the event, not a list of events. A Kafka message should represent one fact.
*   **Consumer Complexity:** Every single consumer now has to be written to expect a list. It has to deserialize the list and loop through it.
*   **No Filtering:** A consumer who only cares about `CustomerAddressChanged` still has to receive and parse the entire message containing the `CustomerNameChanged` event, only to discard it. This is inefficient and tightly couples your consumers to the producer's batching behavior.
*   **Versioning Hell:** Versioning a list of events is much harder than versioning a single event.

### Summary

| Action | Recommended Approach |
| :--- | :--- |
| **Event Design** | **Atomic Events**: `CustomerNameChanged`, `CustomerAddressChanged`. |
| **Producing to Kafka** | **Multiple Messages, One Kafka Transaction**: Use `producer.beginTransaction()` and `producer.commitTransaction()`. |
| **Kafka Message Key** | **Aggregate ID**: Use the same key (e.g., `customer-123`) for all events from the same command to ensure ordering. |
| **Consuming from Kafka**| **Manual Offset Commits**: Disable auto-commit. |
| **Database Updates** | **Transactional Batch Processing**: `[Start DB Tx] -> [Process Batch] -> [Commit DB Tx] -> [Commit Kafka Offset]`. |
| **Database Logic** | **Idempotent**: Your `UPDATE`/`INSERT` logic must handle being re-run on the same event without causing errors or incorrect data. |


## Mixed Aggregates vs Single Aggregate

**In the simple batch-processing consumer example I provided, the Kafka message key is *not* being used to segregate processing.** The example processes a batch of records polled from Kafka, and that batch can indeed contain events for many different `user_id`s or `host_id`s, all mixed together in a single database transaction.

Let's break down why this happens, the implications, and how to design a consumer that *does* respect aggregate boundaries for processing.

---

### Why the Simple Batch Consumer Mixes Aggregates

1.  **Kafka's Partitioning:** You use the `user_id`/`host_id` as the key. Kafka's producer hashes this key to determine which partition the message goes to. This is **excellent** because it guarantees that all events for a single user (a single aggregate) will always go to the same partition and will be consumed in the order they were produced.

2.  **The Consumer's Polling:** A Kafka consumer is assigned one or more partitions to read from. When it calls `consumer.poll()`, it fetches a batch of records that have arrived on *all of its assigned partitions* since the last poll.

    *   If your consumer is assigned Partition 0, and events for User A, User B, and User C have all landed on Partition 0, your polled batch will contain `[EventA1, EventB1, EventC1, EventA2, ...]`.
    *   They are mixed together, but the ordering *per key* is preserved (Event A1 will always come before Event A2).

3.  **The Simple Transaction Loop:** The example loop I showed takes this entire mixed batch (`records`) and processes it within one DB transaction.

    ```java
    // This loop combines multiple aggregates into one DB transaction
    dbConnection.beginTransaction();
    for (ConsumerRecord record : records) { // 'records' contains events for User A, B, C...
        updateDatabase(record.value());
    }
    dbConnection.commit();
    ```

### Is This a Problem? (The Trade-offs)

For many use cases, processing mixed aggregates in a single batch is **perfectly fine and often more performant.**

*   **Pro: High Throughput.** Batching database commits is much more efficient than committing after every single event. Committing a transaction that updates 100 rows for 50 different users is faster than running 100 separate transactions.
*   **Con: "Noisy Neighbor" Problem.** If processing an event for User C throws an unrecoverable `SQLException`, the entire batch transaction will be rolled back. This means the valid updates for User A and User B will also be rolled back and retried. The failure of one aggregate's event processing blocks the progress of others in the same batch.
*   **Con: Loss of Concurrency.** You are processing everything serially within a single consumer thread. You aren't taking advantage of the fact that User A's events are independent of User B's events.

---

### The Better Approach: Processing per Aggregate

If you want to isolate failures and potentially parallelize work, you need to change your consumer logic to process events grouped by their key (`user_id`/`host_id`).

This pattern is more complex but far more robust for multi-tenant systems.

#### Conceptual Code for Aggregate-based Processing

This approach reorganizes the polled batch by key *before* processing.

```java
// Still disable auto-commit: enable.auto.commit=false
while (true) {
    ConsumerRecords<String, Event> records = consumer.poll(Duration.ofMillis(1000));
    if (records.isEmpty()) continue;

    // 1. Group the polled records by their key (the aggregate ID)
    Map<String, List<ConsumerRecord<String, Event>>> recordsByAggregate = new HashMap<>();
    for (ConsumerRecord<String, Event> record : records) {
        recordsByAggregate
            .computeIfAbsent(record.key(), k -> new ArrayList<>())
            .add(record);
    }

    // This map now holds the highest offset for each partition from this poll
    Map<TopicPartition, OffsetAndMetadata> offsetsToCommit = new HashMap<>();

    // 2. Process the events for EACH aggregate in its OWN transaction
    for (Map.Entry<String, List<ConsumerRecord<String, Event>>> entry : recordsByAggregate.entrySet()) {
        String aggregateId = entry.getKey();
        List<ConsumerRecord<String, Event>> aggregateEvents = entry.getValue();

        // Start a DB transaction FOR THIS AGGREGATE ONLY
        Connection dbConnection = database.getConnection();
        dbConnection.setAutoCommit(false);

        try {
            for (ConsumerRecord<String, Event> record : aggregateEvents) {
                // Your idempotent database logic
                updateDatabaseForAggregate(record.value(), dbConnection);

                // Keep track of the highest offset we've successfully processed
                TopicPartition partition = new TopicPartition(record.topic(), record.partition());
                OffsetAndMetadata offset = new OffsetAndMetadata(record.offset() + 1);
                offsetsToCommit.merge(partition, offset, (oldVal, newVal) -> newVal.offset() > oldVal.offset() ? newVal : oldVal);
            }
            // Commit the DB transaction for this one aggregate
            dbConnection.commit();

        } catch (Exception e) {
            // FAILURE for a single aggregate!
            System.err.println("Failed to process batch for aggregate: " + aggregateId + ". Rolling back.");
            dbConnection.rollback();
            // What to do now?
            // Option A: Skip this aggregate and continue with others (might break ordering).
            // Option B (Better): Stop processing the entire poll, log the poison pill, and DO NOT commit any offsets.
            // Let's assume Option B. We would break out of this loop.
            // For simplicity, we'll just log and continue, but in reality, you need a robust dead-letter queue strategy here.
        } finally {
            dbConnection.close();
        }
    }

    // 3. After attempting to process all aggregates in the batch, commit the offsets
    // for all the partitions where we made progress.
    if (!offsetsToCommit.isEmpty()) {
        consumer.commitSync(offsetsToCommit);
    }
}
```

### Key Differences and Improvements in this Pattern:

1.  **Isolation:** A failure in processing for `user-123` no longer affects `user-456`. The transaction for `user-456` can still be committed.
2.  **Correctness:** The database state for each aggregate is updated transactionally, respecting its own event sequence.
3.  **Concurrency (Potential):** This design is a stepping stone to true parallel processing. You could submit each `List<ConsumerRecord>` (the events for one aggregate) to a thread pool for processing, allowing you to update multiple users' data concurrently. This requires careful management of the offsets to commit.

### Summary and Recommendation

Your intuition was exactly right. The simple batch consumer ignores the key for processing logic, which can be a problem.

| Approach | When to Use | Key Benefit | Key Drawback |
| :--- | :--- | :--- | :--- |
| **Simple Batch Processing** | - High-throughput, simple ETL jobs. <br> - When a single failure blocking a whole batch is acceptable. <br> - Low-contention systems. | **Simplicity & Performance.** Easiest to write and often the fastest for bulk loading. | **Noisy Neighbor Problem.** One bad event can halt processing for all others in the batch. |
| **Per-Aggregate Processing**| - **Multi-tenant systems (your case).** <br> - Systems requiring high reliability and fault isolation. <br> - When you need to guarantee progress for healthy aggregates even if others are failing. | **Robustness & Isolation.** Failures are contained to a single aggregate. | **Increased Complexity.** Requires more code to group records and manage transactions and offsets carefully. |

**For your system, especially a multi-tenant one, the "Per-Aggregate Processing" model is strongly recommended.** The added complexity is a worthwhile investment for the significant gains in robustness and fault isolation. It correctly uses the Kafka key not just for partitioning, but also as the logical boundary for your downstream processing and transactions.

## DLQ and Process Flow

This is the final, crucial piece of the puzzle for building a truly resilient system. You've identified the exact scenario that separates a robust consumer from a brittle one: handling a "poison pill" message.

A poison pill is a message that your consumer cannot process successfully, no matter how many times it retries. A database constraint violation (`UNIQUE constraint failed`, `FOREIGN KEY constraint failed`) is a perfect example. If you simply roll back and retry, you will be stuck in an infinite loop, processing the same failing message forever and making no progress.

**Yes, you absolutely must handle this by routing the problematic events to a Dead Letter Queue (DLQ), which is typically another Kafka topic.**

Here is the complete, robust workflow for handling these failures.

---

### The Dead Letter Queue (DLQ) Pattern

The goal is to isolate the "bad" event(s) so that the consumer can move on and continue processing subsequent "good" events for that aggregate and others.

#### 1. The DLQ Topic

First, you create another Kafka topic specifically for these failed events. For example, if your main topic is `customer-events`, your DLQ topic might be `customer-events-dlq`.

The messages in the DLQ topic should be enriched with metadata about the failure:
*   The original event payload.
*   The original topic, partition, and offset.
*   The `consumer-group` that failed to process it.
*   A timestamp of the failure.
*   The error message or stack trace (e.g., "UNIQUE constraint failed on customers.email").

#### 2. Modified Consumer Logic with DLQ

Let's refine the "Per-Aggregate Processing" logic to include the DLQ step.

```java
// Assumes you have a separate KafkaProducer instance for the DLQ
KafkaProducer<String, DeadLetterEvent> dlqProducer = ...;

while (true) {
    ConsumerRecords<String, Event> records = consumer.poll(...);
    if (records.isEmpty()) continue;

    // Group records by aggregate key
    Map<String, List<ConsumerRecord<String, Event>>> recordsByAggregate = groupRecordsByKey(records);

    Map<TopicPartition, OffsetAndMetadata> offsetsToCommit = new HashMap<>();

    for (Map.Entry<String, List<ConsumerRecord<String, Event>>> entry : recordsByAggregate.entrySet()) {
        String aggregateId = entry.getKey();
        List<ConsumerRecord<String, Event>> aggregateEvents = entry.getValue();

        Connection dbConnection = database.getConnection();
        dbConnection.setAutoCommit(false);

        try {
            for (ConsumerRecord<String, Event> record : aggregateEvents) {
                // Your idempotent database update logic
                updateDatabaseForAggregate(record.value(), dbConnection);
            }
            // If all events for this aggregate succeed, commit the DB transaction
            dbConnection.commit();

            // And mark the final offset for this aggregate as ready to commit
            markOffsetsAsProcessed(aggregateEvents, offsetsToCommit);

        } catch (SQLException e) {
            // A "poison pill" or unrecoverable error was detected!
            dbConnection.rollback(); // Roll back any partial DB changes for this aggregate

            System.err.println("Unrecoverable error processing aggregate " + aggregateId + ". Sending to DLQ. Error: " + e.getMessage());

            // **THE DLQ LOGIC**
            // Send the entire batch of events for this failing aggregate to the DLQ.
            // It's crucial to send the whole batch to preserve their relative order.
            for (ConsumerRecord<String, Event> failedRecord : aggregateEvents) {
                DeadLetterEvent dlqEvent = createDlqEvent(failedRecord, e);
                // Use the same key to keep ordering in the DLQ
                dlqProducer.send(new ProducerRecord<>("customer-events-dlq", aggregateId, dlqEvent));
            }

            // **CRITICAL STEP:** We have now "handled" these poison pill events by sending them to the DLQ.
            // We must treat them as successfully processed from the perspective of the main topic
            // so we can commit their offsets and move on.
            markOffsetsAsProcessed(aggregateEvents, offsetsToCommit);

        } catch (Exception otherException) {
            // Handle transient errors (e.g., network timeout) differently.
            // You might want to retry these without going to the DLQ immediately.
            dbConnection.rollback();
            // Don't commit offsets, let the consumer re-poll and retry.
            System.err.println("Transient error occurred. Will retry batch.");
            // Break the loop and wait for the next poll
            break;

        } finally {
            dbConnection.close();
        }
    }

    // After processing all aggregates in the poll...
    if (!offsetsToCommit.isEmpty()) {
        // Commit the offsets for both successfully processed and DLQ'd aggregates.
        // This advances the consumer past the poison pill.
        consumer.commitSync(offsetsToCommit);
    }
}

// Helper method to create a DLQ event
private DeadLetterEvent createDlqEvent(ConsumerRecord record, Exception e) {
    // Populate with original event, error message, topic, offset, etc.
    return new DeadLetterEvent(...);
}

// Helper method to update the offsets map
private void markOffsetsAsProcessed(List<ConsumerRecord<String, Event>> records, Map<TopicPartition, OffsetAndMetadata> offsets) {
    records.forEach(rec -> {
        TopicPartition partition = new TopicPartition(rec.topic(), rec.partition());
        OffsetAndMetadata offset = new OffsetAndMetadata(rec.offset() + 1);
        offsets.merge(partition, offset, (oldVal, newVal) -> newVal.offset() > oldVal.offset() ? newVal : oldVal);
    });
}
```

### What to Do with the DLQ Topic?

The DLQ is not a garbage can. It's a hospital for sick messages. You need a strategy for managing it.

1.  **Monitoring and Alerting:** Set up alerts on the DLQ topic. A message landing here is an exceptional event that indicates a bug, bad data, or a system inconsistency. A human needs to be notified.

2.  **Manual Intervention:** An operator or developer should inspect the DLQ message.
    *   **Is it a bug in the consumer?** If so, deploy a fix to the consumer code.
    *   **Is it bad data from the producer?** For example, a `UserRegistered` event was sent with an email that already exists. The upstream service needs to be fixed.
    *   **Is it a state inconsistency?** Maybe an event arrived out of order due to a misconfiguration, and the state it expects in the database doesn't exist yet.

3.  **Reprocessing (The "Re-drive" Pattern):** Once the underlying issue is fixed (e.g., the consumer bug is patched, or the inconsistent DB state is manually corrected), you need a way to re-introduce the events from the DLQ back into the main processing flow. This is typically done with a separate utility or "re-driver" application that reads from the DLQ and publishes the *original* event back to the *original* topic.

### Differentiating Error Types

It's crucial to distinguish between:

*   **Transient Errors:** Network issues, temporary database unavailability, lock timeouts. These are retryable. The correct response is to roll back and **not commit the offset**, forcing a retry on the next poll.
*   **Permanent Errors:** DB constraint violations, deserialization errors, unrecoverable business logic failures (`NullPointerException`). These are **not** retryable. The correct response is to **route to the DLQ and commit the offset** to move on.

Your `catch` blocks should be structured to differentiate these.

```java
try {
    // ... processing logic
} catch (SQLIntegrityConstraintViolationException | DeserializationException e) {
    // PERMANENT: Rollback, send to DLQ, commit offset
} catch (SQLTransientConnectionException | LockTimeoutException e) {
    // TRANSIENT: Rollback, DO NOT commit offset, let it retry
} catch (Exception e) {
    // Generic catch-all, probably treat as permanent to be safe
    // Rollback, send to DLQ, commit offset
}
```

By implementing this complete pattern, you create a system that is not only transactional and correct but also self-healing. It can automatically isolate failures, alert you to the problem, and continue operating for all healthy aggregates, preventing a single bad event from bringing your entire system to a halt.

## Notification and Event Store

---

### 1. Is `notification_t` replacing the DLQ?

**Short Answer: No, not effectively. They serve different primary purposes, though they can complement each other.**

Let's clarify the roles:

*   **Dead Letter Queue (DLQ - Kafka Topic):**
    *   **Primary Purpose:** Operational recovery. It's a **queue of unprocessable messages** that allows your consumer to *move on* and continue processing subsequent messages. It's designed for **reprocessing** the original event once the underlying issue (code bug, bad data, external system outage) is resolved.
    *   **Nature:** A temporary holding area for *raw events* that need to be re-driven into the main processing flow. It's part of your **automated error handling and retry mechanism**.
    *   **Mechanism:** It preserves the *original message payload* (and its context) in a format easily consumable by other Kafka applications (like a re-driver).

*   **`notification_t` (Database Table):**
    *   **Primary Purpose:** Audit, visibility, and user-facing reporting. It's a **record of processing outcomes** (success/failure) and associated metadata (error messages). It's a **read model** or a **projection** for displaying status.
    *   **Nature:** A durable log or materialized view of processing activity. It's primarily for **human intervention and analysis**.
    *   **Mechanism:** Stores a summary or specific details about what happened during processing, typically in a structured way that can be queried and displayed.

**Why `notification_t` doesn't replace a DLQ:**

1.  **Reprocessing:**
    *   If an event fails and you only log it to `notification_t`, your Kafka consumer is still stuck. If it commits the offset for that failed message, the message is **lost from the Kafka topic** (due to retention policies). You'd then have to reconstruct the original message from `notification_t` and *manually re-publish it* to Kafka, which is cumbersome.
    *   A DLQ (Kafka topic) already holds the raw message and allows for a more automated re-driving process.

2.  **Operational Flow:**
    *   A DLQ is part of an automated pipeline: consumer fails -> sends to DLQ -> *consumer moves on*. Alerts are triggered.
    *   With just `notification_t`, you need an external mechanism (human reading the UI, another scheduled job) to query the table, identify failures, and trigger manual re-publishing. This is less reactive and scalable.

3.  **Mixing Concerns:**
    *   Your `notification_t` table correctly stores *processing results*. This is a **projection** of the events.
    *   The raw events themselves are what need to be re-driven.
    *   A DLQ focuses solely on holding the raw, unprocessable events.

**How they can complement each other:**

*   When an event is sent to the DLQ, you **also** log an entry in `notification_t` indicating the failure, which event was sent to DLQ, and why. This provides the user-facing visibility you want while maintaining the operational robustness of the DLQ.
*   Your re-driver for the DLQ could also update the `notification_t` entry when an event is successfully re-processed.

**Conclusion on DLQ vs. `notification_t`:** Your `notification_t` is a valuable audit and reporting tool, but it should not be your sole mechanism for handling unprocessable Kafka messages. The DLQ pattern with a dedicated Kafka topic is the industry standard for robust, scalable error handling and reprocessing in a streaming architecture.

---

### 2. Using `notification_t` as the Event Store for replay?

**Short Answer: This is generally a poor idea due to mixed concerns and potential data loss, unless your `notification_t` is *specifically designed* as a pure Event Store.**

Let's define "Event Store" in Event Sourcing:

*   **The Event Store:** This is the **single, authoritative source of truth** for your system's state. It stores **all historical domain events** (atomic, immutable facts) in the exact order they occurred, for all time (or at least for a very long retention period). It's used to:
    *   Rebuild the current state of an aggregate.
    *   Replay all events to build new read models (projections).
    *   Perform historical analysis.

**Evaluating `notification_t` as an Event Store:**

*   **"Save all the events":** This is the fundamental requirement. If it indeed stores the *full, raw, original event payload* for *every event* that enters your system, then this part is met.
*   **"Success or failure of the processing with error message":** This is where it breaks the Event Store principle. An Event Store should only contain **facts** that happened. Whether an event was processed successfully or failed is a **derived state** (a *projection* or *audit log entry*), not the event itself.
    *   **Problem 1: Mixing Concerns:** Mixing raw events with processing results violates the purity of an Event Store. It makes the Event Store harder to reason about and potentially less efficient for replay.
    *   **Problem 2: Data Integrity/Purity for Replay:** If you replay events from this table, do you replay the "success/failure" status? No, you only care about the event itself. This metadata is irrelevant for rebuilding aggregate state or building new projections.

*   **"Kafka topic might not contain all the events":** This is a critical point.
    *   If your Kafka topics have short retention (e.g., 7 days), then **yes, you absolutely need an external, durable Event Store** that retains events indefinitely.
    *   A relational database is a perfectly valid choice for an Event Store. Many Event Sourcing implementations use a relational DB table (`events` or `event_stream`) where each row is an event, uniquely identified, with the aggregate ID, sequence number, event type, and event payload.

**Recommendation for your Event Store:**

1.  **Dedicate a separate table as your Event Store:** If you want to use a database for event storage (which is fine!), create a table specifically for `events` or `event_store`.
    *   This table should only store the raw, immutable event data (ID, aggregate ID, sequence number, timestamp, type, payload).
    *   It should **not** include processing status or error messages. These are projection data.

2.  **Maintain `notification_t` as a separate read model:** Your `notification_t` table should remain exactly as it is: a valuable projection that tracks the processing success/failure for auditing and user visibility. It is derived from the events, not the source of events.

3.  **Choose your Event Store carefully:**
    *   **Kafka:** If you configure Kafka topics for **infinite retention** (or very long, e.g., years), Kafka can serve as your primary Event Store. This is powerful for stream processing.
    *   **Relational Database:** If Kafka retention is short, or if you prefer a traditional database for your Event Store, design a dedicated `events` table that conforms to the Event Store principles.
    *   **Specialized Event Stores:** There are also purpose-built Event Stores (e.g., EventStoreDB) that excel at this task.

**Combined Ideal Architecture:**

1.  **Producers** send atomic events to **Kafka topics** (e.g., `customer-events`) using Kafka transactions for atomicity.
2.  **Kafka topics** are configured with **long retention** if they are your Event Store, or short retention if you're using a separate database as Event Store.
3.  **Consumers/Stream Processors** read from Kafka.
    *   They process events (e.g., update a materialized view, send to another service).
    *   They **also persist a copy of the event to your dedicated, pure Event Store table** (if Kafka isn't your long-term store). This must happen transactionally with their other updates or be a separate, guaranteed write.
    *   They **also** update your `notification_t` table with the processing status (success/failure) for audit/UI.
    *   If an unrecoverable error occurs, they **send the original event to a DLQ topic** (e.g., `customer-events-dlq`) and **log the failure to `notification_t`**.
    *   They then commit their offsets on the main topic.
4.  **DLQ management:** Separate processes monitor the DLQ, allow manual inspection, and facilitate re-driving events back to the main topic after a fix.
5.  **Replaying:** When needed, new services or new read models can be built by replaying all events from your chosen Event Store (long-retention Kafka topics or your dedicated `events` database table).

This separation of concerns leads to a much more robust, understandable, and maintainable system.

## Event Store

When to populate the event store is a crucial design decision for ensuring the integrity and completeness of your Event Store. There are two main patterns to consider, each with its own trade-offs.

---

### Option 1: Populating the Event Store (DB Table) **Before** Publishing to Kafka (Transactional Outbox Pattern)

This is generally the **most robust and recommended approach** for ensuring **at-least-once (often effectively once) persistence** of your events. It guarantees that an event is durably stored in your Event Store *before* it is ever considered for publishing to Kafka.

#### How it works:

1.  **Command Processing:**
    *   Your `Aggregate` receives a command and generates a list of atomic events.
    *   These events are **persisted to your dedicated Event Store table (e.g., `events_store_t`) within the *same local database transaction*** as any state changes to your aggregate's materialized view (if applicable). This is the key: a single local transaction.
    *   Alongside storing the event in `events_store_t`, the event is also stored in an **"Outbox" table** (e.g., `outbox_messages`) in the same database transaction. The `outbox_messages` table serves as a temporary holding area for events that need to be published to Kafka.

2.  **Outbox Relayer/Publisher:**
    *   A separate, dedicated process (the "Outbox Relayer" or "Change Data Capture (CDC) Publisher") continuously monitors the `outbox_messages` table for new entries.
    *   When it finds new events in the `outbox_messages` table, it reads them and **publishes them to Kafka**.
    *   After successfully publishing to Kafka, it marks the event as "published" in the `outbox_messages` table or deletes it.

#### Why this is best:

*   **Atomicity Guaranteed (Local):** The critical guarantee is that the event is *either stored in your Event Store AND in the Outbox table*, or neither. If the application crashes after generating events but before publishing to Kafka, the events are durably stored in the Outbox and will be published later by the relayer.
*   **No Data Loss:** Events are never lost between generation and publication to Kafka.
*   **Decoupling:** The service generating events doesn't need to know about Kafka's availability. It only needs to commit to its local database. The Outbox Relayer handles the Kafka dependency.
*   **Effective Once:** Combined with Kafka's idempotent producer, this provides effectively once-delivery.

#### Where the `events_store_t` is populated:

*   **In the same local DB transaction where the events are generated and recorded in the Outbox table.**

---

### Option 2: Populating the Event Store (DB Table) **After** Consuming from Kafka

This approach involves two stages of atomicity: first, the producer guarantees delivery to Kafka, and then the consumer guarantees persistence from Kafka to your Event Store.

#### How it works:

1.  **Command Processing & Kafka Publishing:**
    *   Your `Aggregate` generates events.
    *   These events are **immediately published to Kafka** using Kafka producer transactions (as we discussed previously, to guarantee all events from a command are published atomically).

2.  **Consumer Processing:**
    *   Your Kafka consumer (the one responsible for populating your Event Store) reads events from Kafka.
    *   For each event (or batch of events from the same aggregate), it **persists the event to your dedicated `events_store_t` table within a local database transaction**.
    *   **Crucially:** It commits the Kafka offset *only after* the database transaction to `events_store_t` is successful.

#### Why this is generally less ideal for the *primary* Event Store:

*   **Producer Responsibility:** The service that generates the events *also* has the responsibility of publishing to Kafka. If Kafka is down or slow, the producer service might be blocked or need to implement complex retry logic.
*   **Data Durability Gap:** There's a theoretical, albeit small, window where events are generated but might not yet be durably committed to *your* authoritative `events_store_t` database if the consumer or Kafka has issues. (Kafka itself provides durability, but your *application's* Event Store is separate).
*   **Complexity for Replay:** If your consumer fails and you need to replay events, where do you replay from? Kafka? What if Kafka's retention is short? This pattern *requires* Kafka to be the true long-term Event Store, or it introduces a reliance on the consumer correctly populating the DB.

#### Where the `events_store_t` is populated:

*   **In the consumer process, within a local DB transaction, after polling from Kafka.**

---

### Answering your Specific Questions:

*   **"Where is the best place to populate this table?"**
    **The best place is in the same database transaction where the event is generated and stored in an Outbox table (Option 1).** This ensures that your authoritative Event Store (your `events_store_t` table) is always the first and most reliable source of truth.

*   **"In the second case, should we populate the failed events (events went to DLQ) to the event store?"**
    This question is about what constitutes "truth" in your Event Store.

    **No, you should populate *all original events* to the `events_store_t` table regardless of whether they later cause a processing error or end up in a DLQ.**

    **Reasoning:**
    *   The `events_store_t` is a record of *what happened in the domain*. An event like `OrderPlaced` is a fact that occurred, regardless of whether a downstream system successfully processed it or failed due to a unique constraint violation.
    *   The `events_store_t` should be pure. It tells the story of your system's state changes.
    *   The fact that an event failed to be processed by a *consumer* is a *processing audit detail* that belongs in your `notification_t` table or system logs, not in the fundamental Event Store.
    *   If you *don't* put the failed event in `events_store_t`, you are losing part of your system's history. When you rebuild state by replaying from `events_store_t`, you would miss this event, leading to an incorrect state.

    **In summary:**
    *   **`events_store_t`:** Stores *all* events that happened, always.
    *   **`notification_t`:** Stores the *status* of processing each event (success/failure, error message), as a projection.
    *   **DLQ:** Stores *unconsumable events* for reprocessing.

---

### Conclusion

I strongly recommend implementing the **Transactional Outbox pattern (Option 1)** for populating your `events_store_t` table. This pattern has become an industry best practice for achieving reliable event publishing from a database-backed service. It is more complex initially but provides superior durability and resilience compared to directly publishing to Kafka from your domain service.

And regardless of the publishing mechanism, your `events_store_t` should be a complete, immutable log of all domain events, untainted by processing outcomes.
