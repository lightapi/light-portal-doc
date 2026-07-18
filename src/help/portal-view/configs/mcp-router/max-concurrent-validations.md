# MCP Router: schema.maxConcurrentValidations

`schema.maxConcurrentValidations` controls process-wide admission to input and
output schema validation work.

- **Type:** Positive integer
- **Default:** `32`

The runtime creates at most this many validation workers, capped further by
available CPU parallelism, and uses the same value as the bounded work queue
and admission semaphore. When capacity is exhausted, the tool call fails safely
with an MCP error result instead of waiting in an unbounded queue. Each gateway
replica maintains its own pool.

