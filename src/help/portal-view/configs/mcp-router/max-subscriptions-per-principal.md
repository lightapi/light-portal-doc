# MCP Router: protocols.stateless.maxSubscriptionsPerPrincipal

`maxSubscriptionsPerPrincipal` caps active stateless subscriptions for one
authenticated or trusted anonymous binding.

- **Type:** Positive integer
- **Default:** `4`

The limit is checked with the process-wide `maxSubscriptions` limit when a
`subscriptions/listen` request registers. Exceeding either returns HTTP `429`.
Counts are released when the stream closes, expires, is cancelled, or is
superseded by a runtime reload.

