# Router: metricsInjection

Request Java downstream-latency injection into the metrics handler.

**Type:** Boolean. **Default:** `false`.

## Meaning

The Java configuration describes injection of the downstream API's elapsed response time into the metrics handler in the request/response chain. That timing includes downstream work and network latency, helping distinguish proxy overhead from backend time. It does not itself install a metrics handler, select an exporter, or enable a Prometheus endpoint.

```yaml
metricsInjection: false
```

This is the declared default. The configuration description intends to disable the extra downstream metric injection.

```yaml
metricsInjection: true
metricsName: router-response
```

Requests the extra Java downstream timing under `router-response`. An appropriate metrics handler must be available. Compare it with the gateway's overall request timing to investigate where latency is spent; they measure different intervals.

**Java implementation qualification:** current `RouterHandler.handleRequest()` looks up an available metrics handler even when the flag is false and attaches timing metadata if one is found. Therefore the flag is not a reliable hard off-switch in that source revision.

**Rust support:** the configuration accepts the flag, but the current gateway does not use it to control its metrics recorder or reproduce Java's named downstream injection. Rust request/stream metrics have their own runtime paths.

See [Router configuration](./index.md) for Portal/`values.yml` syntax, runtime compatibility, and source references.
