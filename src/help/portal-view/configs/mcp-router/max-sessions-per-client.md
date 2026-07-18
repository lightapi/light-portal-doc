# MCP Router: maxSessionsPerClient

`maxSessionsPerClient` caps legacy sessions for one trusted client binding.

- **Type:** Positive integer
- **Default:** `100`

Authenticated requests bind capacity to the authenticated principal. Anonymous
requests require a trusted connection binding, which is hashed before use.
Expired sessions are purged before the router rejects a new one. If the client
is still at the limit, initialization returns HTTP `429`. The counter is local
to each gateway process and does not affect stateless requests.

