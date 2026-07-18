# WebSocket Router: maxUpgradeRequestsPerSecond

`maxUpgradeRequestsPerSecond` limits accepted WebSocket upgrade attempts before
the gateway selects and connects to an upstream target.

- **Type:** Positive integer
- **Default:** disabled
- **Disabled by:** blank, null, or `0`

```yaml
maxUpgradeRequestsPerSecond: 128
```

The implementation uses a fixed one-second counter shared by the WebSocket
router runtime in one gateway process. It is not per path, user, client IP, or
cluster, and each gateway replica enforces its own limit. The counter state is
preserved across successful configuration reloads.

When the limit has already been reached for the current second, the gateway
rejects the request with HTTP `429`. Requests rejected earlier by handshake or
access-control validation do not consume this counter because those checks run
first.

