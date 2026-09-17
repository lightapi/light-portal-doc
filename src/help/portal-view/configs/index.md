# Configs

Use config help pages to understand runtime configuration properties managed through portal-view and the config server.

Common config areas:

- access control
- WebSocket routing and connection controls
- logging filter
- handler chains and paths

See [WebSocket Router Configuration](./websocket-router/index.md) for the
properties loaded from `light-gateway/config/websocket-router.yml`.

See [Direct Registry Configuration](./direct-registry/index.md) for the
`directUrls` service-to-host mapping loaded from
`light-gateway/config/direct-registry.yml`, including the base path used for a
path-based Kubernetes ingress.

See [MCP Router Configuration](./mcp-router/index.md) for the MCP endpoint,
protocol profile, schema budget, resource limit, cache, and tool properties
loaded from `light-gateway/config/mcp-router.yml`.
