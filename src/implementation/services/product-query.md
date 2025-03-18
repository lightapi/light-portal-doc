# Product Query Service
- [Github Link](https://github.com/lightapi/product-query)

## 1. GetProductVersion Handler

### Key Steps
1. **Extracting Data**: Extracts various fields such as `offset`, `limit`, `hostId`, `productId`, `productVersion`, `light4jVersion`, `breakCode`, `breakConfig`, `releaseNote`, `versionDesc`, `releaseType`, `current`, and `versionStatus` from the input map.
2. **Field Validation**: Validates the extracted fields to ensure they are not blank.
3. **Logging Details**: Logs detailed information about the extracted fields if trace logging is enabled.
4. **Database Query**: Uses the `dbProvider` to query the product version details from the database.
5. **Result Handling**: Checks if the query result is a failure or success.
6. **Response Handling**: Returns the appropriate response based on the query result.

### Input
- `offset` (Integer): Offset for pagination.
- `limit` (Integer): Limit for pagination.
- `hostId` (String): Host identifier.
- `productId` (String): Product identifier.
- `productVersion` (String): Product version.
- `light4jVersion` (String): Light-4j version.
- `breakCode` (Boolean): Break code flag.
- `breakConfig` (Boolean): Break config flag.
- `releaseNote` (String): Release note.
- `versionDesc` (String): Version description.
- `releaseType` (String): Release type.
- `current` (Boolean): Current version flag.
- `versionStatus` (String): Version status.

### Output
- ByteBuffer containing the status of the request or the result from the database query.

### Endpoint
- `lightapi.net/product/getProductVersion/0.1.0`

## 2. GetProductIdLabel Handler

### Key Steps
1. **Extracting Data**: Extracts `hostId` from the input map.
2. **Logging Details**: Logs detailed information about the extracted `hostId` if trace logging is enabled.
3. **Database Query**: Uses the `dbProvider` to query the product ID and label from the database.
4. **Result Handling**: Checks if the query result is a failure or success.
5. **Response Handling**: Returns the appropriate response based on the query result.

### Input
- `hostId` (String): Host identifier.

### Output
- ByteBuffer containing the status of the request or the result from the database query.

### Endpoint
- `lightapi.net/product/getProductIdLabel/0.1.0`

## 3. GetProductVersionLabel Handler

### Key Steps
1. **Extracting Data**: Extracts `hostId` and `productId` from the input map.
2. **Logging Details**: Logs detailed information about the extracted `hostId` and `productId` if trace logging is enabled.
3. **Database Query**: Uses the `dbProvider` to query the product version label from the database.
4. **Result Handling**: Checks if the query result is a failure or success.
5. **Response Handling**: Returns the appropriate response based on the query result.

### Input
- `hostId` (String): Host identifier.
- `productId` (String): Product identifier.

### Output
- ByteBuffer containing the status of the request or the result from the database query.

### Endpoint
- `lightapi.net/product/getProductVersionLabel/0.1.0`
