# Instance Command Service
- [Github Link](https://github.com/lightapi/instance-command)

## 1. CreateInstance Handler

### How it Works with Key Steps
1. **Extracting Data**: Extracts `instanceName`, `productId`, `productVersion`, `serviceId`, and `pipelineId` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID.
3. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
4. **Event Creation**: Constructs an `EventId` and `InstanceCreatedEvent` with the extracted data.
5. **Serialization**: Serializes the event using `AvroSerializer`.
6. **Kafka Producer**: Sends the serialized event to a Kafka topic.
7. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `instanceName` (String): Instance name.
- `productId` (String): Product identifier.
- `productVersion` (String): Product version.
- `serviceId` (String): Service identifier.
- `pipelineId` (String): Pipeline identifier.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/instance/createInstance/0.1.0`

## 2. DeleteInstance Handler

### How it Works with Key Steps
1. **Extracting Data**: Extracts `instanceId` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID.
3. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
4. **Event Creation**: Constructs an `EventId` and `InstanceDeletedEvent` with the extracted data.
5. **Serialization**: Serializes the event using `AvroSerializer`.
6. **Kafka Producer**: Sends the serialized event to a Kafka topic.
7. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `instanceId` (String): Instance identifier.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/instance/deleteInstance/0.1.0`

## 3. UpdateInstance Handler

### How it Works with Key Steps
1. **Extracting Data**: Extracts `instanceId`, `instanceName`, `productId`, `productVersion`, `serviceId`, and `pipelineId` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID.
3. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
4. **Event Creation**: Constructs an `EventId` and `InstanceUpdatedEvent` with the extracted data.
5. **Serialization**: Serializes the event using `AvroSerializer`.
6. **Kafka Producer**: Sends the serialized event to a Kafka topic.
7. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `instanceId` (String): Instance identifier.
- `instanceName` (String): Instance name.
- `productId` (String): Product identifier.
- `productVersion` (String): Product version.
- `serviceId` (String): Service identifier.
- `pipelineId` (String): Pipeline identifier.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/instance/updateInstance/0.1.0`

## 4. CreateInstanceApp Handler

### How it Works with Key Steps
1. **Extracting Data**: Extracts `instanceId`, `appId`, and `appVersion` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID.
3. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
4. **Event Creation**: Constructs an `EventId` and `InstanceAppCreatedEvent` with the extracted data.
5. **Serialization**: Serializes the event using `AvroSerializer`.
6. **Kafka Producer**: Sends the serialized event to a Kafka topic.
7. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `instanceId` (String): Instance identifier.
- `appId` (String): Application identifier.
- `appVersion` (String): Application version.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/instance/createInstanceApp/0.1.0`

## 5. DeleteInstanceApp Handler

### How it Works with Key Steps
1. **Extracting Data**: Extracts `instanceId`, `appId`, and `appVersion` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID.
3. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
4. **Event Creation**: Constructs an `EventId` and `InstanceAppDeletedEvent` with the extracted data.
5. **Serialization**: Serializes the event using `AvroSerializer`.
6. **Kafka Producer**: Sends the serialized event to a Kafka topic.
7. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `instanceId` (String): Instance identifier.
- `appId` (String): Application identifier.
- `appVersion` (String): Application version.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/instance/deleteInstanceApp/0.1.0`

## 6. UpdateInstanceApp Handler

### How it Works with Key Steps
1. **Extracting Data**: Extracts `instanceId`, `appId`, and `appVersion` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID.
3. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
4. **Event Creation**: Constructs an `EventId` and `InstanceAppUpdatedEvent` with the extracted data.
5. **Serialization**: Serializes the event using `AvroSerializer`.
6. **Kafka Producer**: Sends the serialized event to a Kafka topic.
7. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `instanceId` (String): Instance identifier.
- `appId` (String): Application identifier.
- `appVersion` (String): Application version.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/instance/updateInstanceApp/0.1.0`

## 7. CreateInstanceApi Handler

### How it Works with Key Steps
1. **Extracting Data**: Extracts `instanceId`, `apiId`, and `apiVersion` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID.
3. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
4. **Event Creation**: Constructs an `EventId` and `InstanceApiCreatedEvent` with the extracted data.
5. **Serialization**: Serializes the event using `AvroSerializer`.
6. **Kafka Producer**: Sends the serialized event to a Kafka topic.
7. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `instanceId` (String): Instance identifier.
- `apiId` (String): API identifier.
- `apiVersion` (String): API version.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/instance/createInstanceApi/0.1.0`

## 8. DeleteInstanceApi Handler

### How it Works with Key Steps
1. **Extracting Data**: Extracts `instanceId`, `apiId`, and `apiVersion` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID.
3. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
4. **Event Creation**: Constructs an `EventId` and `InstanceApiDeletedEvent` with the extracted data.
5. **Serialization**: Serializes the event using `AvroSerializer`.
6. **Kafka Producer**: Sends the serialized event to a Kafka topic.
7. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `instanceId` (String): Instance identifier.
- `apiId` (String): API identifier.
- `apiVersion` (String): API version.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/instance/deleteInstanceApi/0.1.0`

## 9. UpdateInstanceApi Handler

### How it Works with Key Steps
1. **Extracting Data**: Extracts `instanceId`, `apiId`, and `apiVersion` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID.
3. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
4. **Event Creation**: Constructs an `EventId` and `InstanceApiUpdatedEvent` with the extracted data.
5. **Serialization**: Serializes the event using `AvroSerializer`.
6. **Kafka Producer**: Sends the serialized event to a Kafka topic.
7. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `instanceId` (String): Instance identifier.
- `apiId` (String): API identifier.
- `apiVersion` (String): API version.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/instance/updateInstanceApi/0.1.0`
