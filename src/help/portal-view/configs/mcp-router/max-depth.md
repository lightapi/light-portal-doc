# MCP Router: schema.maxDepth

`schema.maxDepth` limits nesting within each tool schema document.

- **Type:** Positive integer
- **Default:** `64`

The preflight traversal counts nested objects and arrays throughout the schema,
including definitions and keyword values. A schema whose traversal depth
exceeds the limit rejects configuration. Use `maxJsonDepth` for JSON-RPC
request values; the two limits protect different data structures.

