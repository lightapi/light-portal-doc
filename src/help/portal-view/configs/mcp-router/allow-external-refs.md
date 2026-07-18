# MCP Router: schema.allowExternalRefs

`schema.allowExternalRefs` controls whether tool schemas may resolve `$ref` or
`$dynamicRef` outside the schema document.

- **Type:** Boolean
- **Default and required value:** `false`

The current runtime has no approved external resolver policy, so setting this
property to true rejects configuration. Local references beginning with `#`
remain available. Any external reference found during schema preflight is
rejected even when it is nested inside another schema keyword.

