# Router: streamMaxRequestTime

Streaming exchange deadline; 0 disables it.

**Type:** Integer (ms). **Default:** `0`.

## Meaning

The streaming exchange deadline in milliseconds. This limits total stream duration rather than the gap between messages. Use `streamIdleTimeout` for a silent backend.

```yaml
streamMaxRequestTime: 0
```

Disables the router's streaming exchange deadline. This is useful for long-lived SSE subscriptions; other infrastructure timeouts can still close the connection.

```yaml
streamMaxRequestTime: 300000
streamIdleTimeout: 30000
```

A stream has a five-minute total budget and a thirty-second silence budget. Heartbeats can keep the idle timer alive, but do not extend the five-minute total deadline.

**Classification matters:** both runtimes select this deadline immediately for `streamPathPrefixes`. Java also selects it immediately for a matching Accept header. Rust retains the ordinary deadline for an Accept-only request until the response Content-Type confirms streaming, then switches to this budget measured from request start.

**Response-only difference:** Java cancels the ordinary exchange timer if it discovers a streaming Content-Type on a request that was not already classified streaming; it does not install a new positive streaming deadline in that branch. Rust installs the configured streaming deadline on confirmation. To get a deliberate pre-header budget in both runtimes, declare the streaming path and set an explicit value. A request can still expire on its ordinary deadline before response-only recognition occurs.

See [Router configuration](./index.md) for Portal/`values.yml` syntax, runtime compatibility, and source references.
