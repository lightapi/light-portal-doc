# Deployment Command Service
- [Github Link](https://github.com/lightapi/deployment-command)

## 1. CreateDeployment Handler

### How it Works with Key Steps
1. **Extracting Data**: Extracts `deploymentId`, `pipelineId`, and `platformId` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID.
3. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
4. **Event Creation**: Constructs an `EventId` and `DeploymentCreatedEvent` with the extracted data.
5. **Serialization**: Serializes the event using `AvroSerializer`.
6. **Kafka Producer**: Sends the serialized event to a Kafka topic.
7. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `deploymentId` (String): Deployment identifier.
- `pipelineId` (String): Pipeline identifier.
- `platformId` (String): Platform identifier.
- Additional fields: Any other fields are included in the event's value.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/deployment/createDeployment/0.1.0`

## 2. CreatePipeline Handler

### How it Works with Key Steps
1. **Extracting Data**: Extracts `pipelineId`, `name`, and `description` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID.
3. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
4. **Event Creation**: Constructs an `EventId` and `PipelineCreatedEvent` with the extracted data.
5. **Serialization**: Serializes the event using `AvroSerializer`.
6. **Kafka Producer**: Sends the serialized event to a Kafka topic.
7. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `pipelineId` (String): Pipeline identifier.
- `name` (String): Pipeline name.
- `description` (String): Pipeline description.
- Additional fields: Any other fields are included in the event's value.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/deployment/createPipeline/0.1.0`

## 3. CreatePlatform Handler

### How it Works with Key Steps
1. **Extracting Data**: Extracts `platformId`, `name`, and `description` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID.
3. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
4. **Event Creation**: Constructs an `EventId` and `PlatformCreatedEvent` with the extracted data.
5. **Serialization**: Serializes the event using `AvroSerializer`.
6. **Kafka Producer**: Sends the serialized event to a Kafka topic.
7. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `platformId` (String): Platform identifier.
- `name` (String): Platform name.
- `description` (String): Platform description.
- Additional fields: Any other fields are included in the event's value.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/deployment/createPlatform/0.1.0`

## 4. DeleteDeployment Handler

### How it Works with Key Steps
1. **Extracting Data**: Extracts `deploymentId` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID.
3. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
4. **Event Creation**: Constructs an `EventId` and `DeploymentDeletedEvent` with the extracted data.
5. **Serialization**: Serializes the event using `AvroSerializer`.
6. **Kafka Producer**: Sends the serialized event to a Kafka topic.
7. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `deploymentId` (String): Deployment identifier.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/deployment/deleteDeployment/0.1.0`

## 5. DeletePipeline Handler

### How it Works with Key Steps
1. **Extracting Data**: Extracts `pipelineId` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID.
3. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
4. **Event Creation**: Constructs an `EventId` and `PipelineDeletedEvent` with the extracted data.
5. **Serialization**: Serializes the event using `AvroSerializer`.
6. **Kafka Producer**: Sends the serialized event to a Kafka topic.
7. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `pipelineId` (String): Pipeline identifier.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/deployment/deletePipeline/0.1.0`

## 6. DeletePlatform Handler

### How it Works with Key Steps
1. **Extracting Data**: Extracts `platformId` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID.
3. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
4. **Event Creation**: Constructs an `EventId` and `PlatformDeletedEvent` with the extracted data.
5. **Serialization**: Serializes the event using `AvroSerializer`.
6. **Kafka Producer**: Sends the serialized event to a Kafka topic.
7. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `platformId` (String): Platform identifier.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/deployment/deletePlatform/0.1.0`

## 7. UpdateDeployment Handler

### How it Works with Key Steps
1. **Extracting Data**: Extracts `deploymentId`, `pipelineId`, and `platformId` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID.
3. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
4. **Event Creation**: Constructs an `EventId` and `DeploymentUpdatedEvent` with the extracted data.
5. **Serialization**: Serializes the event using `AvroSerializer`.
6. **Kafka Producer**: Sends the serialized event to a Kafka topic.
7. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `deploymentId` (String): Deployment identifier.
- `pipelineId` (String): Pipeline identifier.
- `platformId` (String): Platform identifier.
- Additional fields: Any other fields are included in the event's value.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/deployment/updateDeployment/0.1.0`

## 8. UpdateDeploymentJobId Handler

### How it Works with Key Steps
1. **Extracting Data**: Extracts `deploymentId` and `jobId` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID.
3. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
4. **Event Creation**: Constructs an `EventId` and `DeploymentJobIdUpdatedEvent` with the extracted data.
5. **Serialization**: Serializes the event using `AvroSerializer`.
6. **Kafka Producer**: Sends the serialized event to a Kafka topic.
7. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `deploymentId` (String): Deployment identifier.
- `jobId` (String): Job identifier.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/deployment/updateDeploymentJobId/0.1.0`

## 9. UpdatePipeline Handler

### How it Works with Key Steps
1. **Extracting Data**: Extracts `pipelineId`, `name`, and `description` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID.
3. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
4. **Event Creation**: Constructs an `EventId` and `PipelineUpdatedEvent` with the extracted data.
5. **Serialization**: Serializes the event using `AvroSerializer`.
6. **Kafka Producer**: Sends the serialized event to a Kafka topic.
7. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `pipelineId` (String): Pipeline identifier.
- `name` (String): Pipeline name.
- `description` (String): Pipeline description.
- Additional fields: Any other fields are included in the event's value.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/deployment/updatePipeline/0.1.0`

## 10. UpdatePlatform Handler

### How it Works with Key Steps
1. **Extracting Data**: Extracts `platformId`, `name`, and `description` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID.
3. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
4. **Event Creation**: Constructs an `EventId` and `PlatformUpdatedEvent` with the extracted data.
5. **Serialization**: Serializes the event using `AvroSerializer`.
6. **Kafka Producer**: Sends the serialized event to a Kafka topic.
7. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `platformId` (String): Platform identifier.
- `name` (String): Platform name.
- `description` (String): Platform description.
- Additional fields: Any other fields are included in the event's value.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/deployment/updatePlatform/0.1.0`
