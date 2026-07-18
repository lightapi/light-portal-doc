# MCP Router: enabled

Three `enabled` properties control different layers:

| Full property | Shipped default | Behavior |
| :--- | :--- | :--- |
| `mcp-router.enabled` | `true` | Builds and registers the MCP runtime. When false, the `mcp` handler does not match requests. |
| `mcp-router.protocols.legacy.enabled` | `true` | Enables session-oriented MCP. It must remain true in the current dual-profile release. |
| `mcp-router.protocols.stateless.enabled` | `true` | Enables the `2026-07-28` sessionless profile. |

```yaml
enabled: true
protocols:
  legacy:
    enabled: true
  stateless:
    enabled: true
```

The `mcp` handler must also appear in the applicable `handler.yml` chain. A
false top-level flag or an inactive handler disables routing. Setting legacy to
false rejects configuration. If stateless is enabled, its `versions` list must
be non-empty. Although the Rust struct's bare fallback leaves stateless off,
the shipped `light-gateway` template explicitly defaults it to true.

