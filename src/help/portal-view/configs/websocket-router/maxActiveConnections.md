# WebSocket Router: maxActiveConnections

`maxActiveConnections` caps the number of active WebSocket connections held by
one `light-gateway` process.

- **Type:** Positive integer
- **Default:** disabled
- **Disabled by:** blank, null, or `0`

```yaml
maxActiveConnections: 1024
```

The limit is process-wide across routes handled by this WebSocket router; it is
not per path, user, client IP, or gateway cluster. Each gateway replica keeps
its own counter. A permit is acquired after routing, authorization, rate-limit,
and upstream target selection, and is released when that request context ends.

When the process is at the limit, a new upgrade is rejected with HTTP `503`.
Use `maxUpgradeRequestsPerSecond` as the complementary control for bursts of
upgrade attempts that may fail before becoming active connections.

