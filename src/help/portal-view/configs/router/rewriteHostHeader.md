# Router: rewriteHostHeader

Set Host for the selected target and retain the original in X-Forwarded-Host.

**Type:** Boolean. **Default:** `true`.

## Meaning

Controls the HTTP `Host` sent to the selected backend. With rewriting enabled, the original incoming host is recorded in `X-Forwarded-Host`.

```yaml
rewriteHostHeader: true
```

For an incoming request with `Host: gateway.example.com` routed to `https://api.example.com:8443`, Rust sends `Host: api.example.com:8443` and `X-Forwarded-Host: gateway.example.com`. Java constructs the rewritten Host from the connected peer's host and port, which can be an IP address after resolution. Virtual-host backends should be checked against that difference.

```yaml
rewriteHostHeader: false
```

Preserves the incoming Host, such as `gateway.example.com`. Use this only when the target expects that virtual host. This setting controls an HTTP header; it does not independently change TLS SNI, certificate verification, or the destination selected by discovery.

`reuseXForwarded` does not prevent `rewriteHostHeader: true` from setting `X-Forwarded-Host` to the original Host.

See [Router configuration](./index.md) for Portal/`values.yml` syntax, runtime compatibility, and source references.
