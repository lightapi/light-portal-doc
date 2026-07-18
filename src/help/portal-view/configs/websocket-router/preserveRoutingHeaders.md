# WebSocket Router: preserveRoutingHeaders

`preserveRoutingHeaders` controls whether service-id routing headers are sent to
the upstream service after the gateway has selected a target.

- **Type:** Boolean
- **Default:** `false`

When `false`, the gateway removes these headers from the upstream request:

- `Service-Id`
- `service_id`
- `serviceId`

```yaml
preserveRoutingHeaders: false
```

Keep the default unless the upstream application explicitly consumes one of
these headers. Setting the property to `true` exposes client-supplied routing
metadata to that application. It does not preserve browser credentials for the
control-plane route: `/ctrl/mcp` applies an additional credential-sanitization
step and installs only the trusted authorization created by the gateway.

