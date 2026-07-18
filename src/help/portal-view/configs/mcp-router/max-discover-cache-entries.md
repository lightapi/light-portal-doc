# MCP Router: protocols.stateless.maxDiscoverCacheEntries

`maxDiscoverCacheEntries` caps cached stateless `server/discover` results in one
gateway process.

- **Type:** Positive integer
- **Default:** `1024`

The cache removes expired records on lookup and evicts the least recently
touched key when insertion exceeds capacity. Entries are not shared across
gateway replicas. Because keys are principal- and revision-sensitive, size this
limit for the expected active identity and policy cardinality.

