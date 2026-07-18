# MCP Router: protocols.stateless.maxSubscriptions

`maxSubscriptions` caps active stateless `subscriptions/listen` streams in one
gateway process.

- **Type:** Positive integer
- **Default:** `10000`

The subscription hub holds bounded channels and removes a subscription when
the stream ends or its lease is dropped. If the global or per-principal limit
is reached, registration returns HTTP `429`. Gateway replicas do not share
subscription counters.

