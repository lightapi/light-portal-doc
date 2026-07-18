# MCP Router: protocols.stateless.maxToolsListItems

`maxToolsListItems` caps the number of authorization-visible tools returned by
one stateless `tools/list` operation.

- **Type:** Positive integer
- **Default:** `1024`

The router evaluates visibility first and then applies this limit. If the
visible catalog is larger, it returns a bounded catalog-limit error instead of
pagination; non-empty pagination cursors are not currently supported. The
serialized result must also fit `maxResponseBodyBytes`.

