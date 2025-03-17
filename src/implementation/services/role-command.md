# Role Command Service
- [Github Link](https://github.com/lightapi/role-command)

## 1. CreateRole Handler

### Key Steps
1. **Extracting Data**: Extracts `roleId`, `roleName`, and `permissions` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID.
3. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
4. **Event Creation**: Constructs an `EventId` and `RoleCreatedEvent` with the extracted data.
5. **Serialization**: Serializes the event using `AvroSerializer`.
6. **Kafka Producer**: Sends the serialized event to a Kafka topic.
7. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `roleId` (String): Role identifier.
- `roleName` (String): Role name.
- `permissions` (List<String>): List of permissions associated with the role.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/role/createRole/0.1.0`

## 2. CreateRoleColFilter Handler

### Key Steps
1. **Extracting Data**: Extracts `roleId` and `colFilter` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID.
3. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
4. **Event Creation**: Constructs an `EventId` and `RoleColFilterCreatedEvent` with the extracted data.
5. **Serialization**: Serializes the event using `AvroSerializer`.
6. **Kafka Producer**: Sends the serialized event to a Kafka topic.
7. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `roleId` (String): Role identifier.
- `colFilter` (String): Column filter associated with the role.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/role/createRoleColFilter/0.1.0`

## 3. CreateRolePermission Handler

### Key Steps
1. **Extracting Data**: Extracts `roleId` and `permission` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID.
3. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
4. **Event Creation**: Constructs an `EventId` and `RolePermissionCreatedEvent` with the extracted data.
5. **Serialization**: Serializes the event using `AvroSerializer`.
6. **Kafka Producer**: Sends the serialized event to a Kafka topic.
7. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `roleId` (String): Role identifier.
- `permission` (String): Permission associated with the role.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/role/createRolePermission/0.1.0`

## 4. CreateRoleRowFilter Handler

### Key Steps
1. **Extracting Data**: Extracts `roleId` and `rowFilter` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID.
3. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
4. **Event Creation**: Constructs an `EventId` and `RoleRowFilterCreatedEvent` with the extracted data.
5. **Serialization**: Serializes the event using `AvroSerializer`.
6. **Kafka Producer**: Sends the serialized event to a Kafka topic.
7. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `roleId` (String): Role identifier.
- `rowFilter` (String): Row filter associated with the role.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/role/createRoleRowFilter/0.1.0`

## 5. CreateRoleUser Handler

### Key Steps
1. **Extracting Data**: Extracts `roleId` and `userId` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID.
3. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
4. **Event Creation**: Constructs an `EventId` and `RoleUserCreatedEvent` with the extracted data.
5. **Serialization**: Serializes the event using `AvroSerializer`.
6. **Kafka Producer**: Sends the serialized event to a Kafka topic.
7. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `roleId` (String): Role identifier.
- `userId` (String): User identifier associated with the role.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/role/createRoleUser/0.1.0`

## 6. DeleteRole Handler

### Key Steps
1. **Extracting Data**: Extracts `roleId` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID.
3. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
4. **Event Creation**: Constructs an `EventId` and `RoleDeletedEvent` with the extracted data.
5. **Serialization**: Serializes the event using `AvroSerializer`.
6. **Kafka Producer**: Sends the serialized event to a Kafka topic.
7. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `roleId` (String): Role identifier.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/role/deleteRole/0.1.0`

## 7. DeleteRoleColFilter Handler

### Key Steps
1. **Extracting Data**: Extracts `roleId` and `colFilter` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID.
3. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
4. **Event Creation**: Constructs an `EventId` and `RoleColFilterDeletedEvent` with the extracted data.
5. **Serialization**: Serializes the event using `AvroSerializer`.
6. **Kafka Producer**: Sends the serialized event to a Kafka topic.
7. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `roleId` (String): Role identifier.
- `colFilter` (String): Column filter associated with the role.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/role/deleteRoleColFilter/0.1.0`

## 8. DeleteRolePermission Handler

### Key Steps
1. **Extracting Data**: Extracts `roleId` and `permission` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID.
3. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
4. **Event Creation**: Constructs an `EventId` and `RolePermissionDeletedEvent` with the extracted data.
5. **Serialization**: Serializes the event using `AvroSerializer`.
6. **Kafka Producer**: Sends the serialized event to a Kafka topic.
7. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `roleId` (String): Role identifier.
- `permission` (String): Permission associated with the role.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/role/deleteRolePermission/0.1.0`

## 9. DeleteRoleRowFilter Handler

### Key Steps
1. **Extracting Data**: Extracts `roleId` and `rowFilter` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID.
3. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
4. **Event Creation**: Constructs an `EventId` and `RoleRowFilterDeletedEvent` with the extracted data.
5. **Serialization**: Serializes the event using `AvroSerializer`.
6. **Kafka Producer**: Sends the serialized event to a Kafka topic.
7. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `roleId` (String): Role identifier.
- `rowFilter` (String): Row filter associated with the role.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/role/deleteRoleRowFilter/0.1.0`

## 10. DeleteRoleUser Handler

### Key Steps
1. **Extracting Data**: Extracts `roleId` and `userId` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID.
3. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
4. **Event Creation**: Constructs an `EventId` and `RoleUserDeletedEvent` with the extracted data.
5. **Serialization**: Serializes the event using `AvroSerializer`.
6. **Kafka Producer**: Sends the serialized event to a Kafka topic.
7. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `roleId` (String): Role identifier.
- `userId` (String): User identifier associated with the role.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/role/deleteRoleUser/0.1.0`

## 11. UpdateRole Handler

### Key Steps
1. **Extracting Data**: Extracts `roleId`, `roleName`, and `permissions` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID.
3. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
4. **Event Creation**: Constructs an `EventId` and `RoleUpdatedEvent` with the extracted data.
5. **Serialization**: Serializes the event using `AvroSerializer`.
6. **Kafka Producer**: Sends the serialized event to a Kafka topic.
7. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `roleId` (String): Role identifier.
- `roleName` (String): Role name.
- `permissions` (List<String>): List of permissions associated with the role.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/role/updateRole/0.1.0`

## 12. UpdateRoleColFilter Handler

### Key Steps
1. **Extracting Data**: Extracts `roleId` and `colFilter` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID.
3. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
4. **Event Creation**: Constructs an `EventId` and `RoleColFilterUpdatedEvent` with the extracted data.
5. **Serialization**: Serializes the event using `AvroSerializer`.
6. **Kafka Producer**: Sends the serialized event to a Kafka topic.
7. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `roleId` (String): Role identifier.
- `colFilter` (String): Column filter associated with the role.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/role/updateRoleColFilter/0.1.0`

## 13. UpdateRoleRowFilter Handler

### Key Steps
1. **Extracting Data**: Extracts `roleId` and `rowFilter` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID.
3. **Nonce Generation**: Fetches a nonce for the transaction using the user ID.
4. **Event Creation**: Constructs an `EventId` and `RoleRowFilterUpdatedEvent` with the extracted data.
5. **Serialization**: Serializes the event using `AvroSerializer`.
6. **Kafka Producer**: Sends the serialized event to a Kafka topic.
7. **Response Handling**: Waits for the Kafka producer to complete and returns the appropriate status.

### Input
- `roleId` (String): Role identifier.
- `rowFilter` (String): Row filter associated with the role.

### Output
- ByteBuffer containing the status of the request.

### Endpoint
- `lightapi.net/role/updateRoleRowFilter/0.1.0`
