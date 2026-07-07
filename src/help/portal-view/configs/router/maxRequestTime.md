# Router: maxRequestTime

The `maxRequestTime` property defines the global maximum timeout (in milliseconds) for a request to be processed and a response to be received from a downstream service.

## Configuration Options

```yaml
maxRequestTime: 1000
```

* **Default**: `1000` (1 second).
* If the downstream service does not respond within this time, the router will terminate the connection and return a `504 Gateway Timeout`.
* You can override this value for specific endpoints using `pathPrefixMaxRequestTime`.
