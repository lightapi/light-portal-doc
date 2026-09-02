# Control-Plane Policy Publication Through Config Server

## Status

Proposed target architecture.

This document defines how Light Portal publishes immutable policy and runtime
configuration to independently operated workloads such as Agent, Gateway, and
Knowledge. It also defines how publication identity is shared with the internal
Workflow service.

The development placement and migration contract for the Config Server,
Knowledge, and Host operational databases is defined in
[Operational Storage Registration And Development PostgreSQL Topology](development-database-topology.md).

## Decision Summary

Light Portal is the policy authoring and publication control plane. Agent,
Gateway, Knowledge, and other independently operated application runtimes are
Config Server policy consumers. They receive control-plane configuration only
from Config Server and have no Light Portal database or event-store credentials.

Workflow remains an internal platform service in the current architecture. It
may consume Portal events and read the event-backed projections needed to admit
and pin work, and it writes its own operational tables through dedicated
least-privilege roles. Knowledge instead loads its audience-specific immutable
policy through Config Server, and its API/job roles write only service-owned
operational data. It does not consume Portal events or create an independent
Portal policy authority. Its snapshot-loader role may materialize the content-
minimized Knowledge audience fields as published control replicas in its
operational database for local constraints and transactionally consistent
runtime queries.

Config Server returns the immutable configuration snapshot selected as current
for the authenticated runtime identity `(host, serviceId, envTag)`. The caller
has read-only access to its own audience-specific `values.yml` document.

Publishing a policy consists of:

1. resolving and validating the effective policy in Light Portal;
2. creating a separate least-privilege projection for each publication target;
3. emitting events that create or update the target instance properties;
4. waiting until those events and required internal views have been projected
   completely;
5. creating an immutable configuration snapshot for every Config Server target
   instance;
6. validating and digesting the snapshots; and
7. moving the target instances' current pointers to the new snapshots as one
   coordinated release.

`instance_property_t` is mutable desired configuration. It is not a publication
staging artifact or runtime contract. An immutable publication manifest records
the exact intended property set before property events are emitted.
`config_snapshot_t` and its snapshot content are immutable deployable artifacts.
The `current` flag is a projected pointer to one of those immutable artifacts.

For Gateway tools, publication is an explicit Tool-catalog action after tool
authoring is complete. A single-tool or batch publication pins each current tool
revision, including its published workflow-version binding, and stages the
corresponding `mcp-router.yml` entries for the selected Gateway instance. The
Instance Admin then creates a configuration snapshot and moves the current
pointer to activate it. Changing a tool or selecting another workflow version
requires another publication; it never mutates an existing snapshot.

Configuration snapshots replace user-managed digest fields, not integrity
checks. End users neither enter nor see schema, definition, or policy digests on
the tool form. Portal derives those values from canonical server-side content
where an internal admission or audit contract still requires them. Config
Server separately computes the snapshot and artifact digests described below.

### Implemented Gateway Tool publication slice

Gateway Tool publication has one authoring path: the Tool catalog at
`/app/genai/Tool`. The old Instance API MCP Tool route is a compatibility
redirect to that catalog. Opening the catalog from an Instance API applies the
API-version filter; the operator may then select one or more endpoint and/or
workflow-backed Tools and choose an active `gtw` instance.

The persistence layer enforces this boundary: new create or update events for
the legacy Instance API `mcp-router.tools` property are rejected with guidance
to use the Tool catalog. Historical-import projections remain accepted so an
existing event store can be rebuilt before the first Tool-catalog publication
migrates and deactivates those legacy rows.

Portal produces a server-side preview and never asks the operator to enter or
inspect a digest. A selection containing only endpoints from one API version
uses `REPLACE_API_SCOPE`: it replaces that API version's endpoint Tools while
preserving Tools from other APIs and all workflow Tools. Mixed selections and
workflow Tools use `ADD_OR_UPDATE`, which preserves every unselected Tool.

`GatewayToolPublicationUpdatedEvent` stores the exact compiled
`mcp-router.tools` array and its exact source-binding records. Consequently,
event replay projects the event payload and does not re-resolve mutable Tool,
API, Instance API, or Workflow records. Publications share the ordered
Portal-internal `hostId + instanceId` event stream, so a competing stale
publication is rejected at append instead of becoming a projection failure.
This authoring aggregate key is not a workload identity. Synchronous
projection:

- records the immutable attempt in `gateway_tool_publication_t`;
- writes the complete desired array to the instance-level
  `instance_property_t` row for `mcp-router.tools`;
- records the endpoint or published Workflow version pin for each Tool in
  `gateway_tool_binding_t`; and
- deactivates legacy `instance_api_property_t` rows for the same property so
  the Gateway has one configuration source.

On the first Tool-catalog publication, Portal folds the active legacy
per-Instance-API Tool arrays into the new instance-level array before those
legacy rows are deactivated. Existing API Tools are therefore preserved during
the one-path migration.

The publication response is `STAGED`. It deliberately does not create or
activate a snapshot. An Instance Admin creates the immutable config snapshot
and moves the instance's current snapshot pointer in the existing snapshot
workflow. A later Tool or Workflow change has no effect on the live Gateway
until another Tool publication is staged and another snapshot is activated.

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
- partial unique indexes enforce the existing internal instance relationship
  and permit only one current snapshot for the logical runtime identity
  `(host_id, service_id, env_tag)`.

Config Server already resolves effective values from the selected current
snapshot by host, environment, service ID, configuration phase, and property
type. This design extends that mechanism into the only supported policy delivery
path for Config Server runtime services.

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

- Prevent Config Server runtimes from using Light Portal database tables as a
  control-plane policy source.
- Define safe database boundaries for internal Workflow and the independently
  operated Knowledge data plane while preserving event sourcing for authoring
  state.
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
  out of the shared PostgreSQL deployment immediately; logical roles and policy
  delivery boundaries still apply when databases are physically colocated.

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
bound to its authenticated `(host, serviceId, envTag)` identity and permitted
audience.

An `instance_id` UUID may remain an internal Portal database key for Instance
Admin relationships, snapshot ownership, and audit. It is not part of workload
identification, is not a Config Server query parameter or required workload
claim, and must not be used to select or authorize runtime configuration.

Config Server must never resolve policy from live authoring tables on behalf of
a runtime. It serves immutable snapshot content only.

### Config Server audience runtimes

Agent, Gateway, Knowledge, and other independently operated application
runtimes:

- load configuration from Config Server;
- validate the delivered identity, schema, and digest;
- cache the last known good configuration;
- enforce their local audience projection; and
- store runtime state only in service-owned storage.

They have no Light Portal database credentials and use their own storage where
persistence is required.

### Knowledge and internal Workflow services

Knowledge is a Config Server audience. It loads and validates an immutable
Knowledge-specific configuration and policy snapshot at startup and on an
explicit refresh. It has no Portal event-store or authoring-projection
credential. Its database role is restricted to Knowledge-owned operational data
such as ingestion jobs, sync runs, documents, chunks, derived search indexes,
index generations, and runtime evidence. A separate snapshot-loader role is the
only writer of published control replicas. Operational rows pin the exact
configuration snapshot, publication, and policy digests admitted for the work.

Workflow remains an internal platform service in the current architecture. It
may read the explicitly granted event-backed projections needed to resolve and
pin internal work and may write Workflow-owned operational data such as
workflow instances, tasks, attempts, leases, artifacts, and execution history.
Those reads select an immutable definition, version, and digest at admission.
All authoring mutations still enter through commands and events; Workflow never
inserts or updates event-backed projection rows. Direct writes are limited to
explicitly operational state owned by the service.

Workflow versions use one stable `wfDefId` for their complete history. A user
may save a `DRAFT` version repeatedly. Publishing that version freezes its YAML;
the next edit must create a new version under the same `wfDefId`. Tools bind to
the pair `(wfDefId, workflowVersion)` and only published versions are selectable.
This permits an operator to roll a tool back to a previously published workflow
version without inventing a second workflow identity. Portal provides a
side-by-side, normalized YAML comparison between versions.

Every database role must be least privilege and must not be a database
superuser. Workflow roles are restricted to enumerated projection reads and
operational writes. Knowledge roles are restricted to its operational database:
the loader may write published control replicas, while API/job roles may write
only service-owned operational state. None can read Portal authoring,
event-store, or projection tables.

## Required Invariants

1. A Config Server runtime never queries a Light Portal domain or projection table
   to resolve control-plane policy. Knowledge receives policy only through
   Config Server; only its loader writes published control replicas, and other
   Knowledge roles write only operational tables. Internal Workflow may read
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
14. An unavailable Config Server does not cause a runtime to accept
    unknown or unvalidated policy.
15. Workflow never mutates event-backed authoring projections directly, and
    Knowledge cannot read or mutate them; operational writes are not authoring
    shortcuts.
16. A tool may bind only to a published workflow version. A published workflow
    version is immutable and remains addressable by its stable `wfDefId` and
    version string.

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
Config Server audience    Internal service view
projection                (Workflow)
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

### Knowledge projection

The Config Server Knowledge audience projection may contain:

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

The Knowledge projection is published through Config Server and follows the
same immutable snapshot, validation, acknowledgement, last-known-good, and
rollback contract as other independently operated runtimes. The Workflow view
remains an explicit least-privilege internal projection until Workflow adopts a
Config Server audience contract of its own.

## Publication Data Contract

Each Config Server audience projection must carry a common envelope. Internal views
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
  host: "dev.lightapi.net"
  serviceId: "com.networknt.light-gateway-1.0.0"
  envTag: "dev"
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

Mutable authoring and instance-property projections are never served directly
to a runtime. A runtime observes a change only after Portal creates and
validates an immutable snapshot, activates its current pointer, and explicitly
requests a module reload. Reload makes the runtime call `/configs` again; it
does not bypass snapshot creation or read unpublished property changes.

```mermaid
sequenceDiagram
    autonumber
    actor Operator
    participant Portal as Light Portal control plane
    participant Store as Config Server database
    participant Config as Config Server
    participant Controller as Controller
    participant Runtime as Runtime service

    Operator->>Portal: Publish configuration changes
    Portal->>Store: Project mutable desired instance properties
    Store-->>Portal: Projection watermark and property-set digest
    Portal->>Store: Create immutable snapshot (current = false)
    Portal->>Store: Validate snapshot and move current pointer
    Note over Store: Snapshot content never changes; only the current pointer moves
    Portal->>Controller: Reload module for host + serviceId + envTag
    Controller->>Runtime: Reload configuration
    Runtime->>Config: GET /configs?host&serviceId&envTag
    Config->>Store: Read current snapshot for logical runtime identity
    Store-->>Config: Immutable snapshot properties
    Config-->>Runtime: values.yml + snapshot identity and digest
    alt Validation succeeds
        Runtime->>Runtime: Atomically apply candidate
        Runtime-->>Controller: APPLIED + snapshotId + digest
    else Validation fails
        Runtime->>Runtime: Keep last-known-good configuration
        Runtime-->>Controller: REJECTED + reason
    end
    Controller-->>Portal: Reload result
```

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

The publisher generates Agent, Gateway, and Knowledge audience projections plus
the coordinated internal Workflow view from explicit schemas and field
allowlists. Each target is canonicalized and digested independently.

### 5. Stage instance properties

For every Config Server target instance, the publisher first persists an immutable
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
- host, service, environment, and audience binding;
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

Each Config Server runtime reports or exposes:

- current configuration snapshot ID;
- publication ID;
- content and policy digests;
- load timestamp;
- last validation result; and
- last known good snapshot ID.

Acknowledgement is operational evidence. It does not make an invalid snapshot
valid and does not grant authority beyond the snapshot itself.

## Config Server Contract

`GET /configs` is the canonical workload configuration endpoint. It returns
only the current immutable YAML snapshot selected by `(host, serviceId,
envTag)`. There is no secondary live-resolution mode: `productId` and
`productVersion` are not contract fields and never influence snapshot
selection. During the compatibility window, Config Server ignores these and
the former `apiId` and `apiVersion` query fields so older clients do not fail
before the handler runs. `serviceId` is never inferred from `productId`. The
same snapshot-only rule applies to `/certs` and `/files`. `configPhase` may
remain an optional content selector within the authorized logical identity.

The response uses `Content-Type: application/yaml`. As the publication contract
is implemented, `/configs` should also return `ETag`, RFC 9530 `Repr-Digest`,
`X-Config-Snapshot-Id`, `X-Policy-Publication-Id`, `X-Policy-Digest`,
`X-Content-Digest`, `X-Artifact-Digest`, validity-window headers,
`X-Manifest-Key-Id`, and `X-Manifest-Signature`. The signature covers the
logical runtime identity, publication/snapshot identity, all digests,
compatibility generation, revocation epoch, and the validity window.
`If-None-Match` should be supported.

`X-Light-Config-Instance-Id` remains temporary response metadata while existing
`light-workflow` releases use it in their last-known-good cache record. It is
not a lookup input, authorization claim, or member of workload identity. A
later Workflow cache-schema migration removes that dependency before the
header and the corresponding optional runtime-provenance field are retired.

No separate workload acknowledgement endpoint is required. The existing
control-plane module-reload path returns the runtime's applied or rejected
result and records the snapshot identity and digest as operational evidence.

### Current configuration

The runtime requests current configuration using a workload JWT and, where
required by the deployment, mTLS. The request supplies `host`, `serviceId`, and
`envTag`; Config Server verifies them against the authenticated identity. These
three values are the complete runtime lookup identity and are unique within one
Light Portal installation. Audience and permitted configuration phase are
authorization and content constraints, not additional identity keys.
Caller-controlled values cannot override or widen authenticated claims. Config
Server returns the exact immutable snapshot selected as current; its ETag is
the quoted `artifactDigest`.

During the rolling-upgrade window only, an older client may omit `serviceId` or
`envTag` from the query when the authenticated JWT supplies the missing `sid`
or `env` claim. This is claim-derived compatibility, not product-based lookup.
New clients must send all three canonical identity fields and fail locally when
one is absent.

### Historical configuration

Config Server should also support retrieval by an explicit `snapshotId` for:

- session resume under a pinned policy;
- rollback preparation;
- audit and diagnosis; and
- recovery of a runtime that did not persist an older pinned policy locally.

Historical retrieval is an operator/Portal concern unless a future explicitly
authorized snapshot endpoint is required. Any such endpoint must use the same
`(host, serviceId, envTag)` authorization boundary and must not introduce an
`instanceId` workload binding.

### Read-only semantics

Runtime credentials authorize only configuration reads. They do not authorize
property editing, snapshot creation, current-pointer changes, policy
publication, or direct writes of reload evidence.

Config Server access logs record identifiers and response size only. Trace,
debug, error, and acknowledgement paths must never log the rendered YAML body.

## Runtime Loading And Enforcement

At startup, a Config Server runtime:

1. authenticates to Config Server using its workload identity;
2. requests `/configs` with its host, service ID, and environment tag;
3. verifies the response identity, audience, schema, signature, digests, and
   validity window;
4. compiles the audience policy into its local enforcement representation;
5. stores the immutable policy in service-owned storage when necessary;
6. atomically replaces its in-memory current configuration and, for Knowledge,
   the complete version-matched published control-replica set; and
7. records acknowledgement and health evidence.

During operation, configuration changes are applied through the explicit
control-plane module-reload lifecycle shown above. The runtime does not poll
mutable Portal state and a property publication alone does not change its
configuration. On reload, the runtime fetches the current snapshot again and
fully parses and validates the candidate before replacing the current in-memory
object.

The Knowledge artifact is a complete replica inventory with explicit
tombstones, aggregate control versions, source event watermark, and a manifest
digest. Knowledge stages and validates the entire set, rejects a regressing
release/watermark/version, and activates the replica set and applied-snapshot
pointer in one Knowledge transaction. Partial delivery cannot delete state, and
snapshot application never creates jobs or repeats historical external effects.

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

Agent, Gateway, and Knowledge runtimes cannot be assumed to refresh at the same
instant, and the internal Workflow projection may advance on a different
checkpoint. The publication protocol therefore uses a shared release manifest
containing:

- publication ID and release version;
- domain policy snapshot and digest;
- required audience targets;
- Config Server target instance and configuration snapshot IDs;
- internal view identifiers and projection checkpoints where they participate;
- each audience content digest;
- compatibility generation;
- source event watermark;
- staged, active, failed, or rolled-back state; and
- validation and acknowledgement evidence.

Adjacent releases should normally support an overlap window:

- an old Agent may call a new Gateway or Knowledge runtime;
- a new Agent may call an old Gateway or Knowledge runtime; and
- the receiver can distinguish compatible transition traffic from an unknown
  or forged publication.

If overlap is impossible, activation requires a two-phase rollout: prefetch and
validate all Config Server targets, verify required internal views are pinable,
then activate traffic only after every required runtime audience acknowledges
readiness.

## Security Requirements

- Bind every response to the authenticated workload's host, service ID, and
  environment tag; enforce audience as an authorization/content constraint.
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
`configSnapshotId`, `policyDigest`, host, environment, and service ID. Portal
authoring audit may additionally carry its internal instance database key, but
workload delivery and runtime logs do not require it.

## Current Implementation Gaps

The Rust Config Server in `portal-service` provides the correct delivery
foundation: `/configs`, `/certs`, and `/files` select current snapshot content
by `(host, serviceId, envTag)` and do not expose a mutable property-resolution
mode. Runtime clients send only that logical identity. Remaining work includes
the publication envelope, audience authorization, artifact digest/ETag,
validity lease, signed manifest, and structured reload-result evidence.

`config-query` can read a historical snapshot by `hostId` and `snapshotId`, but
that Portal query operation remains an operator API rather than a Config Server
workload-identity API.

The current snapshot schema also lacks an immutable staged publication target,
coordinated release manifest, property-set/content/artifact digests, source
event watermark, audience, validation state, validity lease, and compatibility
generation. Snapshot creation from mutable instance rows is vulnerable to
mixing a concurrent change into a publication unless the staged target and
projected digest are checked.

### Current Workflow database access

`light-workflow` creates one SQLx PostgreSQL pool from its registered
operational-store URL and shares it across direct invocation admission,
execution, and reconcilers. The database is customer-owned and is not the
Portal `configserver` database. The service starts its legacy
`WorkflowStartedEvent` outbox consumer only when the same database explicitly
contains the legacy `outbox_message_t` and `log_counter` source tables. Normal
customer-managed deployments use `/v1/workflow-invocations` and do not receive
direct Portal database access.

Its access falls into three categories:

| Category | Current tables/path | Target boundary |
| --- | --- | --- |
| Legacy event consumption | Optional local `outbox_message_t`, `log_counter`, `consumer_offsets`, and quarantine state | Compatibility-only. Do not connect a customer runtime directly to the Portal control-plane database. |
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
follows a different boundary: Config Server supplies its immutable policy and
its database roles are restricted to snapshot-loader writes of published
control replicas and service-owned operational state.

## Migration Plan

### Phase 1: Publication contract

- Define the common policy envelope, Agent/Gateway/Knowledge audience schemas,
  and the coordinated identity carried by the internal Workflow view.
- Define canonical serialization and digest rules.
- Add immutable staged target manifests, publication/release metadata, and
  target snapshot linkage.
- Add source-event watermark and validation state to the snapshot contract.

### Phase 2: Portal compiler and staging

- Implement deterministic effective-policy resolution.
- Compile audience projections through explicit allowlists.
- Freeze each Config Server target's complete resolved configuration, desired
  property changes, and every inherited input version/digest.
- Emit correlated, idempotent instance-property events.
- Verify projection checkpoints and exact property-set digests before snapshot
  creation; mark mismatches stale rather than snapshotting live rows.
- Render and validate staged `values.yml` artifacts.

### Phase 3: Config Server delivery

- Roll out compatibility first: ignore obsolete product/API query fields,
  resolve an omitted service or environment only from authenticated claims,
  and retain the non-authoritative instance metadata header required by
  deployed Workflow last-known-good caches.
- Upgrade Rust and light-4j clients to send only `(host, serviceId, envTag)` and
  fail locally when a canonical identity field is missing.
- Migrate Workflow last-known-good metadata away from the Portal instance UUID;
  remove the transitional header only after the fleet no longer requires it.
- Harden the existing `/configs` snapshot endpoint as the canonical workload
  delivery contract; do not introduce a parallel runtime-query API.
- Bind current reads to host, service ID, and environment-tag workload claims,
  with audience enforced as an authorization/content constraint.
- Return snapshot and publication metadata with content.
- Add artifact-digest ETag/conditional retrieval and canonical digest
  verification.
- Carry bounded applied/rejected evidence through the existing module-reload
  response path.
- Enforce signed validity windows and fail-closed last-known-good behavior.

### Phase 4: Runtime consumers

- Add typed Config Server policy loaders to Agent, Gateway, and Knowledge
  runtimes.
- Persist immutable pinned policies in service-owned storage where needed.
- Implement staged, atomic Knowledge control-replica materialization with
  complete inventory/tombstones, ordering, backfill, replay publication,
  last-known-good, acknowledgement, and event-versus-snapshot parity gates.
- Remove Knowledge event-consumer and Portal projection access; restrict the
  loader to published replicas and other roles to service-owned operational
  writes and reads.
- Inventory Workflow database access and grant only required read-only
  projection access plus service-owned operational writes.
- Pin the Knowledge configuration snapshot and Workflow internal policy view at
  work admission and remove mutable fallback reads during execution.
- Carry publication and policy identity on cross-service calls.
- Add runtime acknowledgement and divergence metrics.

### Phase 5: Coordinated activation

- Stage all target snapshots under one publication.
- Validate compatibility and optionally prefetch.
- Activate and roll back all target pointers through one audited release event
  and one projection transaction.
- Add Portal status, failure details, and operator controls.

### Phase 6: Boundary enforcement

- Remove Portal database credentials from Agent, Gateway, and Knowledge
  deployments.
- Replace the local Workflow superuser credential with a dedicated role and
  restrict Workflow to enumerated projection reads and operational writes. Deny
  direct authoring-projection mutation. Restrict Knowledge to its snapshot-
  loader and service-owned operational database roles.
- Add network and database policy enforcing these differentiated boundaries.
- Prove configuration delivery across independently operated environments.
- Run rollback, partial outage, stale snapshot, and mixed-generation exercises.

## Executable Agent Publisher Implementation Plan

The generic phases above remain the target architecture. The following track
closes the concrete bootstrap failure in which an imported Agent snapshot
contains only bootstrap and `operationalStore.*` values while `light-agent`
requires a complete immutable `runtimePolicy`, `portalAssociation`, and
`agentPolicy` projection. This track is deliberately Agent-first; it must not
invent a local-only policy format or bypass the Config Server snapshot
authority.

### P0: Freeze the cross-language contract and fail before Compose

Owners: `light-fabric`, `light-portal`, `portal-config-loc`, and
`light-portal-install`.

- Freeze one machine-checked manifest of the Agent property names, value types,
  required/non-empty fields, UUID fields, digest fields, identity equalities,
  and validity-window ordering accepted by `light-agent`.
- Add a Java/Rust fixture proving the two existing digest contracts exactly:
  RFC 8785 for `runtimePolicy.contentDigest`, and the deployed ordered
  `PolicySnapshot` JSON representation for `runtimePolicy.policyDigest`.
- Make local and installer bootstrap query each current Agent snapshot for the
  complete mandatory projection. Report the service ID and missing properties
  before starting application services. The existing 15-property
  operational-store check is necessary but not sufficient.
- Record the current incomplete 21-property snapshot as a negative fixture so
  a future validation regression cannot again report it as ready.

Exit gate: both deployment paths reject the current incomplete baseline with a
bounded missing-property diagnostic, and accept a cross-language full-policy
fixture.

### P1: Compile the base Agent audience projection

Owner: `light-portal`.

- Add an `AgentPolicyProjectionCompiler` that resolves one active native Agent
  runtime through `instance_t -> instance_api_t -> api_version_t ->
  agent_definition_t` and rejects missing, duplicate, read-only, cross-host, or
  environment-mismatched links.
- Resolve the selected `llm_public_alias_t`, Agent definition limits, assigned
  `agent_skill_t`/`skill_t` records, and the existing operational-store
  projection. Prompt text comes from the registered Agent/API description;
  provider credentials never enter the Agent projection.
- Compile safe empty collections for optional quota, rate, runner, Knowledge,
  A2A, channel, data-boundary, and delegation policy only when no authoring
  record grants them. Absence must never widen authority.
- Produce every component digest, the ordered policy-snapshot digest, the
  canonical Agent content digest, source aggregate versions, schema version,
  compatibility generation, and the canonical workload identity
  `(host, serviceId, envTag)`.
- Use an explicit `LOCAL_DEMO` lease profile for `local.localhost` installations
  so downloadable release baselines do not expire before evaluation. Production
  profiles retain bounded leases; changing a lease profile creates a new
  publication.

Exit gate: real-PostgreSQL compiler tests cover all three local Agent instances,
model-alias mismatch, duplicate runtime links, stale Skills, digest parity, and
deny-safe optional defaults.

### P2: Persist an event-backed atomic publication

Owners: `light-portal`, `genai-command`, and `genai-query`.

- Add an Agent publication-candidate query and an explicit publish command.
  Publishing emits one immutable `AgentPolicyPublishedEvent` whose manifest
  contains the exact property writes, expected property versions, source
  versions, lease profile, policy/content digests, publication ID, and Config
  snapshot ID.
- Project the event idempotently in one database transaction into
  `instance_property_t`, `agent_policy_snapshot_t`, and the immutable Config
  snapshot, then move the logical current pointer. No incomplete intermediate
  snapshot is observable. Bootstrap projection reconstructs the same desired
  properties and snapshot without calling external services or consulting
  wall-clock time. Operational repair replay is excluded, matching the Config
  snapshot events, so an obsolete publication cannot become current later.
- Reject stale expected versions and property ownership conflicts. Updates and
  removals are explicit; a second publisher cannot silently take ownership.
- Register the events in aggregate identity, replay policy, global snapshot
  dependency, export, and import contracts.

Exit gate: live command execution and bootstrap reconstruction produce
byte-identical property sets and digests, and global snapshot export contains
all authority needed to rebuild them.

### P3: Snapshot validation and atomic activation

Owners: `light-portal`, Config Server, and `light-fabric`.

- Validate the candidate digest and expected property versions before applying
  any write. Create and activate the Agent configuration snapshot in the same
  projection transaction; any validation, write, evidence, or snapshot failure
  rolls the entire publication back.
- The compiler renders the exact Agent values accepted by the frozen Rust
  contract before event creation. The projector stores the policy and content
  digests as immutable evidence and activates any compatible staged A2A overlay
  only after the new snapshot contains all of its proposed properties.
- A2A publication may overlay an already active base Agent generation but may
  not create or repair that base generation.
- Preserve last-known-good behavior and return the publication, policy,
  content, and snapshot identities in Config Server metadata.

Exit gate: an incomplete snapshot, wrong identity, bad digest, expired lease,
or mixed property generation never becomes current.

### P4: Release and operator workflow

Owners: Portal View, release automation, and `portal-config-loc`.

- Expose `Current` or `Ready to publish` for each linked native Agent, including
  candidate validation failures. Publication is an explicit action after Agent
  registration or policy changes.
- Before `daily-release.sh` exports the global snapshot, require active and
  applied base publications for the Account, Advisor, and Tech Support local
  Agents. Release generation fails if any required Agent is missing or stale.
- Export the publication events before their `ConfigSnapshotCreatedEvent`
  dependencies. Never export derived snapshot-property rows as replacement
  authority.

Exit gate: a release artifact recreated into an empty database yields the same
three active Agent policy generations without manual SQL or retained container
caches.

### P5: Local and installer end-to-end qualification

Owners: `portal-config-loc` and `light-portal-install`.

- Run identical full Agent snapshot preflight in both repositories.
- Qualify every required Agent container through health/readiness, then verify
  its reported snapshot and content digest against Config Server.
- Exercise fresh Docker and Podman/Silverblue installs, database recreation,
  update over an existing last-known-good cache, and rollback.
- Keep only the user-supplied LLM provider API key in `.env`; Agent publication
  identifiers, database URLs, and local demo policy are non-secret configuration.

Exit gate: both repositories recreate from the same signed release bundle and
all required Agents remain healthy with matching publication evidence.

## Acceptance Criteria

The design is complete when:

1. Agent, Gateway, and Knowledge start and serve authorized traffic without
   Portal database credentials. Knowledge uses only its Config Server audience
   snapshot, published control replicas, and service-owned operational tables;
   Workflow uses only enumerated read-only projections and service-owned
   operational tables through non-superuser roles.
2. Each Config Server workload can retrieve only its own audience projection from
   Config Server; query parameters cannot override workload identity.
3. A publication produces immutable snapshots for all required target
   instances from one declared event watermark.
4. No current pointer changes when any required projection or validation fails.
5. A successful release exposes matching publication identity across Config
   Server audience snapshots and participating internal policy views.
6. Existing sessions remain pinned to their original domain policy snapshot
   after a new release.
7. Rollback and forward activation work by pointer movement without modifying
   historical snapshot content.
8. Config Server unavailability preserves last known good behavior only until
   the signed `expiresAt` lease and fails closed afterward.
9. A Config Server runtime rejects a snapshot with the wrong host, service ID,
   environment tag, audience, schema, digest, signature, or validity window.
10. Portal database access is denied to Agent, Gateway, and Knowledge. Knowledge
    proves immutable Config Server snapshot loading, atomic published-replica
    materialization and pinning, and otherwise operational-only database access.
    Workflow proves least-privilege projection reads, immutable work pinning,
    operational-only writes, and denial of direct authoring-projection mutation.
11. Concurrent inherited- or instance-configuration changes cannot contaminate
    a staged publication, and activation/rollback changes all target pointers
    through one event-backed transaction.

## Design Consequences

This architecture adds a publication compiler and coordinated release state,
but it establishes a clean company and security boundary. Light Portal owns
authoring and immutable publication. Config Server owns read-only delivery.
Agent, Gateway, and Knowledge workloads own enforcement and runtime state
without Portal database access. Knowledge receives its narrow policy projection
from Config Server; internal Workflow consumes narrowly scoped event-backed
projections.

The result is independently deployable services, reproducible authorization,
safe rollback, and no Config Server runtime dependency on Light Portal database
tables for control-plane policy. The accepted Workflow shared-database topology
remains an explicit internal contract that can later be replaced by Config
Server delivery without changing pinned policy identities.
