# Logging Filter

Use `logging.filter` to control Rust runtime logging for `light-gateway` and other `light-fabric` services from config server `values.yml`.

The value uses the Rust `tracing` filter syntax. Set a default level first, then add more specific module targets when you need detailed logs for one area.

Example:

```yaml
logging.filter: info,light_pingora::security=debug
```

This keeps the service at `info` level overall and enables `debug` logs only for the `light_pingora::security` target. This is useful when debugging JWT verification failures without turning on debug logs for HTTP clients, TLS, and every gateway request.

## Log Levels

Supported levels, from least to most verbose:

| Level | Use |
| --- | --- |
| `error` | Only failures that require attention. |
| `warn` | Warnings and errors. |
| `info` | Normal operational events. This is the recommended default. |
| `debug` | Diagnostic details for troubleshooting. |
| `trace` | Very detailed execution flow. Use for short troubleshooting windows only. |

`off` can be used for a specific noisy target when you want to suppress it.

## Filter Syntax

Common patterns:

```yaml
# Default info for all targets.
logging.filter: info

# Debug only JWT/security logic.
logging.filter: info,light_pingora::security=debug

# Trace unified-security routing while keeping the rest at info.
logging.filter: info,light_pingora::unified_security=trace

# Debug MCP request handling.
logging.filter: info,light_pingora::mcp=debug

# Debug config loading and runtime reloads.
logging.filter: info,light_runtime=debug

# Reduce noisy dependency logs while debugging gateway code.
logging.filter: info,light_pingora::security=debug,reqwest=warn,hyper_util=warn,rustls=warn
```

Rules:

- Separate directives with commas.
- The first bare level, such as `info`, is the default for all targets.
- Use `target=level` for a specific crate or module.
- More specific targets override broader targets.
- Target names use Rust module paths, such as `light_pingora::security`.

## Common Gateway Targets

These targets are useful for `light-gateway` troubleshooting:

| Target | What it covers |
| --- | --- |
| `light_gateway` | Gateway application code and proxy handling. |
| `light_pingora` | Shared Pingora framework code. |
| `light_pingora::security` | JWT verification, JWK loading, issuer and audience checks. |
| `light_pingora::unified_security` | Unified security handler routing across JWT, SJWT, Basic Auth, and API key. |
| `light_pingora::mcp` | MCP routing, backend MCP calls, and MCP response diagnostics. |
| `light_pingora::handler` | Handler duration reporting when handler timing is enabled. |
| `light_pingora::pii_tokenization` | PII tokenization and detokenization runtime warnings. |
| `light_runtime` | Runtime bootstrap, config loading, module registry, config reload, and controller registration. |
| `light_client` | HTTP client configuration and OAuth client support. |
| `portal_registry` | Control-plane websocket registration and registry client behavior. |
| `reqwest` | Outbound HTTP client internals. |
| `hyper_util` | Lower-level HTTP client connection and pooling logs. |
| `rustls` | TLS handshake and certificate details. |
| `pingora_core` | Pingora server lifecycle, listeners, and protocol logs. |
| `pingora_proxy` | Pingora proxy request handling. |
| `tungstenite` | WebSocket handshake and frame-level support used by registry connections. |

Use the narrowest target that contains the evidence you need. For example, prefer `info,light_pingora::security=debug` over plain `debug` when investigating JWT verification.

## Reload Behavior

`logging.filter` is reloadable. If the control plane reloads all modules, the runtime logging module reloads the filter from the latest config server values. If `logging.filter` is not present in `values.yml`, an all-module reload can return the process to the default filter.

To keep a debug filter across reloads, store it in config server `values.yml`:

```yaml
logging.filter: info,light_pingora::security=debug
```

Then reload the runtime configuration from the control plane. The new filter applies without restarting the gateway.

## Recommendations

- Keep the default at `info` in shared environments.
- Add `debug` or `trace` only for the module under investigation.
- Remove short-term `debug` or `trace` overrides after the issue is resolved.
- Avoid logging full tokens, secrets, request bodies, or response bodies unless the target log point is known to mask sensitive data.
