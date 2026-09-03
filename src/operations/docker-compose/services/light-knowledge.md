# Light Knowledge

The Knowledge subsystem is split into three services with separate runtime
responsibilities.

| Service | Published port | Responsibility |
| --- | ---: | --- |
| `light-knowledge` | `8092` | Knowledge API, retrieval and MCP adapter. |
| `light-knowledge-admin` | Internal | Administrative commands and control snapshot application. |
| `light-knowledge-worker` | Internal | Asynchronous ingestion, embedding and maintenance jobs. |

`knowledge-schema-migration` prepares the Knowledge database before these
services start.

## Shared configuration

| Variable | Secret | Purpose |
| --- | ---: | --- |
| `LIGHT_KNOWLEDGE_DATABASE_URL` | Yes | Knowledge API/admin database connection. |
| `LIGHT_KNOWLEDGE_WORKER_DATABASE_URL` | Yes | Worker-scoped database connection. |
| `LIGHT_PORTAL_AUTHORIZATION`, `KNOWLEDGE_PORTAL_AUTHORIZATION` | Yes | Service identities for protected integrations. |
| `LIGHT_AGENT_DELEGATION_SECRET` | Yes | Agent-to-Knowledge delegation verification where enabled. |
| `LIGHT_KNOWLEDGE_QUERY_CACHE_KEY` | Yes | Protects bounded query-cache material. |
| `CLIENT_CACERTPATH`, `CLIENT_VERIFYHOSTNAME` | No | Outbound TLS trust policy. |

## Admin configuration

`light-knowledge-admin` uses `LIGHT_KNOWLEDGE_CONTROL_SNAPSHOT_SIGNING_KEY` and
`LIGHT_KNOWLEDGE_ADMIN_OPAQUE_ACTOR_KEY` as cryptographic material. Its
`KNOWLEDGE_ADMIN_SNAPSHOT_*` variables select and validate the Portal-owned
control snapshot source. `SECURITY_ISSUER` and `SECURITY_AUDIENCE` must agree
with the deployed OAuth environment.

## Worker and LLM dependency

The worker uses the configured LLM Gateway for embeddings. Provider selection,
model alias and embedding-space contracts come from published configuration;
the Knowledge worker should not receive provider keys directly. If LLM Gateway
has no compiled router, embedding jobs remain unavailable even when the worker
itself is healthy.

Knowledge projections and migration state belong to the Knowledge database.
Use the supported command, notification and worker lifecycle for repairs rather
than directly advancing cursors or editing content/ACL projections.

