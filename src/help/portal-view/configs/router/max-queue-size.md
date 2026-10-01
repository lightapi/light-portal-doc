# Router: maxQueueSize

Java pending connection-request queue limit.

**Type:** Integer. **Default:** `0`.

## Meaning

In Java, the maximum pending connection requests held when a backend connection pool cannot immediately supply a connection.

```yaml
maxQueueSize: 0
```

Disables this pool's pending-request queue. It does not disable retry/alternate-host handling or guarantee that every busy request fails immediately. If the proxy cannot acquire a connection through its allowed attempts, the request can fail with service unavailable.

The template and Portal description say that `0` means "there is queued requests". Read this as **no queued requests**; zero is the queue limit.

```yaml
maxQueueSize: 20
```

Allows up to twenty waiting connection requests in the Java pool. This can absorb a short burst but adds memory use and waiting time. The ordinary request deadline still limits how long a queued request can wait. Tune only after checking backend capacity and connection failures; a large queue can worsen latency under sustained overload.

**Rust support:** accepted as a compatibility property, but the current gateway does not wire it to a Pingora pending-request queue.

See [Router configuration](./index.md) for Portal/`values.yml` syntax, runtime compatibility, and source references.
