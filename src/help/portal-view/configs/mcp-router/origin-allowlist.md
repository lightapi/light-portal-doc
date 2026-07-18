# MCP Router: originAllowlist

`originAllowlist` lists exact browser origins allowed to call the MCP endpoint.
It is independent of `cors.allowedOrigins`.

- **Type:** Array of strings
- **Default:** `[]`

```yaml
originAllowlist:
  - https://local.localhost
  - https://localhost:3000
```

Each entry must be an absolute `http` or `https` origin containing only scheme,
host, and optional port. Credentials, path, query, fragment, suffix rules, and
wildcards are rejected. Host names are normalized to lowercase; matching
remains scheme- and port-sensitive.

Requests with exactly one `Origin` header must match the list. Missing/empty
allowlists, malformed origins, multiple Origin headers, and unlisted origins
return HTTP `403` before payload parsing. Non-browser clients that omit Origin
are allowed to continue through normal authentication and authorization.

