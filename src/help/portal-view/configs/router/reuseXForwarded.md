# Router: reuseXForwarded

The `reuseXForwarded` property determines how the router handles `X-Forwarded-For`, `X-Forwarded-Host`, and `X-Forwarded-Proto` headers.

## Configuration Options

```yaml
reuseXForwarded: false
```

* **`true`**: The gateway appends to existing `X-Forwarded-*` headers if they were provided by upstream proxies.
* **`false`** (Default): The gateway ignores existing `X-Forwarded-*` headers (preventing spoofing) and generates new ones based on the incoming connection.
