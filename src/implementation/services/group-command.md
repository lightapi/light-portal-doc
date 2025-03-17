# Group Command Service
- [Github Link](https://github.com/lightapi/group-command)

## 1. CreateGroup Handler

### Key Steps
1. **Extracting Data**: Extracts `hostId`, `groupId`, and `groupDesc` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID.
3. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
4. **Event Creation**: Constructs an `EventId` and `GroupCreatedEvent` with the extracted data.
5. **Serialization**: Serializes the event using `AvroSerializer`.
6. **Kafka Producer**: Sends the serialized event to a Kafka topic.
7. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `hostId` (String): Host identifier.
- `groupId` (String): Group identifier.
- `groupDesc` (String): Group description.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/group/createGroup/0.1.0`

## 2. DeleteGroup Handler

### Key Steps
1. **Extracting Data**: Extracts `hostId` and `groupId` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID.
3. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
4. **Event Creation**: Constructs an `EventId` and `GroupDeletedEvent` with the extracted data.
5. **Serialization**: Serializes the event using `AvroSerializer`.
6. **Kafka Producer**: Sends the serialized event to a Kafka topic.
7. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `hostId` (String): Host identifier.
- `groupId` (String): Group identifier.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/group/deleteGroup/0.1.0`

## 3. UpdateGroup Handler

### Key Steps
1. **Extracting Data**: Extracts `hostId`, `groupId`, and `groupDesc` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID.
3. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
4. **Event Creation**: Constructs an `EventId` and `GroupUpdatedEvent` with the extracted data.
5. **Serialization**: Serializes the event using `AvroSerializer`.
6. **Kafka Producer**: Sends the serialized event to a Kafka topic.
7. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `hostId` (String): Host identifier.
- `groupId` (String): Group identifier.
- `groupDesc` (String): Group description.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/group/updateGroup/0.1.0`

## 4. CreateGroupPermission Handler

### Key Steps
1. **Extracting Data**: Extracts `hostId`, `groupId`, `apiId`, `apiVersion`, and `endpoint` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID.
3. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
4. **Event Creation**: Constructs an `EventId` and `GroupPermissionCreatedEvent` with the extracted data.
5. **Serialization**: Serializes the event using `AvroSerializer`.
6. **Kafka Producer**: Sends the serialized event to a Kafka topic.
7. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `hostId` (String): Host identifier.
- `groupId` (String): Group identifier.
- `apiId` (String): API identifier.
- `apiVersion` (String): API version.
- `endpoint` (String): API endpoint.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/group/createGroupPermission/0.1.0`

## 5. DeleteGroupPermission Handler

### Key Steps
1. **Extracting Data**: Extracts `hostId`, `groupId`, `apiId`, `apiVersion`, and `endpoint` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID.
3. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
4. **Event Creation**: Constructs an `EventId` and `GroupPermissionDeletedEvent` with the extracted data.
5. **Serialization**: Serializes the event using `AvroSerializer`.
6. **Kafka Producer**: Sends the serialized event to a Kafka topic.
7. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `hostId` (String): Host identifier.
- `groupId` (String): Group identifier.
- `apiId` (String): API identifier.
- `apiVersion` (String): API version.
- `endpoint` (String): API endpoint.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/group/deleteGroupPermission/0.1.0`

## 6. CreateGroupUser Handler

### Key Steps
1. **Extracting Data**: Extracts `hostId`, `groupId`, and `userId` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID.
3. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
4. **Event Creation**: Constructs an `EventId` and `GroupUserCreatedEvent` with the extracted data.
5. **Serialization**: Serializes the event using `AvroSerializer`.
6. **Kafka Producer**: Sends the serialized event to a Kafka topic.
7. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `hostId` (String): Host identifier.
- `groupId` (String): Group identifier.
- `userId` (String): User identifier.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/group/createGroupUser/0.1.0`

## 7. DeleteGroupUser Handler

### Key Steps
1. **Extracting Data**: Extracts `hostId`, `groupId`, and `userId` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID.
3. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
4. **Event Creation**: Constructs an `EventId` and `GroupUserDeletedEvent` with the extracted data.
5. **Serialization**: Serializes the event using `AvroSerializer`.
6. **Kafka Producer**: Sends the serialized event to a Kafka topic.
7. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `hostId` (String): Host identifier.
- `groupId` (String): Group identifier.
- `userId` (String): User identifier.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/group/deleteGroupUser/0.1.0`

## 8. CreateGroupColFilter Handler

### Key Steps
1. **Extracting Data**: Extracts `hostId`, `groupId`, `apiId`, `apiVersion`, `endpoint`, and `columns` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID.
3. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
4. **Event Creation**: Constructs an `EventId` and `GroupColFilterCreatedEvent` with the extracted data.
5. **Serialization**: Serializes the event using `AvroSerializer`.
6. **Kafka Producer**: Sends the serialized event to a Kafka topic.
7. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `hostId` (String): Host identifier.
- `groupId` (String): Group identifier.
- `apiId` (String): API identifier.
- `apiVersion` (String): API version.
- `endpoint` (String): API endpoint.
- `columns` (String): Columns to be filtered.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/group/createGroupColFilter/0.1.0`

## 9. DeleteGroupColFilter Handler

### Key Steps
1. **Extracting Data**: Extracts `hostId`, `groupId`, `apiId`, `apiVersion`, and `endpoint` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID.
3. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
4. **Event Creation**: Constructs an `EventId` and `GroupColFilterDeletedEvent` with the extracted data.
5. **Serialization**: Serializes the event using `AvroSerializer`.
6. **Kafka Producer**: Sends the serialized event to a Kafka topic.
7. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `hostId` (String): Host identifier.
- `groupId` (String): Group identifier.
- `apiId` (String): API identifier.
- `apiVersion` (String): API version.
- `endpoint` (String): API endpoint.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/group/deleteGroupColFilter/0.1.0`

## 10. CreateGroupRowFilter Handler

### Key Steps
1. **Extracting Data**: Extracts `hostId`, `groupId`, `apiId`, `apiVersion`, `endpoint`, `colName`, `colValue`, and `operator` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID.
3. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
4. **Event Creation**: Constructs an `EventId` and `GroupRowFilterCreatedEvent` with the extracted data.
5. **Serialization**: Serializes the event using `AvroSerializer`.
6. **Kafka Producer**: Sends the serialized event to a Kafka topic.
7. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `hostId` (String): Host identifier.
- `groupId` (String): Group identifier.
- `apiId` (String): API identifier.
- `apiVersion` (String): API version.
- `endpoint` (String): API endpoint.
- `colName` (String): Column name.
- `colValue` (String): Column value.
- `operator` (String): Operator for the filter.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/group/createGroupRowFilter/0.1.0`

## 11. DeleteGroupRowFilter Handler

### Key Steps
1. **Extracting Data**: Extracts `hostId`, `groupId`, `apiId`, `apiVersion`, `endpoint`, and `colName` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID.
3. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
4. **Event Creation**: Constructs an `EventId` and `GroupRowFilterDeletedEvent` with the extracted data.
5. **Serialization**: Serializes the event using `AvroSerializer`.
6. **Kafka Producer**: Sends the serialized event to a Kafka topic.
7. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `hostId` (String): Host identifier.
- `groupId` (String): Group identifier.
- `apiId` (String): API identifier.
- `apiVersion` (String): API version.
- `endpoint` (String): API endpoint.
- `colName` (String): Column name.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/group/deleteGroupRowFilter/0.1.0`

## 12. UpdateGroupColFilter Handler

### Key Steps
1. **Extracting Data**: Extracts `hostId`, `groupId`, `apiId`, `apiVersion`, `endpoint`, and `columns` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID.
3. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
4. **Event Creation**: Constructs an `EventId` and `GroupColFilterUpdatedEvent` with the extracted data.
5. **Serialization**: Serializes the event using `AvroSerializer`.
6. **Kafka Producer**: Sends the serialized event to a Kafka topic.
7. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `hostId` (String): Host identifier.
- `groupId` (String): Group identifier.
- `apiId` (String): API identifier.
- `apiVersion` (String): API version.
- `endpoint` (String): API endpoint.
- `columns` (String): Columns to be filtered.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/group/updateGroupColFilter/0.1.0`

## 13. UpdateGroupRowFilter Handler

### Key Steps
1. **Extracting Data**: Extracts `hostId`, `groupId`, `apiId`, `apiVersion`, `endpoint`, `colName`, `colValue`, and `operator` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID.
3. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
4. **Event Creation**: Constructs an `EventId` and `GroupRowFilterUpdatedEvent` with the extracted data.
5. **Serialization**: Serializes the event using `AvroSerializer`.
6. **Kafka Producer**: Sends the serialized event to a Kafka topic.
7. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `hostId` (String): Host identifier.
- `groupId` (String): Group identifier.
- `apiId` (String): API identifier.
- `apiVersion` (String): API version.
- `endpoint` (String): API endpoint.
- `colName` (String): Column name.
- `colValue` (String): Column value.
- `operator` (String): Operator for the filter.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/group/updateGroupRowFilter/0.1.0`
