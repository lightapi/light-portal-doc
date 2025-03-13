# Host Query Service
- [Github Link](https://github.com/lightapi/host-query)

## 1. GetHost Handler

### How it Works with Key Steps
1. **Extracting Data**: Extracts `offset`, `limit`, `hostId`, `domain`, `subDomain`, `hostDesc`, and `hostOwner` from the input map.
2. **Logging Parameters**: Logs the extracted parameters for traceability.
3. **Database Query**: Queries the `host_t` table using the extracted parameters.
4. **Result Handling**: Checks if the query result is successful.
5. **Response Handling**: Returns the query result or an error status if the query fails.

### Input
- `offset` (Integer): Record offset.
- `limit` (Integer): Record limit.
- `hostId` (String): Host identifier (optional).
- `domain` (String): Domain name (optional).
- `subDomain` (String): Subdomain name (optional).
- `hostDesc` (String): Host description (optional).
- `hostOwner` (String): Host owner (optional).

### Output
- ByteBuffer containing the query result or an error status.

### Endpoint
- `lightapi.net/host/getHost/0.1.0`

## 2. GetHostByDomain Handler

### How it Works with Key Steps
1. **Extracting Data**: Extracts `domain`, `subDomain`, and `hostDesc` from the input map.
2. **Logging Parameters**: Logs the extracted parameters for traceability.
3. **Database Query**: Queries the `host_t` table using the extracted parameters.
4. **Result Handling**: Checks if the query result is successful.
5. **Response Handling**: Returns the query result or an error status if the query fails.

### Input
- `domain` (String): Domain name.
- `subDomain` (String): Subdomain name (optional).
- `hostDesc` (String): Host description (optional).

### Output
- ByteBuffer containing the query result or an error status.

### Endpoint
- `lightapi.net/host/getHostByDomain/0.1.0`

## 3. GetHostById Handler

### How it Works with Key Steps
1. **Extracting Data**: Extracts `hostId` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID.
3. **Token Validation**: Ensures the token type is correct.
4. **Database Query**: Queries the `host_t` table using the `hostId`.
5. **Result Handling**: Checks if the query result is successful.
6. **Response Handling**: Returns the query result or an error status if the query fails.

### Input
- `hostId` (String): Host identifier.

### Output
- ByteBuffer containing the query result or an error status.

### Endpoint
- `lightapi.net/host/getHostById/0.1.0`

## 4. GetHostDomainById Handler

### How it Works with Key Steps
1. **Extracting Data**: Extracts `hostId` from the input map.
2. **User Authentication**: Retrieves audit information from the exchange and verifies the user ID.
3. **Token Validation**: Ensures the token type is correct.
4. **Database Query**: Queries the `host_t` table using the `hostId`.
5. **Result Handling**: Checks if the query result is successful.
6. **Response Handling**: Returns the query result or an error status if the query fails.

### Input
- `hostId` (String): Host identifier.

### Output
- ByteBuffer containing the query result or an error status.

### Endpoint
- `lightapi.net/host/getHostDomainById/0.1.0`

## 5. GetHostLabel Handler

### How it Works with Key Steps
1. **Database Query**: Queries the `host_t` table to get host labels.
2. **Result Handling**: Checks if the query result is successful.
3. **Response Handling**: Returns the query result or an error status if the query fails.

### Input
- No input required.

### Output
- ByteBuffer containing the query result or an error status.

### Endpoint
- `lightapi.net/host/getHostLabel/0.1.0`

## 6. GetOrg Handler

### How it Works with Key Steps
1. **Extracting Data**: Extracts `offset`, `limit`, `domain`, `orgName`, `orgDesc`, and `orgOwner` from the input map.
2. **Database Query**: Queries the `org_t` table using the extracted parameters.
3. **Result Handling**: Checks if the query result is successful.
4. **Response Handling**: Returns the query result or an error status if the query fails.

### Input
- `offset` (Integer): Record offset.
- `limit` (Integer): Record limit.
- `domain` (String): Domain name (optional).
- `orgName` (String): Organization name (optional).
- `orgDesc` (String): Organization description (optional).
- `orgOwner` (String): Organization owner (optional).

### Output
- ByteBuffer containing the query result or an error status.

### Endpoint
- `lightapi.net/host/getOrg/0.1.0`
