# Access Control: Skip Path Prefixes

The `skipPathPrefixes` property specifies a list of path or tool name prefixes that bypass access control checking and filtering entirely.

## Configuration Options

```yaml
skipPathPrefixes:
  - /api/v1/public
  - local_mcp
```

---

## Behavior Separation

### HTTP API Access Control
For HTTP API traffic, the gateway compares the request URI path against the configured prefixes:
* If the request path starts with one of the prefixes in `skipPathPrefixes` (e.g., `/api/v1/public`), the request bypasses the request authorization (`req-acc`) phase and the response bypasses response filtering (`res-fil`).
* This is commonly used for health check endpoints, public documentation, or unauthenticated assets.

### MCP Router Access Control
For MCP traffic, the router applies prefix matching in two distinct ways:
1. **Tool Name Prefix**: If the invoked tool name starts with a prefix listed in `skipPathPrefixes` (e.g. `local_mcp` matching a tool named `local_mcp_echo`), the tool call bypasses `req-acc` and the results bypass `res-fil` response filtering.
2. **Endpoint Key Prefix**: If the target endpoint key derived for the tool call starts with a configured prefix (e.g. `accounts` matching `accounts@call`), the tool call and response also bypass all access control enforcement.
