# Client Query Service
- [Github Link](https://github.com/lightapi/client-query)

## 1. GetApp Handler

### How it Works with Key Steps
1. **Extracting Data**: Extracts `hostId`, `offset`, `limit`, `appId`, `appName`, `appDesc`, `isKafkaApp`, `operationOwner`, and `deliveryOwner` from the input map.
2. **Database Query**: Uses the `PortalDbProvider` to query the database for apps based on the extracted parameters.
3. **Result Handling**: Checks if the query result is successful.
4. **Response Handling**: If the query is successful, returns the result. If not, returns an error status.

### Input
- `hostId` (String): Host identifier.
- `offset` (Integer): Record offset.
- `limit` (Integer): Record limit.
- `appId` (String, optional): Application identifier.
- `appName` (String, optional): Application name.
- `appDesc` (String, optional): Application description.
- `isKafkaApp` (Boolean, optional): Indicates if the app is a Kafka app.
- `operationOwner` (String, optional): Operation owner.
- `deliveryOwner` (String, optional): Delivery owner.

### Output
- ByteBuffer containing the query result or an error status.

### Endpoint
- `lightapi.net/client/getApp/0.1.0`

## 2. GetAppIdLabel Handler

### How it Works with Key Steps
1. **Extracting Data**: Extracts `hostId` from the input map.
2. **Database Query**: Uses the `PortalDbProvider` to query the database for app ID labels based on the `hostId`.
3. **Result Handling**: Checks if the query result is successful.
4. **Response Handling**: If the query is successful, returns the result. If not, returns an error status.

### Input
- `hostId` (String): Host identifier.

### Output
- ByteBuffer containing the query result or an error status.

### Endpoint
- `lightapi.net/client/getAppIdLabel/0.1.0`