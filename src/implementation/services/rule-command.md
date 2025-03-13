# Rule Command Service
- [Github Link](https://github.com/lightapi/rule-command)

## 1. CreateRule Handler

### How it Works with Key Steps
1. **Extracting Data**: Extracts `hostId`, `ruleId`, `ruleName`, `ruleVersion`, `ruleType`, `ruleGroup`, `ruleDesc`, `ruleOwner`, `common`, and `conditions` from the input map.
2. **Domain Retrieval**: Fetches the domain associated with the `hostId`.
3. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID.
4. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
5. **Event Creation**: Constructs an `EventId` and `RuleCreatedEvent` with the extracted data.
6. **Serialization**: Serializes the event using `AvroSerializer`.
7. **Kafka Producer**: Sends the serialized event to a Kafka topic.
8. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `hostId` (String): Host identifier.
- `ruleId` (String): Rule identifier.
- `ruleName` (String): Rule name.
- `ruleVersion` (String): Rule version.
- `ruleType` (String): Rule type.
- `ruleGroup` (String): Rule group.
- `ruleDesc` (String): Rule description.
- `ruleOwner` (String): Rule owner.
- `common` (String): Common flag.
- `conditions` (Array): Rule conditions.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/rule/createRule/0.1.0`

## 2. DeleteRule Handler

### How it Works with Key Steps
1. **Extracting Data**: Extracts `hostId` and `ruleId` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID.
3. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
4. **Event Creation**: Constructs an `EventId` and `RuleDeletedEvent` with the extracted data.
5. **Serialization**: Serializes the event using `AvroSerializer`.
6. **Kafka Producer**: Sends the serialized event to a Kafka topic.
7. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `hostId` (String): Host identifier.
- `ruleId` (String): Rule identifier.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/rule/deleteRule/0.1.0`

## 3. UpdateRule Handler

### How it Works with Key Steps
1. **Extracting Data**: Extracts `hostId`, `ruleId`, `ruleName`, `ruleVersion`, `ruleType`, `ruleGroup`, `ruleDesc`, `ruleOwner`, `common`, and `conditions` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID.
3. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
4. **Event Creation**: Constructs an `EventId` and `RuleUpdatedEvent` with the extracted data.
5. **Serialization**: Serializes the event using `AvroSerializer`.
6. **Kafka Producer**: Sends the serialized event to a Kafka topic.
7. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `hostId` (String): Host identifier.
- `ruleId` (String): Rule identifier.
- `ruleName` (String): Rule name.
- `ruleVersion` (String): Rule version.
- `ruleType` (String): Rule type.
- `ruleGroup` (String): Rule group.
- `ruleDesc` (String): Rule description.
- `ruleOwner` (String): Rule owner.
- `common` (String): Common flag.
- `conditions` (Array): Rule conditions.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/rule/updateRule/0.1.0`
