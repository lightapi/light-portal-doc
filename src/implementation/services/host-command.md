# Host Command Service
- [Github Link](https://github.com/lightapi/host-command)

## 1. CreateHost Handler

### Key Steps
1. **Extracting Data**: Extracts `domain`, `subDomain`, `hostDesc`, and `hostOwner` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID.
3. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
4. **Event Creation**: Constructs an `EventId` and `HostCreatedEvent` with the extracted data.
5. **Serialization**: Serializes the event using `AvroSerializer`.
6. **Kafka Producer**: Sends the serialized event to a Kafka topic.
7. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `domain` (String): Domain name.
- `subDomain` (String): Subdomain name.
- `hostDesc` (String): Host description.
- `hostOwner` (String): Host owner.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/host/createHost/0.1.0`

## 2. CreateOrg Handler

### Key Steps
1. **Extracting Data**: Extracts `domain`, `orgName`, `orgDesc`, `subDomain`, `hostDesc`, and `hostOwner` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID.
3. **Email Verification**: Ensures the email contains the domain.
4. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
5. **Event Creation**: Constructs an `EventId` and `OrgCreatedEvent` with the extracted data.
6. **Serialization**: Serializes the event using `AvroSerializer`.
7. **Kafka Producer**: Sends the serialized event to a Kafka topic.
8. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `domain` (String): Domain name.
- `orgName` (String): Organization name.
- `orgDesc` (String): Organization description.
- `subDomain` (String): Subdomain name.
- `hostDesc` (String): Host description.
- `hostOwner` (String): Host owner.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/host/createOrg/0.1.0`

## 3. DeleteHost Handler

### Key Steps
1. **Extracting Data**: Extracts `hostId` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID.
3. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
4. **Event Creation**: Constructs an `EventId` and `HostDeletedEvent` with the extracted data.
5. **Serialization**: Serializes the event using `AvroSerializer`.
6. **Kafka Producer**: Sends the serialized event to a Kafka topic.
7. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `hostId` (String): Host identifier.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/host/deleteHost/0.1.0`

## 4. DeleteOrg Handler

### Key Steps
1. **Extracting Data**: Extracts `domain` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID.
3. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
4. **Event Creation**: Constructs an `EventId` and `OrgDeletedEvent` with the extracted data.
5. **Serialization**: Serializes the event using `AvroSerializer`.
6. **Kafka Producer**: Sends the serialized event to a Kafka topic.
7. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `domain` (String): Domain name.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/host/deleteOrg/0.1.0`

## 5. SwitchHost Handler

### Key Steps
1. **Extracting Data**: Extracts `hostId` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID.
3. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
4. **Event Creation**: Constructs an `EventId` and `HostSwitchedEvent` with the extracted data.
5. **Serialization**: Serializes the event using `AvroSerializer`.
6. **Kafka Producer**: Sends the serialized event to a Kafka topic.
7. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `hostId` (String): Host identifier.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/host/switchHost/0.1.0`

## 6. UpdateHost Handler

### Key Steps
1. **Extracting Data**: Extracts `hostId`, `domain`, `subDomain`, `hostDesc`, and `hostOwner` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID.
3. **Email Verification**: Ensures the email contains the domain.
4. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
5. **Event Creation**: Constructs an `EventId` and `HostUpdatedEvent` with the extracted data.
6. **Serialization**: Serializes the event using `AvroSerializer`.
7. **Kafka Producer**: Sends the serialized event to a Kafka topic.
8. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `hostId` (String): Host identifier.
- `domain` (String): Domain name.
- `subDomain` (String): Subdomain name.
- `hostDesc` (String): Host description.
- `hostOwner` (String): Host owner.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/host/updateHost/0.1.0`

## 7. UpdateOrg Handler

### Key Steps
1. **Extracting Data**: Extracts `domain`, `orgName`, `orgDesc`, and `orgOwner` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID.
3. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
4. **Event Creation**: Constructs an `EventId` and `OrgUpdatedEvent` with the extracted data.
5. **Serialization**: Serializes the event using `AvroSerializer`.
6. **Kafka Producer**: Sends the serialized event to a Kafka topic.
7. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `domain` (String): Domain name.
- `orgName` (String): Organization name.
- `orgDesc` (String): Organization description.
- `orgOwner` (String): Organization owner.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/host/updateOrg/0.1.0`
