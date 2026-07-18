# MCP Router: protocol versions

The final property name `versions` is used by both protocol profiles.

## protocols.legacy.versions

- **Default:** `[2025-11-25, 2025-06-18, 2025-03-26, 2024-11-05]`
- The list must be non-empty and contain no duplicates.
- Only those four versions are supported by the legacy adapter.

## protocols.stateless.versions

- **Shipped default:** `[2026-07-28]`
- When stateless is enabled, the list must be non-empty.
- The current stateless adapter accepts only `2026-07-28`, without duplicates.

```yaml
protocols:
  legacy:
    versions: [2025-11-25, 2025-06-18, 2025-03-26, 2024-11-05]
  stateless:
    versions: [2026-07-28]
```

The stateless classifier requires the request header version and the
`params._meta["io.modelcontextprotocol/protocolVersion"]` value to agree.
Unsupported, duplicated, or cross-profile versions reject configuration or the
request, depending on where the mismatch is found.

