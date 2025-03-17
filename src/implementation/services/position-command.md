# Position Command Service
- [Github Link](https://github.com/lightapi/position-command)

## 1. CreatePosition Handler

### Key Steps
1. **Extracting Data**: Extracts `hostId`, `positionId`, `positionDesc`, `inheritToAncestor`, and `inheritToSibling` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID.
3. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
4. **Event Creation**: Constructs an `EventId` and `PositionCreatedEvent` with the extracted data.
5. **Serialization**: Serializes the event using `AvroSerializer`.
6. **Kafka Producer**: Sends the serialized event to a Kafka topic.
7. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `hostId` (String): Host identifier.
- `positionId` (String): Position identifier.
- `positionDesc` (String): Description of the position.
- `inheritToAncestor` (String): Inheritance to ancestor flag.
- `inheritToSibling` (String): Inheritance to sibling flag.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/position/createPosition/0.1.0`

## 2. DeletePosition Handler

### Key Steps
1. **Extracting Data**: Extracts `hostId` and `positionId` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID.
3. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
4. **Event Creation**: Constructs an `EventId` and `PositionDeletedEvent` with the extracted data.
5. **Serialization**: Serializes the event using `AvroSerializer`.
6. **Kafka Producer**: Sends the serialized event to a Kafka topic.
7. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `hostId` (String): Host identifier.
- `positionId` (String): Position identifier.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/position/deletePosition/0.1.0`

## 3. UpdatePosition Handler

### Key Steps
1. **Extracting Data**: Extracts `hostId`, `positionId`, `positionDesc`, `inheritToAncestor`, and `inheritToSibling` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID.
3. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
4. **Event Creation**: Constructs an `EventId` and `PositionUpdatedEvent` with the extracted data.
5. **Serialization**: Serializes the event using `AvroSerializer`.
6. **Kafka Producer**: Sends the serialized event to a Kafka topic.
7. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `hostId` (String): Host identifier.
- `positionId` (String): Position identifier.
- `positionDesc` (String): Description of the position.
- `inheritToAncestor` (String): Inheritance to ancestor flag.
- `inheritToSibling` (String): Inheritance to sibling flag.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/position/updatePosition/0.1.0`

## 4. CreatePositionPermission Handler

### Key Steps
1. **Extracting Data**: Extracts `hostId`, `positionId`, `apiId`, `apiVersion`, and `endpoint` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID.
3. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
4. **Event Creation**: Constructs an `EventId` and `PositionPermissionCreatedEvent` with the extracted data.
5. **Serialization**: Serializes the event using `AvroSerializer`.
6. **Kafka Producer**: Sends the serialized event to a Kafka topic.
7. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `hostId` (String): Host identifier.
- `positionId` (String): Position identifier.
- `apiId` (String): API identifier.
- `apiVersion` (String): API version.
- `endpoint` (String): API endpoint.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/position/createPositionPermission/0.1.0`

## 5. DeletePositionPermission Handler

### Key Steps
1. **Extracting Data**: Extracts `hostId`, `positionId`, `apiId`, `apiVersion`, and `endpoint` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID.
3. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
4. **Event Creation**: Constructs an `EventId` and `PositionPermissionDeletedEvent` with the extracted data.
5. **Serialization**: Serializes the event using `AvroSerializer`.
6. **Kafka Producer**: Sends the serialized event to a Kafka topic.
7. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `hostId` (String): Host identifier.
- `positionId` (String): Position identifier.
- `apiId` (String): API identifier.
- `apiVersion` (String): API version.
- `endpoint` (String): API endpoint.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/position/deletePositionPermission/0.1.0`

## 6. CreatePositionUser Handler

### Key Steps
1. **Extracting Data**: Extracts `hostId` and `positionId` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID.
3. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
4. **Event Creation**: Constructs an `EventId` and `PositionUserCreatedEvent` with the extracted data.
5. **Serialization**: Serializes the event using `AvroSerializer`.
6. **Kafka Producer**: Sends the serialized event to a Kafka topic.
7. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `hostId` (String): Host identifier.
- `positionId` (String): Position identifier.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/position/createPositionUser/0.1.0`

## 7. DeletePositionUser Handler

### Key Steps
1. **Extracting Data**: Extracts `hostId` and `positionId` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID.
3. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
4. **Event Creation**: Constructs an `EventId` and `PositionUserDeletedEvent` with the extracted data.
5. **Serialization**: Serializes the event using `AvroSerializer`.
6. **Kafka Producer**: Sends the serialized event to a Kafka topic.
7. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `hostId` (String): Host identifier.
- `positionId` (String): Position identifier.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/position/deletePositionUser/0.1.0`

## 8. CreatePositionColFilter Handler

### Key Steps
1. **Extracting Data**: Extracts `hostId`, `positionId`, `apiId`, `apiVersion`, `endpoint`, and `columns` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID.
3. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
4. **Event Creation**: Constructs an `EventId` and `PositionColFilterCreatedEvent` with the extracted data.
5. **Serialization**: Serializes the event using `AvroSerializer`.
6. **Kafka Producer**: Sends the serialized event to a Kafka topic.
7. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `hostId` (String): Host identifier.
- `positionId` (String): Position identifier.
- `apiId` (String): API identifier.
- `apiVersion` (String): API version.
- `endpoint` (String): API endpoint.
- `columns` (String): Columns to be filtered.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/position/createPositionColFilter/0.1.0`

## 9. DeletePositionColFilter Handler

### Key Steps
1. **Extracting Data**: Extracts `hostId`, `positionId`, `apiId`, `apiVersion`, and `endpoint` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID.
3. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
4. **Event Creation**: Constructs an `EventId` and `PositionColFilterDeletedEvent` with the extracted data.
5. **Serialization**: Serializes the event using `AvroSerializer`.
6. **Kafka Producer**: Sends the serialized event to a Kafka topic.
7. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `hostId` (String): Host identifier.
- `positionId` (String): Position identifier.
- `apiId` (String): API identifier.
- `apiVersion` (String): API version.
- `endpoint` (String): API endpoint.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/position/deletePositionColFilter/0.1.0`

## 10. CreatePositionRowFilter Handler

### Key Steps
1. **Extracting Data**: Extracts `hostId`, `positionId`, `apiId`, `apiVersion`, `endpoint`, `colName`, `colValue`, and `operator` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID.
3. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
4. **Event Creation**: Constructs an `EventId` and `PositionRowFilterCreatedEvent` with the extracted data.
5. **Serialization**: Serializes the event using `AvroSerializer`.
6. **Kafka Producer**: Sends the serialized event to a Kafka topic.
7. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `hostId` (String): Host identifier.
- `positionId` (String): Position identifier.
- `apiId` (String): API identifier.
- `apiVersion` (String): API version.
- `endpoint` (String): API endpoint.
- `colName` (String): Column name for the filter.
- `colValue` (String): Column value for the filter.
- `operator` (String): Operator for the filter.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/position/createPositionRowFilter/0.1.0`

## 11. DeletePositionRowFilter Handler

### Key Steps
1. **Extracting Data**: Extracts `hostId`, `positionId`, `apiId`, `apiVersion`, `endpoint`, and `colName` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID.
3. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
4. **Event Creation**: Constructs an `EventId` and `PositionRowFilterDeletedEvent` with the extracted data.
5. **Serialization**: Serializes the event using `AvroSerializer`.
6. **Kafka Producer**: Sends the serialized event to a Kafka topic.
7. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `hostId` (String): Host identifier.
- `positionId` (String): Position identifier.
- `apiId` (String): API identifier.
- `apiVersion` (String): API version.
- `endpoint` (String): API endpoint.
- `colName` (String): Column name for the filter.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/position/deletePositionRowFilter/0.1.0`

## 12. UpdatePositionColFilter Handler

### Key Steps
1. **Extracting Data**: Extracts `hostId`, `positionId`, `apiId`, `apiVersion`, `endpoint`, and `columns` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID.
3. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
4. **Event Creation**: Constructs an `EventId` and `PositionColFilterUpdatedEvent` with the extracted data.
5. **Serialization**: Serializes the event using `AvroSerializer`.
6. **Kafka Producer**: Sends the serialized event to a Kafka topic.
7. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `hostId` (String): Host identifier.
- `positionId` (String): Position identifier.
- `apiId` (String): API identifier.
- `apiVersion` (String): API version.
- `endpoint` (String): API endpoint.
- `columns` (String): Columns to be filtered.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/position/updatePositionColFilter/0.1.0`

## 13. UpdatePositionRowFilter Handler

### Key Steps
1. **Extracting Data**: Extracts `hostId`, `positionId`, `apiId`, `apiVersion`, `endpoint`, `colName`, `colValue`, and `operator` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID.
3. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
4. **Event Creation**: Constructs an `EventId` and `PositionRowFilterUpdatedEvent` with the extracted data.
5. **Serialization**: Serializes the event using `AvroSerializer`.
6. **Kafka Producer**: Sends the serialized event to a Kafka topic.
7. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `hostId` (String): Host identifier.
- `positionId` (String): Position identifier.
- `apiId` (String): API identifier.
- `apiVersion` (String): API version.
- `endpoint` (String): API endpoint.
- `colName` (String): Column name for the filter.
- `colValue` (String): Column value for the filter.
- `operator` (String): Operator for the filter.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/position/updatePositionRowFilter/0.1.0`
