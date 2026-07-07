# Router: maxConnectionRetries

The `maxConnectionRetries` property limits how many times the router will attempt to retry a failed connection to a downstream target.

## Configuration Options

```yaml
maxConnectionRetries: 3
```

* **Default**: `3`.
* This only applies to connection establishment failures (e.g., TCP timeout, connection refused). It does not retry failed HTTP responses (like `500 Internal Server Error`).
