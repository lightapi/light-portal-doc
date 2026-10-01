# Router: preResolveFQDN2IP

Java discovery-time hostname-to-IP conversion.

**Type:** Boolean. **Default:** `false`.

## Meaning

In Java, optionally converts a discovered backend URI's fully qualified domain name to an IP before storing its host in the router pool.

```yaml
preResolveFQDN2IP: false
```

Retains `https://api.example.com:8443` as a hostname-based target. Normal client/resolver behavior determines resolution; this does not mean DNS is necessarily queried for every request.

```yaml
preResolveFQDN2IP: true
```

If discovery returns that URI and the hostname resolves to `192.0.2.10`, the Java router stores a URI using `192.0.2.10`. The conversion occurs when discovery hosts are added, which can happen on the first request, rather than being guaranteed at process startup. The inspected `service_url` branch does not use this discovery conversion.

The template recommends this only for selected downstream load-balancer cases. It can affect DNS rotation, Host headers, TLS SNI, and hostname verification, so verify those behaviors before using it for an HTTPS virtual host.

**Rust support:** the legacy spelling `preResolveFQDN2IP` is accepted, but the current gateway has no corresponding conversion wired to this property. Ordinary Pingora address resolution still occurs independently.

See [Router configuration](./index.md) for Portal/`values.yml` syntax, runtime compatibility, and source references.
