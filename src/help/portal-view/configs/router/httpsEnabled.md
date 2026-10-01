# Router: httpsEnabled

Control TLS for Java discovery and HTTPS discovery filtering in Rust.

**Type:** Boolean. **Default:** `true`.

## Meaning

Controls Java discovery's TLS mode and Rust's HTTPS discovery filtering. This is an outbound routing setting, not the gateway's incoming TLS listener or certificate configuration.

```yaml
httpsEnabled: true
```

Java attaches its configured client SSL context and asks discovery for HTTPS services. Rust permits HTTPS discovery nodes, while each node's advertised protocol determines whether its connection uses TLS. Rust can also retain HTTP discovery nodes with this setting enabled.

```yaml
httpsEnabled: false
```

Java asks discovery for HTTP services without attaching the normal router SSL context. Rust excludes HTTPS discovery nodes. In Rust, an explicit `service_url` or a direct-registry URL still uses its own `http://` or `https://` scheme; this flag does not convert an HTTPS URL to HTTP or forbid all explicit HTTPS targets.

TLS trust, client certificates, and hostname verification belong to client/runtime TLS configuration. Use HTTPS targets with the appropriate TLS configuration for test and production traffic.

See [Router configuration](./index.md) for Portal/`values.yml` syntax, runtime compatibility, and source references.
