# Attribute Query Service
- [Github Link](https://github.com/lightapi/attribute-query)

## 1. GetAttribute Handler

### How it Works with Key Steps
1. **Extracting Data**: Extracts `offset`, `limit`, `hostId`, `attributeId`, `attributeType`, and `attributeDesc` from the input map.
2. **Null Checks**: Checks if `attributeId`, `attributeType`, and `attributeDesc` are empty and sets them to null if they are.
3. **Logging Parameters**: Logs the extracted parameters.
4. **Database Query**: Queries the database for attributes using the extracted parameters.
5. **Error Handling**: Checks if the query result is a failure and returns an error status if it is.
6. **Logging Result**: Logs the query result.
7. **Response Handling**: Converts the query result to a ByteBuffer and returns it.

### Input
- `offset` (Integer): The offset for pagination.
- `limit` (Integer): The limit for pagination.
- `hostId` (String): The host identifier.
- `attributeId` (String): The attribute identifier (optional).
- `attributeType` (String): The attribute type (optional).
- `attributeDesc` (String): The attribute description (optional).

### Output
- ByteBuffer containing the list of attributes or an error status.

### Endpoint
- `lightapi.net/attribute/getAttribute/0.1.0`

## 2. GetAttributeLabel Handler

### How it Works with Key Steps
1. **Extracting Data**: Extracts `hostId` from the input map.
2. **Logging Parameters**: Logs the extracted parameters.
3. **Database Query**: Queries the database for attribute labels using the extracted parameters.
4. **Error Handling**: Checks if the query result is a failure and returns an error status if it is.
5. **Logging Result**: Logs the query result.
6. **Response Handling**: Converts the query result to a ByteBuffer and returns it.

### Input
- `hostId` (String): The host identifier.

### Output
- ByteBuffer containing the list of attribute labels or an error status.

### Endpoint
- `lightapi.net/attribute/getAttributeLabel/0.1.0`

## 3. QueryAttributeColFilter Handler

### How it Works with Key Steps
1. **Extracting Data**: Extracts `offset`, `limit`, `hostId`, `attributeId`, `attributeValue`, `apiId`, `apiVersion`, and `endpoint` from the input map.
2. **Null Checks**: Checks if `attributeId`, `attributeValue`, `apiId`, `apiVersion`, and `endpoint` are empty and sets them to null if they are.
3. **Database Query**: Queries the database for attribute column filters using the extracted parameters.
4. **Error Handling**: Checks if the query result is a failure and returns an error status if it is.
5. **Response Handling**: Converts the query result to a ByteBuffer and returns it.

### Input
- `offset` (Integer): The offset for pagination.
- `limit` (Integer): The limit for pagination.
- `hostId` (String): The host identifier.
- `attributeId` (String): The attribute identifier (optional).
- `attributeValue` (String): The attribute value (optional).
- `apiId` (String): The API identifier (optional).
- `apiVersion` (String): The API version (optional).
- `endpoint` (String): The endpoint (optional).

### Output
- ByteBuffer containing the list of attribute column filters or an error status.

### Endpoint
- `lightapi.net/attribute/queryAttributeColFilter/0.1.0`

## 4. QueryAttributePermission Handler

### How it Works with Key Steps
1. **Extracting Data**: Extracts `offset`, `limit`, `hostId`, `attributeId`, `attributeType`, `attributeValue`, `apiId`, `apiVersion`, and `endpoint` from the input map.
2. **Null Checks**: Checks if `attributeId`, `attributeType`, `attributeValue`, `apiId`, `apiVersion`, and `endpoint` are empty and sets them to null if they are.
3. **Database Query**: Queries the database for attribute permissions using the extracted parameters.
4. **Error Handling**: Checks if the query result is a failure and returns an error status if it is.
5. **Logging Result**: Logs the query result.
6. **Response Handling**: Converts the query result to a ByteBuffer and returns it.

### Input
- `offset` (Integer): The offset for pagination.
- `limit` (Integer): The limit for pagination.
- `hostId` (String): The host identifier.
- `attributeId` (String): The attribute identifier (optional).
- `attributeType` (String): The attribute type (optional).
- `attributeValue` (String): The attribute value (optional).
- `apiId` (String): The API identifier (optional).
- `apiVersion` (String): The API version (optional).
- `endpoint` (String): The endpoint (optional).

### Output
- ByteBuffer containing the list of attribute permissions or an error status.

### Endpoint
- `lightapi.net/attribute/queryAttributePermission/0.1.0`

## 5. QueryAttributeRowFilter Handler

### How it Works with Key Steps
1. **Extracting Data**: Extracts `offset`, `limit`, `hostId`, `attributeId`, `attributeValue`, `apiId`, `apiVersion`, and `endpoint` from the input map.
2. **Null Checks**: Checks if `attributeId`, `attributeValue`, `apiId`, `apiVersion`, and `endpoint` are empty and sets them to null if they are.
3. **Database Query**: Queries the database for attribute row filters using the extracted parameters.
4. **Error Handling**: Checks if the query result is a failure and returns an error status if it is.
5. **Response Handling**: Converts the query result to a ByteBuffer and returns it.

### Input
- `offset` (Integer): The offset for pagination.
- `limit` (Integer): The limit for pagination.
- `hostId` (String): The host identifier.
- `attributeId` (String): The attribute identifier (optional).
- `attributeValue` (String): The attribute value (optional).
- `apiId` (String): The API identifier (optional).
- `apiVersion` (String): The API version (optional).
- `endpoint` (String): The endpoint (optional).

### Output
- ByteBuffer containing the list of attribute row filters or an error status.

### Endpoint
- `lightapi.net/attribute/queryAttributeRowFilter/0.1.0`

## 6. QueryAttributeUser Handler

### How it Works with Key Steps
1. **Extracting Data**: Extracts `offset`, `limit`, `hostId`, `attributeId`, `attributeType`, `attributeValue`, `userId`, `entityId`, `email`, `firstName`, `lastName`, and `userType` from the input map.
2. **Null Checks**: Checks if `attributeId`, `attributeType`, `attributeValue`, `userId`, `entityId`, `email`, `firstName`, `lastName`, and `userType` are empty and sets them to null if they are.
3. **Database Query**: Queries the database for attribute-user relationships using the extracted parameters.
4. **Error Handling**: Checks if the query result is a failure and returns an error status if it is.
5. **Logging Result**: Logs the query result.
6. **Response Handling**: Converts the query result to a ByteBuffer and returns it.

### Input
- `offset` (Integer): The offset for pagination.
- `limit` (Integer): The limit for pagination.
- `hostId` (String): The host identifier.
- `attributeId` (String): The attribute identifier (optional).
- `attributeType` (String): The attribute type (optional).
- `attributeValue` (String): The attribute value (optional).
- `userId` (String): The user identifier (optional).
- `entityId` (String): The entity identifier (optional).
- `email` (String): The email address (optional).
- `firstName` (String): The first name (optional).
- `lastName` (String): The last name (optional).
- `userType` (String): The user type (optional).

### Output
- ByteBuffer containing the list of attribute-user relationships or an error status.

### Endpoint
- `lightapi.net/attribute/queryAttributeUser/0.1.0`
