# OpenAPI Endpoint Parameter Mapping Design

This document outlines the design for passing OpenAPI parameter mapping details (path parameters, query parameters, headers, cookies, and body) from `SpecUtil` to the `mcp-router` in `light-fabric`. This enables the MCP router to correctly invoke the backend REST APIs based on flat tool call arguments provided by AI agents.

---

## Context & Motivation

When the OpenAPI specification is parsed by `SpecUtil.java`, endpoints are registered in the Light Portal database, and a flat `toolSchema` is generated to represent the input schema.

For example, given a GET request with query parameters (like `/offers`) or path parameters (like `/customers/{customerId}`), the parameters are flattened into a single JSON schema structure:
```json
{
  "type": "object",
  "properties": {
    "segment": { "type": "string", "description": "Customer segment filter." },
    "state": { "type": "string", "description": "Region or province filter." }
  }
}
```

The AI agent invokes this tool by passing a flat map of arguments:
```json
{
  "segment": "premium",
  "state": "ON"
}
```

Currently, the `mcp-router` in `light-fabric` does not know where each argument belongs (e.g., whether it should be placed in the URL path, query string, headers, or request body). For `GET` requests, it defaults to appending all arguments as query parameters. For `POST`/`PUT`/`PATCH` requests, it defaults to placing all arguments in the JSON body.

This leads to several failures:
1. **Path parameters** (e.g. `{customerId}`) are not substituted in the URL path.
2. **Header parameters** and **Cookies** are completely lost or put in the wrong place.
3. Mixed requests (e.g. a `POST` with a URL path parameter and a JSON body) cannot be assembled correctly.

---

## Design Requirements

- **Accuracy**: The router must place every argument in the exact location (path, query, header, cookie, or body) defined by the OpenAPI specification.
- **Efficiency / Cleanliness**: The solution must not increase token usage for the LLM agents. Gateway-specific routing details should remain hidden from public tool schemas exposed to agents.
- **Backward Compatibility**: If no mapping metadata is provided, the router should fall back to its existing default routing rules.

---

## Design Options for Storing Parameter Locations

We evaluated two options for conveying parameter mapping information from the Spec parser to the gateway router:

### Option A: Schema-Level Annotations (`toolSchema`)
Inject custom attributes (such as `"x-in": "query"`, `"x-in": "path"`) directly into the JSON Schema properties:
```json
{
  "type": "object",
  "properties": {
    "customerId": {
      "type": "string",
      "x-in": "path"
    }
  }
}
```
* **Pros**: Self-contained schema where each field is annotated with its location.
* **Cons**: Increases the payload size of `inputSchema` sent to the LLM agent via `tools/list`, leading to wasted token count and exposing gateway-internal routing details to the agent.

### Option B: Metadata-Level Mappings (`toolMetadata`) - *RECOMMENDED*
Store the parameter locations in the private `toolMetadata` payload, which is saved in the database and loaded by the gateway, but is filtered out and never sent to the LLM agent.
```json
{
  "routing": {
    "domain": "Offers",
    "sourceProtocol": "openapi"
  },
  "parameters": {
    "customerId": "path",
    "segment": "query",
    "X-Trace-Id": "header",
    "body": "body"
  }
}
```
* **Pros**:
  - Keeps the public `toolSchema` clean and minimal.
  - Saves LLM token costs.
  - Consistently places all gateway-internal routing decisions inside the private `toolMetadata` structure.
* **Cons**: Slightly split parsing (schema for validation, metadata for execution), but since the gateway already deserializes both, this has negligible overhead.

---

## Detailed Solution

We will implement **Option B**. The design requires updates to two components: `SpecUtil.java` (spec parsing) and `mcp.rs` (routing execution in the Rust gateway).

### 1. Spec Parser Changes (`SpecUtil.java`)

When parsing an OpenAPI spec in `SpecUtil.java`, we will build a `parameters` location map of type `Map<String, String>` mapping each parameter name to its location:

- `path` -> `"path"`
- `query` -> `"query"`
- `header` -> `"header"`
- `cookie` -> `"cookie"`
- Request Body -> `"body"` (mapped from the unified schema body property for body-capable HTTP methods)

This map will be attached to `routingExtras` during metadata enrichment under the `"parameters"` key, resulting in the following `toolMetadata` structure:

```json
{
  "routing": {
    "domain": "Offers",
    "sourceProtocol": "openapi",
    "parameters": {
      "segment": "query",
      "state": "query",
      "customerId": "path"
    }
  },
  "safety": {
    "read_only": true,
    "destructive": false
  }
}
```

### 2. Rust Gateway Router Changes (`mcp.rs`)

The `mcp.rs` module in `light-pingora` will be updated as follows:

1. **Extract Parameter Locations**: When caching or loading tools, the router will deserialize the `parameters` map from `tool_metadata.routing.parameters`.
2. **Argument Placement**: When executing an HTTP tool call, the router will partition the `arguments` map into:
   - **Path Map**: Key-value pairs where location is `"path"`.
   - **Query Map**: Key-value pairs where location is `"query"`.
   - **Header Map**: Key-value pairs where location is `"header"`.
   - **Cookie Map**: Key-value pairs where location is `"cookie"`.
   - **Body Val**: The argument corresponding to the key mapped to `"body"`. If no explicit body mapping is defined but the HTTP method allows a body (POST/PUT/PATCH), any arguments not explicitly mapped to path/query/header/cookie will be packed into the JSON request body.
3. **Build Outbound Request**:
   - **Path Substitution**: Iterate through the path map and replace `{key}` placeholders in the tool URL path.
   - **Query Serialization**: Append the query map properties to the target URL's query string using URL-encoding.
   - **Header Injection**: Append header map values as HTTP headers.
   - **Cookie Injection**: Format cookie map values into the `Cookie` header.
   - **Body Serialization**: Attach the JSON body payload to the outbound HTTP request.

---

## Concrete Examples

### Example 1: GET `/offers` (Query Filters)

#### Original OpenAPI Specification
```yaml
  /offers:
    get:
      operationId: searchOffers
      parameters:
        - name: segment
          in: query
          schema:
            type: string
        - name: state
          in: query
          schema:
            type: string
```

#### Generated Database Artifacts
* **`toolSchema`**:
  ```json
  {
    "type": "object",
    "properties": {
      "segment": { "type": "string" },
      "state": { "type": "string" }
    }
  }
  ```
* **`toolMetadata`**:
  ```json
  {
    "routing": {
      "domain": "Offers",
      "sourceProtocol": "openapi",
      "parameters": {
        "segment": "query",
        "state": "query"
      }
    }
  }
  ```

#### Tool Call Arguments
```json
{
  "segment": "premium",
  "state": "ON"
}
```

#### Outgoing REST Call
```http
GET /offers?segment=premium&state=ON HTTP/1.1
Host: backend-service
```

---

### Example 2: GET `/customers/{customerId}` (Path Parameter)

#### Original OpenAPI Specification
```yaml
  /customers/{customerId}:
    get:
      operationId: getCustomerProfile
      parameters:
        - name: customerId
          in: path
          required: true
          schema:
            type: string
```

#### Generated Database Artifacts
* **`toolSchema`**:
  ```json
  {
    "type": "object",
    "properties": {
      "customerId": { "type": "string" }
    },
    "required": ["customerId"]
  }
  ```
* **`toolMetadata`**:
  ```json
  {
    "routing": {
      "domain": "Customers",
      "sourceProtocol": "openapi",
      "parameters": {
        "customerId": "path"
      }
    }
  }
  ```

#### Tool Call Arguments
```json
{
  "customerId": "CUST-1001"
}
```

#### Outgoing REST Call
```http
GET /customers/CUST-1001 HTTP/1.1
Host: backend-service
```

---

### Example 3: PUT `/customers/{customerId}/preferences` (Mixed Path & Body)

#### Original OpenAPI Specification
```yaml
  /customers/{customerId}/preferences:
    put:
      operationId: updateCustomerPreferences
      parameters:
        - name: customerId
          in: path
          required: true
          schema:
            type: string
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              properties:
                channel:
                  type: string
                consent:
                  type: boolean
```

#### Generated Database Artifacts
* **`toolSchema`**:
  ```json
  {
    "type": "object",
    "properties": {
      "customerId": { "type": "string" },
      "body": {
        "type": "object",
        "properties": {
          "channel": { "type": "string" },
          "consent": { "type": "boolean" }
        }
      }
    },
    "required": ["customerId", "body"]
  }
  ```
* **`toolMetadata`**:
  ```json
  {
    "routing": {
      "domain": "Customers",
      "sourceProtocol": "openapi",
      "parameters": {
        "customerId": "path",
        "body": "body"
      }
    }
  }
  ```

#### Tool Call Arguments
```json
{
  "customerId": "CUST-1001",
  "body": {
    "channel": "portal",
    "consent": true
  }
}
```

#### Outgoing REST Call
```http
PUT /customers/CUST-1001/preferences HTTP/1.1
Host: backend-service
Content-Type: application/json

{"channel":"portal","consent":true}
```
