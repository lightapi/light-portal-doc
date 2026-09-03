# PostgreSQL And Bootstrap Jobs

The supported Compose distributions use one PostgreSQL container while keeping
Portal, Knowledge and operational responsibilities logically separated.

## Databases and ownership

| Database class | Typical name | Owner |
| --- | --- | --- |
| Portal control plane | `configserver` | Portal command/query services, OAuth and configuration services |
| Knowledge plane | `knowledge` | Light Knowledge API, admin and worker identities |
| Operational plane | `operations` and optional host-specific variants | Controller, Workflow, Gateway, Agent, A2A and evidence publishers through bounded roles |
| LLM audit | Deployment-specific database or operational sink | LLM audit publisher/runtime contract |

Sharing a PostgreSQL container does not authorize cross-database or cross-schema
queries. Service database roles carry explicit search paths and grants.

## Compose services

`postgres` owns the durable volume. The one-shot helpers normally include:

- `knowledge-schema-migration`, which installs or upgrades Knowledge objects;
- `operational-store-bootstrap`, which installs the versioned operational
  bundle and creates bounded runtime roles;
- `operational-runtime-secrets-init`, which materializes database URLs and
  related runtime keys into protected files where required;
- `operational-schema-validation`, which verifies the expected database,
  schema generation and grants before runtime services start; and
- config-cache/artifact initialization jobs needed to correct volume ownership.

The runtime services should depend on successful completion of the relevant
bootstrap and validation jobs, not merely on the PostgreSQL TCP port opening.

## Important environment variables

| Variable | Secret | Purpose |
| --- | ---: | --- |
| `POSTGRES_PASSWORD` | Yes | PostgreSQL administrative bootstrap password. |
| `PORTAL_DB_NAME` | No | Portal database name. |
| `PORTAL_DB_KNOWLEDGE_NAME` | No | Knowledge database name. |
| `PORTAL_DB_OPERATIONAL_NAMES` | No | Operational database set created for the deployment. |
| `PORTAL_DB_TOPOLOGY` | No | Selects the supported logical layout. |
| `OPERATIONAL_BUNDLE_VERSION` | No | Required migration bundle version. |
| `OPERATIONAL_CONTRACT_GENERATION` | No | Minimum operational contract generation. |
| `OPERATIONAL_DATABASE_URL`, `WORKFLOW_DATABASE_URL`, `GATEWAY_DATABASE_URL` | Yes | Role-specific operational database credentials used during materialization. |
| `EXECUTION_DATABASE_URL`, `A2A_DATABASE_URL`, `AUDIT_DATABASE_URL`, `ARTIFACT_DATABASE_URL` | Yes | Additional bounded operational identities. |

Some distributions mount secret sources; local/install distributions may inject
development-only values and write protected files in an initialization step.
Consumers should receive only their own URL or key.

## Persistence and reset

The PostgreSQL named volume is authoritative runtime state. `docker compose
down` preserves it; a volume-removal or deployment-specific clean flag destroys
it. Recreate event-backed Portal projections through the signed event bundle and
supported importer, not through direct SQL seeding.

Before a reset, identify which release bundle will be imported. Refresh and
database deletion are separate actions in the deployment wrappers.

