# Config Command Service
- [Github Link](https://github.com/lightapi/config-command)

## 1. CreateConfig Handler

### Key Steps
1. **Extracting Data**: Extracts `configId`, `configName`, and other relevant fields from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID to ensure the request is authorized.
3. **Nonce Generation**: Fetches a nonce for the transaction using the user ID to ensure uniqueness.
4. **Event Creation**: Constructs an `EventId` and `ConfigCreatedEvent` with the extracted data.
5. **Serialization**: Serializes the event using `AvroSerializer` for efficient transmission.
6. **Kafka Producer**: Sends the serialized event to a Kafka topic for further processing.
7. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status to the client.

### Input
- `configId` (String): Unique identifier for the configuration.
- `configName` (String): Name of the configuration.
- `properties` (Map<String, String>): Key-value pairs representing configuration properties.

### Output
- `status` (String): Status of the request, e.g., "success" or "failure".
- `message` (String): Additional information about the result of the operation.

### Endpoint
- `lightapi.net/config/createConfig/0.1.0`

---

## 2. DeleteConfig Handler

### Key Steps
1. **Extracting Data**: Extracts `configId` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID to ensure the request is authorized.
3. **Nonce Generation**: Fetches a nonce for the transaction using the user ID to ensure uniqueness.
4. **Event Creation**: Constructs an `EventId` and `ConfigDeletedEvent` with the extracted data.
5. **Serialization**: Serializes the event using `AvroSerializer` for efficient transmission.
6. **Kafka Producer**: Sends the serialized event to a Kafka topic for further processing.
7. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status to the client.

### Input
- `configId` (String): Unique identifier for the configuration to be deleted.

### Output
- `status` (String): Status of the request, e.g., "success" or "failure".
- `message` (String): Additional information about the result of the operation.

### Endpoint
- `lightapi.net/config/deleteConfig/0.1.0`

---

## 3. UpdateConfig Handler

### Key Steps
1. **Extracting Data**: Extracts `configId`, `configName`, and other relevant fields from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID to ensure the request is authorized.
3. **Nonce Generation**: Fetches a nonce for the transaction using the user ID to ensure uniqueness.
4. **Event Creation**: Constructs an `EventId` and `ConfigUpdatedEvent` with the extracted data.
5. **Serialization**: Serializes the event using `AvroSerializer` for efficient transmission.
6. **Kafka Producer**: Sends the serialized event to a Kafka topic for further processing.
7. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status to the client.

### Input
- `configId` (String): Unique identifier for the configuration.
- `configName` (String): Updated name of the configuration.
- `properties` (Map<String, String>): Updated key-value pairs representing configuration properties.

### Output
- `status` (String): Status of the request, e.g., "success" or "failure".
- `message` (String): Additional information about the result of the operation.

### Endpoint
- `lightapi.net/config/updateConfig/0.1.0`

---

## 4. CreateConfigEnvironment Handler

### Key Steps
1. **Extracting Data**: Extracts `environmentId`, `environmentName`, and other relevant fields from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID to ensure the request is authorized.
3. **Nonce Generation**: Fetches a nonce for the transaction using the user ID to ensure uniqueness.
4. **Event Creation**: Constructs an `EventId` and `EnvironmentCreatedEvent` with the extracted data.
5. **Serialization**: Serializes the event using `AvroSerializer` for efficient transmission.
6. **Kafka Producer**: Sends the serialized event to a Kafka topic for further processing.
7. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status to the client.

### Input
- `environmentId` (String): Unique identifier for the environment.
- `environmentName` (String): Name of the environment.
- `properties` (Map<String, String>): Key-value pairs representing environment properties.

### Output
- `status` (String): Status of the request, e.g., "success" or "failure".
- `message` (String): Additional information about the result of the operation.

### Endpoint
- `lightapi.net/config/createConfigEnvironment/0.1.0`

---

## 5. DeleteConfigEnvironment Handler

### Key Steps
1. **Extracting Data**: Extracts `environmentId` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID to ensure the request is authorized.
3. **Nonce Generation**: Fetches a nonce for the transaction using the user ID to ensure uniqueness.
4. **Event Creation**: Constructs an `EventId` and `EnvironmentDeletedEvent` with the extracted data.
5. **Serialization**: Serializes the event using `AvroSerializer` for efficient transmission.
6. **Kafka Producer**: Sends the serialized event to a Kafka topic for further processing.
7. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status to the client.

### Input
- `environmentId` (String): Unique identifier for the environment to be deleted.

### Output
- `status` (String): Status of the request, e.g., "success" or "failure".
- `message` (String): Additional information about the result of the operation.

### Endpoint
- `lightapi.net/config/deleteConfigEnvironment/0.1.0`