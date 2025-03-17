# Instance Query Service
- [Github Link](https://github.com/lightapi/instance-query)

## 1. GetInstance Handler

### Key Steps
1. **Extracting Data**: Extracts various fields such as `offset`, `limit`, `hostId`, `instanceId`, `instanceName`, `productId`, `productVersion`, `serviceId`, `apiId`, `apiVersion`, `environment`, `pipelineId`, `serviceDesc`, `instanceDesc`, and `tagId` from the input map.
2. **Database Query**: Uses the `dbProvider` to query the database for instances matching the extracted criteria.
3. **Response Handling**: Checks if the query result is successful. If not, returns an error status. Otherwise, returns the query result.

### Input
- `offset` (Integer): The offset for pagination.
- `limit` (Integer): The limit for pagination.
- `hostId` (String): Host identifier.
- `instanceId` (String): Instance identifier.
- `instanceName` (String): Instance name.
- `productId` (String): Product identifier.
- `productVersion` (String): Product version.
- `serviceId` (String): Service identifier.
- `apiId` (String): API identifier.
- `apiVersion` (String): API version.
- `environment` (String): Environment.
- `pipelineId` (String): Pipeline identifier.
- `serviceDesc` (String): Service description.
- `instanceDesc` (String): Instance description.
- `tagId` (String): Tag identifier.

### Output
- ByteBuffer containing the status of the request or the query result.

### Endpoint
- `lightapi.net/instance/getInstance/0.1.0`

## 2. GetInstanceApi Handler

### Key Steps
1. **Extracting Data**: Extracts various fields such as `offset`, `limit`, `hostId`, `instanceId`, `apiId`, `apiVersion`, and `active` from the input map.
2. **Database Query**: Uses the `dbProvider` to query the database for instance APIs matching the extracted criteria.
3. **Response Handling**: Checks if the query result is successful. If not, returns an error status. Otherwise, returns the query result.

### Input
- `offset` (Integer): The offset for pagination.
- `limit` (Integer): The limit for pagination.
- `hostId` (String): Host identifier.
- `instanceId` (String): Instance identifier.
- `apiId` (String): API identifier.
- `apiVersion` (String): API version.
- `active` (Boolean): Active status.

### Output
- ByteBuffer containing the status of the request or the query result.

### Endpoint
- `lightapi.net/instance/getInstanceApi/0.1.0`

## 3. GetInstanceApp Handler

### Key Steps
1. **Extracting Data**: Extracts various fields such as `offset`, `limit`, `hostId`, `instanceId`, `appId`, `appVersion`, and `active` from the input map.
2. **Database Query**: Uses the `dbProvider` to query the database for instance apps matching the extracted criteria.
3. **Response Handling**: Checks if the query result is successful. If not, returns an error status. Otherwise, returns the query result.

### Input
- `offset` (Integer): The offset for pagination.
- `limit` (Integer): The limit for pagination.
- `hostId` (String): Host identifier.
- `instanceId` (String): Instance identifier.
- `appId` (String): Application identifier.
- `appVersion` (String): Application version.
- `active` (Boolean): Active status.

### Output
- ByteBuffer containing the status of the request or the query result.

### Endpoint
- `lightapi.net/instance/getInstanceApp/0.1.0`

## 4. GetInstanceLabel Handler

### Key Steps
1. **Extracting Data**: Extracts the `hostId` from the input map.
2. **Database Query**: Uses the `dbProvider` to query the database for instance labels matching the extracted `hostId`.
3. **Response Handling**: Checks if the query result is successful. If not, returns an error status. Otherwise, returns the query result.

### Input
- `hostId` (String): Host identifier.

### Output
- ByteBuffer containing the status of the request or the query result.

### Endpoint
- `lightapi.net/instance/getInstanceLabel/0.1.0`
