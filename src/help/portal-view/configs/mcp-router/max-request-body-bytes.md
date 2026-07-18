# MCP Router: maxRequestBodyBytes

`maxRequestBodyBytes` limits the complete MCP HTTP request body.

- **Type:** Positive integer, in bytes
- **Default:** `1048576` (1 MiB)

The gateway reads the request through a bounded buffer before JSON parsing. A
larger body is rejected with HTTP `413` and JSON-RPC code `-32600`. Compressed
request bodies are rejected by the gateway's MCP path, so this budget applies
to the bytes actually received as the JSON request body.

