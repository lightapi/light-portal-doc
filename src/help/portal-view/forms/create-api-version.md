# Create API Version

Use this form to add a version to an existing API.

After submission, the API version can be linked to instances, gateway flows,
MCP tools, marketplace publishing, and access-control rules.

Important fields:

- `apiId`: parent API
- `apiVersion`: version label
- `apiType`: API style such as OpenAPI, GraphQL, Hybrid, or MCP
- `serviceId`: backing service identifier
- `spec`: API specification text, or MCP `tools/list` JSON output for MCP API versions
- `transportConfig`: MCP transport and URL when `apiType` is MCP
- `ownerPositionId`: optional position owner for team access

## MCP Tool Discovery

For MCP API versions, there are two ways to populate tools:

- If the portal service can reach the MCP server, select `MCP` as the API Type and fill `transportConfig`, for example `{"transport":"streamable http","url":"http://localhost:5000/mcp"}`.
- If the portal service cannot reach the MCP server because of firewall or security boundaries, call the MCP server yourself and paste the response into `spec`.

Example manual discovery call:

```bash
curl --location --request POST 'http://localhost:5000/mcp' \
  --header 'Content-Type: application/json' \
  --data-raw '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
```

Paste the response into `Spec / MCP Tools JSON`. The form accepts any of these
payload shapes.

Full JSON-RPC response:

```json
{
  "jsonrpc": "2.0",
  "result": {
    "tools": [
      {
        "name": "echo",
        "description": "Echoes back the input",
        "inputSchema": {
          "type": "object",
          "properties": {
            "message": {
              "type": "string"
            }
          },
          "required": [
            "message"
          ]
        }
      }
    ]
  },
  "id": 1
}
```

Object with a top-level `tools` array:

```json
{
  "tools": [
    {
      "name": "echo",
      "description": "Echoes back the input",
      "inputSchema": {
        "type": "object",
        "properties": {
          "message": {
            "type": "string"
          }
        },
        "required": [
          "message"
        ]
      }
    }
  ]
}
```

Raw tools array:

```json
[
  {
    "name": "echo",
    "description": "Echoes back the input",
    "inputSchema": {
      "type": "object",
      "properties": {
        "message": {
          "type": "string"
        }
      },
      "required": [
        "message"
      ]
    }
  }
]
```

Keep `transportConfig` populated with the real MCP transport and URL when the runtime still needs it for invocation.
