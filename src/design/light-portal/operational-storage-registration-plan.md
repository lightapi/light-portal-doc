# Operational Storage Registration Implementation Plan

## Objective

Replace the current asynchronous operational-store provisioning workflow with a
Host-scoped registration workflow, then make `portal-config-loc`,
`portal-config-dev`, `portal-config-bootstrap`, and `light-portal-install`
create and register the agreed databases in their existing PostgreSQL container.

This plan implements the decisions in
[Operational Storage Registration And Development PostgreSQL Topology](development-database-topology.md).

## Baseline And Migration Principle

The current implementation has a `requestOperationalStoreBinding` command,
provisioning jobs, worker callbacks, a `DEV_DEDICATED` Docker provider, and UI
states such as `REQUESTED`, `PENDING`, and `PROVISIONING`. Existing event streams
and snapshots may contain those records.

The migration must preserve replay while preventing new infrastructure work:

- add registration contract version 2 before removing version 1 handlers;
- replay historical provisioning events as historical control-plane state only;
- do not start a worker or create a job while replaying;
- migrate an accepted existing binding to a registration only through an
  explicit, idempotent conversion; and
- remove deployment worker wiring only after all default registrations publish
  successfully.

## Current Checked-In Delta

The four deployment repositories already run one PostgreSQL service and their
current `init-environment.sh` scripts ensure `configserver`, `knowledge`, and one
`operations` database. They accept only one `PORTAL_DB_OPERATIONAL_NAME`, so the
database manifest/loop is the first deployment change needed for
`operations_networknt` and `operations_taiji`.

`portal-config-loc/all-in-lt` currently contains the active Compose provisioner
profile and its supervisor/token handling. The other deployment repositories
stage the same provisioner/provider assets with the operational migration bundle
and run the one-shot database bootstrap. Those staged assets must converge with
the canonical bundle change; they should not be edited independently.

The checked-in baselines currently contain the bootstrap `dev.lightapi.net`
Host, while `dev.networknt.com` and `dev.taiji.io` exist only in the operator's
current local Portal state. Their canonical Org/Host events and UUIDs must be
exported and reviewed before the other repositories can register them safely.

## Target User Workflow

1. A Host administrator selects **Operational Storage** from a Host row.
2. The page displays the fully qualified Host name and no Environment field.
3. The administrator enters an existing PostgreSQL connection descriptor and
   an absolute mounted credential-file path.
4. **Register storage** creates and publishes the Host binding synchronously.
5. **Update registration**, **Deactivate**, and **Unregister** manage only the
   control-plane binding.
6. Runtime validation status may be displayed, but there are no provisioning
   jobs, retries, attempts, provider containers, retention holds, or destructive
   database actions on this page.

## P0: Freeze Contract Version 2

Status: complete on 2026-09-02.

Owners: `light-portal-doc`, `host-command`, `host-query`, `light-portal`,
`portal-view`, and runtime consumers in `light-fabric`.

- Define one active registration per `hostId`.
- Remove user-supplied `environment` from the registration request.
- Define fields for engine, server host, port, expected database, TLS mode,
  mounted credential source and absolute reference, minimum schema
  generation, and credential generation.
- Separate non-secret Config Server fields from secret material.
- Define `REGISTERED`, `DEACTIVATED`, and `UNREGISTERED` lifecycle states.
- Define update concurrency through `aggregateVersion`.
- Define contract-v1 replay and conversion rules.

Exit gate: Java, TypeScript, Rust, and configuration fixtures agree on property
names, required fields, digest canonicalization, and rejection cases.

Delivered contract:

- one active registration key: `hostId`;
- request fields: `targetHostId`, `engine`, `serverHost`, `port`,
  `expectedDatabase`, `tlsMode`, `credentialSource`,
  `credentialReference`, `minimumSchemaGeneration`, and
  `credentialGeneration`;
- update-only concurrency field: `aggregateVersion`;
- registration retries require an idempotency key and derive a stable binding
  identity from the Host plus that key;
- generated projection fields: `bindingId`, `bindingDigest`, `scopeKind`,
  lifecycle, aggregate version, activation, and publication state;
- lifecycle values: `REGISTERED`, `DEACTIVATED`, and `UNREGISTERED`;
- digest: RFC 8785 plus SHA-256 over the frozen 12-field digest subject; and
- version-1 history remains projectable by ordinary consumers and replay, with
  new version-1 commands rejected before append; no automatic conversion is
  performed.

The P0 artifacts define and test the contract but do not register a handler,
change a database projection, or alter current runtime configuration. Those
changes start in P1.

## P1: Replace The Portal Provisioning API

Status: complete on 2026-09-02.

Owners: `host-command`, `host-query`, `light-portal`, and `portal-db`.

- Add `registerOperationalStoreBinding`, `updateOperationalStoreBinding`, and
  `unregisterOperationalStoreBinding` command contracts.
- Keep `deactivateOperationalStoreBinding`, but redefine it as publication
  revocation only.
- Append version-2 registration events and project/publish them atomically.
- Change the uniqueness constraint from `(host_id, environment)` to one active
  registration per `host_id`.
- Store the connection descriptor, binding digest, credential reference, schema
  generation, and audit metadata in `configserver`.
- Do not create an `operational_store_job_t` row for version-2 commands.
- Remove new-call access to retry, rotate-through-worker, retention-hold,
  decommission, and worker-report endpoints.
- Retain legacy event constants and replay policies until every supported
  snapshot/event baseline has crossed the compatibility window.
- Update global snapshot export/import so registration records and version-2
  events round-trip without credentials leaking into logs or exports.

Exit gates:

- PostgreSQL integration tests prove register/update/deactivate/unregister and
  duplicate-Host concurrency behavior;
- replay tests prove old events cannot enqueue work;
- publication tests prove exact Host audience and secret redaction; and
- legacy endpoint removal is covered by authorization and route fixtures.

Delivered backend:

- four version-2 write actions are exposed at version `0.2.0`: register,
  update, deactivate, and unregister;
- command append and registration projection/publication share one PostgreSQL
  transaction;
- version-2 registration is Host-scoped, publishes immediately, and is guarded
  by a partial unique index allowing one active registration per Host;
- the projection stores the non-secret connection descriptor, digest,
  credential reference, schema and credential generations, lifecycle, and
  audit metadata;
- version-2 commands and replay create no provisioning jobs;
- legacy provisioning event handlers remain available for historical replay,
  but retry, rotate, retention-hold, decommission, and worker-report actions are
  absent from the current command route specification;
- Host snapshots carry sanitized version-2 registration events, while jobs,
  publications, ownership rows, and legacy profiles remain destination-local or
  derived; and
- live PostgreSQL tests cover the complete lifecycle, replay, publication,
  secret/environment omission, and duplicate-Host rejection.

The P2 Portal View uses this backend. P1 did not alter deployment topology; P3
subsequently removed the provisioner and created the five local databases, while
their Portal registrations remain P4 work.

## P2: Convert Portal View To Registration

Status: complete on 2026-09-02.

Owner: `portal-view`.

- Rename page copy from provisioning to registration while retaining the route
  initially for link compatibility.
- Remove Environment and storage-profile selectors.
- Add connection descriptor and credential-source fields.
- Replace **Request provisioning** with **Register storage**.
- Replace job state, attempts, provider resource, retry, credential rotation,
  retention hold, and decommission controls with registration version,
  publication state, database identity, update, deactivate, and unregister.
- Never place a password-bearing URL in query parameters, navigation state,
  telemetry, or browser persistence.
- Update the help page and add component/API tests for all lifecycle states.

Exit gate: the page cannot invoke a provisioning or destructive database action,
and it always binds the Host from the selected Host Admin row.

Delivered Portal View:

- the existing `/app/host/operationalStore` route now displays the selected
  Host's fully qualified name and contains no Environment or storage-profile
  selector;
- the form sends only the version-2 PostgreSQL descriptor, credential reference,
  schema/credential generations, and the selected Host ID;
- registration cards expose lifecycle, publication, database identity, digest,
  and aggregate version, with update, deactivate, and unregister actions;
- version-1 provisioning records remain visible as read-only history, with no
  retry, rotation, retention, decommission, job, or provider controls; and
- component/API tests cover register, update/reactivate, deactivate, and
  unregistered-history states and assert omission of environment, profile,
  password, and database URL fields.

## P3: Create The Five Databases In One Container

Status: complete on 2026-09-02.

Owners: all four deployment repositories.

Required databases:

```text
configserver
knowledge
operations
operations_networknt
operations_taiji
```

- Extend `init-environment.sh` from one operational database variable to a
  validated list or manifest of three operational databases.
- Ensure all five databases on fresh initialization and on every idempotent
  existing-volume upgrade.
- Apply the same pinned operational migration bundle to `operations`,
  `operations_networknt`, and `operations_taiji`.
- Write a distinct immutable scope root and database identity into each database.
- Generate or materialize Host-specific local runtime URL files.
- Keep one `postgres` Compose service; do not add per-Host PostgreSQL containers.
- Remove `operational-store-provisioner` service/profile wiring and Docker socket
  access after registration cutover.
- Keep database bootstrap one-shot and idempotent; it is deployment installation,
  not a Portal background service.

Exit gate: fresh and existing volumes converge to the same five-database catalog
and identical operational migration generation.

Delivered deployment topology:

- all four repositories declare `operations`, `operations_networknt`, and
  `operations_taiji` alongside `configserver` and `knowledge` in their single
  PostgreSQL service;
- a shared three-row manifest drives one-shot, idempotent creation and
  validation on both fresh and existing volumes;
- the pinned bundle remains checksum-verified and is rendered only for the
  target database identity and isolated role prefix, preserving identical
  migration IDs and digests in all three ledgers;
- each database records the canonical Portal Host UUID as its immutable scope
  root, binding the database identity to the registration audience;
- each Host/database has separate least-privilege service roles and
  permission-restricted runtime URL files under
  `postgres-db/secrets/operational-hosts/<host-name>/`;
- validation rejects cross-database `CONNECT` privilege and checks identities,
  schemas, ledgers, roles, secret modes, and URL targets; and
- the Compose provisioner, Docker socket access, dedicated-container provider,
  worker token handling, and `deploy-local.sh` provisioner commands are removed.

The three Portal registration events are delivered in P4 from the reviewed
canonical Host export.

## P4: Canonical Host Data And Default Registrations

Owners: `portal-config-loc`, `portal-config-dev`,
`portal-config-bootstrap`, and `light-portal-install`.

The canonical mappings are:

| Host | Database |
| --- | --- |
| `dev.lightapi.net` | `operations` |
| `dev.networknt.com` | `operations_networknt` |
| `dev.taiji.io` | `operations_taiji` |

- Export the three Org and Host creations currently present in the local Portal
  as canonical CloudEvents, preserving their UUIDs, owners, and aggregate
  versions.
- Review the export to ensure it contains no unrelated local data.
- Add those events to the shared bootstrap baseline consumed by the four
  repositories.
- Generate three version-2 registration events using the canonical Host UUIDs;
  do not insert registration projection rows directly.
- Import Host events before registration events.
- Make repeated imports idempotent and compatible with existing volumes.
- Assert that the canonical Host FQDN, `hostId`, expected database, scope root,
  and publication audience all agree.

Exit gate: a clean installation and an upgraded installation both show three
published registrations without a running provisioner.

Delivered implementation:

- `20260902-001-operational-store-default-registrations.json` is byte-identical
  in the four deployment repositories and contains only three Org creations,
  three Host creations, and three registration events in dependency order;
- the export preserves the canonical UUIDs, owners, descriptions, and aggregate
  versions from the local authoring Portal, while portable nonce sentinel `0`
  is transactionally allocated by the importer;
- all three version-2 registrations publish immediately with
  `serverHost=postgres`, the exact database-specific Agent runtime role, and
  `/run/secrets/operational-database-url` as the mounted credential reference;
- database manifests now use the canonical Host UUIDs as scope roots, and a
  contract test validates FQDN, Host ID, database, runtime role, RFC 8785 digest,
  event ordering, UUIDv7 generation, and publication audience;
- `portal-config-loc` applies the registration schema patch on retained volumes
  and imports the delta through the same checksum ledger used by the other
  deployment paths; and
- the provisioner remains absent: registration projection and publication are
  synchronous control-plane work, not a background job.

## P5: Publish And Consume Host-Specific Runtime Configuration

Status: complete on 2026-09-02.

Owners: `light-portal`, Config Server consumers, `light-fabric`, and deployment
configuration repositories.

- Compile version-2 operational-store properties into each exact
  Host/service/instance audience.
- Point each local runtime deployment at its Host-specific URL file while keeping
  `/run/secrets/operational-database-url` as the in-container path.
- Make Light Gateway, Light Workflow, Light Deployer, Light Agent, and Light A2A
  reject Host, binding digest, database identity, or schema-generation mismatch
  before readiness.
- Preserve last-known-good snapshot behavior across Portal/Config Server outages.
- Remove transitional direct operational access to `configserver` only after the
  owning schema and runtime have passed cutover gates.

Exit gate: three Host audiences resolve three database identities and negative
tests prove that swapping any two URL files fails closed.

Delivered implementation:

- version-2 publication is Host-wide and compiles the registered database into
  each writable instance's own environment, preserving an exact
  Host/service/instance audience instead of reusing the page environment;
- an importable Config Property delta completes Gateway's version-2 identity
  fields and adds Deployer's operational-store audience without publishing any
  credential value;
- the catalog delta assigns the applicable product versions for
  `dev.lightapi.net` and `dev.networknt.com`; `dev.taiji.io` intentionally has
  no assignments because the authoring Config Server currently has no product
  versions or instances for that Host, so future Taiji product onboarding must
  create its property assignments before creating runtime instances;
- a following registration-update delta reconciles all three publications only
  after the catalog assignments exist, preventing preserved databases from
  retaining legacy version-1 instance properties because the registration birth
  was projected first;
- Agent, Workflow, A2A, Gateway, execution, and Deployer startup validation now
  shares one fail-closed verifier for the URL role/database, active binding ID
  and digest, Host identity, database identity, and minimum schema generation;
- Deployer receives a read-only `operational_meta` audience and cannot start
  against an unregistered or substituted database;
- all four local deployment repositories materialize Host-specific URL files
  from `operational-hosts/<fqdn>` into per-service volumes, while runtimes see
  only `/run/secrets/operational-database-url` (or the execution-specific file
  for Controller);
- the database bootstrap records the exact active version-2 binding in each of
  the three operational databases, grants every runtime audience read-only
  access to the database identity row, and creates the least-privilege Deployer
  metadata reader alongside the other service roles;
- the existing atomic Config Server snapshot/cache paths remain the runtime
  authority during an outage: a rejected candidate does not replace the active
  generation, and A2A and Workflow regression tests retain last-known-good
  state; and
- a shared three-Host negative test resolves `operations`,
  `operations_networknt`, and `operations_taiji`, then proves that every
  cross-Host URL substitution is rejected before database readiness.

## P6: Repository-Specific Work

Status: complete on 2026-09-02.

Owners: `portal-config-loc`, `portal-config-dev`, `portal-config-bootstrap`, and
`light-portal-install`.

### `portal-config-loc/all-in-lt`

- Treat the currently created three Orgs/Hosts as the source for a reviewed
  canonical event export.
- Expand local database initialization and existing-volume upgrade to all five
  databases.
- Register all three Host mappings automatically after baseline import.
- Remove provisioner Compose profile, token instructions, supervisor functions,
  Docker socket mount, and dedicated-child-container tests.
- Add local qualification for catalog, migrations, publications, and Host-to-DB
  isolation.

### `portal-config-dev`

- Consume the same canonical Host and registration events.
- Mirror the five-database manifest and migration loop.
- Extend restart/startup validation to wait for three registrations and their
  Config Server publications, not for provisioning jobs.
- Add existing-volume upgrade coverage and keep the development gateway default
  on `dev.lightapi.net -> operations`.

### `portal-config-bootstrap`

- Place the canonical Org, Host, and registration events in the ordered bootstrap
  artifact after their dependencies.
- Create/migrate the five databases before importing registration events.
- Verify direct bootstrap and replay/bootstrap modes produce identical
  registrations and digests.
- Remove worker endpoint/profile data from the newly generated baseline only
  after compatibility consumers no longer require it.

### `light-portal-install`

- Stage the same database manifest, migration bundle, checksums, and registration
  events for offline installation.
- Make install, upgrade, clean-volume, and retained-volume paths converge.
- Materialize local URL files and document production overrides for customer DB
  DNS, TLS, username, and mounted credential-file path.
- Remove staged worker/provider assets, any remaining profile wiring, and related
  token/operator instructions.
- Validate that installer defaults use one PostgreSQL container and no Docker
  socket privilege.

Exit gate: all four repository paths converge on the same five-database
topology, canonical registration events and digests, projected publication
readiness, retained-volume migrations, and fail-closed Host isolation without
an operational-store provisioner or Docker socket mount.

Delivered implementation:

- all four repositories consume byte-identical Org/Host/registration events,
  runtime catalog events, operational database manifests, migration order,
  bundle manifest, and bundle checksum files;
- fresh and retained PostgreSQL volumes converge on `configserver`, `knowledge`,
  `operations`, `operations_networknt`, and `operations_taiji`, with identical
  migration ledgers in the three operational databases;
- the local, development, bootstrap, and installer lifecycle paths now wait for
  the three exact active version-2 registration/publication pairs after delta
  projection, including matching Host, database, binding ID, and binding digest,
  and reject any legacy provisioning job for those registrations;
- direct event bootstrap and verified archive restore both pass through the same
  release-delta and readiness path, so fresh, upgrade, clean-volume, and
  retained-volume installs converge;
- runtime qualification now swaps two Host-specific URL files and proves the
  database validator fails closed before restoring and revalidating the files;
- the last local provisioner supervisor call is removed, and every Compose stack
  renders with exactly one PostgreSQL service and no operational provisioner or
  Docker socket mount; and
- newly staged registration artifacts contain no worker endpoint, provider
  profile, token, or callback data; version-1 rows remain only as write-guarded
  replay and audit history; and
- installer documentation distinguishes the five local databases from
  customer-owned production databases and specifies DNS, TLS, username, and
  secret-reference overrides without publishing credentials to Config Server.

## P7: Removal And Compatibility Closure

Status: complete on 2026-09-02.

Owners: all affected repositories.

- Stop generating version-1 provisioning commands and profiles.
- Remove `DEV_DEDICATED`, `DEV_POOLED`, job leasing, worker callbacks, and Docker
  provider code after the declared replay window.
- Preserve a read-only representation or migration for historical bindings where
  audit requirements demand it.
- Regenerate API specifications, event bundles, endpoint registrations, access
  rules, release manifests, and checksums from their owning repositories.
- Remove obsolete help text and operator runbooks.

Exit gate: repository-wide searches find no active provisioning command, worker,
job poller, Docker socket mount, or page action; replay of the oldest supported
baseline still succeeds.

Delivered implementation:

- Host command/query specifications expose only the version-2 registration
  lifecycle, and the API correction delta replaces their endpoint inventory so
  omitted version-1 endpoints and access rows become inactive;
- Portal rejects live version-1 events, retains replay projection without job
  side effects, and exposes historical bindings only through the read path;
- the legacy profile and provisioning-job tables remain for audit but are
  write-guarded, with old provider profiles inactive and outstanding work
  cancelled by the P7 database patch;
- the Docker provider, polling worker, worker callbacks, lease validation,
  profile query, and credential-rotation scripts are removed;
- operational bundle 2.0.0 migrates local metadata to Host-scoped
  `CUSTOMER_MANAGED` registration and is checksum-identical across the four
  deployment repositories; and
- the P7 closure gates qualify source absence, API/event parity, bundle parity,
  oldest-supported replay, and version-2 registration without provisioning.

## Cross-Repository Qualification Matrix

| Gate | loc | dev | bootstrap | install |
| --- | --- | --- | --- | --- |
| Compose renders with one PostgreSQL container | Required | Required | Required | Required |
| Fresh volume has five databases | Required | Required | Required | Required |
| Existing volume converges | Required | Required | Required | Required |
| Three operational DB migration digests match | Required | Required | Required | Required |
| Three Host registrations publish | Required | Required | Required | Required |
| No provisioning worker starts | Required | Required | Required | Required |
| Swapped Host URL fails readiness | Required | Required | Required | Required |
| Offline bundle checksum parity | N/A | Optional | Required | Required |

## Recommended Delivery Order

1. Land contract version 2 and replay compatibility in the Portal backend.
2. Land the registration UI behind backend capability detection.
3. Export and review canonical Org/Host events from `portal-config-loc`.
4. Land the shared database manifest/bootstrap changes in all four repositories.
5. Import default registration events and qualify Config Server publication.
6. Cut runtime consumers to the Host-specific bindings.
7. Remove the provisioning worker and legacy write endpoints.

This order prevents a deployment repository from publishing a registration that
the backend or runtime cannot yet understand and preserves rollback until the
three Host mappings are qualified.
