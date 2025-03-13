# OAuth Query Service
- [Github Link](https://github.com/lightapi/oauth-query)

## 1. GetAuthCode Handler

### How it Works with Key Steps
1. **Extracting Data**: Extracts `authCode` from the input map.
2. **Database Query**: Queries the database for the authorization code details.
3. **Response Handling**: Constructs the response with the authorization code details and returns it.

### Input
- `authCode` (String): Authorization code.

### Output
- JSON object containing the authorization code details.

### Endpoint
- `lightapi.net/oauth/getAuthCode/0.1.0`

## 2. GetAuthCodeDetail Handler

### How it Works with Key Steps
1. **Extracting Data**: Extracts `authCode` from the input map.
2. **Database Query**: Queries the database for detailed information about the authorization code.
3. **Response Handling**: Constructs the response with the detailed authorization code information and returns it.

### Input
- `authCode` (String): Authorization code.

### Output
- JSON object containing detailed authorization code information.

### Endpoint
- `lightapi.net/oauth/getAuthCodeDetail/0.1.0`

## 3. GetClient Handler

### How it Works with Key Steps
1. **Extracting Data**: Extracts `clientId` from the input map.
2. **Database Query**: Queries the database for the client details.
3. **Response Handling**: Constructs the response with the client details and returns it.

### Input
- `clientId` (String): Client identifier.

### Output
- JSON object containing the client details.

### Endpoint
- `lightapi.net/oauth/getClient/0.1.0`

## 4. GetClientById Handler

### How it Works with Key Steps
1. **Extracting Data**: Extracts `clientId` from the input map.
2. **Database Query**: Queries the database for the client details by ID.
3. **Response Handling**: Constructs the response with the client details and returns it.

### Input
- `clientId` (String): Client identifier.

### Output
- JSON object containing the client details.

### Endpoint
- `lightapi.net/oauth/getClientById/0.1.0`

## 5. GetClientByProviderClientId Handler

### How it Works with Key Steps
1. **Extracting Data**: Extracts `providerClientId` from the input map.
2. **Database Query**: Queries the database for the client details by provider client ID.
3. **Response Handling**: Constructs the response with the client details and returns it.

### Input
- `providerClientId` (String): Provider client identifier.

### Output
- JSON object containing the client details.

### Endpoint
- `lightapi.net/oauth/getClientByProviderClientId/0.1.0`

## 6. GetProvider Handler

### How it Works with Key Steps
1. **Extracting Data**: Extracts `providerId` from the input map.
2. **Database Query**: Queries the database for the provider details.
3. **Response Handling**: Constructs the response with the provider details and returns it.

### Input
- `providerId` (String): Provider identifier.

### Output
- JSON object containing the provider details.

### Endpoint
- `lightapi.net/oauth/getProvider/0.1.0`

## 7. GetProviderDetail Handler

### How it Works with Key Steps
1. **Extracting Data**: Extracts `providerId` from the input map.
2. **Database Query**: Queries the database for detailed information about the provider.
3. **Response Handling**: Constructs the response with the detailed provider information and returns it.

### Input
- `providerId` (String): Provider identifier.

### Output
- JSON object containing detailed provider information.

### Endpoint
- `lightapi.net/oauth/getProviderDetail/0.1.0`

## 8. GetProviderKey Handler

### How it Works with Key Steps
1. **Extracting Data**: Extracts `providerId` from the input map.
2. **Database Query**: Queries the database for the provider key.
3. **Response Handling**: Constructs the response with the provider key and returns it.

### Input
- `providerId` (String): Provider identifier.

### Output
- JSON object containing the provider key.

### Endpoint
- `lightapi.net/oauth/getProviderKey/0.1.0`

## 9. GetRefreshToken Handler

### How it Works with Key Steps
1. **Extracting Data**: Extracts `refreshToken` from the input map.
2. **Database Query**: Queries the database for the refresh token details.
3. **Response Handling**: Constructs the response with the refresh token details and returns it.

### Input
- `refreshToken` (String): Refresh token.

### Output
- JSON object containing the refresh token details.

### Endpoint
- `lightapi.net/oauth/getRefreshToken/0.1.0`

## 10. GetRefreshTokenDetail Handler

### How it Works with Key Steps
1. **Extracting Data**: Extracts `refreshToken` from the input map.
2. **Database Query**: Queries the database for detailed information about the refresh token.
3. **Response Handling**: Constructs the response with the detailed refresh token information and returns it.

### Input
- `refreshToken` (String): Refresh token.

### Output
- JSON object containing detailed refresh token information.

### Endpoint
- `lightapi.net/oauth/getRefreshTokenDetail/0.1.0`

## 11. GetRefToken Handler

### How it Works with Key Steps
1. **Extracting Data**: Extracts `refToken` from the input map.
2. **Database Query**: Queries the database for the reference token details.
3. **Response Handling**: Constructs the response with the reference token details and returns it.

### Input
- `refToken` (String): Reference token.

### Output
- JSON object containing the reference token details.

### Endpoint
- `lightapi.net/oauth/getRefToken/0.1.0`

## 12. GetRefTokenDetail Handler

### How it Works with Key Steps
1. **Extracting Data**: Extracts `refToken` from the input map.
2. **Database Query**: Queries the database for detailed information about the reference token.
3. **Response Handling**: Constructs the response with the detailed reference token information and returns it.

### Input
- `refToken` (String): Reference token.

### Output
- JSON object containing detailed reference token information.

### Endpoint
- `lightapi.net/oauth/getRefTokenDetail/0.1.0`
