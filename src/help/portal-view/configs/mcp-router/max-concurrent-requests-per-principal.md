# MCP Router: protocols.stateless.maxConcurrentRequestsPerPrincipal

`maxConcurrentRequestsPerPrincipal` caps in-flight stateless requests for one
authenticated or trusted anonymous binding.

- **Type:** Positive integer
- **Default:** `32`

The per-principal permit is acquired together with the global request permit.
If either limit is exhausted, the gateway returns HTTP `429`. Counters are
process-local and disappear when no active permit retains that principal's
semaphore.

