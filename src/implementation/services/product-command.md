# Product Command Service
- [Github Link](https://github.com/lightapi/product-command)

## 1. CreateProductVersion Handler

### Key Steps
1. **Extracting Data**: Extracts `productId`, `productVersion`, `light4jVersion`, `versionStatus`, `releaseType`, and `current` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID.
3. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
4. **Event Creation**: Constructs an `EventId` and `ProductCreatedEvent` with the extracted data.
5. **Serialization**: Serializes the event using `AvroSerializer`.
6. **Kafka Producer**: Sends the serialized event to a Kafka topic.
7. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `productId` (String): Product identifier.
- `productVersion` (String): Product version.
- `light4jVersion` (String): Light-4j version.
- `versionStatus` (String): Status of the version.
- `releaseType` (String): Type of release.
- `current` (Boolean): Indicates if this is the current version.
- Additional fields: Any other fields are included in the event's value.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/product/createProductVersion/0.1.0`

## 2. UpdateProductVersion Handler

### Key Steps
1. **Extracting Data**: Extracts `productId`, `productVersion`, `light4jVersion`, `versionStatus`, `releaseType`, and `current` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID.
3. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
4. **Event Creation**: Constructs an `EventId` and `ProductUpdatedEvent` with the extracted data.
5. **Serialization**: Serializes the event using `AvroSerializer`.
6. **Kafka Producer**: Sends the serialized event to a Kafka topic.
7. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `productId` (String): Product identifier.
- `productVersion` (String): Product version.
- `light4jVersion` (String): Light-4j version.
- `versionStatus` (String): Status of the version.
- `releaseType` (String): Type of release.
- `current` (Boolean): Indicates if this is the current version.
- Additional fields: Any other fields are included in the event's value.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/product/updateProductVersion/0.1.0`

## 3. DeleteProductVersion Handler

### Key Steps
1. **Extracting Data**: Extracts `productId` and `productVersion` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID.
3. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
4. **Event Creation**: Constructs an `EventId` and `ProductDeletedEvent` with the extracted data.
5. **Serialization**: Serializes the event using `AvroSerializer`.
6. **Kafka Producer**: Sends the serialized event to a Kafka topic.
7. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `productId` (String): Product identifier.
- `productVersion` (String): Product version.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/product/deleteProductVersion/0.1.0`
