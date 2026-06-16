# Handler Path

Use handler paths to select the handler chain for an incoming gateway request.

Each path entry matches a request by HTTP method and path. The `exec` list names the chain or handlers to run.

Supported path patterns:

- exact path, such as `/customers`
- path template, such as `/customers/{customerId}`
- trailing wildcard, such as `/customers/*` or `/*`

Examples:

```yaml
paths:
  - path: /customers/{customerId}
    method: GET
    exec:
      - apiChain
  - path: /customers/*
    method: GET
    exec:
      - apiChain
  - path: /*
    method: POST
    exec:
      - apiChain
```

Important behavior:

- `/customers` matches only `/customers`
- `/customers/{customerId}` matches one segment after `/customers`
- `/customers/*` matches `/customers` and any deeper path under `/customers`
- `/*` matches any path for the configured method

For sidecar API proxy routes, point the matching API methods to the API proxy chain.

