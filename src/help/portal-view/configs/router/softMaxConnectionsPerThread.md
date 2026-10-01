# Router: softMaxConnectionsPerThread

Java soft connection-pool limit.

**Type:** Integer. **Default:** `5`.

## Meaning

In Java, the soft connection limit supplied to Undertow's backend connection-pool manager. It helps the pool manage connection growth and retention below the hard `connectionsPerThread` limit. It is not itself a guaranteed request-concurrency or queue threshold.

```yaml
connectionsPerThread: 10
softMaxConnectionsPerThread: 5
```

The pool has a soft limit of five and a hard limit of ten connections per backend host per I/O thread. Keep the soft limit no larger than the hard limit. Queuing is controlled separately by `maxQueueSize`.

**Rust support:** accepted by the configuration model, but not wired to a Pingora soft pool limit in the current gateway.

See [Router configuration](./index.md) for Portal/`values.yml` syntax, runtime compatibility, and source references.
