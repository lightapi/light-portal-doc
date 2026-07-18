# MCP Router: maxSessions

`maxSessions` caps legacy frontend sessions stored by one gateway process.

- **Type:** Positive integer
- **Default:** `10000`

Before rejecting a new initialize request, the router purges expired sessions.
Legacy sessions expire after 30 minutes of inactivity and the normal purge
interval is one minute. If the store remains full, initialization returns HTTP
`503` with an MCP resource-limit error. Stateless requests do not consume this
session store. Each gateway replica enforces its own limit.

