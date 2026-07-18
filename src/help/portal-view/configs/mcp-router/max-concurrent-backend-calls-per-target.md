# MCP Router: protocols.stateless.maxConcurrentBackendCallsPerTarget

`maxConcurrentBackendCallsPerTarget` caps concurrent calls to one normalized
backend target.

- **Type:** Positive integer
- **Default:** `32`

The limit applies to stateless frontend calls and calls to stateless MCP
backends. Different targets have independent semaphores. Capacity is fail-fast
and process-local; an exhausted target produces a tool execution error stating
that the backend exceeds a gateway resource limit.

