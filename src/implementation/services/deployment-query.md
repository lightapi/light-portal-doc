# Deployment Query Service
- [Github Link](https://github.com/lightapi/deployment-query)

## 1. GetDeployment Handler

### Key Steps
1. **Extracting Data**: Extracts `offset`, `limit`, `hostId`, `deploymentId`, `instanceId`, `deploymentStatus`, `deploymentType`, and `platformJobId` from the input map.
2. **Null Check**: Checks if any of the extracted values are blank and sets them to null if they are.
3. **Database Query**: Calls `dbProvider.getDeployment` with the extracted values to retrieve deployment data.
4. **Response Handling**: Checks if the result is a failure and returns an error status if it is. Otherwise, returns the result.

### Input
- `offset` (Integer): Offset for pagination.
- `limit` (Integer): Limit for pagination.
- `hostId` (String): Host identifier.
- `deploymentId` (String): Deployment identifier.
- `instanceId` (String): Instance identifier.
- `deploymentStatus` (String): Deployment status.
- `deploymentType` (String): Deployment type.
- `platformJobId` (String): Platform job identifier.

### Output
- ByteBuffer containing the deployment data or an error status.

### Endpoint
- `lightapi.net/deployment/getDeployment/0.1.0`

## 2. GetPipeline Handler

### Key Steps
1. **Extracting Data**: Extracts `offset`, `limit`, `hostId`, `pipelineId`, `platformId`, `endpoint`, `requestSchema`, and `responseSchema` from the input map.
2. **Null Check**: Checks if any of the extracted values are blank and sets them to null if they are.
3. **Database Query**: Calls `dbProvider.getPipeline` with the extracted values to retrieve pipeline data.
4. **Response Handling**: Checks if the result is a failure and returns an error status if it is. Otherwise, returns the result.

### Input
- `offset` (Integer): Offset for pagination.
- `limit` (Integer): Limit for pagination.
- `hostId` (String): Host identifier.
- `pipelineId` (String): Pipeline identifier.
- `platformId` (String): Platform identifier.
- `endpoint` (String): Endpoint.
- `requestSchema` (String): Request schema.
- `responseSchema` (String): Response schema.

### Output
- ByteBuffer containing the pipeline data or an error status.

### Endpoint
- `lightapi.net/deployment/getPipeline/0.1.0`

## 3. GetPipelineLabel Handler

### Key Steps
1. **Extracting Data**: Extracts `hostId` from the input map.
2. **Database Query**: Calls `dbProvider.getPipelineLabel` with the extracted `hostId` to retrieve pipeline label data.
3. **Response Handling**: Checks if the result is a failure and returns an error status if it is. Otherwise, returns the result.

### Input
- `hostId` (String): Host identifier.

### Output
- ByteBuffer containing the pipeline label data or an error status.

### Endpoint
- `lightapi.net/deployment/getPipelineLabel/0.1.0`

## 4. GetPlatform Handler

### Key Steps
1. **Extracting Data**: Extracts `offset`, `limit`, `hostId`, `platformId`, `platformName`, `platformVersion`, `clientType`, `clientUrl`, `credentials`, `proxyUrl`, `proxyPort`, `environment`, `systemEnv`, `runtimeEnv`, `zone`, `region`, and `lob` from the input map.
2. **Null Check**: Checks if any of the extracted values are blank and sets them to null if they are.
3. **Database Query**: Calls `dbProvider.getPlatform` with the extracted values to retrieve platform data.
4. **Response Handling**: Checks if the result is a failure and returns an error status if it is. Otherwise, returns the result.

### Input
- `offset` (Integer): Offset for pagination.
- `limit` (Integer): Limit for pagination.
- `hostId` (String): Host identifier.
- `platformId` (String): Platform identifier.
- `platformName` (String): Platform name.
- `platformVersion` (String): Platform version.
- `clientType` (String): Client type.
- `clientUrl` (String): Client URL.
- `credentials` (String): Credentials.
- `proxyUrl` (String): Proxy URL.
- `proxyPort` (Integer): Proxy port.
- `environment` (String): Environment.
- `systemEnv` (String): System environment.
- `runtimeEnv` (String): Runtime environment.
- `zone` (String): Zone.
- `region` (String): Region.
- `lob` (String): Line of business.

### Output
- ByteBuffer containing the platform data or an error status.

### Endpoint
- `lightapi.net/deployment/getPlatform/0.1.0`

## 5. GetPlatformLabel Handler

### Key Steps
1. **Extracting Data**: Extracts `hostId` from the input map.
2. **Database Query**: Calls `dbProvider.getPlatformLabel` with the extracted `hostId` to retrieve platform label data.
3. **Response Handling**: Checks if the result is a failure and returns an error status if it is. Otherwise, returns the result.

### Input
- `hostId` (String): Host identifier.

### Output
- ByteBuffer containing the platform label data or an error status.

### Endpoint
- `lightapi.net/deployment/getPlatformLabel/0.1.0`
