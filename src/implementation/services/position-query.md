# Position Query Service
- [Github Link](https://github.com/lightapi/position-query)

## 1. GetPosition Handler

### Key Steps
1. **Extracting Data**: Extracts `offset`, `limit`, `hostId`, `positionId`, `positionDesc`, `inheritToAncestor`, and `inheritToSibling` from the input map.
2. **Database Query**: Uses the extracted data to query the database for positions.
3. **Result Handling**: Checks if the query was successful and handles the result accordingly.
4. **Response Handling**: Converts the result to a ByteBuffer and returns it.

### Input
- `offset` (Integer): The offset for pagination.
- `limit` (Integer): The limit for pagination.
- `hostId` (String): Host identifier.
- `positionId` (String): Position identifier (optional).
- `positionDesc` (String): Position description (optional).
- `inheritToAncestor` (String): Inherit to ancestor flag (optional).
- `inheritToSibling` (String): Inherit to sibling flag (optional).

### Output
- ByteBuffer containing the positions data or an error message.

### Endpoint
- `lightapi.net/position/getPosition/0.1.0`

## 2. GetPositionLabel Handler

### Key Steps
1. **Extracting Data**: Extracts `hostId` from the input map.
2. **Database Query**: Uses the extracted data to query the database for position labels.
3. **Result Handling**: Checks if the query was successful and handles the result accordingly.
4. **Response Handling**: Converts the result to a ByteBuffer and returns it.

### Input
- `hostId` (String): Host identifier.

### Output
- ByteBuffer containing the position labels data or an error message.

### Endpoint
- `lightapi.net/position/getPositionLabel/0.1.0`

## 3. QueryPositionColFilter Handler

### Key Steps
1. **Extracting Data**: Extracts `offset`, `limit`, `hostId`, `positionId`, `apiId`, `apiVersion`, and `endpoint` from the input map.
2. **Database Query**: Uses the extracted data to query the database for position column filters.
3. **Result Handling**: Checks if the query was successful and handles the result accordingly.
4. **Response Handling**: Converts the result to a ByteBuffer and returns it.

### Input
- `offset` (Integer): The offset for pagination.
- `limit` (Integer): The limit for pagination.
- `hostId` (String): Host identifier.
- `positionId` (String): Position identifier (optional).
- `apiId` (String): API identifier (optional).
- `apiVersion` (String): API version (optional).
- `endpoint` (String): Endpoint (optional).

### Output
- ByteBuffer containing the position column filters data or an error message.

### Endpoint
- `lightapi.net/position/queryPositionColFilter/0.1.0`

## 4. QueryPositionRowFilter Handler

### Key Steps
1. **Extracting Data**: Extracts `offset`, `limit`, `hostId`, `positionId`, `apiId`, `apiVersion`, and `endpoint` from the input map.
2. **Database Query**: Uses the extracted data to query the database for position row filters.
3. **Result Handling**: Checks if the query was successful and handles the result accordingly.
4. **Response Handling**: Converts the result to a ByteBuffer and returns it.

### Input
- `offset` (Integer): The offset for pagination.
- `limit` (Integer): The limit for pagination.
- `hostId` (String): Host identifier.
- `positionId` (String): Position identifier (optional).
- `apiId` (String): API identifier (optional).
- `apiVersion` (String): API version (optional).
- `endpoint` (String): Endpoint (optional).

### Output
- ByteBuffer containing the position row filters data or an error message.

### Endpoint
- `lightapi.net/position/queryPositionRowFilter/0.1.0`

## 5. QueryPositionPermission Handler

### Key Steps
1. **Extracting Data**: Extracts `offset`, `limit`, `hostId`, `positionId`, `inheritToAncestor`, `inheritToSibling`, `apiId`, `apiVersion`, and `endpoint` from the input map.
2. **Database Query**: Uses the extracted data to query the database for position permissions.
3. **Result Handling**: Checks if the query was successful and handles the result accordingly.
4. **Response Handling**: Converts the result to a ByteBuffer and returns it.

### Input
- `offset` (Integer): The offset for pagination.
- `limit` (Integer): The limit for pagination.
- `hostId` (String): Host identifier.
- `positionId` (String): Position identifier (optional).
- `inheritToAncestor` (String): Inherit to ancestor flag (optional).
- `inheritToSibling` (String): Inherit to sibling flag (optional).
- `apiId` (String): API identifier (optional).
- `apiVersion` (String): API version (optional).
- `endpoint` (String): Endpoint (optional).

### Output
- ByteBuffer containing the position permissions data or an error message.

### Endpoint
- `lightapi.net/position/queryPositionPermission/0.1.0`

## 6. QueryPositionUser Handler

### Key Steps
1. **Extracting Data**: Extracts `offset`, `limit`, `hostId`, `positionId`, `positionType`, `inheritToAncestor`, `inheritToSibling`, `userId`, `entityId`, `email`, `firstName`, `lastName`, and `userType` from the input map.
2. **Database Query**: Uses the extracted data to query the database for position users.
3. **Result Handling**: Checks if the query was successful and handles the result accordingly.
4. **Response Handling**: Converts the result to a ByteBuffer and returns it.

### Input
- `offset` (Integer): The offset for pagination.
- `limit` (Integer): The limit for pagination.
- `hostId` (String): Host identifier.
- `positionId` (String): Position identifier (optional).
- `positionType` (String): Position type (optional).
- `inheritToAncestor` (String): Inherit to ancestor flag (optional).
- `inheritToSibling` (String): Inherit to sibling flag (optional).
- `userId` (String): User identifier (optional).
- `entityId` (String): Entity identifier (optional).
- `email` (String): Email address (optional).
- `firstName` (String): First name (optional).
- `lastName` (String): Last name (optional).
- `userType` (String): User type (optional).

### Output
- ByteBuffer containing the position users data or an error message.

### Endpoint
- `lightapi.net/position/queryPositionUser/0.1.0`
