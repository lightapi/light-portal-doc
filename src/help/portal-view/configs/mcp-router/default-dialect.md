# MCP Router: schema.defaultDialect

`schema.defaultDialect` selects the JSON Schema dialect used to compile tool
input and output schemas.

- **Type:** String
- **Default and only supported value:** `https://json-schema.org/draft/2020-12/schema`

A tool schema may omit `$schema` and inherit this dialect. If `$schema` is
present, it must equal the configured dialect exactly. Any other configured or
per-tool dialect rejects the router configuration during startup or reload.

