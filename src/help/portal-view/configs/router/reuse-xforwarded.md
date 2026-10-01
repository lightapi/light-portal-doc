# Router: reuseXForwarded

Reuse forwarding metadata from a trusted preceding proxy.

**Type:** Boolean. **Default:** `false`.

## Meaning

Controls reuse of forwarding metadata supplied by an earlier proxy. It does not simply append to every `X-Forwarded-*` header.

```yaml
reuseXForwarded: false
```

Builds forwarding metadata from the connection reaching this gateway. For example, if the peer is `10.0.0.5` and it supplied `X-Forwarded-For: 198.51.100.20`, the downstream sees `X-Forwarded-For: 10.0.0.5` rather than trusting that supplied client address.

```yaml
reuseXForwarded: true
```

With the same peer and incoming header, the forwarded chain becomes `198.51.100.20,10.0.0.5`. Existing `X-Forwarded-Proto` and `X-Forwarded-Port` can be retained rather than regenerated. This is useful behind a trusted TLS-terminating proxy when the external scheme is HTTPS but the proxy-to-gateway connection is HTTP.

Enable reuse only when the preceding proxy supplies trusted metadata. The router does not authenticate arbitrary forwarding headers. `X-Forwarded-Host` is also affected independently by `rewriteHostHeader`, so it is not covered by a blanket preservation guarantee.

See [Router configuration](./index.md) for Portal/`values.yml` syntax, runtime compatibility, and source references.
