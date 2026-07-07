# Router: httpsEnabled

The `httpsEnabled` property defines whether the router should use HTTPS (TLS) when connecting to downstream target services.

## Configuration Options

```yaml
httpsEnabled: true
```

* **`true`** (Default): The router will establish TLS connections for HTTPS targets.
* **`false`**: The router will communicate with targets over plain HTTP. Note: If discovery targets return `https` protocols, they will be ignored if this property is false.
