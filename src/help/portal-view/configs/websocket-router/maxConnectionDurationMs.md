# WebSocket Router: maxConnectionDurationMs

`maxConnectionDurationMs` limits the total lifetime of a WebSocket tunnel,
regardless of activity.

- **Type:** Positive integer, in milliseconds
- **Default:** disabled
- **Disabled by:** blank, null, or `0`

```yaml
maxConnectionDurationMs: 900000
```

The timer starts when the upstream connection is established. Once the limit is
exceeded, the gateway terminates the tunnel with a timeout error even if data is
still flowing. This is useful for forcing periodic reauthentication and limiting
the lifetime of credentials captured during the original upgrade.

For authenticated connections, choose a value no longer than the intended
authorization lifetime. Existing tunnels retain the limits selected when they
were upgraded; a configuration reload does not disconnect them immediately.

