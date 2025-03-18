# Config Query Service
- [Github Link](https://github.com/lightapi/config-query)

## 1. GetConfig Handler

### Key Steps
1. **Extracting Data**: Extracts the required parameters from the input map, such as `configId`.
2. **Validation**: Validates the extracted parameters to ensure they meet the required format and constraints.
3. **Query Execution**: Queries the configuration database or service using the `configId`.
4. **Response Construction**: Constructs a response object containing the retrieved configuration details.
5. **Serialization**: Serializes the response object into a format suitable for transmission (e.g., JSON).
6. **Response Handling**: Sends the serialized response back to the client.

### Input
- `configId` (String): The unique identifier for the configuration to be retrieved.

### Output
- `config` (Object): The configuration details, including:
    - `id` (String): The unique identifier of the configuration.
    - `name` (String): The name of the configuration.
    - `value` (String): The value of the configuration.
    - `metadata` (Object): Additional metadata about the configuration.

### Endpoint
- `lightapi.net/config/getConfig/0.1.0`

---

## 2. GetConfigById Handler

### Key Steps
1. **Extracting Data**: Extracts the `configId` from the input map.
2. **Validation**: Validates the `configId` to ensure it is not null or empty.
3. **Query Execution**: Executes a query to fetch the configuration details by `configId`.
4. **Response Construction**: Constructs a response object with the retrieved configuration details.
5. **Serialization**: Serializes the response object into JSON format.
6. **Response Handling**: Sends the serialized response back to the client.

### Input
- `configId` (String): The unique identifier for the configuration.

### Output
- `config` (Object): The configuration details, including:
    - `id` (String): The unique identifier of the configuration.
    - `name` (String): The name of the configuration.
    - `value` (String): The value of the configuration.

### Endpoint
- `lightapi.net/config/getConfigById/0.1.0`

---

## 3. GetConfigEnvironment Handler

### Key Steps
1. **Extracting Data**: Extracts the `environmentId` from the input map.
2. **Validation**: Validates the `environmentId` to ensure it is valid.
3. **Query Execution**: Queries the database or service to fetch configurations for the specified environment.
4. **Response Construction**: Constructs a response object containing the list of configurations for the environment.
5. **Serialization**: Serializes the response object into JSON format.
6. **Response Handling**: Sends the serialized response back to the client.

### Input
- `environmentId` (String): The identifier for the environment.

### Output
- `configurations` (Array): A list of configuration objects, each containing:
    - `id` (String): The unique identifier of the configuration.
    - `name` (String): The name of the configuration.
    - `value` (String): The value of the configuration.

### Endpoint
- `lightapi.net/config/getConfigEnvironment/0.1.0`

---

## 4. GetConfigIdApiAppLabel Handler

### Key Steps
1. **Extracting Data**: Extracts `api`, `app`, and `label` from the input map.
2. **Validation**: Validates the extracted parameters to ensure they are not null or empty.
3. **Query Execution**: Queries the database or service to fetch the configuration ID based on the `api`, `app`, and `label`.
4. **Response Construction**: Constructs a response object containing the configuration ID.
5. **Serialization**: Serializes the response object into JSON format.
6. **Response Handling**: Sends the serialized response back to the client.

### Input
- `api` (String): The API identifier.
- `app` (String): The application identifier.
- `label` (String): The label associated with the configuration.

### Output
- `configId` (String): The unique identifier of the configuration.

### Endpoint
- `lightapi.net/config/getConfigIdApiAppLabel/0.1.0`

---

## 5. GetConfigIdLabel Handler

### Key Steps
1. **Extracting Data**: Extracts `label` from the input map.
2. **Validation**: Validates the `label` to ensure it is not null or empty.
3. **Query Execution**: Queries the database or service to fetch the configuration ID based on the `label`.
4. **Response Construction**: Constructs a response object containing the configuration ID.
5. **Serialization**: Serializes the response object into JSON format.
6. **Response Handling**: Sends the serialized response back to the client.

### Input
- `label` (String): The label associated with the configuration.

### Output
- `configId` (String): The unique identifier of the configuration.

### Endpoint
- `lightapi.net/config/getConfigIdLabel/0.1.0`

---

## 6. GetConfigInstance Handler

### Key Steps
1. **Extracting Data**: Extracts `instanceId` from the input map.
2. **Validation**: Validates the `instanceId` to ensure it is not null or empty.
3. **Query Execution**: Queries the database or service to fetch the configuration instance details.
4. **Response Construction**: Constructs a response object containing the configuration instance details.
5. **Serialization**: Serializes the response object into JSON format.
6. **Response Handling**: Sends the serialized response back to the client.

### Input
- `instanceId` (String): The unique identifier for the configuration instance.

### Output
- `instance` (Object): The configuration instance details, including:
    - `id` (String): The unique identifier of the instance.
    - `name` (String): The name of the instance.
    - `value` (String): The value of the instance.

### Endpoint
- `lightapi.net/config/getConfigInstance/0.1.0`