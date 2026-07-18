# WebSocket Router: applicationProtocols

`applicationProtocols` lists optional WebSocket application subprotocols that
clients may offer for a protected path.

- **Type:** Map of path to an array of strings
- **Default:** `{}`

```yaml
applicationProtocols:
  /ctrl/mcp:
    - mcp.v1
```

For `/ctrl/mcp`, the browser must always offer the gateway-generated CSRF
subprotocol (`csrf.<token>`). That CSRF value is validated separately and must
not be configured here. An empty list means that only the required CSRF
subprotocol is accepted.

Configured values must be valid HTTP token strings, must not start with
`csrf.`, and are de-duplicated at load time. If the client offers any non-CSRF
protocol that is not in the path's list, the gateway rejects the handshake with
HTTP `400` instead of silently ignoring it.

Only allowed application protocols are forwarded upstream; the CSRF protocol
is consumed by the gateway. If the upstream selects a protocol that was not
offered and allowed, the gateway treats the upstream handshake as invalid and
returns `502`.

