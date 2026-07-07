# Router Configuration

The Router configuration defines the global policies for request routing, URL rewriting, connection management, and proxy targeting in the gateway. The configuration resides in `router.yml` and is managed through the portal-view interface and config server.

The gateway uses a shared router runtime (implemented in `light-pingora`) that applies to both **HTTP API routing** and **MCP tool routing**.

## Overview of Configuration Properties

| Property | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| **[http2Enabled](./http2Enabled.md)** | Boolean | `true` | Enables HTTP/2 support for downstream connections. |
| **[httpsEnabled](./httpsEnabled.md)** | Boolean | `true` | Enables HTTPS support for downstream connections. |
| **[maxRequestTime](./maxRequestTime.md)** | Integer | `1000` | Global maximum request timeout in milliseconds. |
| **[pathPrefixMaxRequestTime](./pathPrefixMaxRequestTime.md)** | Object | `{}` | Path-specific request timeouts in milliseconds. |
| **[connectionsPerThread](./connectionsPerThread.md)** | Integer | `10` | Maximum number of concurrent connections per thread. |
| **[maxQueueSize](./maxQueueSize.md)** | Integer | `0` | Maximum queue size for pending connection requests. |
| **[softMaxConnectionsPerThread](./softMaxConnectionsPerThread.md)** | Integer | `5` | Soft limit for concurrent connections per thread before queuing. |
| **[rewriteHostHeader](./rewriteHostHeader.md)** | Boolean | `true` | Determines whether the `Host` header is rewritten to match the target. |
| **[reuseXForwarded](./reuseXForwarded.md)** | Boolean | `false` | Determines whether existing `X-Forwarded-*` headers are reused or overwritten. |
| **[maxConnectionRetries](./maxConnectionRetries.md)** | Integer | `3` | Maximum number of retries for failed downstream connections. |
| **[preResolveFQDN2IP](./preResolveFQDN2IP.md)** | Boolean | `false` | Determines whether to pre-resolve FQDNs to IPs on startup. |
| **[hostWhitelist](./hostWhitelist.md)** | Array of String | `[]` | Allowed downstream hosts for routing. |
| **[serviceIdQueryParameter](./serviceIdQueryParameter.md)** | Boolean | `false` | Determines whether `service_id` query parameters are extracted for routing. |
| **[urlRewriteRules](./urlRewriteRules.md)** | Array of String | `[]` | Rules for rewriting request URLs before routing. |
| **[methodRewriteRules](./methodRewriteRules.md)** | Array of String | `[]` | Rules for rewriting HTTP methods before routing. |
| **[queryParamRewriteRules](./queryParamRewriteRules.md)** | Object | `{}` | Rules for modifying query parameters. |
| **[headerRewriteRules](./headerRewriteRules.md)** | Object | `{}` | Rules for modifying HTTP headers. |
| **[metricsInjection](./metricsInjection.md)** | Boolean | `false` | Determines whether metrics tracking is injected. |
| **[metricsName](./metricsName.md)** | String | `"router-response"` | The metric name to use when tracking router performance. |

---
