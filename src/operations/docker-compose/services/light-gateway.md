# Light Gateway

`light-gateway` is the public Portal BFF and API gateway. It terminates TLS,
serves Portal View assets, performs authentication/authorization, and routes
Portal, MCP and backend API traffic. The standard Compose listener maps host
port `443` to container port `8443`.

## Configuration boundaries

| Variables | Purpose |
| --- | --- |
| `LIGHT_RS_CONFIG_DIR` | Startup and local configuration templates. |
| `LIGHT_PORTAL_AUTHORIZATION` | Gateway service identity for Config Server/Portal operations. |
| `WORKFLOW_INVOCATION_SCOPE_TOKEN` | Gateway identity forwarded as `X-Scope-Token` for Workflow invocation. |
| `STATELESSAUTH_BOOTSTRAPTOKEN` | Bootstrap token for the configured browser authentication flow. |
| `STATELESSAUTH_*CLIENTSECRET` | Optional social-login client secrets. |
| `GROQ_API_KEY`, `GEMINI_API_KEY`, `NVIDIA_API_KEY` | Provider keys only if the public Gateway profile contains LLM routes. |
| `CLIENT_CACERTPATH`, `CLIENT_VERIFYHOSTNAME` | Outbound TLS trust and hostname validation. |
| `gatewayEvidence.*` or normalized `GATEWAYEVIDENCE_*` | Operational evidence sink, binding and schema fences. |
| `RUST_LOG`, `GATEWAY_LOG_ANSI` | Logging controls. |

## Runtime configuration

The mounted `startup.yml` selects Config Server. The promoted Gateway snapshot
defines handler paths, virtual hosts, route policies, MCP tools, backend targets
and static assets. Restarting Portal View does not alter that snapshot.

Gateway evidence uses a protected role-specific operational database URL and a
published binding. Do not substitute the Portal database connection.

## Diagnosis

For an unexpected response, inspect the access log fields for selected handler,
policy outcome, backend target and backend status. A Gateway-generated 503 and
a proxied backend 503 have different owners. For workflow-backed MCP, an
`allowed` policy outcome followed by `WORKFLOW_INVOCATION_UNAVAILABLE` means the
request passed Gateway policy and the Workflow service failed downstream.

