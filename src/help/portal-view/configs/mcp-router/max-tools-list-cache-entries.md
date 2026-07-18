# MCP Router: protocols.stateless.maxToolsListCacheEntries

`maxToolsListCacheEntries` caps cached stateless `tools/list` results in one
gateway process.

- **Type:** Positive integer
- **Default:** `4096`

The cache is process-local, TTL-bound, and evicts the least recently touched
key when capacity is exceeded. Entries vary by principal, protocol, relevant
headers, configuration revision, and policy revision, so this limit may need to
be larger than the discovery cache in multi-tenant deployments.

