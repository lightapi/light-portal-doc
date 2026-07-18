# MCP Router: maxJsonDepth

`maxJsonDepth` limits nesting in the parsed JSON-RPC request value.

- **Type:** Positive integer
- **Default:** `128`

Arrays, objects, and scalar leaves each contribute to the recursive depth. A
request exceeding the limit returns HTTP `400` and JSON-RPC code `-32600`.
This protects runtime request parsing; schema-document complexity is governed
separately by `schema.maxDepth` and `schema.maxSubschemas`.

