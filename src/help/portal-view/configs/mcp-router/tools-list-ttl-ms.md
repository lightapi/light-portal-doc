# MCP Router: protocols.stateless.toolsListTtlMs

`toolsListTtlMs` is the lifetime of a cached authorization-filtered stateless
`tools/list` result.

- **Type:** Positive integer, in milliseconds
- **Default:** `30000`

The result reports the same value as `ttlMs`. Cache keys bind the entry to the
principal, policy/config revisions, protocol version, and relevant forwarded
headers. A tool catalog or policy reload changes the revision and causes a new
result to be produced.

