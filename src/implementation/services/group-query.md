# Group Query Service
- [Github Link](https://github.com/lightapi/group-query)

## 1. GetGroup Handler

### How it Works with Key Steps
1. **Extracting Data**: Extracts `offset`, `limit`, `hostId`, `groupId`, and `groupDesc` from the input map.
2. **Handling Empty Fields**: Checks if `groupId` and `groupDesc` are empty and sets them to null if they are.
3. **Logging Extracted Data**: Logs the extracted data.
4. **Database Query**: Queries the database for groups using the extracted data.
5. **Handling Query Failure**: If the query fails, returns an error status.
6. **Handling Query Success**: If the query succeeds, logs and returns the result.

### Input
- `offset` (Integer): The offset for pagination.
- `limit` (Integer): The limit for pagination.
- `hostId` (String): The host identifier.
- `groupId` (String): The group identifier (optional).
- `groupDesc` (String): The group description (optional).

### Output
- ByteBuffer containing the list of groups or an error status.

### Endpoint
- `lightapi.net/group/getGroup/0.1.0`

## 2. GetGroupLabel Handler

### How it Works with Key Steps
1. **Extracting Data**: Extracts `hostId` from the input map.
2. **Logging Extracted Data**: Logs the extracted data.
3. **Database Query**: Queries the database for group labels using the extracted data.
4. **Handling Query Failure**: If the query fails, returns an error status.
5. **Handling Query Success**: If the query succeeds, logs and returns the result.

### Input
- `hostId` (String): The host identifier.

### Output
- ByteBuffer containing the group labels or an error status.

### Endpoint
- `lightapi.net/group/getGroupLabel/0.1.0`

## 3. QueryGroupColFilter Handler

### How it Works with Key Steps
1. **Extracting Data**: Extracts `offset`, `limit`, `hostId`, `groupId`, `apiId`, `apiVersion`, and `endpoint` from the input map.
2. **Handling Empty Fields**: Checks if `groupId`, `apiId`, `apiVersion`, and `endpoint` are empty and sets them to null if they are.
3. **Database Query**: Queries the database for group column filters using the extracted data.
4. **Handling Query Failure**: If the query fails, returns an error status.
5. **Handling Query Success**: If the query succeeds, returns the result.

### Input
- `offset` (Integer): The offset for pagination.
- `limit` (Integer): The limit for pagination.
- `hostId` (String): The host identifier.
- `groupId` (String): The group identifier (optional).
- `apiId` (String): The API identifier (optional).
- `apiVersion` (String): The API version (optional).
- `endpoint` (String): The endpoint (optional).

### Output
- ByteBuffer containing the group column filters or an error status.

### Endpoint
- `lightapi.net/group/queryGroupColFilter/0.1.0`

## 4. QueryGroupPermission Handler

### How it Works with Key Steps
1. **Extracting Data**: Extracts `offset`, `limit`, `hostId`, `groupId`, `apiId`, `apiVersion`, and `endpoint` from the input map.
2. **Handling Empty Fields**: Checks if `groupId`, `apiId`, `apiVersion`, and `endpoint` are empty and sets them to null if they are.
3. **Database Query**: Queries the database for group permissions using the extracted data.
4. **Handling Query Failure**: If the query fails, returns an error status.
5. **Handling Query Success**: If the query succeeds, logs and returns the result.

### Input
- `offset` (Integer): The offset for pagination.
- `limit` (Integer): The limit for pagination.
- `hostId` (String): The host identifier.
- `groupId` (String): The group identifier (optional).
- `apiId` (String): The API identifier (optional).
- `apiVersion` (String): The API version (optional).
- `endpoint` (String): The endpoint (optional).

### Output
- ByteBuffer containing the group permissions or an error status.

### Endpoint
- `lightapi.net/group/queryGroupPermission/0.1.0`

## 5. QueryGroupRowFilter Handler

### How it Works with Key Steps
1. **Extracting Data**: Extracts `offset`, `limit`, `hostId`, `groupId`, `apiId`, `apiVersion`, and `endpoint` from the input map.
2. **Handling Empty Fields**: Checks if `groupId`, `apiId`, `apiVersion`, and `endpoint` are empty and sets them to null if they are.
3. **Database Query**: Queries the database for group row filters using the extracted data.
4. **Handling Query Failure**: If the query fails, returns an error status.
5. **Handling Query Success**: If the query succeeds, logs and returns the result.

### Input
- `offset` (Integer): The offset for pagination.
- `limit` (Integer): The limit for pagination.
- `hostId` (String): The host identifier.
- `groupId` (String): The group identifier (optional).
- `apiId` (String): The API identifier (optional).
- `apiVersion` (String): The API version (optional).
- `endpoint` (String): The endpoint (optional).

### Output
- ByteBuffer containing the group row filters or an error status.

### Endpoint
- `lightapi.net/group/queryGroupRowFilter/0.1.0`

## 6. QueryGroupUser Handler

### How it Works with Key Steps
1. **Extracting Data**: Extracts `offset`, `limit`, `hostId`, `groupId`, `userId`, `entityId`, `email`, `firstName`, `lastName`, and `userType` from the input map.
2. **Handling Empty Fields**: Checks if `groupId`, `userId`, `entityId`, `email`, `firstName`, `lastName`, and `userType` are empty and sets them to null if they are.
3. **Database Query**: Queries the database for group users using the extracted data.
4. **Handling Query Failure**: If the query fails, returns an error status.
5. **Handling Query Success**: If the query succeeds, logs and returns the result.

### Input
- `offset` (Integer): The offset for pagination.
- `limit` (Integer): The limit for pagination.
- `hostId` (String): The host identifier.
- `groupId` (String): The group identifier (optional).
- `userId` (String): The user identifier (optional).
- `entityId` (String): The entity identifier (optional).
- `email` (String): The email address (optional).
- `firstName` (String): The first name (optional).
- `lastName` (String): The last name (optional).
- `userType` (String): The user type (optional).

### Output
- ByteBuffer containing the group users or an error status.

### Endpoint
- `lightapi.net/group/queryGroupUser/0.1.0`
