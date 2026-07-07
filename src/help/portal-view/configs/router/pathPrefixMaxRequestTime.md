# Router: pathPrefixMaxRequestTime

The `pathPrefixMaxRequestTime` property allows overriding the global `maxRequestTime` for specific request paths or prefixes.

## Configuration Options

```yaml
pathPrefixMaxRequestTime:
  /v1/long-polling: 5000
  /v2/upload: 10000
```

* **Default**: `{}` (Empty map).
* The keys are path prefixes (e.g., `/v1/api`), and the values are the timeout in milliseconds.
* This is highly useful for endpoints that legitimately take longer to respond, such as file uploads, AI generation endpoints, or large report queries.
