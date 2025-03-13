# Service Command Service
- [Github Link](https://github.com/lightapi/service-command)

## 1. CreateEndpointRule Handler

### How it Works with Key Steps
1. **Extracting Data**: Extracts `serviceId`, `ruleId`, and `ruleDefinition` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID.
3. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
4. **Event Creation**: Constructs an `EventId` and `EndpointRuleCreatedEvent` with the extracted data.
5. **Serialization**: Serializes the event using `AvroSerializer`.
6. **Kafka Producer**: Sends the serialized event to a Kafka topic.
7. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `serviceId` (String): Service identifier.
- `ruleId` (String): Rule identifier.
- `ruleDefinition` (String): Definition of the rule.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/service/createEndpointRule/0.1.0`

## 2. CreateService Handler

### How it Works with Key Steps
1. **Extracting Data**: Extracts `serviceId`, `serviceName`, and `serviceDescription` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID.
3. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
4. **Event Creation**: Constructs an `EventId` and `ServiceCreatedEvent` with the extracted data.
5. **Serialization**: Serializes the event using `AvroSerializer`.
6. **Kafka Producer**: Sends the serialized event to a Kafka topic.
7. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `serviceId` (String): Service identifier.
- `serviceName` (String): Service name.
- `serviceDescription` (String): Description of the service.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/service/createService/0.1.0`

## 3. CreateServiceVersion Handler

### How it Works with Key Steps
1. **Extracting Data**: Extracts `serviceId`, `versionId`, and `versionDetails` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID.
3. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
4. **Event Creation**: Constructs an `EventId` and `ServiceVersionCreatedEvent` with the extracted data.
5. **Serialization**: Serializes the event using `AvroSerializer`.
6. **Kafka Producer**: Sends the serialized event to a Kafka topic.
7. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `serviceId` (String): Service identifier.
- `versionId` (String): Version identifier.
- `versionDetails` (String): Details of the version.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/service/createServiceVersion/0.1.0`

## 4. DeleteEndpointRule Handler

### How it Works with Key Steps
1. **Extracting Data**: Extracts `serviceId` and `ruleId` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID.
3. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
4. **Event Creation**: Constructs an `EventId` and `EndpointRuleDeletedEvent` with the extracted data.
5. **Serialization**: Serializes the event using `AvroSerializer`.
6. **Kafka Producer**: Sends the serialized event to a Kafka topic.
7. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `serviceId` (String): Service identifier.
- `ruleId` (String): Rule identifier.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/service/deleteEndpointRule/0.1.0`

## 5. DeleteService Handler

### How it Works with Key Steps
1. **Extracting Data**: Extracts `serviceId` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID.
3. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
4. **Event Creation**: Constructs an `EventId` and `ServiceDeletedEvent` with the extracted data.
5. **Serialization**: Serializes the event using `AvroSerializer`.
6. **Kafka Producer**: Sends the serialized event to a Kafka topic.
7. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `serviceId` (String): Service identifier.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/service/deleteService/0.1.0`

## 6. DeleteServiceVersion Handler

### How it Works with Key Steps
1. **Extracting Data**: Extracts `serviceId` and `versionId` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID.
3. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
4. **Event Creation**: Constructs an `EventId` and `ServiceVersionDeletedEvent` with the extracted data.
5. **Serialization**: Serializes the event using `AvroSerializer`.
6. **Kafka Producer**: Sends the serialized event to a Kafka topic.
7. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `serviceId` (String): Service identifier.
- `versionId` (String): Version identifier.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/service/deleteServiceVersion/0.1.0`

## 7. UpdateService Handler

### How it Works with Key Steps
1. **Extracting Data**: Extracts `serviceId`, `serviceName`, and `serviceDescription` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID.
3. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
4. **Event Creation**: Constructs an `EventId` and `ServiceUpdatedEvent` with the extracted data.
5. **Serialization**: Serializes the event using `AvroSerializer`.
6. **Kafka Producer**: Sends the serialized event to a Kafka topic.
7. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `serviceId` (String): Service identifier.
- `serviceName` (String): Service name.
- `serviceDescription` (String): Description of the service.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/service/updateService/0.1.0`

## 8. UpdateServiceSpec Handler

### How it Works with Key Steps
1. **Extracting Data**: Extracts `serviceId`, `specId`, and `specDetails` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID.
3. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
4. **Event Creation**: Constructs an `EventId` and `ServiceSpecUpdatedEvent` with the extracted data.
5. **Serialization**: Serializes the event using `AvroSerializer`.
6. **Kafka Producer**: Sends the serialized event to a Kafka topic.
7. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `serviceId` (String): Service identifier.
- `specId` (String): Specification identifier.
- `specDetails` (String): Details of the specification.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/service/updateServiceSpec/0.1.0`

## 9. UpdateServiceVersion Handler

### How it Works with Key Steps
1. **Extracting Data**: Extracts `serviceId`, `versionId`, and `versionDetails` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID.
3. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
4. **Event Creation**: Constructs an `EventId` and `ServiceVersionUpdatedEvent` with the extracted data.
5. **Serialization**: Serializes the event using `AvroSerializer`.
6. **Kafka Producer**: Sends the serialized event to a Kafka topic.
7. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `serviceId` (String): Service identifier.
- `versionId` (String): Version identifier.
- `versionDetails` (String): Details of the version.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/service/updateServiceVersion/0.1.0`
