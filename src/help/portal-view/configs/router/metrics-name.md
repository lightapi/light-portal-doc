# Router: metricsName

Name for injected Java downstream timing metrics.

**Type:** String. **Default:** `router-response`.

## Meaning

The name passed to Java's metrics handler for injected downstream timing. It groups the router's downstream measurement separately from overall request timing.

```yaml
metricsName: router-response
```

Uses the default category/name for the downstream API response time, including network latency.

```yaml
metricsInjection: true
metricsName: partner-api-response
```

Requests a recognizable category for a gateway or sidecar forwarding to partner APIs. The property is one router-wide name, not a per-service map; it does not automatically create a service-labelled metrics hierarchy or rename every exported metric.

See `metricsInjection` for the required Java metrics handler and the current flag qualification. Rust accepts this property for compatibility, but the current gateway does not use it to name its request or stream metrics.

See [Router configuration](./index.md) for Portal/`values.yml` syntax, runtime compatibility, and source references.
