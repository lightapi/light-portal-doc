# WebSocket Router: defaultEnvTag

`defaultEnvTag` supplies the service-discovery environment tag when a selected
`pathPrefixService` target does not define `envTag`.

- **Type:** String or null
- **Default:** unset

Blank values are normalized to unset. A target-level `envTag` overrides the
default, and a non-blank `env_tag` or `envTag` query parameter overrides both.
The resolved value is passed to registry discovery together with the service id
and protocol.

```yaml
defaultEnvTag: dev
pathPrefixService:
  /chat: com.networknt.chat-1.0.0
  /events:
    serviceId: com.networknt.events-1.0.0
    envTag: sit
```

In this example, `/chat` discovers the `dev` instance while `/events` discovers
the `sit` instance.

