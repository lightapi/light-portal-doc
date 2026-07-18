# MCP Router: path

`path` is the exact HTTP path owned by the MCP router.

- **Type:** String beginning with `/`
- **Default:** `/mcp`

```yaml
path: /mcp
```

Query strings are ignored during path matching, so `/mcp?sessionId=...` matches
`/mcp`. Child paths such as `/mcp/tools` do not match. `handler.yml` must route
the required methods on the same path to the `mcp` handler. A value without a
leading slash rejects configuration.

