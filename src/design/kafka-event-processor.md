# Kafka Event Processor

## Overview

The Kafka Event Processor (`PortalEventConsumerStartupHook`) consumes events from Kafka topics that are populated by Debezium CDC from the `outbox_message_t` table. It provides robust event processing with transaction-level granularity and Dead Letter Queue (DLQ) support.

## Architecture

The processor uses a **two-phase processing strategy** with automatic fallback to ensure both performance and reliability:

1. **Optimistic Batch Processing**: Attempts to process all transactions in a single database transaction for maximum throughput
2. **Granular Fallback**: On failure, switches to individual transaction processing with JDBC Savepoints to isolate failures

## Transaction ID Header

Events published to Kafka include a `transaction_id` header added by Debezium's `HeaderFrom` transform. This UUID groups all events that were generated within a single business transaction, enabling:

- **Precise transaction boundaries**: Events are grouped by their actual transaction, not just by user/host
- **Atomic DLQ handling**: Failed transactions are moved to DLQ as a complete unit
- **Backward compatibility**: Falls back to Kafka key-based grouping for events without the header

### Debezium Configuration

The `transaction_id` header is added via the Debezium connector configuration:

```json
{
  "transforms": "unwrap,addTransactionIdHeader,timestamp_converter,...",
  
  "transforms.addTransactionIdHeader.type": "org.apache.kafka.connect.transforms.HeaderFrom$Value",
  "transforms.addTransactionIdHeader.fields": "transaction_id",
  "transforms.addTransactionIdHeader.headers": "transaction_id",
  "transforms.addTransactionIdHeader.operation": "copy"
}
```

## Processing Flow

### Phase 1: Optimistic Batch Processing

```java
// 1. Group events by transaction_id from headers
Map<String, List<ConsumerRecord>> transactionBatches = groupByTransactionId(records);

// 2. Process all transactions in one DB transaction
Connection conn = ds.getConnection();
conn.setAutoCommit(false);

for (Map.Entry<String, List<ConsumerRecord>> entry : transactionBatches.entrySet()) {
    for (ConsumerRecord record : entry.getValue()) {
        updateDatabaseWithEvent(conn, record.getValue());
    }
}

conn.commit();
commitOffset(records);
```

**Benefits**:
- High throughput with single database transaction
- Minimal overhead for the common success case

### Phase 2: Fallback with Savepoints

If the batch processing fails, the processor switches to granular mode:

```java
Connection conn = ds.getConnection();
conn.setAutoCommit(false);

for (Map.Entry<String, List<ConsumerRecord>> entry : transactionBatches.entrySet()) {
    String transactionId = entry.getKey();
    List<ConsumerRecord> txRecords = entry.getValue();
    
    Savepoint sp = conn.setSavepoint("TX_" + transactionId.hashCode());
    try {
        for (ConsumerRecord record : txRecords) {
            updateDatabaseWithEvent(conn, record.getValue());
        }
        // Success - continue to next transaction
        
    } catch (Exception e) {
        // Rollback only this transaction
        conn.rollback(sp);
        
        // Send to DLQ
        produceDLQ(txRecords, e);
    }
}

// Commit all successful transactions
conn.commit();
commitOffset(allRecords);
```

**Benefits**:
- **Isolation**: Only failing transactions are moved to DLQ
- **Atomicity**: All events in a transaction are processed together or fail together
- **No Blocking**: Consumer continues processing subsequent transactions
- **Progress Guarantee**: Offsets are committed for all records (successful + DLQ'd)

## Dead Letter Queue (DLQ)

### DLQ Topic

Failed transactions are sent to a DLQ topic: `{original-topic}-dlq`

Each DLQ message includes:
- **Key**: Original Kafka key (user_id)
- **Value**: Original event payload
- **TraceabilityId**: Exception stack trace for debugging

### DLQ Producer Configuration

The DLQ producer is configured via `DeadLetterProducerStartupHook` and must be enabled in the consumer config:

```yaml
# kafka-consumer.yml
deadLetterEnabled: true
deadLetterTopicExt: -dlq
```

### Monitoring and Recovery

1. **Alerting**: Set up monitoring on the DLQ topic for new messages
2. **Investigation**: Inspect DLQ messages to identify root cause (bad data, code bug, constraint violation)
3. **Fix**: Deploy code fix or correct data inconsistency
4. **Replay**: Use a re-driver application to republish events from DLQ back to the original topic

## Transaction Grouping Logic

The processor extracts `transaction_id` from Kafka record headers:

```java
private String extractTransactionId(ConsumerRecord<Object, Object> record) {
    Map<String, String> headers = record.getHeaders();
    if (headers != null) {
        return headers.get("transaction_id");
    }
    return null;
}
```

**Fallback for Legacy Events**:
If no `transaction_id` header is present (old events before the header was added), the processor falls back to using the Kafka key for grouping:

```java
String transactionId = extractTransactionId(record);
if (transactionId == null) {
    transactionId = (String) record.getKey(); // Backward compatibility
}
```

## Error Handling Strategy

### Permanent vs Transient Errors

The processor treats all exceptions during fallback processing as **permanent errors** that warrant DLQ routing. This includes:

- **Database constraint violations** (unique, foreign key, not null)
- **Deserialization errors** (malformed JSON, schema mismatch)
- **Business logic errors** (validation failures, state inconsistencies)

**Rationale**: If an event fails during fallback (after the initial batch attempt failed), it's unlikely to succeed on retry without intervention.

### Health Monitoring

The processor sets `healthy = false` on critical failures, which triggers Kubernetes health probes to restart the pod:

- Consumer instance not found
- Framework exceptions during polling
- Fatal errors in fallback processing (after DLQ attempt)

## Configuration

Consumer configuration in `kafka-consumer.yml`:

```yaml
# Kafka consumer properties
topic: portal-event
groupId: user-query-group
keyFormat: string
valueFormat: string

# DLQ configuration
deadLetterEnabled: true
deadLetterTopicExt: -dlq

# Polling configuration
waitPeriod: 1000  # ms to wait between polls when no records
```

## Comparison with DB Event Consumer

| Feature | Kafka Consumer | DB Consumer |
|---------|---------------|-------------|
| **Event Source** | Kafka topic (via Debezium CDC) | Direct PostgreSQL polling |
| **Transaction ID** | From Kafka headers | From `outbox_message_t.transaction_id` column |
| **Grouping** | `Map<String, List<ConsumerRecord>>` | `Map<String, List<EventData>>` |
| **DLQ Target** | Kafka DLQ topic | PostgreSQL `dead_letter_queue` table |
| **Offset Management** | Kafka consumer offsets | PostgreSQL `consumer_offsets` table |
| **Fallback Mechanism** | JDBC Savepoints | JDBC Savepoints |

Both implementations share the same core DLQ philosophy: **isolate failures at the transaction level to prevent blocking the entire consumer**.

## Best Practices

1. **Idempotent Processing**: Ensure `updateDatabaseWithEvent()` logic is idempotent to handle potential reprocessing
2. **Monitor DLQ**: Set up alerts for DLQ topic activity
3. **Version Events**: Use schema versioning to handle event evolution gracefully
4. **Test Failure Scenarios**: Regularly test DLQ routing with intentional failures
5. **DLQ Retention**: Configure appropriate retention for DLQ topics to allow investigation and replay
