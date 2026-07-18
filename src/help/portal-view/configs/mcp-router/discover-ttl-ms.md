# MCP Router: protocols.stateless.discoverTtlMs

`discoverTtlMs` is the lifetime of a cached stateless `server/discover` result.

- **Type:** Positive integer, in milliseconds
- **Default:** `30000`

The same value is returned to clients as the result's `ttlMs`. Cache keys
include protocol version, principal fingerprint, forwarded cache-vary headers,
configuration revision, and policy revision. Entries are process-local and are
recomputed after expiration or revision change.

