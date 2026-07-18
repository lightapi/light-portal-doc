# WebSocket Router: defaultProtocol

`defaultProtocol` is the discovery protocol used when a selected
`pathPrefixService` entry does not define its own `protocol`.

- **Type:** String
- **Default:** `http`
- **Allowed values:** `http`, `https`

The value is trimmed and converted to lowercase during configuration loading.
Any other value, including `ws`, `wss`, or `ftp`, rejects the configuration.
Use `http` for a non-TLS upstream and `https` for a TLS upstream; the gateway
still performs the WebSocket upgrade after connecting with that HTTP protocol.

```yaml
defaultProtocol: https
pathPrefixService:
  /events: com.networknt.events-1.0.0
```

The `protocol` field on a path target overrides this default. A non-blank
`protocol` query parameter on the request overrides both and is subject to the
same `http`/`https` validation.

