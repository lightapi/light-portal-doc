# MCP Router: protocols.stateless.maxSubscriptionDurationMs

`maxSubscriptionDurationMs` caps a stateless subscription stream's lifetime.

- **Type:** Positive integer, in milliseconds
- **Default:** `900000` (15 minutes)

The actual deadline is the earlier of this configured duration and the
authenticated credential's `exp` time. Expired credentials reject registration
with HTTP `401`. The stream emits keep-alive comments every 15 seconds and a
terminal completion frame at its deadline.

