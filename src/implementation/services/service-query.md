# Service Query Service
- [Github Link](https://github.com/lightapi/service-query)

## 1. GetApiLabel Handler

### Key Steps
1. **Extracting Data**: Extracts `apiId` from the input map.
2. **Database Query**: Queries the database to retrieve the label for the given `apiId`.
3. **Response Construction**: Constructs a response with the retrieved label.
4. **Logging Output**: Logs the output before sending the response.

### Input
- `apiId` (String): API identifier.

### Output
- `label` (String): The label of the API.

### Endpoint
- `lightapi.net/service/getApiLabel/0.1.0`

## 2. GetApiVersionLabel Handler

### Key Steps
1. **Extracting Data**: Extracts `apiId` and `version` from the input map.
2. **Database Query**: Queries the database to retrieve the label for the given `apiId` and `version`.
3. **Response Construction**: Constructs a response with the retrieved label.
4. **Logging Output**: Logs the output before sending the response.

### Input
- `apiId` (String): API identifier.
- `version` (String): Version of the API.

### Output
- `label` (String): The label of the API version.

### Endpoint
- `lightapi.net/service/getApiVersionLabel/0.1.0`

## 3. GetEndpointLabel Handler

### Key Steps
1. **Extracting Data**: Extracts `endpointId` from the input map.
2. **Database Query**: Queries the database to retrieve the label for the given `endpointId`.
3. **Response Construction**: Constructs a response with the retrieved label.
4. **Logging Output**: Logs the output before sending the response.

### Input
- `endpointId` (String): Endpoint identifier.

### Output
- `label` (String): The label of the endpoint.

### Endpoint
- `lightapi.net/service/getEndpointLabel/0.1.0`

## 4. GetEndpointRule Handler

### Key Steps
1. **Extracting Data**: Extracts `endpointId` from the input map.
2. **Database Query**: Queries the database to retrieve the rule for the given `endpointId`.
3. **Response Construction**: Constructs a response with the retrieved rule.
4. **Logging Output**: Logs the output before sending the response.

### Input
- `endpointId` (String): Endpoint identifier.

### Output
- `rule` (String): The rule of the endpoint.

### Endpoint
- `lightapi.net/service/getEndpointRule/0.1.0`

## 5. GetEndpointScope Handler

### Key Steps
1. **Extracting Data**: Extracts `endpointId` from the input map.
2. **Database Query**: Queries the database to retrieve the scope for the given `endpointId`.
3. **Response Construction**: Constructs a response with the retrieved scope.
4. **Logging Output**: Logs the output before sending the response.

### Input
- `endpointId` (String): Endpoint identifier.

### Output
- `scope` (String): The scope of the endpoint.

### Endpoint
- `lightapi.net/service/getEndpointScope/0.1.0`

## 6. GetService Handler

### Key Steps
1. **Extracting Data**: Extracts `serviceId` from the input map.
2. **Database Query**: Queries the database to retrieve the service details for the given `serviceId`.
3. **Response Construction**: Constructs a response with the retrieved service details.
4. **Logging Output**: Logs the output before sending the response.

### Input
- `serviceId` (String): Service identifier.

### Output
- `serviceDetails` (Object): The details of the service.

### Endpoint
- `lightapi.net/service/getService/0.1.0`

## 7. GetServiceById Handler

### Key Steps
1. **Extracting Data**: Extracts `serviceId` from the input map.
2. **Database Query**: Queries the database to retrieve the service details for the given `serviceId`.
3. **Response Construction**: Constructs a response with the retrieved service details.
4. **Logging Output**: Logs the output before sending the response.

### Input
- `serviceId` (String): Service identifier.

### Output
- `serviceDetails` (Object): The details of the service.

### Endpoint
- `lightapi.net/service/getServiceById/0.1.0`

## 8. GetServiceEndpoint Handler

### Key Steps
1. **Extracting Data**: Extracts `serviceId` and `endpointId` from the input map.
2. **Database Query**: Queries the database to retrieve the endpoint details for the given `serviceId` and `endpointId`.
3. **Response Construction**: Constructs a response with the retrieved endpoint details.
4. **Logging Output**: Logs the output before sending the response.

### Input
- `serviceId` (String): Service identifier.
- `endpointId` (String): Endpoint identifier.

### Output
- `endpointDetails` (Object): The details of the endpoint.

### Endpoint
- `lightapi.net/service/getServiceEndpoint/0.1.0`

## 9. GetServiceIdLabel Handler

### Key Steps
1. **Extracting Data**: Extracts `serviceId` from the input map.
2. **Database Query**: Queries the database to retrieve the label for the given `serviceId`.
3. **Response Construction**: Constructs a response with the retrieved label.
4. **Logging Output**: Logs the output before sending the response.

### Input
- `serviceId` (String): Service identifier.

### Output
- `label` (String): The label of the service.

### Endpoint
- `lightapi.net/service/getServiceIdLabel/0.1.0`

## 10. GetServicePermission Handler

### Key Steps
1. **Extracting Data**: Extracts `serviceId` from the input map.
2. **Database Query**: Queries the database to retrieve the permissions for the given `serviceId`.
3. **Response Construction**: Constructs a response with the retrieved permissions.
4. **Logging Output**: Logs the output before sending the response.

### Input
- `serviceId` (String): Service identifier.

### Output
- `permissions` (List): The permissions of the service.

### Endpoint
- `lightapi.net/service/getServicePermission/0.1.0`

## 11. GetServiceRoleById Handler

### Key Steps
1. **Extracting Data**: Extracts `roleId` from the input map.
2. **Database Query**: Queries the database to retrieve the role details for the given `roleId`.
3. **Response Construction**: Constructs a response with the retrieved role details.
4. **Logging Output**: Logs the output before sending the response.

### Input
- `roleId` (String): Role identifier.

### Output
- `roleDetails` (Object): The details of the role.

### Endpoint
- `lightapi.net/service/getServiceRoleById/0.1.0`

## 12. GetServiceRule Handler

### Key Steps
1. **Extracting Data**: Extracts `serviceId` from the input map.
2. **Database Query**: Queries the database to retrieve the rule for the given `serviceId`.
3. **Response Construction**: Constructs a response with the retrieved rule.
4. **Logging Output**: Logs the output before sending the response.

### Input
- `serviceId` (String): Service identifier.

### Output
- `rule` (String): The rule of the service.

### Endpoint
- `lightapi.net/service/getServiceRule/0.1.0`

## 13. GetServiceVersion Handler

### Key Steps
1. **Extracting Data**: Extracts `serviceId` from the input map.
2. **Database Query**: Queries the database to retrieve the version for the given `serviceId`.
3. **Response Construction**: Constructs a response with the retrieved version.
4. **Logging Output**: Logs the output before sending the response.

### Input
- `serviceId` (String): Service identifier.

### Output
- `version` (String): The version of the service.

### Endpoint
- `lightapi.net/service/getServiceVersion/0.1.0`
