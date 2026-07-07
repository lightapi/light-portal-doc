# Router: serviceIdQueryParameter

The `serviceIdQueryParameter` property controls whether the router will extract the `service_id` from the URL query parameters to determine the routing target.

## Configuration Options

```yaml
serviceIdQueryParameter: false
```

* **`true`**: If the request URL contains `?service_id=...`, the router will use it for service discovery and routing, and subsequently remove the query parameter before forwarding the request.
* **`false`** (Default): The router relies solely on HTTP headers (`service_id` or `service_url`) or static routes.
