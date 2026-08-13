# Control-Plane Policy Publication Through Config Server

## Status

Proposed target architecture.

This document defines how Light Portal publishes immutable policy and runtime
configuration to independently operated workloads such as Agent and Gateway.
It also defines how publication identity is shared with the internal Workflow
and Knowledge services without pretending that those services are external
Config Server clients.

## Decision Summary

Light Portal is the policy authoring and publication control plane. Agent,
Gateway, and other independently operated application runtimes are external
policy consumers. They receive configuration only from Config Server and have
no Light Portal database credentials.

Workflow and Knowledge are internal platform services. In the current
architecture they consume Portal events and read the event-backed projections
needed to admit and pin work. They also write their own operational tables.
Those accesses use dedicated least-privilege database roles; neither service
may insert or update event-backed authoring projections directly. Moving their
internal policy views to Config Server is an optional future decoupling step,
not a requirement of this external publication contract.

Config Server renders the immutable configuration snapshot selected as current
for an authenticated external workload instance. The caller has read-only
access to its own audience-specific `values.yml` document.

Publishing a policy consists of:

1. resolving and validating the effective policy in Light Portal;
2. creating a separate least-privilege projection for each publication target;
3. emitting events that create or update the target instance properties;
4. waiting until those events and required internal views have been projected
   completely;
5. creating an immutable configuration snapshot for every external target
   instance;
6. validating and digesting the snapshots; and
7. moving the target instances' current pointers to the new snapshots as one
   coordinated release.

`instance_property_t` is mutable desired configuration. It is not a publication
staging artifact or runtime contract. An immutable publication manifest records
the exact intended property set before property events are emitted.
`config_snapshot_t` and its snapshot content are immutable deployable artifacts.
The `current` flag is a projected pointer to one of those immutable artifacts.

## Context

Agent configuration is authored in Light Portal from multiple control-plane
resources. Depending on the Agent and its capabilities, the effective policy may
include:

- Agent definition and product profile;
- prompt and model selection;
- tool and skill grants;
- execution, token, cost, and concurrency limits;
- memory and data-boundary rules;
- Knowledge Base bindings and retrieval profiles;
- Gateway routing and delegation constraints; and
- tenant, environment, and instance ownership.

The resolved policy must be immutable for an execution or session. At the same
time, runtime deployment configuration must support controlled rollout,
rollback, and forward activation.

The existing configuration subsystem already provides useful foundations:

- instance-level properties are stored in `instance_property_t`;
- snapshot creation copies instance overrides and produces merged effective
  values in `config_snapshot_property_t`;
- snapshot files and other scoped overrides are copied into snapshot tables;
- `config_snapshot_t.current` identifies the selected snapshot; and
- a partial unique index permits only one current snapshot for a
  `(host_id, instance_id)` pair.

Config Server already resolves effective values from the selected current
snapshot by host, environment, service ID, configuration phase, and property
type. This design extends that mechanism into the only supported policy delivery
path for external runtime services.

## Terminology

| Term | Meaning |
| --- | --- |
| Control-plane policy | Mutable authoring resources and rules managed in Light Portal. |
| Effective policy | The fully resolved policy after defaults, bindings, ownership, and limits have been applied. |
| Domain policy snapshot | An immutable semantic policy for an Agent or another governed subject. It is pinned to sessions and requests. |
| Audience projection | The least-privilege subset of an effective policy needed by one runtime service. |
| Instance property | Mutable desired configuration for one registered service instance. |
| Configuration snapshot | An immutable, deployable `values.yml` configuration for one instance. |
| Publication | One attempt to compile, stage, validate, and activate policy projections. |
| Release | A coordinated set of audience-specific configuration snapshots sharing one publication identity. |
| Current pointer | The mutable selection of the configuration snapshot served to an instance by Config Server. |
| Last known good | The most recent snapshot a runtime successfully validated and applied. |

## Goals

- Prevent external runtimes from using Light Portal database tables as a
  control-plane policy source.
- Define safe internal database boundaries for Workflow and Knowledge while
  preserving event sourcing for authoring state.
- Publish only the policy fields required by each runtime audience.
- Preserve an immutable policy identity for every session and request.
- Reuse the existing instance-property and configuration-snapshot model.
- Support deterministic rollback and forward activation by moving a current
  pointer rather than rewriting historical configuration.
- Prevent partially projected policy changes from becoming current.
- Coordinate compatible policy generations across multiple independently
  operated services.
- Let a runtime retain and enforce its last known good configuration when a new
  snapshot is invalid or temporarily unavailable.
- Provide sufficient identifiers and digests for audit, diagnosis, and
  cross-service consistency checks.

## Non-Goals

- Config Server does not make policy decisions for a runtime request.
- Light Portal does not become the runtime session, retrieval, or Gateway data
  store.
- A service token does not replace the end-user or delegated request identity.
- This design does not require simultaneous process restarts for publication.
- This design does not distribute provider credentials as ordinary policy
  values. Production secrets remain references resolved through the appropriate
  secret provider.
- This design does not require all audiences to receive identical policy
  documents.
- This design does not require Knowledge and Workflow operational state to move
  out of the shared PostgreSQL deployment immediately.

## Trust Boundary

### Light Portal control plane

Light Portal owns:

- mutable authoring resources;
- validation and effective-policy resolution;
- domain policy snapshots and publication history;
- audience projection;
- instance-property events and their projections;
- configuration snapshot creation;
- release activation and rollback; and
- publication audit and operator-facing status.

Portal command, query, projection, and Config Server components may access the
Portal database according to their narrowly assigned roles.

### Config Server

Config Server is the read-only delivery boundary. It may read Portal-owned
configuration snapshots, but a runtime caller may retrieve only configuration
bound to its authenticated host, environment, service ID, instance ID, and
audience.

Config Server must never resolve policy from live authoring tables on behalf of
a runtime. It serves immutable snapshot content only.

### External runtime services

Agent, Gateway, and other independently operated application runtimes:

- load configuration from Config Server;
- validate the delivered identity, schema, and digest;
- cache the last known good configuration;
- enforce their local audience projection; and
- store runtime state only in service-owned storage.

They have no Light Portal database credentials and use their own storage where
persistence is required.

### Internal Workflow and Knowledge services

Knowledge and Workflow are platform services, not external applications. They
currently use the same physical PostgreSQL deployment as Light Portal and may
read the event-backed projections necessary to resolve and pin internal work.

Knowledge may use its database role for Knowledge-owned operational data such
as ingestion jobs, sync runs, documents, chunks, index generations, and runtime
evidence. Workflow may use its database role for Workflow-owned operational data
such as workflow instances, tasks, attempts, leases, artifacts, and execution
history.

These reads are read-only and must select an immutable definition, version, and
digest at admission. All authoring mutations still enter through commands and
events; Workflow and Knowledge never insert or update event-backed projection
rows. Direct writes are limited to explicitly operational state owned by the
service.

The shared database roles must be least-privilege roles restricted to the exact
projection reads and operational writes each service needs. They must not be
database superusers. A future physical database split may deliver the same
internal policy views through events or Config Server without changing their
semantic contracts.

## Required Invariants

1. An external runtime never queries a Light Portal domain or projection table
   to resolve control-plane policy. Internal Workflow and Knowledge may read
   explicitly granted event-backed projections and write explicitly granted
   operational tables.
2. Config Server never renders runtime configuration from mutable authoring
   state.
3. Configuration snapshot bytes and their integrity/publication metadata are
   immutable after creation. Only separately stored descriptive labels and the
   event-projected current pointer may change.
4. At most one configuration snapshot is current for a host and instance.
5. Every published snapshot identifies the source publication and the event
   watermark from which it was built.
6. Snapshot creation begins only after all property events for the publication
   have reached their required projections and every inherited input version
   plus the projected property-set digest equals the immutable staged manifest.
7. Each audience receives only its explicitly compiled projection.
8. Every audience projection has a canonical digest and is bound to its host,
   environment, service, instance, and schema version.
9. A runtime applies a new snapshot only after complete validation. Failure
   preserves the last known good snapshot.
10. A session or long-running operation remains pinned to its domain policy
    snapshot unless that policy is explicitly revoked.
11. Moving a current pointer affects new work; it does not silently change the
    policy already pinned to in-flight work.
12. Cross-service requests identify the policy publication and digest under
    which they were authorized.
13. Rollback selects an existing immutable snapshot. It does not edit that
    snapshot or reverse authoring events.
14. An unavailable Config Server does not cause an external runtime to accept
    unknown or unvalidated policy.
15. Workflow and Knowledge never mutate event-backed authoring projections
    directly; operational writes are not authoring shortcuts.

## Architecture

```text
Light Portal policy authoring
            |
            v
Effective-policy resolver and validator
            |
            v
Immutable domain policy snapshot
            |
            v
Publication target compiler
      /-------------------------\
      v                          v
External workload         Internal service view
projection                (Workflow/Knowledge)
      |                          |
      v                          v
immutable publication      event-backed projection
manifest                   + immutable work pin
      |
      v
instance-property events
      |
      v
immutable configuration snapshots
      |
      v
coordinated release activation event
      |
      v
Config Server read-only API
      |
      v
Agent / Gateway / application runtimes
local last-known-good cache
```

## Two Immutable Snapshot Layers

The domain policy snapshot and configuration snapshot solve different problems
and must have different identities.

### Domain policy snapshot

The domain policy snapshot captures the semantic authority for an Agent or
another governed subject. It includes stable component digests and the resolved
policy document. A session or request records this identity so its authority can
be reproduced later.

Updating an Agent definition produces a new domain policy snapshot. It does not
mutate the snapshot used by existing sessions.

### Instance configuration snapshot

The configuration snapshot captures everything one external service instance
needs to start or reload, including its audience projection and ordinary
runtime settings. It is the artifact rendered as `values.yml` by Config Server.

Several external instance snapshots and internal pinned policy views may be
derived from the same domain policy snapshot. They share the same
`publicationId` and `policySnapshotId`, even though the internal views do not
have to be transported through Config Server.

## Publication Targets And Internal Policy Views

Projection is a compile-time allowlist. It must not be implemented as a runtime
filter over a shared complete policy document.

### Agent projection

The Agent projection may contain:

- definition and product-profile identity;
- prompt, model Alias, and model-action limits;
- tool and skill grants with schema digests;
- execution placement and approval requirements;
- memory and data-boundary policy;
- channel configuration;
- Knowledge binding identifiers and retrieval contract digests;
- Gateway delegation constraints; and
- session lifetime and concurrency limits.

It must not contain Knowledge repository credentials, Knowledge index internals,
Gateway provider credentials, or unrelated tenants' bindings.

### Gateway projection

The Gateway projection may contain:

- Agent and subject bindings relevant to Gateway enforcement;
- permitted model and tool Aliases;
- routing, delegation, budget, and rate-limit constraints;
- accepted issuers, audiences, claim requirements, and signing-key references;
- policy and catalog digests; and
- compatibility rules for accepted publication generations.

It must not contain Agent prompts, memory content, Knowledge documents, or
provider secret material.

### Internal Knowledge policy view

The internal Knowledge policy view may contain:

- Agent-to-Knowledge-Base authorization bindings;
- tenant, environment, and ownership constraints;
- retrieval-profile identity and immutable digest;
- permitted released index generations;
- query limits, graph behavior, and result constraints;
- applicable ingestion or retrieval ceilings; and
- accepted Agent and publication identities.

It must not contain Agent prompts, unrelated tool grants, or Gateway routing
internals.

### Internal Workflow policy view

The internal Workflow policy view may contain:

- immutable workflow definition and execution-policy identity;
- allowed Agent, tool, runner, and sandbox bindings;
- task, retry, timeout, concurrency, and cost ceilings;
- approval and human-task requirements;
- data-boundary and artifact-retention rules;
- accepted publication and delegation identities; and
- compatibility requirements for Workflow runtime components.

It must not contain unrelated Agent prompts, Knowledge document content,
Gateway provider credentials, or authoring-only Portal metadata. Workflow pins
the exact definition, binding, endpoint target set, and policy digests accepted
for an invocation so a later projection update cannot change in-flight work.

These internal views are still explicit, least-privilege projections. Their
current delivery mechanism is the shared event/projection boundary. They may be
published through Config Server later if Workflow or Knowledge is separated
from the Portal trust domain.

## Publication Data Contract

Each external audience projection must carry a common envelope. Internal views
must retain the equivalent publication and policy identity with the work they
admit. The field names below are normative even if the transport representation
evolves.

```yaml
runtimePolicy:
  publicationId: "019f..."
  releaseVersion: 12
  policySnapshotId: "019f..."
  policyVersion: 7
  policyDigest: "sha256:..."
  contentDigest: "sha256:..."
  audience: "gateway"
  hostId: "0196..."
  environment: "dev"
  serviceId: "com.networknt.light-gateway-1.0.0"
  instanceId: "019f..."
  sourceEventSequence: 4812
  schemaVersion: 1
  createdAt: "2026-08-13T14:00:00Z"
  validFrom: "2026-08-13T14:00:00Z"
  refreshAfter: "2026-08-13T14:05:00Z"
  expiresAt: "2026-08-13T14:15:00Z"
  revocationEpoch: 4
  compatibilityGeneration: 3
```

Audience-specific configuration follows this envelope under a dedicated
namespace, for example `gatewayPolicy`.

Digest inputs are non-self-referential and normative:

- `policyDigest` is SHA-256 over the RFC 8785 canonical JSON bytes of the
  immutable domain policy object;
- `contentDigest` is SHA-256 over the RFC 8785 canonical JSON bytes of the
  audience-specific namespace only; it excludes `runtimePolicy`, signatures,
  delivery metadata, and every digest field; and
- `artifactDigest` is SHA-256 over the exact UTF-8 `values.yml` bytes returned
  by Config Server. It is stored in snapshot metadata and returned in HTTP
  headers, not embedded in the bytes it hashes.

The compiler rejects data outside the supported canonical-JSON subset. Time is
normalized to UTC RFC 3339, object members use their exact schema names, and no
volatile delivery timestamp participates in a semantic digest.

## Publication Lifecycle

### 1. Resolve

The publisher reads Portal-owned authoring projections and resolves defaults,
bindings, ownership, environment, and limits into one complete effective
policy. Resolution is deterministic for a declared source event watermark.

### 2. Validate

Validation confirms:

- every reference exists and is visible to the owning host;
- required runtime instances are registered;
- every audience has a supported schema version;
- no projection exceeds platform ceilings;
- policy and configuration ownership agree; and
- the proposed release is compatible with the runtime versions receiving it.

Failure terminates publication without changing any current pointer.

### 3. Freeze the domain policy

The canonical effective policy is persisted with a new `policySnapshotId` and
digest. An existing snapshot with the same digest may be reused if its ownership
and revocation state match exactly.

### 4. Compile audience projections

The publisher generates external Agent/Gateway projections and coordinated
internal Workflow/Knowledge views from explicit schemas and field allowlists.
Each target is canonicalized and digested independently.

### 5. Stage instance properties

For every external target instance, the publisher first persists an immutable
staged target manifest containing:

- `publicationId`, target identity, audience, and source watermark;
- the observed versions and digests of every inherited environment, product,
  product-version, instance, file, and certificate input;
- the complete resolved target configuration and desired instance-property
  change set, including removals;
- a canonical property-set digest; and
- the expected audience content digest and compatibility generation.

The publisher then emits idempotent create, update, and deactivate events for
that exact property set. All events carry the same publication and staged-target
identity. Concurrent authoring or instance-property changes do not become part
of this publication merely because they project before snapshot creation.

Property events may be projected asynchronously. Before creating a snapshot,
the publisher verifies both the projection watermark and that every input
version plus the projected instance property-set digest equals the immutable
staged manifest. A time delay is not sufficient. A mismatch marks the target
`STALE`; the publisher must resolve and compile a new publication instead of
snapshotting mixed state.

### 6. Create configuration snapshots

Once the exact staged target is projected, snapshot creation copies from the
immutable staged artifact in one transaction and creates the merged effective
`config_snapshot_property_t` rows. It must not reread an unconstrained mutable
`instance_property_t` state that may include another publication. New snapshots
start as staged and are not served as current.

Snapshot metadata must retain:

- publication and release identity;
- audience;
- content digest;
- exact rendered artifact digest;
- staged property-set digest and inherited input versions/digests;
- source event sequence;
- schema and compatibility versions; and
- validation state.

These fields may be added to `config_snapshot_t` or stored in a publication
manifest linked to each `snapshot_id`.

### 7. Validate deployable artifacts

Validation renders the exact `values.yml` that Config Server will serve and
checks:

- schema and type correctness;
- required keys and files;
- canonical digest agreement;
- instance and audience binding;
- runtime-version compatibility; and
- absence of fields forbidden for the audience.

The validated UTF-8 bytes, media type, renderer profile/version, and
`artifactDigest` are stored as one immutable snapshot artifact. Config Server
serves those stored bytes; it does not rerender the workload response from
mutable properties at request time.

### 8. Activate the release

After every required target snapshot is ready, Portal emits one
`PolicyPublicationActivatedEvent` containing the publication ID, expected prior
release, and the complete target-to-snapshot mapping. One projection transaction
validates every target and updates all current flags plus release state. There
is no handler-side or operator-side direct pointer mutation.

Database transactions can make the Portal-side pointer changes atomic, but
independently operated services will observe them at different times. The
release therefore requires either backward-compatible adjacent generations or
a staged protocol in which runtimes prefetch before activation.

Rollback emits the analogous `PolicyPublicationRolledBackEvent` with an exact
previous target mapping and is projected through the same all-target operation.

### 9. Acknowledge runtime application

Each external runtime reports or exposes:

- current configuration snapshot ID;
- publication ID;
- content and policy digests;
- load timestamp;
- last validation result; and
- last known good snapshot ID.

Acknowledgement is operational evidence. It does not make an invalid snapshot
valid and does not grant authority beyond the snapshot itself.

## Config Server Contract

The workload API is versioned separately from the existing operator and legacy
configuration endpoints:

- `GET /v2/runtime-config/current` returns the authenticated instance's current
  immutable YAML artifact;
- `GET /v2/runtime-config/snapshots/{snapshotId}` returns one authorized
  historical artifact; and
- `POST /v2/runtime-config/acknowledgements` records load or rejection evidence
  for the authenticated instance.

The current and historical responses use `Content-Type: application/yaml` and
return `ETag`, RFC 9530 `Repr-Digest`, `X-Config-Snapshot-Id`,
`X-Policy-Publication-Id`, `X-Policy-Digest`, `X-Content-Digest`,
`X-Artifact-Digest`, validity-window headers, `X-Manifest-Key-Id`, and
`X-Manifest-Signature`. The signature covers workload target identity,
publication/snapshot identity, all digests, compatibility generation,
revocation epoch, and the validity window. `If-None-Match` is supported. The
acknowledgement request contains identifiers, digests, timestamp, and a bounded
stable result code; it never contains the rendered document or secrets.

The legacy `/configs` API remains a migration path for existing clients. An
external workload must not select live configuration by supplying
`productId`, `productVersion`, host, environment, service, audience, or instance
query parameters.

### Current configuration

An external runtime requests current configuration using a workload JWT and,
where required by the deployment, mTLS. Config Server derives:

- host;
- environment;
- service ID;
- instance ID;
- audience; and
- permitted configuration phase.

The token or certificate contract must expose stable host, environment, service
ID, instance ID, and audience claims. Caller-controlled query values cannot
override or widen them. Config Server returns the exact immutable snapshot
selected as current; its ETag is the quoted `artifactDigest`.

### Historical configuration

Config Server should also support retrieval by an explicit `snapshotId` for:

- session resume under a pinned policy;
- rollback preparation;
- audit and diagnosis; and
- recovery of a runtime that did not persist an older pinned policy locally.

Historical access is subject to the same host, service, instance, and audience
checks as current access. An arbitrary service cannot read another instance's
history.

### Read-only semantics

Runtime credentials authorize only configuration reads and optional delivery
acknowledgement through a separate, narrowly scoped endpoint. They do not
authorize property editing, snapshot creation, current-pointer changes, or
policy publication.

Config Server access logs record identifiers and response size only. Trace,
debug, error, and acknowledgement paths must never log the rendered YAML body.

## Runtime Loading And Enforcement

At startup, an external runtime:

1. authenticates to Config Server using its workload identity;
2. requests the current configuration for its bound instance;
3. verifies the response identity, audience, schema, signature, digests, and
   validity window;
4. compiles the audience policy into its local enforcement representation;
5. stores the immutable policy in service-owned storage when necessary;
6. atomically replaces its in-memory current configuration; and
7. records acknowledgement and health evidence.

During operation, the runtime polls, watches, or refreshes Config Server with a
conditional request. A candidate is fully parsed and validated before it
replaces the current in-memory object.

If Config Server is unavailable, the runtime may use its cryptographically
validated last known good snapshot only while `now < expiresAt`, allowing a
bounded clock-skew tolerance. It begins refreshing no later than `refreshAfter`
and must not apply a candidate before `validFrom`. It must not invent defaults
that broaden access. Once the lease expires, protected operations fail closed.
Emergency revocation while disconnected is therefore bounded by the published
lease; deployments needing a shorter revocation objective configure a shorter
lease or an authenticated push channel.

## Session And Request Pinning

The current configuration selects the default policy for new work. It does not
rewrite the authority of existing work.

An Agent session records at least:

- `policySnapshotId`;
- `policyDigest`;
- `publicationId`; and
- relevant data-boundary and execution digests.

Each downstream call to Gateway or Knowledge carries the applicable policy and
publication identity in trusted request metadata. The receiving service checks
that it recognizes a compatible projection and then applies the authenticated
end-user or delegated principal to the locally loaded rules.

The workload credential authenticates the calling service. The end-user or
delegated identity remains request-specific and must not be stored as a static
instance configuration value.

## Rollback And Forward Activation

Rollback changes current pointers to a previously validated release. It does
not:

- edit the historical snapshot;
- overwrite current instance properties with old values;
- reverse domain events; or
- silently change sessions pinned to another policy.

Before rollback, Portal verifies that every target snapshot still exists, is
not revoked, is compatible with the running service version, and belongs to the
same host, environment, instance, and audience.

Forward activation uses the same event/projection operation to point current
back to a newer validated release. Every pointer movement records actor, reason,
timestamp, previous snapshot, next snapshot, and publication ID.

Emergency revocation is separate from rollback. A revoked domain policy may
terminate or deny already pinned work according to explicit policy; merely
publishing a newer version does not revoke the older one.

## Coordinated Multi-Service Releases

External Agent/Gateway runtimes cannot be assumed to refresh at the same
instant, and internal Workflow/Knowledge projections may advance on a different
checkpoint. The publication protocol therefore uses a shared release manifest
containing:

- publication ID and release version;
- domain policy snapshot and digest;
- required audience targets;
- external target instance and configuration snapshot IDs;
- internal view identifiers and projection checkpoints where they participate;
- each audience content digest;
- compatibility generation;
- source event watermark;
- staged, active, failed, or rolled-back state; and
- validation and acknowledgement evidence.

Adjacent releases should normally support an overlap window:

- an old Agent may call a new Gateway or internal Knowledge view;
- a new Agent may call an old Gateway or internal Knowledge view; and
- the receiver can distinguish compatible transition traffic from an unknown
  or forged publication.

If overlap is impossible, activation requires a two-phase rollout: prefetch and
validate all external targets, verify required internal views are pinable, then
activate traffic only after every required external audience acknowledges
readiness.

## Security Requirements

- Bind every response to the authenticated workload's host, service, instance,
  environment, and audience.
- Use TLS with normal CA and hostname verification in production. Local
  development may use explicitly configured local CA material and disabled
  hostname verification, but that exception must remain deployment-scoped.
- Sign every workload snapshot manifest; deployments crossing company trust
  boundaries use a key and verification policy independent of transport TLS.
- Calculate digests from canonical bytes and verify them after transport.
- Reject unknown schema versions and unknown mandatory fields.
- Prevent rollback to a revoked or ownership-incompatible snapshot.
- Never include provider API keys, private signing keys, or unrelated tenant
  policy in an audience projection.
- Treat secret references and ordinary configuration values differently.
- Audit publication, validation, activation, rollback, runtime load, and
  rejection.
- Do not use a long-lived workload token as evidence of end-user authority.

## Failure Handling

| Failure | Required behavior |
| --- | --- |
| Effective policy cannot be resolved | Fail publication; do not stage or activate. |
| One required publication target fails | Fail the release; do not activate the other targets. |
| Property projection is behind | Keep waiting or time out; never snapshot partial state. |
| Snapshot rendering or validation fails | Mark the target and release failed; retain current pointers. |
| One runtime rejects a staged snapshot | Retain the old release and expose the reason. |
| Config Server is temporarily unavailable | Use last known good within policy; otherwise fail closed. |
| Current pointer references no readable snapshot | Report a control-plane incident; never fall back to mutable properties. |
| Multiple snapshots are current | Reject as a cardinality violation. The database uniqueness invariant should prevent this. |
| Cross-service publication is unknown | Reject or use an explicitly declared overlap rule; never infer compatibility. |
| Snapshot is revoked | Stop admitting new work and apply the declared policy to pinned work. |

## Observability And Audit

The Portal UI should show one publication timeline with per-audience status:

```text
Publication 12
  effective policy        VALIDATED
  Agent snapshot          APPLIED      digest sha256:...
  Gateway snapshot        APPLIED      digest sha256:...
  Workflow internal view  PINNABLE     digest sha256:...
  Knowledge internal view PINNABLE     digest sha256:...
  release                 CURRENT
  previous release        Publication 11
```

Required operational signals include:

- publication duration and failures by phase;
- projection watermark lag;
- staged and current snapshot identity per instance;
- snapshot validation failures by audience;
- runtime current and last-known-good identity;
- acknowledgement lag and digest divergence;
- rejected cross-service publication identities; and
- rollback and revocation counts.

Logs and traces should carry `publicationId`, `policySnapshotId`,
`configSnapshotId`, `policyDigest`, host, environment, service ID, and instance
ID where applicable.

## Current Implementation Gaps

The current external delivery path is not yet the workload contract in this
design:

- `light-config-server` exposes `/configs`; when `productId` and
  `productVersion` are supplied it deliberately reads live instance data rather
  than the current immutable snapshot;
- its request authorization binds host, service ID, and environment, but the
  endpoint has no normative instance/audience claim binding, publication
  envelope, artifact digest/ETag, validity lease, or acknowledgement contract;
- `ConfigsGetHandler` trace logging can emit the entire rendered YAML result;
  that must be removed before policy or secret references use this path; and
- `config-query` can read a historical snapshot by `hostId` and `snapshotId`,
  but that Portal query operation is not an external workload-identity API.

The current snapshot schema also lacks an immutable staged publication target,
coordinated release manifest, property-set/content/artifact digests, source
event watermark, audience, validation state, validity lease, and compatibility
generation. Snapshot creation from mutable instance rows is vulnerable to
mixing a concurrent change into a publication unless the staged target and
projected digest are checked.

### Current Workflow database access

`light-workflow` currently creates one SQLx PostgreSQL pool from `DATABASE_URL`
and shares it across admission, execution, event consumption, and reconcilers.
The local composition points it at the same `configserver` database as Portal;
the development credential is a database superuser and is not an acceptable
production role.

Its access falls into three categories:

| Category | Current tables/path | Target boundary |
| --- | --- | --- |
| Portal event consumption | `outbox_message_t`, `consumer_offsets`, notification/counter state | Read event outbox and write only Workflow consumer checkpoint/quarantine state. |
| Admission projection reads | `workflow_tool_binding_t`, `wf_definition_t`, `tool_t`, dependency/approval projections | Read-only; validate versions/digests and copy the accepted immutable definition, binding, policy, and endpoint set into invocation-owned state. |
| Workflow operational state | `process_info_t`, `task_info_t`, `workflow_invocation_t`, budgets, leases, audit outbox, bounded encrypted invocation credentials | Workflow-owned writes with explicit grants and retention. |

Definition execution is normally pinned through
`process_info_t.definition_snapshot`; the legacy fallback that rereads mutable
`wf_definition_t` must be removed after migration. Endpoint dispatch currently
reads `workflow_endpoint_target_t` live by host and endpoint reference. Although
`workflow_invocation_t` pins a binding and definition/policy digests, the live
endpoint lookup can change an in-flight invocation. Admission must therefore
copy the binding-scoped endpoint target set into immutable invocation-owned
operational rows and dispatch only from that copy.

These Workflow projection reads are accepted internal service access, not a
reason to publish Workflow through Config Server now. The required fixes are
least-privilege roles, immutable admission pinning, removal of the legacy live
definition fallback, and an explicit inventory/test of every grant. Knowledge
requires the same read-projection/write-operational classification before its
role is narrowed.

## Migration Plan

### Phase 1: Publication contract

- Define the common policy envelope, external Agent/Gateway schemas, and the
  coordinated identity carried by internal Workflow/Knowledge views.
- Define canonical serialization and digest rules.
- Add immutable staged target manifests, publication/release metadata, and
  target snapshot linkage.
- Add source-event watermark and validation state to the snapshot contract.

### Phase 2: Portal compiler and staging

- Implement deterministic effective-policy resolution.
- Compile audience projections through explicit allowlists.
- Freeze each external target's complete resolved configuration, desired
  property changes, and every inherited input version/digest.
- Emit correlated, idempotent instance-property events.
- Verify projection checkpoints and exact property-set digests before snapshot
  creation; mark mismatches stale rather than snapshotting live rows.
- Render and validate staged `values.yml` artifacts.

### Phase 3: Config Server delivery

- Implement the versioned `/v2/runtime-config` workload endpoints.
- Bind current and historical reads to host, environment, service, instance,
  and audience workload claims.
- Return snapshot and publication metadata with content.
- Add artifact-digest ETag/conditional retrieval and canonical digest
  verification.
- Remove rendered-body trace logging and add bounded acknowledgement.
- Enforce signed validity windows and fail-closed last-known-good behavior.

### Phase 4: Runtime consumers

- Add typed Config Server policy loaders to external Agent and Gateway
  runtimes.
- Persist immutable pinned policies in service-owned storage where needed.
- Inventory Workflow and Knowledge database access; grant read-only projection
  access and service-owned operational writes through separate roles.
- Pin their internal policy views at work admission and remove mutable fallback
  reads during execution.
- Carry publication and policy identity on cross-service calls.
- Add runtime acknowledgement and divergence metrics.

### Phase 5: Coordinated activation

- Stage all target snapshots under one publication.
- Validate compatibility and optionally prefetch.
- Activate and roll back all target pointers through one audited release event
  and one projection transaction.
- Add Portal status, failure details, and operator controls.

### Phase 6: Boundary enforcement

- Remove Portal database credentials from Agent and Gateway deployments.
- Replace the local Workflow superuser credential with a dedicated role and
  restrict Workflow/Knowledge to enumerated projection reads and operational
  writes. Deny direct authoring-projection mutation.
- Add network and database policy enforcing these differentiated boundaries.
- Prove configuration delivery across independently operated environments.
- Run rollback, partial outage, stale snapshot, and mixed-generation exercises.

## Acceptance Criteria

The design is complete when:

1. Agent and Gateway start and serve authorized traffic without Portal database
   credentials. Knowledge and Workflow use only enumerated read-only projections
   and service-owned operational tables through non-superuser roles.
2. Each external workload can retrieve only its own audience projection from
   Config Server; query parameters cannot override workload identity.
3. A publication produces immutable snapshots for all required target
   instances from one declared event watermark.
4. No current pointer changes when any required projection or validation fails.
5. A successful release exposes matching publication identity across external
   snapshots and participating internal policy views.
6. Existing sessions remain pinned to their original domain policy snapshot
   after a new release.
7. Rollback and forward activation work by pointer movement without modifying
   historical snapshot content.
8. Config Server unavailability preserves last known good behavior only until
   the signed `expiresAt` lease and fails closed afterward.
9. An external runtime rejects a snapshot with the wrong host, audience,
   instance, schema, digest, signature, or validity window.
10. External runtime database access is denied. Workflow and Knowledge prove
    least-privilege projection reads, immutable work pinning, operational-only
    writes, and denial of direct authoring-projection mutation.
11. Concurrent inherited- or instance-configuration changes cannot contaminate
    a staged publication, and activation/rollback changes all target pointers
    through one event-backed transaction.

## Design Consequences

This architecture adds a publication compiler and coordinated release state,
but it establishes a clean company and security boundary. Light Portal owns
authoring and immutable publication. Config Server owns read-only delivery.
External Agent/Gateway workloads own enforcement and runtime state without
Portal database access. Internal Workflow/Knowledge services own operational
state and consume narrowly scoped event-backed projections.

The result is independently deployable services, reproducible authorization,
safe rollback, and no external runtime dependency on Light Portal database
tables for control-plane policy. The accepted Workflow/Knowledge shared-database
topology remains an explicit internal contract that can later be replaced by
event or Config Server delivery without changing pinned policy identities.
