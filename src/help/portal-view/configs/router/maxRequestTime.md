# Router: maxRequestTime

Ordinary request deadline; 0 disables this deadline.

**Type:** Integer (ms). **Default:** `Java: 1000; Rust: 0`.

## Meaning

The ordinary proxy exchange deadline in **milliseconds**, including downstream work and response transfer. It is not only a TCP connection timeout or a per-byte idle timeout. A matching `pathPrefixMaxRequestTime` entry overrides it for an ordinary request; streaming policy has its own deadline.

```yaml
maxRequestTime: 1000
```

Ordinary requests have a one-second budget. For example, an API that needs two seconds will exceed this budget unless it has an override. Before response headers are committed, a deadline normally results in a gateway timeout; after streaming or response transfer has begun, the proxy may terminate the exchange rather than send a new HTTP status.

```yaml
maxRequestTime: 0
```

Disables this ordinary exchange deadline. Other client, listener, connection, load-balancer, and upstream timeouts can still apply.

**Default difference:** the Java template, Java annotation, and current Portal database default are `1000`. The Rust gateway template and `RouterConfig` fallback default are `0`. Set an explicit value when moving a configuration between runtimes.

See [Router configuration](./index.md) for Portal/`values.yml` syntax, runtime compatibility, and source references.
