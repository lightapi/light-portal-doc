# MCP Router: schema.maxSchemaBytes

`schema.maxSchemaBytes` limits the serialized size of each configured input or
output schema.

- **Type:** Positive integer, in bytes
- **Default:** `1048576` (1 MiB)

The gateway serializes and preflights each schema independently while building
the tool catalog. Exceeding the limit rejects configuration before traffic is
accepted. This is a schema-compilation budget, not the tool-call request or
response budget.

