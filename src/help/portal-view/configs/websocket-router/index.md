# WebSocket Router Configuration

The WebSocket router selects an upstream service for an HTTP/1.1 WebSocket
upgrade and lets `light-gateway` proxy the upgraded byte stream. Its settings
reside in `websocket-router.yml` and can be supplied through portal-view and
config server properties named `websocket-router.<property>`.

The router is active only when the selected `handler.yml` chain contains the
`websocket` handler. There is intentionally no `enabled` property in the Rust
configuration. `websocket-router.yaml` is accepted as a compatibility fallback,
but `websocket-router.yml` is preferred.

## Properties

| Property | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| **[defaultProtocol](./defaultProtocol.md)** | String | `http` | Default discovery protocol for targets that do not specify one. |
| **[defaultEnvTag](./defaultEnvTag.md)** | String or null | unset | Default discovery environment tag. |
| **[pathPrefixService](./pathPrefixService.md)** | Object | `{}` | Maps request-path prefixes to service discovery targets. |
| **[originAllowlist](./originAllowlist.md)** | Object | `{}` | Lists browser origins allowed to open protected WebSocket paths. |
| **[applicationProtocols](./applicationProtocols.md)** | Object | `{}` | Lists application WebSocket subprotocols allowed for protected paths. |
| **[preserveRoutingHeaders](./preserveRoutingHeaders.md)** | Boolean | `false` | Preserves service-id routing headers when forwarding upstream. |
| **[idleTimeoutMs](./idleTimeoutMs.md)** | Integer | `3600000` | Closes tunnels that have no traffic in either direction for this duration. |
| **[maxConnectionDurationMs](./maxConnectionDurationMs.md)** | Integer or null | disabled | Caps the total lifetime of each WebSocket tunnel. |
| **[maxActiveConnections](./maxActiveConnections.md)** | Integer or null | disabled | Caps active WebSocket connections in one gateway process. |
| **[maxUpgradeRequestsPerSecond](./maxUpgradeRequestsPerSecond.md)** | Integer or null | disabled | Caps WebSocket upgrade attempts per second in one gateway process. |

## Complete example

```yaml
defaultProtocol: https
defaultEnvTag: dev
pathPrefixService:
  /ctrl/mcp:
    serviceId: com.networknt.controller-1.0.0
    protocol: https
    envTag: dev
originAllowlist:
  /ctrl/mcp:
    - https://local.localhost
    - https://localhost:3000
applicationProtocols:
  /ctrl/mcp: []
preserveRoutingHeaders: false
idleTimeoutMs: 3600000
maxConnectionDurationMs: 900000
maxActiveConnections: 1024
maxUpgradeRequestsPerSecond: 128
```

Configuration is validated at startup and reload. An invalid protocol, origin,
path target, or application subprotocol rejects the candidate configuration.
On a failed reload, the last valid runtime remains active. A successful reload
preserves the process-level connection and rate-limit counters, and does not
terminate tunnels that are already upgraded.

