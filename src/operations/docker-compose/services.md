# Compose Service Catalog

The four deployments use a common service architecture. A service may be
omitted, duplicated under another runtime identity, or placed behind a Compose
profile, but its configuration boundary remains the same.

| Service or group | Responsibility | Default host port when published |
| --- | --- | --- |
| [PostgreSQL and bootstrap jobs](./services/postgres.md) | Portal, Knowledge and operational persistence; schema and credential preparation | `5432` |
| [Light OAuth](./services/light-oauth.md) | OAuth/OIDC tokens, authorization and JWKS | `6881` |
| [Controller](./services/controller.md) | Runtime registration, control transport and execution coordination | Internal in current stacks |
| [Config Server](./services/config-server.md) | Host/service/environment-specific configuration snapshots | `8435` |
| [Hybrid command and query](./services/hybrid-services.md) | Java Portal command/query APIs and projections | `8439`, `8440` |
| [Portal service](./services/portal-service.md) | Rust Portal APIs and integration endpoints | `2498` |
| [Light Gateway](./services/light-gateway.md) | Public Portal BFF, API routing, MCP and static UI | `443` |
| [LLM Gateway](./services/llm-gateway.md) | Dedicated OpenAI-compatible model routing profile | `8444` |
| [Light Workflow](./services/light-workflow.md) | Workflow execution and workflow-backed MCP tools | `8436` |
| [Light Agent](./services/light-agent.md) | Agent runtime and optional specialized service instances | `8083` and service-specific ports |
| [Light Knowledge](./services/light-knowledge.md) | Knowledge API, administration and asynchronous worker | `8092` for the public API |
| [Light A2A](./services/light-a2a.md) | Optional Agent-to-Agent transport | Profile-dependent |
| [Demo services](./services/demo-services.md) | Regression and tutorial REST/MCP backends | `8085`–`8087` |
| [Enterprise Portal BFF](./services/portal-bff-sso.md) | Optional Microsoft Entra SSO BFF in bootstrap deployment | `8445` |

Image tags and exact environment assignments are deployment inputs and may
change independently. Use this catalog for meaning and constraints, then check
the selected distribution's current Compose file for its concrete value.
