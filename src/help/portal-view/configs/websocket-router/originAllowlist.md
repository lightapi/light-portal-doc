# WebSocket Router: originAllowlist

`originAllowlist` controls which browser origins may establish protected
WebSocket connections. It is a WebSocket handshake control and is separate from
`cors.allowedOrigins`.

- **Type:** Map of path to an array of origins
- **Default:** `{}` (deny for paths that require an origin allowlist)

```yaml
originAllowlist:
  /ctrl/mcp:
    - https://local.localhost
    - http://localhost:3000
    - https://localhost:3000
```

The current browser control-plane handshake performs an exact lookup for
`/ctrl/mcp`. The map must therefore contain that exact normalized path and a
non-empty list. Missing `Origin`, a missing/empty list, or an unlisted origin
returns HTTP `403` before CSRF, access-control, or upstream discovery checks.

Each entry must be an absolute `http` or `https` origin containing only scheme,
host, and optional port. Paths, queries, fragments, credentials, `null`, and
wildcards are rejected. Comparison uses the normalized origin and remains
scheme- and port-sensitive; for example, `http://localhost:3000` does not allow
`https://localhost:3000`.

When the property is entered as one config-server value, use a JSON object:

```json
{"/ctrl/mcp":["https://local.localhost","https://localhost:3000"]}
```

