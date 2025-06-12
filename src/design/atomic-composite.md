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

## 