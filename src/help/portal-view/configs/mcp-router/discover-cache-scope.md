# MCP Router: protocols.stateless.discoverCacheScope

`discoverCacheScope` declares the privacy scope of stateless
`server/discover` results.

- **Type:** String
- **Default and only supported value:** `private`

The result is cached with identity-, header-, configuration-, and
policy-sensitive keys and reports `cacheScope: private` to the client. Public
or shared caching is rejected because authentication, delegation, and policy
can affect what a caller is permitted to discover.

