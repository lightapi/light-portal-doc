# MCP Router Configuration

The MCP router exposes configured HTTP and MCP backend operations as an MCP
tool facade. Its settings reside in `mcp-router.yml` and are supplied through
portal-view/config server properties named `mcp-router.<property>`.

The selected `handler.yml` chain must contain the `mcp` handler. The top-level
`enabled` property must also be `true`; either control can disable the router.
`mcp-router.yaml` is accepted as a compatibility fallback, but
`mcp-router.yml` is preferred.

## Core properties

| Property | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| **[enabled](./enabled.md)** | Boolean | `true` | Enables the router; the same page explains both protocol-profile flags. |
| **[path](./path.md)** | String | `/mcp` | Exact HTTP path handled by the MCP router. |
| **[maxSessions](./max-sessions.md)** | Integer | `10000` | Process-wide legacy frontend session limit. |
| **[maxSessionsPerClient](./max-sessions-per-client.md)** | Integer | `100` | Legacy session limit for one authenticated or anonymous binding. |
| **[maxRequestBodyBytes](./max-request-body-bytes.md)** | Integer | `1048576` | Maximum MCP request body size. |
| **[maxResponseBodyBytes](./max-response-body-bytes.md)** | Integer | `4194304` | Maximum buffered MCP/backend response size. |
| **[maxJsonDepth](./max-json-depth.md)** | Integer | `128` | Maximum nesting depth of an MCP JSON-RPC request. |
| **[originAllowlist](./origin-allowlist.md)** | Array | `[]` | Exact browser origins allowed to call the MCP endpoint. |
| **[tools](./tools.md)** | Array | `[]` | Tool catalog, target, schema, credential, and runtime metadata. |

## Schema properties

| Property | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| **[schema.defaultDialect](./default-dialect.md)** | String | Draft 2020-12 URI | Required JSON Schema dialect. |
| **[schema.allowExternalRefs](./allow-external-refs.md)** | Boolean | `false` | Controls external `$ref`; currently must remain false. |
| **[schema.maxSchemaBytes](./max-schema-bytes.md)** | Integer | `1048576` | Maximum serialized size of each input/output schema. |
| **[schema.maxDepth](./max-depth.md)** | Integer | `64` | Maximum schema-document nesting depth. |
| **[schema.maxSubschemas](./max-subschemas.md)** | Integer | `4096` | Maximum object/subschema count per schema. |
| **[schema.maxConcurrentValidations](./max-concurrent-validations.md)** | Integer | `32` | Process-wide schema validation admission capacity. |
| **[schema.validationWatchdogMs](./validation-watchdog-ms.md)** | Integer | `50` | Observational warning threshold for validation work. |

## Protocol properties

`protocols.legacy` and `protocols.stateless` share the [enabled](./enabled.md)
and [versions](./versions.md) pages because portal-view property links use the
final property-name segment.

| Property | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| **[protocols.legacy.enabled](./enabled.md)** | Boolean | `true` | Keeps the session-oriented profile available. |
| **[protocols.legacy.versions](./versions.md)** | Array | Four supported versions | Accepted legacy protocol versions. |
| **[protocols.stateless.enabled](./enabled.md)** | Boolean | `true` in the shipped template | Enables the `2026-07-28` stateless profile. |
| **[protocols.stateless.versions](./versions.md)** | Array | `[2026-07-28]` | Accepted stateless protocol versions. |
| **[protocols.stateless.discoverTtlMs](./discover-ttl-ms.md)** | Integer | `30000` | `server/discover` cache lifetime. |
| **[protocols.stateless.discoverCacheScope](./discover-cache-scope.md)** | String | `private` | Identity-aware discovery cache scope. |
| **[protocols.stateless.toolsListTtlMs](./tools-list-ttl-ms.md)** | Integer | `30000` | `tools/list` cache lifetime. |
| **[protocols.stateless.toolsListCacheScope](./tools-list-cache-scope.md)** | String | `private` | Identity-aware tool-list cache scope. |
| **[protocols.stateless.maxDiscoverCacheEntries](./max-discover-cache-entries.md)** | Integer | `1024` | Process-local discovery cache capacity. |
| **[protocols.stateless.maxToolsListCacheEntries](./max-tools-list-cache-entries.md)** | Integer | `4096` | Process-local tool-list cache capacity. |
| **[protocols.stateless.maxToolsListItems](./max-tools-list-items.md)** | Integer | `1024` | Maximum visible tools in one result. |
| **[protocols.stateless.maxConcurrentRequests](./max-concurrent-requests.md)** | Integer | `1024` | Process-wide stateless request capacity. |
| **[protocols.stateless.maxConcurrentRequestsPerPrincipal](./max-concurrent-requests-per-principal.md)** | Integer | `32` | Concurrent stateless requests per principal. |
| **[protocols.stateless.maxConcurrentBackendCallsPerTarget](./max-concurrent-backend-calls-per-target.md)** | Integer | `32` | Concurrent stateless backend calls per target. |
| **[protocols.stateless.maxSubscriptions](./max-subscriptions.md)** | Integer | `10000` | Process-wide stateless subscription limit. |
| **[protocols.stateless.maxSubscriptionsPerPrincipal](./max-subscriptions-per-principal.md)** | Integer | `4` | Subscription limit per principal. |
| **[protocols.stateless.maxSubscriptionDurationMs](./max-subscription-duration-ms.md)** | Integer | `900000` | Maximum subscription lifetime. |
| **[protocols.stateless.statelessToLegacyBridge](./stateless-to-legacy-bridge.md)** | String | `reject` | Rejects stateless calls to legacy MCP backends. |

Every numeric limit must be greater than zero. Configuration is validated at
startup and reload; invalid profiles, schemas, origins, limits, or tool targets
reject the candidate runtime. A successful reload compatibility-filters legacy
sessions, invalidates revision-bound caches, and closes superseded stateless
subscriptions, publishing `tools/list_changed` when the tool catalog or policy
changed.

