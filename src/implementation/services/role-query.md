# Role Query Service
- [Github Link](https://github.com/lightapi/role-query)

## 1. GetRole Handler

### How it Works with Key Steps
1. **Extracting Data**: Extracts `offset`, `limit`, `hostId`, `roleId`, and `roleDesc` from the input map.
2. **Database Query**: Uses `dbProvider` to query roles based on the extracted data.
3. **Response Handling**: Checks if the query result is successful. If not, returns an error status.
4. **Serialization**: Converts the query result to a ByteBuffer.
5. **Returning Response**: Returns the serialized result.

### Input
- `offset` (Integer): Offset for pagination.
- `limit` (Integer): Limit for pagination.
- `hostId` (String): Host identifier.
- `roleId` (String): Role identifier (optional).
- `roleDesc` (String): Role description (optional).

### Output
- ByteBuffer containing the roles data or an error status.

### Endpoint
- `lightapi.net/role/getRole/0.1.0`

## 2. GetRoleLabel Handler

### How it Works with Key Steps
1. **Extracting Data**: Extracts `hostId` from the input map.
2. **Database Query**: Uses `dbProvider` to query role labels based on the `hostId`.
3. **Response Handling**: Checks if the query result is successful. If not, returns an error status.
4. **Serialization**: Converts the query result to a ByteBuffer.
5. **Returning Response**: Returns the serialized result.

### Input
- `hostId` (String): Host identifier.

### Output
- ByteBuffer containing the role labels data or an error status.

### Endpoint
- `lightapi.net/role/getRoleLabel/0.1.0`

## 3. QueryRolePermission Handler

### How it Works with Key Steps
1. **Extracting Data**: Extracts `offset`, `limit`, `hostId`, `roleId`, `apiId`, `apiVersion`, and `endpoint` from the input map.
2. **Database Query**: Uses `dbProvider` to query role permissions based on the extracted data.
3. **Response Handling**: Checks if the query result is successful. If not, returns an error status.
4. **Serialization**: Converts the query result to a ByteBuffer.
5. **Returning Response**: Returns the serialized result.

### Input
- `offset` (Integer): Offset for pagination.
- `limit` (Integer): Limit for pagination.
- `hostId` (String): Host identifier.
- `roleId` (String): Role identifier (optional).
- `apiId` (String): API identifier (optional).
- `apiVersion` (String): API version (optional).
- `endpoint` (String): API endpoint (optional).

### Output
- ByteBuffer containing the role permissions data or an error status.

### Endpoint
- `lightapi.net/role/queryRolePermission/0.1.0`

## 4. QueryRoleColFilter Handler

### How it Works with Key Steps
1. **Extracting Data**: Extracts `offset`, `limit`, `hostId`, `roleId`, `apiId`, `apiVersion`, and `endpoint` from the input map.
2. **Database Query**: Uses `dbProvider` to query role column filters based on the extracted data.
3. **Response Handling**: Checks if the query result is successful. If not, returns an error status.
4. **Serialization**: Converts the query result to a ByteBuffer.
5. **Returning Response**: Returns the serialized result.

### Input
- `offset` (Integer): Offset for pagination.
- `limit` (Integer): Limit for pagination.
- `hostId` (String): Host identifier.
- `roleId` (String): Role identifier (optional).
- `apiId` (String): API identifier (optional).
- `apiVersion` (String): API version (optional).
- `endpoint` (String): API endpoint (optional).

### Output
- ByteBuffer containing the role column filters data or an error status.

### Endpoint
- `lightapi.net/role/queryRoleColFilter/0.1.0`

## 5. QueryRoleRowFilter Handler

### How it Works with Key Steps
1. **Extracting Data**: Extracts `offset`, `limit`, `hostId`, `roleId`, `apiId`, `apiVersion`, and `endpoint` from the input map.
2. **Database Query**: Uses `dbProvider` to query role row filters based on the extracted data.
3. **Response Handling**: Checks if the query result is successful. If not, returns an error status.
4. **Serialization**: Converts the query result to a ByteBuffer.
5. **Returning Response**: Returns the serialized result.

### Input
- `offset` (Integer): Offset for pagination.
- `limit` (Integer): Limit for pagination.
- `hostId` (String): Host identifier.
- `roleId` (String): Role identifier (optional).
- `apiId` (String): API identifier (optional).
- `apiVersion` (String): API version (optional).
- `endpoint` (String): API endpoint (optional).

### Output
- ByteBuffer containing the role row filters data or an error status.

### Endpoint
- `lightapi.net/role/queryRoleRowFilter/0.1.0`

## 6. QueryRoleUser Handler

### How it Works with Key Steps
1. **Extracting Data**: Extracts `offset`, `limit`, `hostId`, `roleId`, `userId`, `entityId`, `email`, `firstName`, `lastName`, and `userType` from the input map.
2. **Database Query**: Uses `dbProvider` to query role users based on the extracted data.
3. **Response Handling**: Checks if the query result is successful. If not, returns an error status.
4. **Serialization**: Converts the query result to a ByteBuffer.
5. **Returning Response**: Returns the serialized result.

### Input
- `offset` (Integer): Offset for pagination.
- `limit` (Integer): Limit for pagination.
- `hostId` (String): Host identifier.
- `roleId` (String): Role identifier (optional).
- `userId` (String): User identifier (optional).
- `entityId` (String): Entity identifier (optional).
- `email` (String): User email (optional).
- `firstName` (String): User first name (optional).
- `lastName` (String): User last name (optional).
- `userType` (String): User type (optional).

### Output
- ByteBuffer containing the role users data or an error status.

### Endpoint
- `lightapi.net/role/queryRoleUser/0.1.0`
