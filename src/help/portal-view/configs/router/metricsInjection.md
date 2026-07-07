# Router: metricsInjection

The `metricsInjection` property enables or disables the injection of performance tracking metrics specific to the router.

## Configuration Options

```yaml
metricsInjection: false
```

* **`true`**: The router will record metrics (like latency and connection counts) to the configured metrics backend (e.g., Prometheus).
* **`false`** (Default): Metric injection for the router is disabled.
