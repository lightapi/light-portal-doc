# WebSocket Router: idleTimeoutMs

`idleTimeoutMs` is the maximum time a WebSocket tunnel may have no payload
traffic in either direction.

- **Type:** Positive integer, in milliseconds
- **Default:** `3600000` (one hour)
- **Disabled by:** blank, null, or `0`

```yaml
idleTimeoutMs: 300000
```

The activity timestamp starts when the upstream connection is established and
is refreshed by non-empty traffic from either client or upstream. When the
elapsed idle time exceeds the limit, the gateway terminates the tunnel with a
timeout error.

This property also helps determine the underlying tunnel I/O timeout. When
`maxConnectionDurationMs` is configured too, the gateway uses the smaller of
the two values for I/O timeout scheduling, while enforcing both semantics
independently.

