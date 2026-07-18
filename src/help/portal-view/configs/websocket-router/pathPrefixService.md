# WebSocket Router: pathPrefixService

`pathPrefixService` maps request paths to service-discovery targets.

- **Type:** Map of path prefix to service id or target object
- **Default:** `{}`

```yaml
pathPrefixService:
  /chat: com.networknt.chat-1.0.0
  /ctrl/mcp:
    serviceId: com.networknt.controller-1.0.0
    protocol: https
    envTag: dev
```

A target object supports:

| Field | Required | Behavior |
| :--- | :--- | :--- |
| `serviceId` | Yes | Non-blank service identifier used for discovery. `service_id` is also accepted. |
| `protocol` | No | `http` or `https`; inherits `defaultProtocol` when omitted. |
| `envTag` | No | Discovery environment; inherits `defaultEnvTag` when omitted. `env_tag` is also accepted. |

Prefixes are trimmed, given a leading `/` when missing, and have trailing `/`
characters removed. Matching respects path-segment boundaries, so `/chat`
matches `/chat` and `/chat/room`, but not `/chatty`. When several prefixes
match, the longest prefix wins. `/` acts as a catch-all.

Target selection precedence is:

1. First non-blank `Service-Id`, `service_id`, or `serviceId` request header.
2. First non-blank `service_id` or `serviceId` query parameter.
3. Longest `pathPrefixService` match.

Routing query parameters (`protocol`, service-id variants, environment-tag
variants, and `csrf`) are removed before the upstream request is sent. The
configuration also accepts a JSON/YAML map string for config-server injection
and the legacy `prefix=serviceId&prefix=serviceId` string, but the object form
is recommended because it can express protocol and environment explicitly.

If no header, query value, or prefix provides a target, the gateway rejects the
upgrade with HTTP `403`. Discovery failure or no usable endpoint returns `502`.
For `/ctrl/mcp`, configure the separate `/ctrl/mcp@connect` access-control rule
as well as this route.

