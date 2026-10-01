# Router: http2Enabled

Enable outbound HTTP/2 negotiation.

**Type:** Boolean. **Default:** `true`.

## Meaning

Controls the router's **outbound** protocol configuration. It does not configure the gateway's listening socket. The older template and Portal description refer to incoming HTTP/2, but `RouterHandler.buildProxy()` applies this option to the Java proxy client; Rust applies it to the upstream peer.

```yaml
http2Enabled: true
```

This enables HTTP/2 where the backend supports it. Rust configures HTTP/2 with HTTP/1 fallback. It is not a guarantee that every connection will use HTTP/2, and it does not enable TLS by itself.

```yaml
http2Enabled: false
```

Use this for an HTTP/1 backend. Configure the incoming listener separately and use `httpsEnabled` and the target URL scheme for the applicable TLS behavior.

See [Router configuration](./index.md) for Portal/`values.yml` syntax, runtime compatibility, and source references.
