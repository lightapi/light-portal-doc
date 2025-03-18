# Client Command Service
- [Github Link](https://github.com/lightapi/client-command)

## 1. CreateApp Handler

### Key Steps
1. **Extracting Data**: Extracts `hostId`, `appId`, and `appName` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID.
3. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
4. **Event Creation**: Constructs an `EventId` and `AppCreatedEvent` with the extracted data.
5. **Serialization**: Serializes the event using `AvroSerializer`.
6. **Kafka Producer**: Sends the serialized event to a Kafka topic.
7. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `hostId` (String): Host identifier.
- `appId` (String): Application identifier.
- `appName` (String): Application name.
- Additional fields: Any other fields are included in the event's value.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/client/createApp/0.1.0`

## 2. DeleteApp Handler

### Key Steps
1. **Extracting Data**: Extracts `hostId` and `appId` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID.
3. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
4. **Event Creation**: Constructs an `EventId` and `AppDeletedEvent` with the extracted data.
5. **Serialization**: Serializes the event using `AvroSerializer`.
6. **Kafka Producer**: Sends the serialized event to a Kafka topic.
7. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `hostId` (String): Host identifier.
- `appId` (String): Application identifier.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/client/deleteApp/0.1.0`

## 3. UpdateApp Handler

### Key Steps
1. **Extracting Data**: Extracts `hostId`, `appId`, and `appName` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID.
3. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
4. **Event Creation**: Constructs an `EventId` and `AppUpdatedEvent` with the extracted data.
5. **Serialization**: Serializes the event using `AvroSerializer`.
6. **Kafka Producer**: Sends the serialized event to a Kafka topic.
7. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `hostId` (String): Host identifier.
- `appId` (String): Application identifier.
- `appName` (String): Application name.
- Additional fields: Any other fields are included in the event's value.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/client/updateApp/0.1.0`
