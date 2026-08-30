# Development PostgreSQL Database Topology

## Status

Proposed target architecture.

This document defines the PostgreSQL topology for:

- `portal-config-loc/all-in-lt`;
- `portal-config-dev`; and
- `light-portal-install` development and demonstration profiles.

It separates Light Portal control-plane data, Knowledge operational data, and
Host-scoped operational data while keeping the development footprint to one
PostgreSQL server by default.

This page complements
[Control-Plane Policy Publication Through Config Server](control-plane-policy-config-server.md),
[Fast Snapshot-Derived Database Bootstrap](database-recreation-event-bootstrap.md),
[Knowledge Base](knowledge-base.md), and
[Light Portal Install](../light-portal-install.md).

## Decision Summary

The default development topology uses one PostgreSQL 17 server with three
separate application databases:

```text
PostgreSQL 17 server or container
|
+-- configserver
|   `-- configserver schema
|       Portal events, CQRS projections, publications, and Config Server
|       snapshots
|
+-- knowledge
|   `-- knowledge schema
|       Knowledge documents, chunks, embeddings, indexing jobs, and runtime
|       evidence
|
`-- operations
    |-- operational_meta
    |-- agent_ops
    |-- a2a_ops
    |-- workflow_ops
    |-- execution_ops
    |-- gateway_ops
    |-- audit_ops
    `-- artifact_ops
        Host- and environment-scoped runtime state
```

The databases may share one PostgreSQL server, volume, network, and development
administrator. Database separation is a logical ownership and migration
boundary; it is not an independent compute, availability, or physical backup
boundary while all databases remain on one server.

The `operations` database is created and migrated with an idempotent deployment
job similar to the existing Knowledge bootstrap. It is not created by an Agent,
Gateway, A2A adapter, Workflow worker, or ordinary Host command handler.

For the initially installed Host and environment, the deployment bootstrap may
create the binding automatically. Additional Hosts created in Host Admin need
an explicit operational-store binding. They must not silently inherit the
initial Host's database.

## Current Checked-In Topology

The three deployment repositories already select the separate Knowledge
topology:

```text
PORTAL_DB_TOPOLOGY=separate
PORTAL_DB_NAME=configserver
PORTAL_DB_KNOWLEDGE_NAME=knowledge
```

The current `init-environment.sh` implementation creates:

- database `configserver` with schema `configserver`; and
- database `knowledge` with schema `knowledge`.

The current development configuration is therefore one PostgreSQL server with
two application databases, not one application database with two schemas. The
same scripts also contain a `shared` compatibility profile that places
environment-suffixed Config Server and Knowledge schemas in one database, but
none of these three default Compose profiles selects it.

The current deployment files are:

```text
portal-config-loc/all-in-lt/postgres-db/init-environment.sh
portal-config-loc/all-in-lt/docker-compose.yml
portal-config-loc/all-in-lt/docker-compose-rust.yml

portal-config-dev/postgres-db/init-environment.sh
portal-config-dev/docker-compose.yml

light-portal-install/postgres-db/init-environment.sh
light-portal-install/docker-compose.yml
light-portal-install/install.sh
```

Several non-Knowledge runtime services still connect to `configserver`. In
particular, current Agent and Controller development configuration contains
transitional direct database connections. Creating `operations` does not by
itself authorize redirecting those connections. Tables, constraints, roles,
migrations, and runtime configuration must move in an owned sequence.

## Why A Database Is Different From A Schema

PostgreSQL schemas and databases solve different problems.

| Concern | Separate database | Separate schema in one database |
| --- | --- | --- |
| Connection | Requires a database-specific connection and pool | One connection can access all schemas |
| Transactions | Ordinary transactions cannot span databases | One transaction can update several schemas |
| Queries | No ordinary cross-database joins | Cross-schema joins are direct |
| Foreign keys | Cannot reference another database | Can reference another schema |
| Catalog and extensions | Database-specific catalog and extension installation | Shared database catalog and extensions |
| Grants | Database connection plus schema/table grants | Schema/table grants inside one connection boundary |
| Migration | Independently versioned database contract | Independently named schemas but one database lifecycle |
| Logical dump and restore | Natural database-level unit | Schema filtering is possible but more coupled |
| Failure and resources on one server | Shared server failure, WAL, CPU, memory, and storage | Shared server failure, WAL, CPU, memory, and storage |

Separate databases make accidental cross-domain transactions, joins, and
foreign keys impossible through ordinary SQL. They also make connection
ownership and migration compatibility visible at runtime.

Separate databases on one PostgreSQL server do not provide independent high
availability, resource isolation, or physical point-in-time recovery. A
deployment that needs those properties must use separate PostgreSQL servers or
managed database instances. The development topology intentionally tests the
logical contract without paying that infrastructure cost.

## Goals

- Match the production control/operational ownership boundary in local and
  development environments.
- Keep the normal development footprint to one PostgreSQL container.
- Keep Portal events, projections, and Config Server snapshots out of runtime
  operational databases.
- Keep Knowledge operational content in its dedicated Knowledge database.
- Give Agent, A2A, Workflow, Gateway, audit, and artifact metadata
  service-owned schemas in a Host-scoped operational database.
- Make existing-volume upgrades idempotent and testable.
- Use the same database identity, scope-root, migration, role, and runtime
  binding contracts with and without Light Portal.
- Let the initial development Host start automatically while keeping additional
  Host provisioning explicit.
- Prevent runtime services from using provisioning or schema-owner
  credentials.
- Preserve independent service migration and eventual physical separation.

## Non-Goals

- Do not run one PostgreSQL container per database by default.
- Do not create a database per logical Agent definition.
- Do not create an operational schema in the `configserver` database.
- Do not merge Knowledge and ordinary Host operational data.
- Do not move every current `DATABASE_URL` before its tables and constraints
  are ready.
- Do not let application startup create a database with an elevated runtime
  credential.
- Do not treat the default development credential or database administrator as
  a production secret-management model.
- Do not automatically bind every Host Admin record to the initial development
  Host's operational data.
- Do not imply that database separation on one server is physical fault
  isolation.

## Data Authority

### `configserver`

The `configserver` database is the Light Portal control-plane database. It
contains:

- canonical Portal command events and outbox records;
- CQRS authoring projections and read models;
- Host, product, API, Agent, skill, Workflow, policy, and instance intended
  state;
- publication records and compatibility metadata;
- mutable instance-property staging state;
- immutable configuration snapshots; and
- Config Server delivery metadata.

It must not become the durable authority for:

- Agent sessions or turns;
- A2A tasks or callback correlation;
- Workflow executions, timers, attempts, or leases;
- concrete memories or session history;
- artifact bytes or runtime artifact metadata;
- traffic/audit records; or
- Knowledge documents, chunks, embeddings, or indexing work.

### `knowledge`

The `knowledge` database remains a separate Knowledge operational boundary. It
contains Knowledge-owned data such as:

- ingestion and synchronization jobs;
- documents and versions;
- chunks and embeddings;
- search and index generations;
- graph and derived retrieval state;
- Knowledge runtime ACL replicas admitted from published policy; and
- query and processing evidence.

Knowledge may be shared across explicitly authorized Hosts in one organization.
It therefore does not use the ordinary `(hostId, envTag)` store identity as its
only boundary. Its scope validation includes the organization, Knowledge-store
binding, residency policy, and authorized Host membership.

Knowledge policy remains authored in Portal and published through Config
Server. Physical placement of operational data does not make the Knowledge
database a control-plane policy source.

### `operations`

The `operations` database is bound to one Host and environment in the default
development profile. Service-owned schemas include:

| Schema | Initial authority |
| --- | --- |
| `operational_meta` | Store identity, Host/environment scope root, schema contract generations, migration ledger, and binding evidence |
| `agent_ops` | Agent sessions, turns, actions, approvals, idempotency, quotas, and initially Agent-owned memory |
| `a2a_ops` | External A2A task facade, callbacks, cancellation, correlation, idempotency, and deletion evidence |
| `workflow_ops` | Workflow process/task state, timers, worklists, retries, and service-owned outbox |
| `execution_ops` | Shared execution attempts, scheduling requests, leases, and common execution foundations |
| `gateway_ops` | Bounded durable Gateway operational state when required; never Agent or Workflow authority |
| `audit_ops` | Durable audit delivery outbox/spool and integrity evidence, not the long-term analytics warehouse |
| `artifact_ops` | Artifact ownership, immutable digest, scan, retention, hold, and object-store references; not large artifact bytes |

Colocation does not grant cross-schema write authority. Cross-service
relationships use stable identifiers, authenticated APIs, outbox/integration
events, and reconciliation rather than permanent cross-schema foreign keys.

`memory_ops` may initially remain part of `agent_ops`. It becomes a separate
schema only after the Memory API owns the session-to-bank invariant and no
cross-schema foreign key is required.

## Development Deployment Profiles

### Default Single-Host Profile

Each of the three development deployments starts with one configured Host and
environment. The deployment bootstrap creates:

```text
database: operations
scopeKind: HOST_ENVIRONMENT
hostId: <configured development Host UUID>
environment: <configured envTag>
bindingId: <stable deployment binding UUID>
```

The Host UUID and `envTag` are explicit inputs. They are never inferred from a
subdomain, Compose project name, database name, or Config Server property
profile such as `loc` or `demo`.

The simple database name `operations` is acceptable because the scope root is
authoritative. Production provisioning may generate an opaque database name
from the binding identifier.

### Additional Dedicated Host

To test the enterprise dedicated profile, an additional runnable Host and
environment receives another database on the same development PostgreSQL
server:

```text
operations_<opaque-scope-suffix>
```

The suffix is generated from a stable binding identifier rather than a
user-visible Host name. This avoids leaking names and avoids rename coupling.
The new database gets the same service schemas, distinct scope root, and
distinct runtime role credentials.

### Explicit Pooled Development Profile

A high-density or Portal-cloud simulation may bind several Hosts to one
`operations` database. This is an explicit `DEV_POOLED` profile, not an
automatic fallback.

In pooled mode:

- every tenant-owned primary or unique key includes `host_id`;
- every query binds Host identity from authenticated runtime state;
- caches, outbox records, object prefixes, audit records, exports, and erasure
  jobs are Host-scoped;
- service runtime roles do not own their tables;
- PostgreSQL Row-Level Security is enabled and forced as defense in depth; and
- cross-Host denial tests are release gates.

The default single-Host development database must not be relabeled as pooled
without those contracts.

## Host Admin Boundary

Host identity and database provisioning are coordinated but separate state
machines.

For the initially installed development Host, deployment bootstrap may create
the Host binding from pinned deployment inputs. For a Host later created in
Host Admin:

1. the existing `createHost` command creates the control-plane Host identity;
2. the administrator selects or defers an operational-store profile;
3. a separate binding command records Host, environment, profile, and desired
   generation;
4. an asynchronous provisioning worker creates or validates the database;
5. the worker installs roles, scope root, and schemas;
6. validation moves the binding to `READY`; and
7. only then may Config Server publish the binding to runtime instances.

Until that control-plane lifecycle exists, development scripts may bootstrap
only the pinned initial Host. Creating another Host in Portal must not
implicitly share the `operations` database or grant runtime activation.

Host deactivation does not drop the database. Decommissioning is a separate,
authorized, retention-aware operation.

## Bootstrap And Migration Architecture

Fresh-volume initialization and existing-volume migration are different
paths. Both are required.

```text
Fresh PostgreSQL volume
        |
        v
init-environment.sh
  |-- ensure configserver
  |-- ensure knowledge
  `-- ensure operations
        |
        v
versioned schema installers

Every deployment or restart
        |
        v
operational-store-bootstrap
  |-- discover or create database idempotently
  |-- validate scope root
  |-- install/validate roles
  `-- invoke pinned service migrations
        |
        v
operational-schema-validation
        |
        v
runtime services may start
```

PostgreSQL entrypoint scripts run only when the data directory is empty.
Adding `operations` only to `/docker-entrypoint-initdb.d` would leave existing
`portal-config-loc`, `portal-config-dev`, and installer volumes unchanged.

The target therefore has two cooperating jobs:

1. `init-environment.sh` creates all three databases during fresh bootstrap;
   and
2. an idempotent `operational-store-bootstrap` one-shot service runs on every
   deployment and can safely bring an existing volume to the desired database
   and schema generation.

Database creation and schema migration should remain separate checkpoints even
when one development container performs both. Database creation may require a
cluster administration role and cannot be assumed to share the application
migration transaction.

## Bootstrap Inputs

The development bootstrap accepts non-secret identity and topology inputs:

```yaml
PORTAL_DB_TOPOLOGY: separate
PORTAL_DB_NAME: configserver
PORTAL_DB_KNOWLEDGE_NAME: knowledge
PORTAL_DB_OPERATIONAL_NAME: operations
PORTAL_DB_OPERATIONAL_PROFILE: DEV_DEDICATED
PORTAL_DB_OPERATIONAL_HOST_ID: <development-host-uuid>
PORTAL_DB_OPERATIONAL_ENVIRONMENT: dev
PORTAL_DB_OPERATIONAL_BINDING_ID: <stable-binding-uuid>
PORTAL_DB_OPERATIONAL_CONTRACT_GENERATION: "1"
```

The exact environment value differs by deployment and must match the runtime
`envTag`. The example `dev` is not a universal default.

Production credentials remain secret-provider references or mounted files.
Development Compose may use generated local credentials, but URLs and passwords
must not enter Portal events, configuration snapshots, exported `values.yml`,
or the operational scope root.

## Operational Scope Root

The `operational_meta` schema contains an immutable root row similar to:

```text
binding_id
binding_version
binding_digest
scope_kind
scope_id
host_id
environment
database_identity
deployment_profile
schema_contract_generation
created_at
activated_at
```

A runtime must validate this row before becoming ready. A syntactically valid
connection to an `operations` database for another Host or environment fails
closed.

The database name alone is not identity. Copying or restoring a database must
retain or deliberately replace the scope root under a controlled clone or
relocation workflow.

## Roles And Privileges

The development server may have one PostgreSQL administrator for bootstrap,
but runtime services do not use it.

| Role class | Purpose |
| --- | --- |
| Bootstrap administrator | Create/adopt databases and role classes; used only by the deployment job |
| Scope/migration owner | Own `operational_meta` or one service schema and apply pinned migrations |
| Agent runtime | Read/write only `agent_ops` and approved shared interfaces |
| A2A runtime | Read/write only `a2a_ops` and approved shared interfaces |
| Workflow runtime | Read/write only `workflow_ops` and approved execution interfaces |
| Execution runtime | Read/write only `execution_ops` |
| Gateway runtime | Read/write only the bounded `gateway_ops` and audit interfaces it requires |
| Audit publisher | Append/read delivery state needed to publish audit evidence |
| Artifact runtime | Read/write artifact metadata and approved object references |

Each role receives `CONNECT` only to the database it needs and `USAGE` only on
its schemas. `CREATE` on `public` is revoked. Unqualified `search_path` use is
constrained to the owned schema and reviewed shared interfaces.

Development may initially share a generated password file among transitional
services, but role separation remains a release gate before the operational
store is treated as qualified.

## Runtime Binding

Config Server publishes non-secret operational-store metadata to the exact
Host, service, environment, and instance audience. The runtime combines it
with a deployment-owned secret file.

An illustrative projection is:

```yaml
operationalStore:
  contractVersion: ${operationalStore.contractVersion:1}
  bindingId: ${operationalStore.bindingId:}
  bindingDigest: ${operationalStore.bindingDigest:}
  profileId: ${operationalStore.profileId:dev-dedicated-postgres-v1}
  deploymentProfile: ${operationalStore.deploymentProfile:DEV_DEDICATED}
  scopeKind: ${operationalStore.scopeKind:HOST_ENVIRONMENT}
  scopeId: ${operationalStore.scopeId:}
  hostId: ${operationalStore.hostId:}
  environment: ${operationalStore.environment:}
  serviceOwner: ${operationalStore.serviceOwner:}
  schema: ${operationalStore.schema:}
  minimumSchemaVersion: ${operationalStore.minimumSchemaVersion:1}
  expectedDatabase: ${operationalStore.expectedDatabase:operations}
  databaseUrlFile: ${operationalStore.databaseUrlFile:/run/secrets/operational-database-url}
  objectStoreProfileId: ${operationalStore.objectStoreProfileId:}
  auditSinkProfileId: ${operationalStore.auditSinkProfileId:}
```

This is a common semantic contract, not one file copied between products:

- native `light-agent` receives it in its Agent audience projection;
- `light-a2a` receives it in the A2A audience projection;
- Workflow receives its Workflow/execution schema bindings;
- Gateway receives only its bounded operational and audit bindings; and
- Knowledge continues using its separately scoped Knowledge connection and
  policy projection.

The actual database URL remains a deployment secret. Config Server publishes
the expected file path and binding identity, not the credential.

## Service Connection Matrix

| Service class | Target database | Notes |
| --- | --- | --- |
| Portal command/event processors | `configserver` | Event-sourced control-plane writes and projections |
| Portal query services | `configserver` | Control-plane and authoring read models only |
| Config Server | `configserver` | Immutable audience snapshot delivery |
| Knowledge admin/API/worker | `knowledge` | Separate service-owned roles; policy still arrives through Config Server |
| Native Agent runtime | `operations.agent_ops` | Move only after Agent operational tables and constraints are migrated |
| External A2A integration | `operations.a2a_ops` | Production durability begins after schema and scope gates |
| Workflow runtime | `operations.workflow_ops` and approved `execution_ops` interfaces | Move after shared execution foundations are decoupled |
| Gateway | Usually no database; otherwise owned `gateway_ops`/audit interfaces | Never owns Agent, A2A, or Workflow state |
| Portal View | None | Uses authenticated command, query, and operational APIs |

Controller/runtime-registry tables require a separate ownership decision. The
development rollout must not replace every `configserver` URL mechanically.
Each connection changes only when its table ownership and compatibility gate
are explicit.

## Schema Migration Ownership

The deployment repository orchestrates migrations but does not become the
semantic owner of every schema.

- A common operational-store package owns `operational_meta` and scope
  validation.
- Agent-owned migrations own `agent_ops`.
- A2A-owned migrations own `a2a_ops`.
- Workflow and execution packages own their respective schemas.
- Gateway, audit, and artifact packages own their schemas or interfaces.
- Deployment repositories pin exact migration artifact versions and checksums.

The bootstrap job applies migrations in a declared dependency order and records
checksum, schema version, compatibility generation, owner, start/completion,
and failure evidence. It never edits an old migration in place.

No target schema migration may introduce a foreign key to `configserver`,
`knowledge`, or another service-owned database. Required references are stable
identifiers validated at admission and reconciled through APIs or integration
events.

## Existing Volume Upgrade

The first release adding `operations` must work for both fresh and persistent
development volumes.

### Fresh volume

1. PostgreSQL initializes.
2. `init-environment.sh` creates `configserver`, `knowledge`, and `operations`.
3. Pinned schema installers and baseline import run.
4. Validation proves all three database identities.
5. Runtime services start only after their required database is ready.

### Existing volume

1. PostgreSQL starts without rerunning entrypoint initialization.
2. `operational-store-bootstrap` discovers that `operations` is absent.
3. It creates the database idempotently and records the development binding.
4. It applies service migrations that are ready for the current phase.
5. It validates roles and scope identity.
6. It leaves existing services on `configserver` until each cutover phase is
   explicitly activated.

The database may exist before any runtime table moves. Empty provisioned
schemas and migration ledgers are a valid preparatory state.

Recreating a development database remains explicit. Normal deployment scripts
must not drop `operations`, `knowledge`, or `configserver` merely to repair a
failed migration. Clean-volume flags may remove all three only after showing
that development data will be lost.

## Reset, Backup, And Restore

Development needs both convenient reset and production-shaped identity checks.

- A full clean reset removes the PostgreSQL volume and recreates all databases.
- A control-plane reset rebuilds `configserver` from the supported event and
  snapshot bootstrap without treating operational rows as events.
- A Knowledge reset follows Knowledge's source/reindex contracts.
- An operational reset is scoped to the selected Host/environment binding and
  uses service-owned cleanup or database recreation.
- Logical `pg_dump` artifacts may be produced per database.
- Physical backup and point-in-time recovery remain server-wide while all
  databases share one PostgreSQL server.
- Restores validate the scope root before runtimes reconnect.

Configuration export and operational export remain separate formats and
endpoints. Downloaded `values.yml` contains intended runtime configuration and
binding references, not Agent sessions, memories, A2A tasks, Workflow state, or
database credentials.

## Failure Semantics

| Failure | Required development behavior |
| --- | --- |
| `operations` is missing | Bootstrap creates it idempotently; runtime stays unready until validation passes |
| Database exists with a different scope root | Fail closed; never rewrite the Host/environment silently |
| Service migration fails | Preserve diagnostics and last completed migration; do not start that service |
| Existing service still needs `configserver` tables | Keep its old connection during the declared transitional phase |
| Runtime receives the wrong schema binding | Reject readiness before traffic |
| Config Server is unavailable | An already started runtime follows last-known-good binding validity rules |
| Portal is unavailable | Runtime operational writes continue directly to the accepted database |
| Knowledge is unavailable | Knowledge-dependent work follows its own availability policy; ordinary operational authority does not move to `configserver` |
| One database is dropped manually | Other databases may remain present, but all dependent services fail their own readiness gates |

## Repository Change Matrix

The implementation should land coherently in all three deployment repositories.

| Repository | Required target changes |
| --- | --- |
| `portal-config-loc/all-in-lt` | Add operational database inputs, bootstrap/migration service, secret mount, role/schema validation, and local reset/qualification coverage |
| `portal-config-dev` | Mirror the local contract with development Host/environment inputs and existing-volume upgrade coverage |
| `light-portal-install` | Include operational bootstrap artifact, installer validation, secret materialization, clean-install/reset behavior, and customer-managed override points |

The SQL and migration artifacts should come from one versioned release source.
Copying independently edited schema files into all three repositories is not an
acceptable long-term source-of-truth model. Deployment repositories may stage
verified release artifacts for offline installation, with checksums proving
parity.

## Implementation Sequence

### Phase 0: Contract And Empty Database

Deliver:

- `PORTAL_DB_OPERATIONAL_*` bootstrap inputs;
- common scope-root schema and validation contract;
- idempotent database creation for fresh and existing volumes;
- migration ledger and role conventions;
- empty service schemas or explicitly versioned initial migrations; and
- three-repository parity tests.

No production runtime is redirected in this phase.

### Phase 1: Constraint Decoupling

Classify existing operational tables and remove cross-database foreign keys.
Replace them with pinned identity/digest admission checks, stable references,
authenticated APIs, outbox/integration events, and reconciliation tests.

Shared execution foundations move before Agent and Workflow dependents when
their current constraints require that ordering.

### Phase 2: Agent And Embedded Memory

Move Agent session, turn, action, approval, idempotency, quota, and initially
embedded Memory authority to `agent_ops`. Publish the binding through Config
Server and change Agent readiness to validate it.

Remove Agent's Config Server database credential only after the new store is
authoritative and rollback is bounded.

### Phase 3: A2A And Workflow

Create production-qualified `a2a_ops`, move Workflow-owned execution state,
and enable governed inbound/outbound A2A durability only after restart,
idempotency, cancellation, artifact, and audit recovery gates pass.

### Phase 4: Gateway, Audit, And Artifact Completion

Move bounded durable Gateway state, audit outboxes, and artifact metadata to
their owned schemas. Long-term traffic analytics and artifact bytes remain in
approved external sinks/object storage.

### Phase 5: Multi-Host Development Profiles

Enable Host Admin provisioning for `DEV_DEDICATED` and `DEV_POOLED`, including
asynchronous status, secret references, cleanup, retention, and cross-Host
isolation tests.

## Verification Gates

### Topology

- one PG17 server exposes separate `configserver`, `knowledge`, and
  `operations` databases;
- each database has the expected schema and database identity;
- `PORTAL_DB_TOPOLOGY=shared` does not activate accidentally;
- no operational service schema exists in `configserver`; and
- fresh and existing-volume paths converge on the same topology.

### Authority

- Portal events, authoring projections, and configuration snapshots remain in
  `configserver`;
- Knowledge content remains in `knowledge`;
- operational runtime writes land only in the owning `operations` schema;
- Portal View uses APIs rather than database access; and
- Config Server projections contain bindings but no operational rows or
  credentials.

### Isolation

- a runtime rejects the wrong Host, environment, database identity, binding
  digest, schema owner, or schema generation;
- service roles cannot write other service schemas;
- no cross-database foreign key remains;
- pooled tests prevent cross-Host reads and writes through queries, caches,
  outboxes, artifacts, exports, and cleanup; and
- runtime roles cannot create databases, roles, or schemas.

### Lifecycle

- duplicate bootstrap runs are safe;
- a crash after database creation resumes without creating another database;
- migration checksum drift fails before runtime startup;
- a Host can exist without an operational binding;
- disabling a Host does not destroy operational data; and
- full reset requires an explicit destructive-development option.

### Repository Parity

- all three repositories use the same topology contract and pinned migration
  artifact generation;
- Compose configuration renders successfully;
- fresh-volume and existing-volume integration tests pass;
- checked-in secrets contain no production credential; and
- documentation, scripts, and runtime examples use the same database names and
  scope semantics.

## Resolved Decisions

1. Development uses one PostgreSQL server with three application databases by
   default.
2. `configserver` remains the event-sourced control-plane and Config Server
   snapshot database.
3. `knowledge` remains the separately governed Knowledge operational database.
4. `operations` is the ordinary Host/environment operational database.
5. Service-owned operational domains use separate schemas and runtime roles
   inside `operations`.
6. Separate databases on one server are logical boundaries, not independent
   infrastructure failure domains.
7. The initial configured Host may be bootstrapped automatically.
8. Additional Hosts require explicit bindings and do not inherit the initial
   database silently.
9. Fresh initialization and persistent-volume migration are both supported.
10. Runtime services never provision databases with application credentials.
11. Creating `operations` precedes, but does not itself perform, table cutover.
12. Existing service connections move only after ownership, constraint,
    migration, rollback, and readiness gates pass.
13. Config Server publishes non-secret bindings; deployment-owned files or
    secret providers supply credentials.
14. Knowledge's organization-sharing rules remain distinct from ordinary
    Host/environment scope validation.
15. Deployment repositories orchestrate pinned service-owned migrations rather
    than independently owning divergent schema copies.

## Open Questions

1. Which repository publishes the first versioned `operational_meta` migration
   artifact?
2. Is `operational-store-bootstrap` initially a `light-deployer` profile, a
   dedicated executable, or a thin deployment script over shared tooling?
3. Which exact Agent and Workflow tables define the first cutover slice?
4. Which Controller/runtime-registration tables are control-plane evidence and
   which are operational authority?
5. Do initial development credentials use one transitional runtime role or
   require all service-specific roles in Phase 0?
6. Is `DEV_POOLED` required in the first implementation, or can it wait until
   dedicated single-Host cutover is qualified?
7. Which release artifact and checksum manifest is consumed consistently by
   `portal-config-loc`, `portal-config-dev`, and `light-portal-install`?
8. Which clean-reset flags and warnings should be standardized across the three
   deployment repositories?
