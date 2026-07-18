# MCP Router: protocols.stateless.maxConcurrentRequests

`maxConcurrentRequests` caps in-flight stateless MCP requests in one gateway
process.

- **Type:** Positive integer
- **Default:** `1024`

Admission is fail-fast and uses an owned semaphore, so completion,
cancellation, or panic releases capacity automatically. When no global permit
is available, the request returns HTTP `429` with an MCP resource-limit error.
Legacy session requests use separate controls.

