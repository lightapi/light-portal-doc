# OAuth Command Service
- [Github Link](https://github.com/lightapi/oauth-command)

## 1. CreateAuthCode Handler

### Key Steps
1. **Extracting Data**: Extracts `clientId`, `userId`, and `scope` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID.
3. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
4. **Event Creation**: Constructs an `EventId` and `AuthCodeCreatedEvent` with the extracted data.
5. **Serialization**: Serializes the event using `AvroSerializer`.
6. **Kafka Producer**: Sends the serialized event to a Kafka topic.
7. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `clientId` (String): Client identifier.
- `userId` (String): User identifier.
- `scope` (String): Scope of the authorization.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/oauth/createAuthCode/0.1.0`

## 2. CreateClient Handler

### Key Steps
1. **Extracting Data**: Extracts `clientId`, `clientSecret`, and `redirectUri` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID.
3. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
4. **Event Creation**: Constructs an `EventId` and `ClientCreatedEvent` with the extracted data.
5. **Serialization**: Serializes the event using `AvroSerializer`.
6. **Kafka Producer**: Sends the serialized event to a Kafka topic.
7. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `clientId` (String): Client identifier.
- `clientSecret` (String): Client secret.
- `redirectUri` (String): Redirect URI.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/oauth/createClient/0.1.0`

## 3. CreateProvider Handler

### Key Steps
1. **Extracting Data**: Extracts `providerId`, `providerName`, and `providerUrl` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID.
3. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
4. **Event Creation**: Constructs an `EventId` and `ProviderCreatedEvent` with the extracted data.
5. **Serialization**: Serializes the event using `AvroSerializer`.
6. **Kafka Producer**: Sends the serialized event to a Kafka topic.
7. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `providerId` (String): Provider identifier.
- `providerName` (String): Provider name.
- `providerUrl` (String): Provider URL.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/oauth/createProvider/0.1.0`

## 4. CreateRefreshToken Handler

### Key Steps
1. **Extracting Data**: Extracts `clientId`, `userId`, and `scope` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID.
3. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
4. **Event Creation**: Constructs an `EventId` and `RefreshTokenCreatedEvent` with the extracted data.
5. **Serialization**: Serializes the event using `AvroSerializer`.
6. **Kafka Producer**: Sends the serialized event to a Kafka topic.
7. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `clientId` (String): Client identifier.
- `userId` (String): User identifier.
- `scope` (String): Scope of the authorization.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/oauth/createRefreshToken/0.1.0`

## 5. CreateRefToken Handler

### Key Steps
1. **Extracting Data**: Extracts `clientId`, `userId`, and `scope` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID.
3. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
4. **Event Creation**: Constructs an `EventId` and `RefTokenCreatedEvent` with the extracted data.
5. **Serialization**: Serializes the event using `AvroSerializer`.
6. **Kafka Producer**: Sends the serialized event to a Kafka topic.
7. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `clientId` (String): Client identifier.
- `userId` (String): User identifier.
- `scope` (String): Scope of the authorization.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/oauth/createRefToken/0.1.0`

## 6. DeleteAuthCode Handler

### Key Steps
1. **Extracting Data**: Extracts `authCodeId` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID.
3. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
4. **Event Creation**: Constructs an `EventId` and `AuthCodeDeletedEvent` with the extracted data.
5. **Serialization**: Serializes the event using `AvroSerializer`.
6. **Kafka Producer**: Sends the serialized event to a Kafka topic.
7. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `authCodeId` (String): Authorization code identifier.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/oauth/deleteAuthCode/0.1.0`

## 7. DeleteClient Handler

### Key Steps
1. **Extracting Data**: Extracts `clientId` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID.
3. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
4. **Event Creation**: Constructs an `EventId` and `ClientDeletedEvent` with the extracted data.
5. **Serialization**: Serializes the event using `AvroSerializer`.
6. **Kafka Producer**: Sends the serialized event to a Kafka topic.
7. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `clientId` (String): Client identifier.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/oauth/deleteClient/0.1.0`

## 8. DeleteProvider Handler

### Key Steps
1. **Extracting Data**: Extracts `providerId` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID.
3. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
4. **Event Creation**: Constructs an `EventId` and `ProviderDeletedEvent` with the extracted data.
5. **Serialization**: Serializes the event using `AvroSerializer`.
6. **Kafka Producer**: Sends the serialized event to a Kafka topic.
7. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `providerId` (String): Provider identifier.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/oauth/deleteProvider/0.1.0`

## 9. DeleteRefreshToken Handler

### Key Steps
1. **Extracting Data**: Extracts `refreshTokenId` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID.
3. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
4. **Event Creation**: Constructs an `EventId` and `RefreshTokenDeletedEvent` with the extracted data.
5. **Serialization**: Serializes the event using `AvroSerializer`.
6. **Kafka Producer**: Sends the serialized event to a Kafka topic.
7. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `refreshTokenId` (String): Refresh token identifier.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/oauth/deleteRefreshToken/0.1.0`

## 10. DeleteRefToken Handler

### Key Steps
1. **Extracting Data**: Extracts `refTokenId` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID.
3. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
4. **Event Creation**: Constructs an `EventId` and `RefTokenDeletedEvent` with the extracted data.
5. **Serialization**: Serializes the event using `AvroSerializer`.
6. **Kafka Producer**: Sends the serialized event to a Kafka topic.
7. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `refTokenId` (String): Reference token identifier.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/oauth/deleteRefToken/0.1.0`

## 11. RotateProvider Handler

### Key Steps
1. **Extracting Data**: Extracts `providerId` and `newProviderUrl` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID.
3. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
4. **Event Creation**: Constructs an `EventId` and `ProviderRotatedEvent` with the extracted data.
5. **Serialization**: Serializes the event using `AvroSerializer`.
6. **Kafka Producer**: Sends the serialized event to a Kafka topic.
7. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `providerId` (String): Provider identifier.
- `newProviderUrl` (String): New provider URL.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/oauth/rotateProvider/0.1.0`

## 12. UpdateClient Handler

### Key Steps
1. **Extracting Data**: Extracts `clientId`, `clientSecret`, and `redirectUri` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID.
3. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
4. **Event Creation**: Constructs an `EventId` and `ClientUpdatedEvent` with the extracted data.
5. **Serialization**: Serializes the event using `AvroSerializer`.
6. **Kafka Producer**: Sends the serialized event to a Kafka topic.
7. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `clientId` (String): Client identifier.
- `clientSecret` (String): Client secret.
- `redirectUri` (String): Redirect URI.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/oauth/updateClient/0.1.0`

## 13. UpdateProvider Handler

### Key Steps
1. **Extracting Data**: Extracts `providerId`, `providerName`, and `providerUrl` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID.
3. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
4. **Event Creation**: Constructs an `EventId` and `ProviderUpdatedEvent` with the extracted data.
5. **Serialization**: Serializes the event using `AvroSerializer`.
6. **Kafka Producer**: Sends the serialized event to a Kafka topic.
7. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `providerId` (String): Provider identifier.
- `providerName` (String): Provider name.
- `providerUrl` (String): Provider URL.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/oauth/updateProvider/0.1.0`
