# Router: connectionsPerThread

Java per-target, per-I/O-thread pool connection limit.

**Type:** Integer. **Default:** `10`.

## Meaning

In Java, the hard maximum number of pooled connections to a backend host **per I/O thread**. It also supplies that host pool's maximum cached connections. This is not a gateway-wide connection count or a direct limit on HTTP/2 concurrent streams.

```yaml
connectionsPerThread: 10
softMaxConnectionsPerThread: 5
maxQueueSize: 0
```

Each Java I/O thread's pool for a target can grow to ten connections, with a soft threshold of five and no pending-connection queue. With four I/O threads and one target, ten per thread represents up to roughly forty pooled connections for that target, rather than ten for the entire gateway. Multiple backend hosts have their own pools.

Choose the limit with backend capacity and worker count in mind; increasing it does not make a slow backend faster.

**Rust support:** `RouterConfig` accepts and reports this property, but the current gateway does not connect it to Pingora pool sizing. It must not be used as evidence that Pingora enforces this hard limit.

See [Router configuration](./index.md) for Portal/`values.yml` syntax, runtime compatibility, and source references.
