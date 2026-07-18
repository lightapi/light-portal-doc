# MCP Router: maxResponseBodyBytes

`maxResponseBodyBytes` bounds MCP responses and buffered downstream responses.

- **Type:** Integer of at least `2048`, in bytes
- **Default:** `4194304` (4 MiB)

The router checks known `Content-Length`, enforces the limit while buffering,
and bounds serialized JSON-RPC results such as `tools/list`. Oversized backend
or catalog results fail safely instead of allocating without limit. Values
below 2048 reject configuration because the gateway reserves enough space for
bounded protocol error responses.

