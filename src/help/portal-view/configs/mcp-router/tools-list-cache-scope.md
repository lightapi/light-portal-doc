# MCP Router: protocols.stateless.toolsListCacheScope

`toolsListCacheScope` declares the privacy scope of cached stateless
`tools/list` responses.

- **Type:** String
- **Default and only supported value:** `private`

Tool visibility is authorization-sensitive, so cache entries are keyed by
principal fingerprint, policy/config revisions, protocol version, and relevant
headers. The gateway reports `cacheScope: private`; configuring another value
rejects the stateless profile.

