# MCP Router: tools

`tools` is the catalog exposed by `tools/list` and executed by `tools/call`.

- **Type:** Array of tool objects
- **Default:** `[]`

```yaml
tools:
  - name: weather.get
    endpointName: get_weather
    description: Get weather information
    apiType: http
    serviceId: com.networknt.weather-1.0.0
    protocol: https
    envTag: dev
    path: /weather/{city}
    method: GET
    endpoint: /weather/{city}@get
    inputSchema:
      type: object
      required: [city]
      properties:
        city:
          type: string
    outputSchema:
      type: object
    toolMetadata:
      routing:
        parameters:
          city: path
      safety:
        idempotent: true
```

## Tool fields

| Field | Default | Behavior |
| :--- | :--- | :--- |
| `name` | required | Unique gateway-facing tool name. When stateless is enabled, it must be 1-128 ASCII letters, digits, `.`, `-`, or `_`. |
| `endpointName` | `name` | Real backend MCP operation name when it differs from the gateway-facing name. |
| `description` | empty | Description returned by `tools/list`. |
| `apiType` | `http` | `http` (also accepts `rest`/`openapi`) or `mcp`. |
| `protocol` | target-dependent | Discovery protocol used with `serviceId`. |
| `serviceId` | unset | Registry target. Either non-blank `serviceId` or `targetHost` is required. |
| `envTag` | unset | Optional registry environment tag. |
| `targetHost` | unset | Absolute direct target base URL. Private/loopback/link-local/metadata targets are blocked unless explicitly approved in runtime metadata. |
| `path` | required | Backend path beginning with `/`; OpenAPI placeholders must have matching routing metadata. |
| `method` | `GET` | `GET`, `POST`, `PUT`, `PATCH`, `DELETE`, `HEAD`, `OPTIONS`, or `CALL`. `CALL` resolves to POST when an input schema was explicitly configured, otherwise GET. |
| `endpoint` | `<path>@<method>` | Access-control endpoint identifier. |
| `backendMcpProtocol` | legacy for MCP tools | `legacy` or `stateless`; stateless must be selected explicitly. |
| `sessionIndependent` | `false` | MCP-backend declaration; invalid on an HTTP tool. It does not by itself convert a legacy backend into stateless. |
| `backendCredentialMode` | compatibility-dependent | `caller`, `exchange`, `service`, `anonymous`, or legacy-only `caller-compat`. Stateless backends require an explicit mode. |
| `backendResource` | unset | OAuth resource/audience. Required for `caller` and `exchange`. |
| `inputSchema` | `{type: object}` | Draft 2020-12 object-root schema used to validate arguments. |
| `outputSchema` | unset | Optional schema used to validate structured tool output. |
| `toolMetadata` | `{}` | Routing, safety, lifecycle, and runtime controls. |

Tool names and backend contracts must be unique and internally consistent.
Tools resolving to the same backend identity must agree on backend profile,
credential mode, and resource. HTTP tools cannot configure MCP backend-profile
fields.

## Important toolMetadata controls

- `routing.parameters.<name>` maps an input property to `path`, `query`,
  `header`, `cookie`, or `body`. Every `{placeholder}` in `path` requires the
  same parameter to be mapped to `path`.
- `routing.endpointId` or top-level `endpointId` supplies runtime endpoint
  identity metadata.
- `runtime.allowPrivateTargetHost: true` opts an approved internal direct target
  out of public-address SSRF blocking. Do not enable it for untrusted values.
- `runtime.retry.enabled`, `maxAttempts`, retry status/events, and backoff
  configure bounded retries. Retries require `safety.idempotent: true`; a
  destructive tool also needs an idempotency-key argument.
- `safety.idempotent`, `safety.destructive`, and schema `x-mask` annotations
  affect retry and argument masking behavior.
- `lifecycle` carries published lifecycle metadata consumed by the runtime
  catalog.

An input-schema property may use `x-mcp-header` to require its canonical value
in a stateless transport header. Header names must be safe HTTP tokens, cannot
be gateway-owned or sensitive, and may annotate only bounded string, boolean,
or safe-range integer properties.

