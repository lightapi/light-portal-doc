# Router: http2Enabled

The `http2Enabled` property specifies whether the router should attempt to establish HTTP/2 connections with downstream target services.

## Configuration Options

```yaml
http2Enabled: true
```

* **`true`** (Default): The router will use HTTP/2 for downstream connections where supported.
* **`false`**: The router will fall back to HTTP/1.1 for all downstream communication.
