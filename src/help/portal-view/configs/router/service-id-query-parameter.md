# Router: serviceIdQueryParameter

Allow query service_id to override header service_id.

**Type:** Boolean. **Default:** `false`.

## Meaning

Enables legacy clients to select a registered service using the **`service_id`** query key. The property is named `serviceIdQueryParameter`, but the query parameter itself uses an underscore.

```yaml
serviceIdQueryParameter: false
```

The router does not use the query key as a routing override. It obtains routing headers such as `service_id` from the client or preceding path/service handlers. It does not automatically strip a query key simply because its name is `service_id` when this option is disabled.

```yaml
serviceIdQueryParameter: true
```

For this request:

```http
GET /v1/address?service_id=party.address-2.0.0&country=CA HTTP/1.1
Host: gateway.example.com
service_id: party.address-1.0.0
```

The query value selects `party.address-2.0.0`, overriding the header's `party.address-1.0.0`. The intended downstream request keeps `country=CA` and removes the routing query key. Rust explicitly removes it when constructing the upstream URI. Java removes it from the parsed query map, but its no-query-rewrite branch copies the original query string; verify stripping on that Java path rather than relying on it as a confidentiality guarantee.

An explicit `service_url` still takes precedence over service-ID discovery. `env_tag` can select the environment for service-ID routing. Routing headers `service_id` and `service_url` are removed from the upstream request by the proxy.

Use this only for clients that cannot manipulate headers. It lets the client override a service ID assigned by earlier handlers; authorize the request and its routing choice through the appropriate handler chain.

See [Router configuration](./index.md) for Portal/`values.yml` syntax, runtime compatibility, and source references.
