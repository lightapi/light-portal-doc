# MCP Router: schema.maxSubschemas

`schema.maxSubschemas` limits the number of object nodes examined in one tool
schema.

- **Type:** Positive integer
- **Default:** `4096`

Every object encountered by schema preflight contributes to the count,
including nested property schemas and definitions. Exceeding the budget rejects
configuration before validator compilation. This prevents broad schemas from
consuming unbounded startup CPU and memory even when their nesting depth is
acceptable.

