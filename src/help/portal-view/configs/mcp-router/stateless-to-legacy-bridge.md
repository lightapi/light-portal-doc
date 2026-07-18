# MCP Router: protocols.stateless.statelessToLegacyBridge

`statelessToLegacyBridge` controls whether a stateless frontend request may be
adapted to a session-oriented legacy MCP backend.

- **Type:** String
- **Default and only supported value:** `reject`

The current release deliberately fails closed: a stateless call to a tool whose
backend profile is legacy returns an MCP tool error instead of creating or
reusing hidden backend session state. Other values reject configuration. Use a
tool with `backendMcpProtocol: stateless` and explicit credential settings for
a stateless-to-stateless path.

