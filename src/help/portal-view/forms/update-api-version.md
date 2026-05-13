# Update API Version

Use this form to update API version metadata and integration details.

Updating a version can affect downstream instance links, gateway behavior, and
task flows that reference the API version.

Important fields:

- `apiVersion`: version label
- `apiType`: API style
- `serviceId`: backing service identifier
- `spec`: API specification text, or MCP `tools/list` JSON output for MCP API versions
- `transportConfig`: MCP transport and URL when `apiType` is MCP
- `protocol`, `envTag`, and `targetHost`: runtime routing details
- `ownerPositionId`: optional position owner for team access

## MCP Tool Discovery

For MCP API versions, there are two ways to refresh tools:

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
