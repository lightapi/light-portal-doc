# Attribute Command Service
- [Github Link](https://github.com/lightapi/attribute-command)

## 1. CreateAttribute Handler

### How it Works with Key Steps
1. **Extracting Data**: Extracts `hostId`, `attributeId`, `attributeType`, and `attributeDesc` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID.
3. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
4. **Event Creation**: Constructs an `EventId` and `AttributeCreatedEvent` with the extracted data.
5. **Serialization**: Serializes the event using `AvroSerializer`.
6. **Kafka Producer**: Sends the serialized event to a Kafka topic.
7. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `hostId` (String): Host identifier.
- `attributeId` (String): Attribute identifier.
- `attributeType` (String): Type of the attribute.
- `attributeDesc` (String): Description of the attribute.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/attribute/createAttribute/0.1.0`

## 2. DeleteAttribute Handler

### How it Works with Key Steps
1. **Extracting Data**: Extracts `hostId` and `attributeId` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID.
3. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
4. **Event Creation**: Constructs an `EventId` and `AttributeDeletedEvent` with the extracted data.
5. **Serialization**: Serializes the event using `AvroSerializer`.
6. **Kafka Producer**: Sends the serialized event to a Kafka topic.
7. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `hostId` (String): Host identifier.
- `attributeId` (String): Attribute identifier.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/attribute/deleteAttribute/0.1.0`

## 3. UpdateAttribute Handler

### How it Works with Key Steps
1. **Extracting Data**: Extracts `hostId`, `attributeId`, `attributeType`, and `attributeDesc` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID.
3. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
4. **Event Creation**: Constructs an `EventId` and `AttributeUpdatedEvent` with the extracted data.
5. **Serialization**: Serializes the event using `AvroSerializer`.
6. **Kafka Producer**: Sends the serialized event to a Kafka topic.
7. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `hostId` (String): Host identifier.
- `attributeId` (String): Attribute identifier.
- `attributeType` (String): Type of the attribute.
- `attributeDesc` (String): Description of the attribute.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/attribute/updateAttribute/0.1.0`

## 4. CreateAttributePermission Handler

### How it Works with Key Steps
1. **Extracting Data**: Extracts `hostId`, `attributeId`, `attributeValue`, `apiId`, `apiVersion`, and `endpoint` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID.
3. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
4. **Event Creation**: Constructs an `EventId` and `AttributePermissionCreatedEvent` with the extracted data.
5. **Serialization**: Serializes the event using `AvroSerializer`.
6. **Kafka Producer**: Sends the serialized event to a Kafka topic.
7. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `hostId` (String): Host identifier.
- `attributeId` (String): Attribute identifier.
- `attributeValue` (String): Value of the attribute.
- `apiId` (String): API identifier.
- `apiVersion` (String): API version.
- `endpoint` (String): API endpoint.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/attribute/createAttributePermission/0.1.0`

## 5. DeleteAttributePermission Handler

### How it Works with Key Steps
1. **Extracting Data**: Extracts `hostId`, `attributeId`, `apiId`, `apiVersion`, and `endpoint` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID.
3. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
4. **Event Creation**: Constructs an `EventId` and `AttributePermissionDeletedEvent` with the extracted data.
5. **Serialization**: Serializes the event using `AvroSerializer`.
6. **Kafka Producer**: Sends the serialized event to a Kafka topic.
7. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `hostId` (String): Host identifier.
- `attributeId` (String): Attribute identifier.
- `apiId` (String): API identifier.
- `apiVersion` (String): API version.
- `endpoint` (String): API endpoint.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/attribute/deleteAttributePermission/0.1.0`

## 6. CreateAttributeUser Handler

### How it Works with Key Steps
1. **Extracting Data**: Extracts `hostId`, `attributeId`, `attributeValue`, `userId`, `startTs`, and `endTs` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID.
3. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
4. **Event Creation**: Constructs an `EventId` and `AttributeUserCreatedEvent` with the extracted data.
5. **Serialization**: Serializes the event using `AvroSerializer`.
6. **Kafka Producer**: Sends the serialized event to a Kafka topic.
7. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `hostId` (String): Host identifier.
- `attributeId` (String): Attribute identifier.
- `attributeValue` (String): Value of the attribute.
- `userId` (String): User identifier.
- `startTs` (Instant): Start timestamp.
- `endTs` (Instant): End timestamp.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/attribute/createAttributeUser/0.1.0`

## 7. DeleteAttributeUser Handler

### How it Works with Key Steps
1. **Extracting Data**: Extracts `hostId`, `attributeId`, and `userId` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID.
3. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
4. **Event Creation**: Constructs an `EventId` and `AttributeUserDeletedEvent` with the extracted data.
5. **Serialization**: Serializes the event using `AvroSerializer`.
6. **Kafka Producer**: Sends the serialized event to a Kafka topic.
7. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `hostId` (String): Host identifier.
- `attributeId` (String): Attribute identifier.
- `userId` (String): User identifier.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/attribute/deleteAttributeUser/0.1.0`

## 8. CreateAttributeColFilter Handler

### How it Works with Key Steps
1. **Extracting Data**: Extracts `hostId`, `attributeId`, `attributeValue`, `apiId`, `apiVersion`, `endpoint`, and `columns` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID.
3. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
4. **Event Creation**: Constructs an `EventId` and `AttributeColFilterCreatedEvent` with the extracted data.
5. **Serialization**: Serializes the event using `AvroSerializer`.
6. **Kafka Producer**: Sends the serialized event to a Kafka topic.
7. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `hostId` (String): Host identifier.
- `attributeId` (String): Attribute identifier.
- `attributeValue` (String): Value of the attribute.
- `apiId` (String): API identifier.
- `apiVersion` (String): API version.
- `endpoint` (String): API endpoint.
- `columns` (String): Columns to filter.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/attribute/createAttributeColFilter/0.1.0`

## 9. DeleteAttributeColFilter Handler

### How it Works with Key Steps
1. **Extracting Data**: Extracts `hostId`, `attributeId`, `apiId`, `apiVersion`, and `endpoint` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID.
3. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
4. **Event Creation**: Constructs an `EventId` and `AttributeColFilterDeletedEvent` with the extracted data.
5. **Serialization**: Serializes the event using `AvroSerializer`.
6. **Kafka Producer**: Sends the serialized event to a Kafka topic.
7. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `hostId` (String): Host identifier.
- `attributeId` (String): Attribute identifier.
- `apiId` (String): API identifier.
- `apiVersion` (String): API version.
- `endpoint` (String): API endpoint.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/attribute/deleteAttributeColFilter/0.1.0`

## 10. CreateAttributeRowFilter Handler

### How it Works with Key Steps
1. **Extracting Data**: Extracts `hostId`, `attributeId`, `attributeValue`, `apiId`, `apiVersion`, `endpoint`, `colName`, `colValue`, and `operator` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID.
3. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
4. **Event Creation**: Constructs an `EventId` and `AttributeRowFilterCreatedEvent` with the extracted data.
5. **Serialization**: Serializes the event using `AvroSerializer`.
6. **Kafka Producer**: Sends the serialized event to a Kafka topic.
7. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `hostId` (String): Host identifier.
- `attributeId` (String): Attribute identifier.
- `attributeValue` (String): Value of the attribute.
- `apiId` (String): API identifier.
- `apiVersion` (String): API version.
- `endpoint` (String): API endpoint.
- `colName` (String): Column name.
- `colValue` (String): Column value.
- `operator` (String): Operator for the filter.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/attribute/createAttributeRowFilter/0.1.0`

## 11. DeleteAttributeRowFilter Handler

### How it Works with Key Steps
1. **Extracting Data**: Extracts `hostId`, `attributeId`, `apiId`, `apiVersion`, `endpoint`, and `colName` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID.
3. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
4. **Event Creation**: Constructs an `EventId` and `AttributeRowFilterDeletedEvent` with the extracted data.
5. **Serialization**: Serializes the event using `AvroSerializer`.
6. **Kafka Producer**: Sends the serialized event to a Kafka topic.
7. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `hostId` (String): Host identifier.
- `attributeId` (String): Attribute identifier.
- `apiId` (String): API identifier.
- `apiVersion` (String): API version.
- `endpoint` (String): API endpoint.
- `colName` (String): Column name.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/attribute/deleteAttributeRowFilter/0.1.0`

## 12. UpdateAttributeColFilter Handler

### How it Works with Key Steps
1. **Extracting Data**: Extracts `hostId`, `attributeId`, `attributeValue`, `apiId`, `apiVersion`, `endpoint`, and `columns` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID.
3. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
4. **Event Creation**: Constructs an `EventId` and `AttributeColFilterUpdatedEvent` with the extracted data.
5. **Serialization**: Serializes the event using `AvroSerializer`.
6. **Kafka Producer**: Sends the serialized event to a Kafka topic.
7. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `hostId` (String): Host identifier.
- `attributeId` (String): Attribute identifier.
- `attributeValue` (String): Value of the attribute.
- `apiId` (String): API identifier.
- `apiVersion` (String): API version.
- `endpoint` (String): API endpoint.
- `columns` (String): Columns to filter.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/attribute/updateAttributeColFilter/0.1.0`

## 13. UpdateAttributeRowFilter Handler

### How it Works with Key Steps
1. **Extracting Data**: Extracts `hostId`, `attributeId`, `attributeValue`, `apiId`, `apiVersion`, `endpoint`, `colName`, `colValue`, and `operator` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID.
3. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
4. **Event Creation**: Constructs an `EventId` and `AttributeRowFilterUpdatedEvent` with the extracted data.
5. **Serialization**: Serializes the event using `AvroSerializer`.
6. **Kafka Producer**: Sends the serialized event to a Kafka topic.
7. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `hostId` (String): Host identifier.
- `attributeId` (String): Attribute identifier.
- `attributeValue` (String): Value of the attribute.
- `apiId` (String): API identifier.
- `apiVersion` (String): API version.
- `endpoint` (String): API endpoint.
- `colName` (String): Column name.
- `colValue` (String): Column value.
- `operator` (String): Operator for the filter.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/attribute/updateAttributeRowFilter/0.1.0`
