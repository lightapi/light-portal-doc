# Entity Creation Uniqueness

## Status

Proposed design for [light-portal issue 691](https://github.com/lightapi/light-portal/issues/691).

## Executive Decision

Light Portal must enforce entity creation uniqueness in the authoritative command
transaction, before a `*CreatedEvent` is appended. The UI and the asynchronous
projection database may provide early feedback, but neither is authoritative.

Two invariants are required:

1. An aggregate stream can contain only one birth event. A normal create command
   must use expected version `0`, append version `1`, and fail if the aggregate
   stream already exists.
2. Every creatable aggregate must declare either a semantic creation identity or
   explicitly declare that multiple semantically similar entities are allowed.
   This declaration is required even when the storage key is a generated UUID.

A generated UUID makes two rows technically distinct. It does not prove that they
represent different business entities. For example, categories with different
UUIDs can still be the same category when host, entity type, parent, and normalized
name are equal.

The recommended implementation is a versioned creation-policy registry plus an
`entity_identity_t` reservation table. The identity reservation, event-store
append, outbox write, nonce allocation, and idempotency record must commit in one
PostgreSQL transaction.

## Problem

Issue 691 demonstrates the same-aggregate form of the defect:

1. A role such as `abc-123` already exists at aggregate version 1.
2. A second create request uses the same role identity.
3. The command path finds the existing stream and emits another
   `RoleCreatedEvent` at aggregate version 2.
4. The role projection refuses to replace an active row and leaves it at version
   1.
5. `GetFreshRole` compares the projection with the event store and returns
   `ERR11645` because the read model is behind the write model.

This behavior follows directly from the current shared command flow.
`AbstractCommandHandler.populateAggregateVersion()` increments the aggregate
version whenever a stream exists; it does not distinguish create from update.
The role and rule create projections use conflict handling that only reactivates a
soft-deleted row. A conflicting create for an active row is skipped, including its
new aggregate version.

The existing event-store constraint on `(aggregate_id, aggregate_version)` prevents
two events from occupying the same version. It does not prevent a second birth
event at version 2, 3, or later.

Generated UUID aggregates have a second form of the same problem:

- `CreateCategory` and `CreateTag` generate a new UUID for every request, while
  their projection tables define business uniqueness using names, scope, entity
  type, and parent fields.
- Some handlers, such as platform and config creation, query the projection for an
  existing business key and reuse its UUID. That check is vulnerable to projection
  lag and concurrent requests.
- Two create commands can therefore append two valid-looking event streams before
  the second event reaches a projection unique constraint.

The failure is not specific to role or rule. It is a missing write-side creation
contract shared by many command services.

## Goals

- Reject a second create for an existing aggregate without changing its event
  stream.
- Prevent semantic duplicates when each request generates a different UUID.
- Resolve concurrent create races atomically.
- Distinguish a retry of the same request from a new conflicting request.
- Preserve tenant, global, and parent-scoped uniqueness boundaries.
- Preserve immutable event history and make existing corrupt streams repairable.
- Provide one reusable implementation rather than handler-specific query checks.
- Return an actionable conflict to the UI without exposing another tenant's data.

## Non-goals

- Treating all equal request payloads as the same entity.
- Preventing valid multiplicity for events such as audit records, workflow runs,
  messages, or orders.
- Replacing update optimistic concurrency control.
- Making the projection database part of the authoritative command transaction.
- Turning create into an upsert or silently changing an existing entity.
- Automatically allowing an identity to be reused after delete or rename.

## Terminology

### Aggregate ID

The event-stream subject. It may be a natural composite ID such as
`hostId|roleId`, or a generated UUID.

### Semantic Creation Identity

The minimum immutable domain fields that answer: "Would another create request
represent the same entity?" It includes the uniqueness scope.

Examples include:

| Aggregate | Storage ID | Candidate semantic creation identity |
|---|---|---|
| Role | `hostId\|roleId` | host + normalized role ID |
| Rule | rule ID or composite event subject | global/host scope + normalized rule ID |
| Category | generated UUID | global/host scope + entity type + parent category + normalized category name |
| Tag | generated UUID | global/host scope + entity type + normalized tag name |
| Platform | generated UUID | host + normalized platform name + platform version |
| Config | generated UUID | normalized config name in its catalog scope |
| Instance | generated UUID | host + service + resolved environment catalog tuple (`scope_type`, `scope_id`, normalized value) + product version |

These are candidate contracts derived from current event-subject and projection
constraints. Phase 0 of implementation must inventory and approve the exact key for
every create event.

### Idempotency Key

A client-generated identifier for one create attempt. It answers "Is this a retry
of the same request?" It does not answer "Is this the same business entity?"

### Birth Event

The one event that establishes an aggregate stream, normally a registered
`*CreatedEvent`. A restore or reactivation is a lifecycle mutation, not another
birth event.

## Required Invariants

### One Birth Event Per Aggregate

For a normal command append:

- a birth event must carry expected aggregate version `0`;
- its new aggregate version must be `1`;
- no event may already exist for the aggregate ID; and
- a second birth event is rejected even when the existing entity is inactive.

Create handlers must not call the current "max version plus one" behavior. The
shared command abstraction should expose an explicit command kind so that create
commands always build a provisional version-1 event. The transactional append path
remains the final enforcement point.

### Declared Semantic Multiplicity

Every registered birth event must have exactly one creation policy:

- `UNIQUE`: extract and reserve a semantic creation identity; or
- `ALLOW_MULTIPLE`: different aggregate IDs may intentionally have the same
  semantic fields.

`ALLOW_MULTIPLE` must be an explicit reviewed decision. It does not permit a second
birth event on the same aggregate stream.

This fail-closed inventory prevents a new UUID-based entity from accidentally
bypassing semantic uniqueness just because nobody added a handler check.

### Write-side Authority

The event-store append transaction and its identity registry are authoritative.
The following are advisory or defensive only:

- create-form duplicate checks;
- query-service existence checks;
- projection primary keys and unique indexes; and
- create-button disabling.

## Creation Policy Registry

Add a versioned, exact-event-type `EntityCreationPolicyRegistry` in the database
provider. It should reuse the inventory and fail-closed techniques of the existing
replay policy registry without mixing creation semantics into replay policy.

Each entry contains at least:

```text
eventType
eventSchemaVersion
aggregateType
commandKind: CREATE
multiplicity: UNIQUE | ALLOW_MULTIPLE
scopeExtractor: HOST | GLOBAL | HOST_OR_GLOBAL | PARENT | CUSTOM
identityFields
normalizerVersion
reusePolicy: NEVER | EXPLICIT_RELEASE
idempotencyRetention
```

`idempotencyRetention` gives the policy-specific retention requirement a
configuration owner. Without it the `ALLOW_MULTIPLE` retention rule is prose that
nothing can enforce or validate. The registry startup check must reject an
`ALLOW_MULTIPLE` entry whose retention is shorter than the configured maximum
client and gateway retry horizon.

The registry must verify at startup that every portal birth event has exactly one
entry. A digest of the complete birth-event inventory should make addition or
removal of a create event fail tests until its uniqueness policy is reviewed.

The registry extracts identity fields from the validated CloudEvent data in the
database provider. A handler must not supply an opaque, client-controlled identity
string that bypasses the registered extractor.

### Scope Is Security-sensitive

Uniqueness scope must come from trusted command context, not an unverified
`hostId` in the request body.

- Host scope uses the authenticated and validated host identity.
- Coarse permission to invoke a command is decided by Light Gateway against the
  command's logical endpoint and its Portal-managed role and CEL policy.
- Global scope requires a gateway authorization decision that is specific to a
  global-only endpoint or to the global branch of a combined endpoint policy.
- Parent scope includes the trusted host plus the parent aggregate identity.
- The CloudEvent host extension identifies event ownership/routing; it must not be
  mistaken for entity scope when an authorized administrator creates a global
  entity.

The command path should stamp an authenticated entity-scope extension when the
scope cannot be derived unambiguously by the database provider.

#### Tenant-local And Global Name Reuse

Semantic uniqueness is enforced *within* a declared scope, not across every
tenant. `scope_type` and `scope_id` are part of the complete reservation key, so
the same normalized identity may be reserved independently by different tenants.
For example, the `environment` reference table supports a global catalog plus
tenant-defined environment values:

| Environment value | Scope tuple | Result |
|---|---|---|
| Global `dev` | `(GLOBAL, GLOBAL_SENTINEL)` | one global reservation |
| Tenant A `dev` | `(HOST, tenant-a-host-id)` | permitted; distinct reservation |
| Tenant B `dev` | `(HOST, tenant-b-host-id)` | permitted; distinct reservation |
| Second Tenant A `dev` | `(HOST, tenant-a-host-id)` | rejected as a duplicate in Tenant A |

The effective `envTag` catalog may concatenate or merge global values with the
authenticated tenant's values. That read-side composition does not change the
write-side reservation scope: a host reservation neither blocks another host nor
claims the global name. If a catalog needs tenant-over-global precedence or
deduplication for display, its query policy owns that behavior; the identity
registry must not silently turn it into cross-tenant uniqueness.

Every creation policy must therefore name its scope extractor explicitly. A
tenant-owned reference value uses trusted host scope, a global reference value
uses the global sentinel, and a parent-owned value includes both trusted host and
parent identity. A missing or ambiguous scope is a policy error and fails closed.

#### Current Scope Derivation Is Unsound

The existing code does not yet meet this contract, and identity enforcement must
not be built on it as-is. The legacy command layer still makes a coarse
authorization decision that now belongs to Light Gateway:

- `handle()` decides global scope with `role.contains(PortalConstants.ADMIN_ROLE)`
  where `ADMIN_ROLE` is `"admin"`. Both `org-admin` and `host-admin` contain
  `"admin"` as a substring, so a tenant-scoped administrator can set the global
  flag, have `hostId` removed, and create a global entity.

Replacing that substring test with `hasAnyRole()` would fix the immediate match
bug, but it would preserve duplicated coarse authorization in every command
service. The target model is instead:

1. Light Portal assigns roles and request-access rules to logical endpoints such
   as `lightapi.net/role/createRole/0.1.0` and
   `lightapi.net/rule/createRule/0.1.0`.
2. Light Portal publishes the generated endpoint permissions and rule bodies to
   the config server. Gateway instances load the effective policy from the config
   server; static `values.yml` is not the authorization source.
3. Light Gateway derives the logical portal endpoint from the hybrid request,
   exposes the command `data` as the CEL request context, and denies the request
   unless the endpoint's configured policy passes.
4. After that deployment contract is proven, `AbstractCommandHandler` stops
   deciding whether the caller may invoke the command by parsing `admin`,
   `org-admin`, or `host-admin` itself.

Policy publication needs an activation boundary. The Portal/config-server write
must expose a revision or digest, and every gateway instance serving portal
commands must acknowledge that effective revision before the command-layer role
check is removed. An instance on an unacknowledged revision must be kept out of
the portal route. `defaultDeny` protects an endpoint that is absent from the
loaded policy, but it cannot make an older, still-permissive rule equivalent to a
new revision.

Assigning roles to an endpoint is necessary but not sufficient. The endpoint
must also have an active `req-acc` rule, and the effective gateway policy must
fail closed when either the role permission or rule is absent. For a command
that supports both host and global creation, a static list such as
`admin org-admin host-admin` cannot distinguish the two branches. Prefer
separate tenant and global logical endpoints. If one endpoint must remain
shared, use one combined CEL decision, or `accessRuleLogic: all`, so that:

- a host-scoped request requires an assigned role and the request host must match
  the authenticated host; and
- a global request requires the exact global-administrator permission.

Do not combine an unconditional role rule and a scope rule under
`accessRuleLogic: any`; either rule succeeding would admit the request.

Gateway authorization is still not a replacement for command-side data
integrity. The gateway currently returns allow or deny; it does not turn a
caller-supplied `hostId` or `globalFlag` into trusted scope and it cannot inspect
the stored target owner. The command boundary must therefore remain role-neutral
and enforce:

- `effectiveHost()` must not prefer a request-body `hostId` over the trusted host;
- `handle()` must not fall back to `map.get(HOST_ID)` when authenticated host
  context is required;
- request host, target host, and parent scope must match trusted context;
- owner and owner-position checks must use the stored target; and
- ownership transfer, aggregate version, lifecycle, and uniqueness rules remain
  database-backed command invariants.

Where an existing helper still uses a raw role to choose owner-wide or global
scope, remove that dependency only after the gateway supplies an unforgeable
authorization-scope decision or the operation is split into scope-specific
logical endpoints. Until then, deleting the check would widen access rather than
eliminate duplication.

This is a pre-existing defect rather than one introduced here, but reserving
identities under a spoofable scope converts it from a contained privilege bug into
permanent cross-tenant name squatting: a host-admin could reserve global
identities that, under the default `NEVER` reuse policy, block every other tenant
forever. That is why Phase 0 treats this as a deployment gate.

### Canonicalization

Identity canonicalization must be versioned and field-specific:

- encode a typed, field-named canonical JSON structure in a stable field order;
- normalize Unicode, whitespace, and case only when the domain and database
  constraint define those values as equivalent;
- distinguish null, an empty string, and an absent optional field unless the
  entity contract says otherwise;
- use canonical parent IDs rather than display names;
- when an identity references a scoped catalog value, encode its resolved
  `(scope_type, scope_id, normalized value)` tuple rather than the bare display
  name; and
- exclude mutable descriptions, timestamps, generated IDs, and secrets.

For example, an Instance identity must distinguish global `dev` from Tenant A's
`dev` even though both render the same `envTag` text. A later change to catalog
precedence, fallback, or deduplication must not silently reinterpret an existing
reservation. If the resolution contract changes, treat it as an identity
normalizer-version change and follow the materialization and mixed-version
protocol below.

Do not lowercase all entity names globally and do not hash the entire request.
Those shortcuts change domain semantics and make harmless mutable fields part of
identity.

The registry stores a SHA-256 digest for indexed lookup. The complete reservation
key is `(scope_type, scope_id, aggregate_type, identity_schema_version,
identity_hash)`; `identity_hash` is the discriminating component within a fixed
scope, aggregate type, and schema version, not the whole key. Two identities
producing the same digest under the same scope, aggregate type, and schema version
are treated as the same reserved identity and fail closed.

The canonical value is not persisted by default. A reviewed per-aggregate policy
may opt in to retaining specific non-sensitive explanatory fields when operators
need to explain a conflict; nothing else is stored. Identity material must not
contain credentials, tokens, or other secrets.

Changing a normalizer creates a new identity schema version. Because
`identity_schema_version` is part of the reservation key, a lookup at version N+1
does not see a reservation stored at version N. Retaining old-version rows as
aliases is therefore **not sufficient**: an existing entity would be unprotected
under the new hash, and a duplicate create could succeed against it.

Before enforcement is enabled at a new version, every live entity's identity must
be **materialized at the current version** — recompute the canonical identity with
the new normalizer and insert a version-N+1 row with `binding_status = CURRENT`
for each aggregate whose owner row is `ACTIVE`. Version-N rows are retained
unchanged so a create cannot impersonate a pre-migration identity; they keep their
own `binding_status`, and an aggregate legitimately holds a `CURRENT` binding at
both versions for the duration of the migration. Enforcement at version N+1 may
only begin once materialization is complete and verified for the aggregate group.

Materialization alone is not enough during a rolling deployment. A node still
running version N writes version-N reservations, so it can create an identity
*after* the N+1 backfill has run and that identity will have no version-N+1 row
protecting it. Choose one of:

- **Dual-write.** Nodes write both version-N and version-N+1 reservations for the
  duration of the migration. Both rows are inserted in the create transaction, so
  a late version-N writer still produces the N+1 row that enforcement depends on.
- **Drain.** Stop all version-N writers for the aggregate group, then materialize,
  then enable N+1 enforcement. Simpler, but requires a write pause.

Dual-write is preferred for aggregate groups that cannot tolerate a write pause.
Either way, N+1 enforcement may only be enabled after the chosen protocol has
completed, and the backfill must be re-verified after the last version-N writer
exits.

## Persistence Model

### Entity Identity Registry

A command-side table reserves semantic identities independently of asynchronous
projections:

Entity lifecycle belongs to the aggregate, not to any one identity binding, so it
lives in its own owner table:

```sql
CREATE TABLE entity_aggregate_t (
    aggregate_type   VARCHAR(255) NOT NULL,
    aggregate_id     VARCHAR(255) NOT NULL,
    entity_status    VARCHAR(16)  NOT NULL,
    created_event_id UUID         NOT NULL,
    created_ts       TIMESTAMPTZ  NOT NULL DEFAULT CURRENT_TIMESTAMP,
    retired_ts       TIMESTAMPTZ,
    PRIMARY KEY (aggregate_type, aggregate_id),
    CHECK (entity_status IN ('ACTIVE', 'RETIRED'))
);

CREATE TABLE entity_identity_t (
    scope_type              VARCHAR(16)  NOT NULL,
    scope_id                VARCHAR(255) NOT NULL,
    aggregate_type          VARCHAR(255) NOT NULL,
    identity_schema_version INTEGER      NOT NULL,
    identity_hash           BYTEA        NOT NULL,
    identity_explanation    JSONB,
    aggregate_id            VARCHAR(255) NOT NULL,
    binding_status          VARCHAR(16)  NOT NULL,
    created_event_id        UUID         NOT NULL,
    created_ts              TIMESTAMPTZ  NOT NULL DEFAULT CURRENT_TIMESTAMP,
    demoted_ts              TIMESTAMPTZ,
    PRIMARY KEY (
        scope_type,
        scope_id,
        aggregate_type,
        identity_schema_version,
        identity_hash
    ),
    FOREIGN KEY (aggregate_type, aggregate_id)
        REFERENCES entity_aggregate_t (aggregate_type, aggregate_id),
    CHECK (binding_status IN ('CURRENT', 'ALIAS'))
);

CREATE UNIQUE INDEX entity_identity_current_aggregate_version_uk
    ON entity_identity_t (
        aggregate_type,
        aggregate_id,
        identity_schema_version
    )
    WHERE binding_status = 'CURRENT';
```

The invariant is one *current binding* per aggregate per identity schema version,
not one row per aggregate. A plain `UNIQUE (aggregate_type, aggregate_id)` would
forbid the aliases that rename requires, and scoping the index to the aggregate
alone would forbid the version-N/N+1 dual-write that normalizer migration
requires.

`identity_explanation` is null unless a reviewed policy opts in to retaining
non-sensitive explanatory fields. It is never part of the reservation key.

Scoping the index by `identity_schema_version` is what permits normalizer
dual-write: during a migration an aggregate legitimately holds one `CURRENT`
binding at version N and another at version N+1.

#### Why Lifecycle Is Not Stored On The Binding

An aggregate can hold several identity rows at once — aliases from earlier renames
plus one `CURRENT` binding per schema version during dual-write. Entity lifecycle
is a property of the aggregate, so storing `entity_status` on each binding would
denormalize one fact across every one of those rows. Delete, restore, rename, and
reparent would each have to update a set whose size depends on rename history and
migration state, and any missed row would leave the aggregate simultaneously live
and deleted.

`entity_aggregate_t` holds exactly one `entity_status` per aggregate:

- **Delete and restore** update a single row, so they are correct regardless of how
  many aliases or schema versions exist. No fan-out, nothing to reconcile.
- **Rename and reparent** touch only `binding_status`, and must demote the old
  binding and create the new `CURRENT` binding **for every schema version
  currently participating in dual-write**, all in one version-checked transaction.
  A rename that updated only version N would leave version N+1 pointing at the old
  name and enforcement inconsistent between them.
- **Conflict responses** join to `entity_aggregate_t` for `entity_status`. There is
  one value to read, so `ENTITY_RETIRED` and `ENTITY_ALREADY_EXISTS` cannot
  disagree across bindings.

The foreign key makes an orphaned binding unrepresentable, and the owner row is
inserted in the same create transaction as the first binding and the first event.

An `ALLOW_MULTIPLE` aggregate has no identity reservation and therefore no owner
row; its lifecycle remains where it is today, in the projection. This keeps both
write-side tables sparse rather than turning `entity_aggregate_t` into a general
aggregate registry by accident.

`scope_id` is never null. A global scope uses an explicit canonical sentinel and a
different `scope_type`, avoiding PostgreSQL null-uniqueness ambiguity.

An `ALLOW_MULTIPLE` create inserts no row in this table; the table is sparse by
design. Those aggregates are still covered by stream-birth enforcement, which
rejects a second birth event on an existing aggregate stream.

The table is a write-side reservation ledger, not a query projection. Its row is
inserted in the same transaction as the first event. A rolled-back event append
cannot leave an orphaned reservation, and a committed event cannot exist without
its reservation.

The two statuses are deliberately separate, and live on different tables, because
they answer different questions and have different cardinality:

- `binding_status` on `entity_identity_t` is **identity binding**: is this row the
  aggregate's current identity at this schema version (`CURRENT`), or a historical
  name it no longer answers to (`ALIAS`)? A rename produces an `ALIAS` row. There
  are many per aggregate.
- `entity_status` on `entity_aggregate_t` is **entity lifecycle**: is the entity
  live (`ACTIVE`) or deleted (`RETIRED`)? A delete updates it. There is exactly
  one per aggregate.

These are orthogonal. A renamed but perfectly live entity has an `ALIAS` binding
while its owner row stays `ACTIVE`. Collapsing both into one column would make a
create that collides with a live entity's former name report `ENTITY_RETIRED`,
telling the user to restore an entity that was never deleted.

Conflict responses must therefore read `entity_status` from the owner row, never
infer lifecycle from `binding_status`. Both `CURRENT` and `ALIAS` rows reserve an
identity by default; the binding only determines which name the aggregate
currently answers to.

### Operational Ownership And Maintenance

The creation-policy registry and the identity tables have different cardinality
and must not be maintained as the same artifact:

- the creation-policy registry has one reviewed definition per birth event type;
  for example, one `RoleCreatedEvent` policy declares its scope, multiplicity,
  identity fields, normalizer version, and reuse policy;
- `entity_aggregate_t` has one row per actual `UNIQUE` aggregate instance; and
- `entity_identity_t` has one or more rows per actual `UNIQUE` aggregate instance,
  including aliases and every normalizer version participating in dual-write.

For example, creating 100 roles produces 100 owner rows and at least 100 identity
bindings, while the registry still contains only one `RoleCreatedEvent` policy.
The tables therefore cannot be populated or maintained by a hand-written list of
event types.

One shared database-backed identity transition component owns the rows. Every
append path that can persist a registered lifecycle event must use it, including
normal commands, event import, snapshot-generated event import, approved repair,
and any replay or internal append path permitted to create authoritative events.
Command handlers, UI code, and asynchronous projectors must not issue independent
identity-table writes.

| Domain transition | `entity_aggregate_t` | `entity_identity_t` |
|---|---|---|
| `UNIQUE` create | insert one `ACTIVE` owner | insert one `CURRENT` binding per participating normalizer version |
| Rename or reparent | unchanged | demote the old binding and reserve or reclaim the new binding at every participating version |
| Delete | set the owner to `RETIRED` | leave all bindings reserved |
| Restore | set the owner to `ACTIVE` | leave all bindings unchanged |
| Normalizer migration | unchanged | materialize or dual-write bindings at the new version |
| Explicit release | leave the owner row for aggregate lifecycle and audit | for the exact released identity, delete its reservation rows at every normalizer version participating in dual-write after appending the audited release event |
| Approved repair | apply the registered lifecycle rule | apply an audited, versioned identity mutation |
| `ALLOW_MULTIPLE` transition | no row | no row |

These are synchronous write-side guard tables, not asynchronous query
projections. Domain events define the business history and can be reduced to
reconstruct the registry, but the corresponding owner and identity transition
must commit in the same transaction as the event and outbox writes during normal
operation. Projecting it later would reopen the race in which another create is
admitted before the first reservation becomes visible.

Every mutation that cannot be derived from an existing domain event, especially
an explicit identity release, must have a versioned, audited event or repair
record with deterministic rebuild semantics. Direct SQL or a UI edit that changes
the guard without durable provenance is forbidden because a later rebuild would
silently undo or contradict it.

`entity_identity_t` contains active reservations only, so its `binding_status`
constraint remains `CURRENT | ALIAS`; it does not add a `RELEASED` state that
would still occupy the reservation primary key. An `EXPLICIT_RELEASE` operation
must append a versioned `*IdentityReleasedEvent` containing the aggregate, scope,
released schema versions, and identity digests. The shared transition component,
not the caller, derives the required schema-version set. During normalizer
dual-write the release must cover every participating version in one transaction;
an event whose version list is incomplete is rejected before any event or binding
mutation. Within that complete version set, release deletes only the exact named
identity and never unrelated current or alias bindings. The event store and repair
audit retain provenance, and replaying that event deterministically removes the
same reservations during a rebuild. The owner row remains. Restoring an aggregate
after its identity has been released must reserve a permitted free identity
through an explicit command; it cannot silently recreate the deleted binding.

### Bootstrap, Backfill, And Generated SQL

For a new empty database, `ddl.sql` creates empty identity tables. Bootstrap then
imports the registered domain events through the same shared append transaction
used at runtime; each imported birth, rename, reparent, delete, and restore event
updates the identity tables synchronously. The expected order is:

```text
ddl.sql
  -> validate the creation-policy registry
  -> preflight every bootstrap event and planned identity transition
  -> import bootstrap events through the authoritative append path
  -> verify owner/binding counts and registry digest
  -> enable uniqueness enforcement
```

That sequence is the Phase 5 target contract, not a capability of the legacy
bootstrap fixture today. The current `event-importer/events.json` birth events do
not carry the trusted `commandkind` and `entityscope` extensions required by the
Phase 2 guard, and the importer must not guess whether historical Category or Tag
events were tenant-local or global. Therefore a newly created database populated
from that fixture is treated exactly like an existing database: keep create
traffic fenced, import the events, run the Phase 5 scope-provenance preflight and
versioned backfill, verify the completion record, and only then enable reject
mode. Only an empty database that imports no historical identity-protected events
may enable Phase 2 writers immediately.

Phase 5 records materialization completion per aggregate group. The record is
bound to the covered event range or high-water mark and input digest, creation-
policy registry version, normalizer version, expected owner/binding counts, and
verification digest. Deployment refuses reject mode without a matching completion
record. A non-zero reservation count is not an acceptable substitute: a partial
import or failed backfill can produce rows while still leaving older identities
unprotected.

Preflight is required even when the destination is expected to be empty. It must
report duplicate streams, semantic-identity conflicts, unsupported policy or
normalizer versions, and invalid scope provenance before the first write. This
makes bootstrap, event import, and generated-SQL backfill share the same
fail-before-mutation contract.

A generated SQL artifact such as `entity-identity-bootstrap.sql` may be used to
upgrade an existing database that already contains authoritative events. It is an
output of the versioned backfill tool, not a hand-maintained source of truth and
not the ongoing maintenance mechanism. It must:

- identify the exact input event range or snapshot, creation-policy registry
  version, normalizer versions, and input digest;
- insert `entity_aggregate_t` owners before their binding rows;
- preserve current bindings, aliases, lifecycle, and source event provenance;
- execute in one controlled transaction after report-only conflict analysis;
- be idempotent only when an existing row has exactly the expected owner and
  binding, and fail rather than overwrite a conflicting reservation;
- include expected row counts and a deterministic verification digest; and
- be regenerated whenever the authoritative input or policy version changes.

After bootstrap, creates, renames, reparents, deletes, restores, releases, imports,
and normalizer migrations continue to maintain the rows transactionally. A static
SQL file cannot replace those runtime transitions.

### Rebuild And Environment Promotion

The event store is the historical source for a complete rebuild, while the
identity tables are the authoritative current admission index. A rebuild must run
the same versioned identity transition component over events in aggregate-version
order, preferably into shadow tables. It must report conflicts, verify owner and
binding counts and digests, and replace or enable the rebuilt registry only after
the affected aggregate groups are write-fenced or otherwise protected by the
documented dual-write protocol.

Event-history promotion is the preferred way to move identity-protected entities
between environments:

1. Export the domain event history and its policy/schema metadata.
2. Apply approved target-host, scope, and identifier transformations.
3. Preflight the transformed events against the destination creation-policy
   registry and report every reservation conflict.
4. Recompute the destination owner and binding transitions from the transformed
   events; do not copy source rows with an unverified scope or normalizer version.
5. Insert each event, identity transition, and outbox record atomically.
6. Verify the destination registry before enabling writes for the imported groups.

The current-materialized-snapshot flow needs an additional safeguard. A business
snapshot contains current values but may omit former names that must remain
reserved as `ALIAS` bindings. Snapshot-only promotion must therefore either carry
a versioned identity-reservation manifest containing every required current and
alias binding, or be rejected for identity-protected aggregate groups unless the
relevant event history accompanies it.

`entity_aggregate_t`, `entity_identity_t`, and `command_idempotency_t` must be
excluded from generic projection-table export and generic table-to-CreatedEvent
conversion. They are not standalone business aggregates and must never become
synthetic `EntityAggregateCreatedEvent`, `EntityIdentityCreatedEvent`, or
`CommandIdempotencyCreatedEvent` records. If a snapshot carries an identity
manifest, the importer handles that manifest explicitly, validates its policy and
normalizer versions, and binds it to the imported business-event or snapshot
digest.

`command_idempotency_t` is different from the identity tables: its rows describe
request attempts and cannot be reconstructed from domain events. An in-place
identity-registry rebuild must leave the existing ledger untouched. A promotion
to a new database starts with an empty ledger unless a separate, security-reviewed
active-ledger transfer is performed.

For `UNIQUE` aggregates, an empty destination ledger does not permit a semantic
duplicate because the reconstructed identity reservation remains authoritative.
For `ALLOW_MULTIPLE` aggregates, the ledger is the only retry-deduplication
defense. Their create endpoints must therefore be write-fenced during promotion
and remain fenced until the maximum supported pre-promotion retry horizon has
drained, or the promotion must securely transfer every still-live ledger entry.
An idempotency epoch may be changed only when old-epoch keys are explicitly
rejected; an old retry must never be treated as a new request merely because the
destination ledger is empty.

### Administrative UI

There is no general CRUD UI for these tables. Operators must not insert, update,
or delete reservation rows directly. An administrative identity-registry view may
provide read-only status, rebuild preview, conflict review, and source-event and
policy-version diagnostics. Any release or repair action must invoke a dedicated,
elevated, audited command and produce the durable event or repair record required
for deterministic reconstruction.

### Command Idempotency Ledger

Use a separate table for retry semantics:

```sql
CREATE TABLE command_idempotency_t (
    scope_type       VARCHAR(16)  NOT NULL,
    scope_id         VARCHAR(255) NOT NULL,
    principal_id     VARCHAR(255) NOT NULL,
    command_type     VARCHAR(255) NOT NULL,
    idempotency_key  VARCHAR(128) NOT NULL,
    request_hash     BYTEA        NOT NULL,
    request_fingerprint_version INTEGER NOT NULL,
    aggregate_id     VARCHAR(255) NOT NULL,
    event_id         UUID         NOT NULL,
    completed_ts     TIMESTAMPTZ  NOT NULL,
    PRIMARY KEY (scope_type, scope_id, principal_id, command_type, idempotency_key)
);
```

`principal_id` is the authenticated caller, taken from trusted command context and
never from the request body. Binding the key to a principal rather than only to a
tenant prevents one user from replaying another user's client-generated key and
receiving the original success result, which would disclose an `aggregateId`
without passing that entity's own authorization check. It also removes accidental
collisions between users whose clients derive weak keys from timestamps or form
names.

The ledger stores only the minimum response reference required to reproduce a
successful response. It must not persist secrets copied from a create response.

#### Request Fingerprint

`request_hash` is a versioned fingerprint over **validated client intent plus
trusted scope**. It must not be computed over the enriched event payload.

Enrichment is where retries diverge: `CreateCategory` and `CreateTag` generate a
fresh UUID per request, and the command path stamps event IDs, timestamps, and
aggregate versions before the event is built. Hashing any of that makes a genuine
retry look like a different request, so every retry would return
`409 IDEMPOTENCY_KEY_REUSED` — turning the mechanism into the opposite of what it
is for.

The fingerprint therefore covers:

- the validated client-supplied command fields, after input validation and after
  defaults are applied, so that an unchanged resubmission is stable;
- the trusted scope (`scope_type`, `scope_id`) and `command_type`; and
- the fingerprint version.

It explicitly excludes server-generated and transient values: generated aggregate
UUIDs, event IDs, correlation and trace IDs, aggregate versions, timestamps,
audit metadata, and any field the enrichment step introduces.

Serialization follows the same discipline as identity canonicalization — typed,
field-named, stable field order — and the version is bumped whenever the included
field set or serialization changes.

A retry must be compared using the fingerprint version that produced the stored
entry, which is why `request_fingerprint_version` is persisted alongside
`request_hash`. On lookup, read the stored version, compute the fingerprint with
*that* implementation, and compare. Treating an older version as non-matching
would break the guaranteed retry horizon during a rolling deployment: a request
accepted by an old node and retried against a new one would return
`IDEMPOTENCY_KEY_REUSED` for an identical request.

Prior fingerprint implementations must therefore be retained and executable for at
least the maximum configured `idempotencyRetention` across all policies. An
implementation may only be deleted once no ledger entry can still reference it.

Storing the version only solves the old-to-new direction. It does not help when a
**new** node writes a version-N+1 entry and an **old** node — which has no N+1
implementation — then serves the retry. That node cannot compute the stored
version at all, so the comparison fails and an identical request is rejected. A
fingerprint version change is therefore an expand/contract rollout:

1. Deploy nodes that can **read** both N and N+1 but still **write** N.
2. Drain every node that understands only N.
3. Switch new entries to write N+1.
4. Retain the N implementation until no retained ledger row references it.

The ordering is what matters: read capability must be everywhere before any node
writes the new version. Skipping step 1 or reordering step 3 before step 2 leaves
a window where a retry lands on a node that cannot evaluate the entry it is
being asked about.

Retention is policy-specific, not one global TTL:

- For `UNIQUE` aggregates, retention may be bounded by the supported client retry
  window. The permanent entity identity reservation remains the semantic
  duplicate defense after an idempotency record expires.
- For `ALLOW_MULTIPLE` aggregates, there is no identity reservation, so this
  ledger is the *only* retry-deduplication defense. Its retention window is a
  correctness boundary: a delayed retry arriving after expiry creates a second
  entity. Retention for these aggregates must be at least the maximum client and
  gateway retry horizon.

## Atomic Create Algorithm

The create path should be implemented inside the existing graph-aware command
append transaction, not as a query followed by an unrelated event insert.

```text
BEGIN
  validate the registered creation policy and event schema
  derive trusted scope
  if multiplicity = UNIQUE:
      derive canonical semantic identity
  compute the lock key set:
      aggregate lock
      idempotency lock (always, when an idempotency key is supplied)
      semantic-identity lock (only when multiplicity = UNIQUE)
  acquire the deduplicated, numerically sorted lock set
  resolve the idempotency ledger:
      same key and same request fingerprint -> return the original result
      same key and different fingerprint    -> IDEMPOTENCY_KEY_REUSED
  verify that the aggregate stream does not exist
  if multiplicity = UNIQUE:
      insert the entity_aggregate_t owner row (entity_status = ACTIVE)
      insert the entity_identity_t reservation (binding_status = CURRENT)
      during dual-write, insert one CURRENT binding per participating version
  reserve graph revision and user nonce as applicable
  insert event_store_t and outbox_message_t rows
  complete the idempotency record
COMMIT
```

The semantic-identity steps are conditional. An `ALLOW_MULTIPLE` create derives no
identity and inserts no reservation, but still takes the aggregate and idempotency
locks and still enforces stream birth.

The idempotency lock is what makes retry deduplication work for `ALLOW_MULTIPLE`.
Those aggregates generate a fresh UUID per request, so two concurrent retries
carrying the same idempotency key take *different* aggregate locks and would
otherwise both pass the ledger check. The `command_idempotency_t` primary key
still prevents two entities from being created — the loser fails on the unique
constraint and rolls back — but the client receives a constraint error at exactly
the moment idempotency was supposed to shield it. Locking on the idempotency key
first makes the loser wait, observe the completed row, and return the original
success result instead.

### Advisory Lock Keys

PostgreSQL advisory locks take a `bigint`, so the lock key is derived, not the
logical identity string. There are three lock domains, each with a fixed prefix.
The prefixes remove *serialization* ambiguity — they guarantee that a field value
in one domain cannot serialize to the same string as a different field in another.
They do not and cannot prevent two distinct strings from hashing to the same
`BIGINT`; that is handled by cross-domain deduplication below.

```text
aggregate:   "eiu:v1:agg\x1F"  || aggregate_id
identity:    "eiu:v1:sid\x1F"  || scope_type || "\x1F" || scope_id || "\x1F"
                                || aggregate_type || "\x1F"
                                || identity_schema_version || "\x1F"
                                || lower(hex(identity_hash))
idempotency: "eiu:v1:idem\x1F" || scope_type || "\x1F" || scope_id || "\x1F"
                                || principal_id || "\x1F" || command_type || "\x1F"
                                || idempotency_key
```

The encoding rules are exact, because two implementations that serialize
differently do not share a lock:

- The aggregate lock follows the current event-store stream key and
  `UNIQUE (aggregate_id, aggregate_version)` constraint, so it deliberately
  excludes `aggregate_type`. Two candidate births with the same aggregate ID
  must serialize on one lock even if their declared types differ. Changing the
  event-store stream key requires a coordinated lock-format migration.

- UTF-8, no normalization, no case folding — the canonical identity was already
  normalized before hashing.
- `\x1F` (ASCII unit separator) is the only field delimiter, and it may not appear
  in any field value. Fields that could contain it are rejected at validation.
- No field is optional or omitted. `scope_id` is never null; a global scope uses
  its canonical sentinel.
- `eiu:v1:` is the version prefix. Changing any encoding rule requires bumping it.

Because a bumped prefix produces different `BIGINT` keys, old and new nodes would
lock disjoint key spaces and provide no mutual exclusion at all — the most
dangerous moment being precisely a rolling deployment. A lock-format change is
therefore a three-step rollout, not a swap:

1. Deploy a version that computes **both** the old and the new lock keys, adds
   both to the same set, and deduplicates and numerically sorts them together with
   every other key. Correctness is preserved because any two nodes now share at
   least one key for the same logical lock.
2. Wait until all writers running the old-only format are drained.
3. Deploy a version that computes the new format only.

Skipping step 1 leaves a window in which two concurrent creates for the same
identity take different locks and both proceed to the unique constraint — which
still holds, but surfaces as a constraint error rather than an orderly conflict.

Then:

1. Compute each key with `hashtextextended(<serialized lock key>, 0)`.
2. Deduplicate the resulting signed `BIGINT` values **across all three domains
   together**, not per domain.
3. Sort the deduplicated values numerically.
4. Call `pg_advisory_xact_lock` on each, in that order, within the lock-order
   phase below.

Sorting must be on the numeric key, not on the logical identity string. Two
strings that sort one way but hash into the opposite order would otherwise let
concurrent transactions acquire locks in conflicting order and deadlock.
Deduplication must span domains for the same reason: an aggregate key and an
identity key can collide into one `BIGINT`, and a single sorted pass would then
attempt the same key twice.

`pg_advisory_xact_lock` is required rather than a session-scoped lock. Transaction
locks release at commit or rollback; session locks would leak across pooled
connections and outlive the command.

Key collisions may add contention but cannot weaken correctness, because the
database unique constraints remain the final arbiter.

The identity, aggregate, and idempotency locks join the existing documented lock
order in `GraphCommandPersistence`. All call paths must use the same order:

1. graph-root locks;
2. the single sorted set of aggregate, semantic-identity, and idempotency locks;
3. identity, idempotency, and graph-revision rows;
4. user nonce;
5. event offset, event store, outbox, and notification rows.

The database unique constraints are the final race arbiter even when an advisory
lock is omitted by a future bug. SQL unique-constraint failures must be translated
to the same typed conflict instead of a generic database error.

### Concurrent Example

Two category requests can generate UUID A and UUID B while carrying the same host,
entity type, parent, and category name.

- Both derive the same canonical semantic identity.
- One transaction obtains the identity lock and commits UUID A plus its event.
- The other waits, observes the committed reservation, and returns a conflict.
- No event for UUID B is appended, so the projection never has to repair the race.

## Result Contract

The command path returns a typed result rather than relying on projection or SQL
error text.

| Condition | Result |
|---|---|
| New aggregate and new semantic identity | create succeeds |
| Same idempotency key and same request hash | return the original success result |
| Same idempotency key and different request hash | `409 IDEMPOTENCY_KEY_REUSED` |
| Existing aggregate stream | `409 ENTITY_ALREADY_EXISTS` |
| Different UUID with an existing semantic identity | `409 ENTITY_ALREADY_EXISTS` |
| Identity held by a live entity's former name (`ALIAS` binding, owner `ACTIVE`) | `409 ENTITY_ALREADY_EXISTS` |
| Identity held by a deleted entity (owner `RETIRED`) and reuse is not allowed | `409 ENTITY_RETIRED` |
| Missing creation policy | fail closed; deployment/startup error |

A permitted response may include `existingAggregateId` so the UI can open the
existing entity. It must only do so after authorization in the same trusted scope.
Cross-tenant conflicts should return the generic not-found/conflict behavior and
must not disclose another tenant's identifier or fields.

## Retry And UI Behavior

`portal-view` should generate an idempotency key when a create form is opened and
reuse it for every retry of that submission. It generates a new key only after the
attempt completes or the form is intentionally reset.

The UI should also:

- disable the submit action while a create request is pending;
- optionally perform a debounced duplicate lookup for faster feedback;
- treat the lookup as advisory and still handle a command-side conflict;
- show "This entity already exists" instead of a generic aggregate-version error;
- show "This identity belongs to a retired entity; restore it or choose another
  identity." for `ENTITY_RETIRED`, because the remedy differs from a live
  conflict;
- link to the existing entity when the response is authorized to reveal its ID;
  and
- preserve the user's form values when a conflict is returned.

The idempotency key and submit-button guard handle network retries and double
clicks. The semantic identity reservation handles a new browser session, a new
idempotency key, API clients, and concurrent users.

## Delete, Restore, And Rename

A delete does not erase the entity's history or release its creation identity.
The default `NEVER` reuse policy keeps every identity row reserved. Delete sets
`entity_status` to `RETIRED` on the single `entity_aggregate_t` row and leaves all
bindings unchanged; restore sets it back to `ACTIVE`. Because lifecycle lives in
one place, both operations are correct however many aliases and schema versions
the aggregate has accumulated.

Reactivating a soft-deleted entity must use an explicit restore/reactivate command
and a `*RestoredEvent` or `*ReactivatedEvent` at the next aggregate version. It must
not append another `*CreatedEvent`.

If a domain genuinely requires identity reuse, it must opt into
`EXPLICIT_RELEASE`, define the retention and audit rules, and provide a dedicated
release operation. Delete alone is not an implicit release. The release event and
binding deletion follow the transaction contract in Operational Ownership And
Maintenance; direct deletion and a `RELEASED` binding status are not supported.
Like rename and reparent, release is a binding change and must fan out across every
normalizer version currently participating in dual-write. A partial-version
release fails closed and leaves the event store and every binding unchanged.

When a mutable field also participates in a uniqueness constraint, update handling
must atomically reserve the new identity before changing it. Under the default
never-reuse policy, the old identity remains as an `ALIAS` binding so a later
create cannot impersonate the renamed entity. The owner row is untouched — renaming
a live entity leaves an `ALIAS` binding while `entity_status` stays `ACTIVE`, so a
create colliding with the former name returns `ENTITY_ALREADY_EXISTS`, not
`ENTITY_RETIRED`.

During a normalizer migration the rename must demote and re-bind at **every schema
version currently participating in dual-write**, in the same version-checked
transaction. Renaming at version N alone would leave N+1 bound to the old name.

Domains that need old-name reuse require an explicit policy and migration design.

### Parent Lifecycle And Child Identities

Parent-scoped identities follow the same never-release default as every other
identity:

- **Deleting a parent does not cascade to child identity reservations and does not
  release them.** The children's rows stay as they are. A delete is a lifecycle
  mutation on the parent, not a licence to reuse names beneath it.
- **Restoring a parent preserves its children's reservations.** Because nothing was
  released, restore needs no identity repair and cannot collide with names created
  in the interim.
- **Reparenting explicitly transfers the child's current identity binding.** The
  child's identity includes its parent, so a reparent demotes the identity under
  the old parent to `ALIAS` and reserves the new one as `CURRENT` in the same
  transaction, gated by the child's expected version, and across every schema
  version participating in dual-write. The owner row is untouched — the child
  stays live throughout. If the destination parent already holds that name, the
  reparent fails with `ENTITY_ALREADY_EXISTS` and the original child is unchanged.

An aggregate may reclaim *its own* alias during a version-checked rename. Renaming
`A` to `B` and back to `A` flips the `A` row's binding from `ALIAS` to `CURRENT`
and demotes `B` to `ALIAS`, both in one transaction, gated by the aggregate's
expected version. This is safe because the reclaiming aggregate is the same one
that created the alias, so no impersonation is possible. Another aggregate may
never claim an alias: a reservation row belongs to exactly one `aggregate_id`, so
a different aggregate's create simply collides with the existing row and is
rejected.

## Projection Contract

Projection primary keys and unique indexes remain required as defense in depth.
They must agree with the creation-policy registry, and conformance tests must fail
when the registry identity and projection constraint diverge.

After enforcement:

- a normal `*CreatedEvent` is always version 1;
- exact redelivery of the same event is idempotent by event identity;
- a different create event for an existing active or retired identity is a
  permanent projection failure, not an upsert; and
- restore/reactivate events own the transition from inactive to active.

Projection code must not silently skip a conflicting create while leaving its
aggregate version behind. That behavior is what turns the original error into
`ERR11645` rather than surfacing the invalid event at its source.

## Existing Data Repair

The new guard prevents future corruption but does not repair streams that already
contain multiple birth events.

Before enforcement, run an inventory that finds:

- aggregate streams with more than one registered birth event;
- projection rows whose aggregate version is below the event-store maximum;
- multiple aggregate IDs that map to one semantic identity; and
- projection uniqueness violations or permanent create-event failures; and
- global-scoped entities whose creating principal and historical policy evidence
  do not prove exact global-create authority at the time of creation.

Older events may not contain a policy revision or enough authorization evidence
to prove the historical decision. Classify those records as
`UNKNOWN_SCOPE_PROVENANCE`; do not assume that a global row was legitimate merely
because it exists. A global identity created through the legacy substring-role
path must be reviewed or quarantined before backfill, otherwise Phase 5 would turn
historical cross-tenant name squatting into a permanent reservation.

Repair procedure:

1. Validate or operator-attest the trusted scope provenance; quarantine ambiguous
   or unauthorized global creations before producing reservations.
2. Select the first valid birth event and entity as canonical.
3. Classify later creates as exact retries, harmless conflicting creates, or
   conflicts with dependent side effects.
4. Backfill the canonical aggregate's `entity_aggregate_t` owner row, then its
   `entity_identity_t` bindings under the foreign key.
5. For a harmless legacy duplicate, apply an approved, versioned projection repair
   that keeps the original entity fields but advances the projection version past
   the invalid create.
6. Require operator review when the later event changed data, created children, or
   triggered external side effects.
7. Record the repair decision and evidence in the existing event-replay repair and
   audit workflow.

Do not delete or rewrite the later event directly, and do not copy the conflicting
create payload over the original entity merely to make versions equal.

## Why Common Alternatives Are Insufficient

### UI-only Duplicate Check

Two users can pass the check concurrently, and the projection may be stale. Keep it
for usability only.

### Query The Projection In Each Create Handler

This is the current pattern for some UUID entities. It cannot close the race
between the query and append and creates inconsistent rules across services.

### Projection Unique Constraint Only

The constraint is evaluated after the event is authoritative. Rejecting the
projection cannot undo the event or outbox publication.

### Create As Upsert

An upsert silently changes the original entity and makes create behave like update
without an expected version. It hides client errors and weakens audit meaning.

### UUID Uniqueness

UUID uniqueness proves that two storage identifiers differ. It says nothing about
whether the domain entities are duplicates.

### Deterministic UUID From The Name

This embeds normalization, scope, and rename policy into an identifier, complicates
migration, and still needs collision and lifecycle rules. A separate semantic
identity registry keeps the surrogate ID stable and the domain contract explicit.

### Hash The Entire Request

Descriptions, timestamps, ordering, and defaults may differ while the request still
describes the same entity. Conversely, identical payloads can be valid for an
`ALLOW_MULTIPLE` entity. Identity fields must be declared by the domain.

## Implementation Plan

### Phase 0: Freeze The Inventory And Move Coarse Authorization To Gateway

**Deployment gate.** Identity enforcement must not ship until every participating
portal command has fail-closed gateway authorization and global and host scope are
derived from trusted context. This is a prerequisite, not a task that can run in
parallel with Phase 2.

- Inventory every logical birth endpoint and classify it as tenant-only,
  global-only, or combined tenant/global.
- Configure its role permissions and `req-acc` rule in Light Portal, publish the
  generated policy through the config server, and verify the effective policy on
  each gateway instance before removing command-layer coarse role checks.
- Record the published policy revision or digest and require every gateway
  instance serving portal commands to acknowledge it. Block promotion or remove
  an unacknowledged instance from routing rather than assuming an older policy
  fails closed.
- Prefer separate tenant and global logical endpoints. For a combined endpoint,
  use one CEL expression or `accessRuleLogic: all` to bind role, requested scope,
  and authenticated host in the same authorization decision.
- Remove the `role.contains(PortalConstants.ADMIN_ROLE)` branch from
  `AbstractCommandHandler.handle()` after the gateway deployment gate passes; do
  not replace it with another command-layer list of `admin`, `org-admin`, and
  `host-admin`.
- Derive host scope only from authenticated context; stop preferring the
  request-body `hostId` in `effectiveHost()` and stop falling back to
  `map.get(HOST_ID)` in `handle()`.
- Preserve command-side target-host, parent, owner, owner-transfer, lifecycle,
  aggregate-version, and uniqueness validation. Replace any remaining raw-role
  scope exemption only with an unforgeable gateway authorization-scope decision
  or a scope-specific endpoint.
- Add tests proving `org-admin` and `host-admin` can call only their configured
  host-scoped endpoints and cannot select global scope. Prove `admin` can use the
  separately protected global endpoint or global branch.
- Add qualification tests proving that a missing role permission, missing
  `req-acc` rule, or unavailable effective policy denies the command before it
  reaches the service, and that an unacknowledged config-server revision blocks
  deployment or routing to the stale gateway instance.
- Enumerate all registered portal birth events and their command handlers.
- Record aggregate ID, scope, projection key, projection unique constraints,
  semantic identity, normalization, delete behavior, and multiplicity.
- Require `UNIQUE` or `ALLOW_MULTIPLE` for every entry.
- Add contract fixtures for role, rule, category, tag, platform, config, instance,
  and at least one intentional-multiplicity aggregate.
- Audit global entities and child-resource scopes separately.

### Phase 1: Stop Same-stream Duplicate Births

- Add explicit create command kind to the shared command abstraction.
- Set create expected/new versions to `0/1`; never use max-plus-one for create.
- Enforce stream absence transactionally in `GraphCommandPersistence`.
- Translate aggregate/version uniqueness conflicts to
  `409 ENTITY_ALREADY_EXISTS`.
- Migrate role and rule first and prove that the second create appends no event.
- Stop silently skipping a conflicting create in projections. Make it a loud,
  alerting failure now rather than in Phase 4: while append protection is rolling
  out group by group, this is the only detector for unprotected append paths such
  as importers, replay tooling, and direct SQL. Permanent-failure enforcement can
  then be enabled per aggregate group as protection lands.
- Migrate aggregate versions from `int` to `long` as a coordinated
  provider-interface change. PostgreSQL already stores `aggregate_version` as
  `BIGINT`, so the Java contract should match it throughout. This touches
  `PortalDbProvider`, `EventPersistence`, their implementations
  (`PortalDbProviderImpl`, `EventPersistenceImpl`), test doubles, the
  `ProductVersionConfig*Enricher` call sites, and the private helper in
  `SchedulePersistenceImpl`. Because db-provider exists so databases can be
  swapped, alternate implementations break on recompile and the change must be
  version-coordinated rather than treated as a local type cleanup.

This phase directly resolves the reported `ERR11645` path.

### Phase 2: Protect Generated UUID Entities

- Add the versioned creation-policy registry.
- Add `entity_identity_t` and semantic identity locks.
- Reserve identity and append event/outbox in one transaction.
- Migrate UUID-based entities in groups, starting with tables that already have
  natural unique constraints.
- Replace projection existence lookups as correctness checks; retain them only for
  optional UX or ID discovery during migration.

### Phase 3: Idempotent Client Retries

- Add `command_idempotency_t`.
- Define and version the request fingerprint over validated client intent plus
  trusted scope, excluding enrichment output. Prove a retry whose enrichment
  regenerates a UUID still matches.
- Add the principal-bound idempotency advisory lock to the sorted lock set so
  concurrent `ALLOW_MULTIPLE` retries replay instead of failing on the ledger
  constraint.
- Ship fingerprint read capability before write capability, following the
  expand/contract order, and gate the N+1 write switch on old readers being
  drained.
- Accept and propagate a standard create idempotency key.
- Update `portal-view` create forms to reuse one key per submission attempt.
- Return the original success for an exact retry and a conflict for key reuse with
  a different request hash.

### Phase 4: Projection And Lifecycle Alignment

- Replace create-as-reactivate behavior with explicit restore/reactivate events.
- Complete permanent-failure enforcement for the remaining aggregate groups.
  Detection and alerting already landed in Phase 1.
- Add registry-to-DDL conformance tests for semantic unique constraints.
- Define explicit identity transfer/release behavior for mutable unique fields.
- Resolve identity collisions through the owner row once delete/restore is
  implemented: an `ACTIVE` owner, including a former-name alias, returns
  `ENTITY_ALREADY_EXISTS`; a `RETIRED` owner returns `ENTITY_RETIRED`.

### Phase 5: Backfill And Enforce

- Run the legacy duplicate, version-gap, and historical scope-provenance inventory.
- Quarantine global entities whose creation lacks exact historical global-create
  authority or an approved operator attestation; never backfill them blindly.
- Repair or quarantine existing conflicts with audit evidence.
- Backfill owner rows and identity reservations with the versioned generator;
  optionally emit a reviewable generated SQL artifact for existing databases.
- Add both guard tables and the idempotency ledger to the generic snapshot export
  and conversion skip lists.
- Make event import invoke the shared identity transition component and add a
  preflight mode that reports every destination reservation conflict before any
  event is written.
- Require event history or a validated identity-reservation manifest for
  snapshot-only promotion of identity-protected aggregate groups.
- Operate first in report-only mode, then reject mode by aggregate group.
- Persist the verified per-group materialization completion record and make the
  deployment gate reject Category/Tag create traffic until its event coverage,
  registry/normalizer versions, expected counts, and digest match.
- Reject deployment when a new birth event lacks a reviewed creation policy.
- Follow the dual-write or drain protocol for any normalizer-version migration,
  and re-verify the backfill after the last old-version writer exits.

## Test Matrix

The shared implementation must cover at least:

| Scenario | Expected result |
|---|---|
| First create for natural aggregate ID | event version 1 and success |
| Sequential second create for same role/rule | conflict; event count unchanged |
| Concurrent creates for same aggregate ID | one success, one conflict |
| Two UUIDs with same category semantic key | one success, one conflict |
| Same name in two permitted host scopes | both succeed |
| Tenant A and Tenant B each define environment `dev` | both succeed with distinct host-scoped reservations |
| Global environment `dev` and Tenant A environment `dev` | both succeed; effective catalog composition remains a query concern |
| Second environment `dev` within Tenant A | conflict in Tenant A only |
| Global and tenant identity according to policy | scope-specific expected result |
| Same idempotency key and request hash | original success returned |
| Same idempotency key with changed request | idempotency conflict |
| New key for existing semantic identity | entity-exists conflict |
| Create after soft delete | retired conflict |
| Explicit restore after soft delete | next version succeeds |
| Sibling names under one parent scope | duplicate rejected within the parent |
| Same child name under two different parents | both succeed |
| Parent deleted while a child identity is reserved | child reservations retained; not released |
| Create child name under a deleted parent | conflict; reservation still held |
| Parent restored after delete | child reservations intact; no repair needed |
| Child reparented to a free destination | old identity retired, new one reserved, one transaction |
| Child reparented into a scope holding that name | conflict; original child unchanged |
| Aggregate reclaims its own alias | version-checked rename succeeds |
| Another aggregate claims an alias | conflict; alias unchanged |
| Create colliding with a live entity's former name | `ENTITY_ALREADY_EXISTS`, not `ENTITY_RETIRED` |
| Normalizer dual-write holds CURRENT at N and N+1 | both rows permitted by the partial index |
| Delete, then restore, with aliases at N and N+1 | one owner row flips; every binding unchanged and still reserved |
| Rename during normalizer dual-write | demoted and re-bound at N and N+1 in one transaction |
| Reparent during normalizer dual-write | transferred at N and N+1 in one transaction; owner row untouched |
| Binding rows referencing a missing owner row | rejected by the foreign key; unrepresentable |
| Conflict lookup for an aliased live entity | single owner read; `ENTITY_ALREADY_EXISTS` |
| Intentional `ALLOW_MULTIPLE` entity | two UUID streams succeed |
| Concurrent `ALLOW_MULTIPLE` retries, same idempotency key | one create; the other returns the original result, not a constraint error |
| Retry after enrichment regenerates a UUID | same fingerprint; original success returned |
| Normalizer upgrade before materialization completes | enforcement blocked for that aggregate group |
| Version-N idempotency retry after version N+1 is deployed | stored version used; identical request replays |
| N+1 write attempted while an N-only reader still serves traffic | rejected; writes stay at N until step 2 completes |
| Concurrent old-format and new-format lock writers, same idempotency key | shared key acquired; one create, one replay |
| Version-N writer creates after N+1 materialization | dual-write produces the N+1 row, or the writer is drained first |
| Projection lag during duplicate create | command-side conflict still occurs |
| Identity normalizer version migration | old aliases remain protected |
| Unauthorized cross-tenant duplicate probe | no existing ID disclosed |
| Failure after identity insert before event insert | whole transaction rolls back |
| New database bootstrap imports a UNIQUE birth event | event, owner, binding, and outbox commit together |
| Generated upgrade SQL reruns against identical rows | verifies exact matches without overwriting them |
| Generated upgrade SQL encounters a different owner or binding | fails closed; no partial backfill |
| Event-history promotion rewrites the target host scope | destination identity is recomputed under the target scope |
| Snapshot-only promotion omits identity history | rejected for identity-protected groups |
| Snapshot promotion includes a valid identity manifest | all current and alias bindings are restored and verified |
| Generic snapshot conversion encounters guard tables | tables are skipped; no synthetic guard-table CreatedEvents are emitted |
| Operator attempts direct identity-table CRUD | no UI/API path exists; audited command or repair workflow is required |
| Bootstrap input contains a semantic conflict | preflight reports it and writes no event or reservation |
| Historical global entity lacks exact authorization evidence | classified `UNKNOWN_SCOPE_PROVENANCE` and quarantined before backfill |
| Explicit release covers every dual-write schema version | audited release event and exact binding deletions commit together; owner remains |
| Explicit release omits one participating schema version | rejected before append; no binding is deleted |
| Rebuild encounters an identity release event | released bindings remain absent after deterministic reduction |
| Catalog precedence changes which scoped `dev` an Instance resolves | requires a new normalizer version; existing identity is not silently reinterpreted |
| Promotion of UNIQUE entities starts with an empty idempotency ledger | identity reservations still prevent semantic duplicates |
| Promotion of ALLOW_MULTIPLE entities with live retry keys | writes remain fenced until the retry horizon drains or live ledger entries transfer |
| Portal role permission and `req-acc` rule published through the config server | gateway admits only configured logical endpoints |
| Role permission exists but `req-acc` rule is absent | gateway denies before command dispatch |
| Gateway effective policy is unavailable | command fails closed; no event or reservation is written |
| Gateway has not acknowledged the published policy revision | deployment or routing to that instance remains blocked |
| `org-admin` or `host-admin` submits global scope on a combined endpoint | gateway denies; command handler is not invoked |
| Host-scoped request contains another tenant's `hostId` | gateway or command boundary denies; no reservation is written |
| Direct command invocation bypasses gateway authorization | rejected by ingress isolation or missing trusted authorization context |

PostgreSQL-backed concurrency tests are required. Mock-only tests cannot prove the
unique constraint, advisory-lock, and rollback behavior.

## Observability

Add bounded metrics without identity values:

- `entity_create_accepted_total{aggregateType}`
- `entity_create_conflict_total{aggregateType,reason}`
- `entity_create_idempotent_replay_total{aggregateType}`
- `entity_create_policy_missing_total{eventType}`
- `entity_identity_backfill_conflict_total{aggregateType}`
- `duplicate_create_projection_failure_total{aggregateType}`

Structured logs may include event type, aggregate type, event ID, correlation ID,
scope type, policy version, and a short identity-digest prefix. They must not log
raw canonical identities, request payloads, or credentials.

Alert on any duplicate-create projection failure after an aggregate group enters
enforce mode. Once command-side enforcement is active, that signal indicates an
unprotected append path, importer problem, or policy drift.

## Security And Abuse Considerations

- Derive scope from authenticated command context.
- Do not reveal an existing aggregate ID until authorization is confirmed.
- Bound identity field count and canonical size before hashing.
- Never use secret fields as semantic identities.
- Rate-limit advisory duplicate lookups so they cannot enumerate catalog names.
- Treat identity-registry or policy-registry unavailability as fail-closed for
  create commands.
- Require elevated, audited authorization for identity release and legacy repair.

## Acceptance Criteria

The design is implemented when:

1. A second role or rule create returns a typed conflict and appends no event.
2. No normal aggregate stream can contain two registered birth events.
3. Every birth event declares `UNIQUE` or `ALLOW_MULTIPLE` in a versioned registry.
4. Concurrent create tests prove one winner for both natural-ID and UUID-based
   semantic identities.
5. Identity reservation, event store, outbox, nonce, and idempotency changes are
   atomic.
6. A generated UUID cannot bypass a declared business unique key.
7. Delete does not silently release identity, and restore is not modeled as create.
8. Projection constraints and creation policies have executable conformance tests.
9. The UI uses stable per-attempt idempotency keys and handles authorized conflicts.
10. Existing multiple-create streams are inventoried and repaired or quarantined
    before full enforcement.
11. Metrics and logs expose conflict cause without leaking identity values.
12. Adding a new birth event without a creation policy fails the deployment gate.
13. Every participating logical command endpoint has a Portal-managed,
    config-server-published role permission and `req-acc` policy that fails closed.
14. Every gateway instance serving portal commands acknowledges the published
    policy revision or is excluded from routing.
15. Java command handlers do not use `admin`, `org-admin`, or `host-admin` token
    parsing as the coarse endpoint-invocation authorization boundary.
16. Host, parent, owner, lifecycle, version, and uniqueness invariants remain
    enforced at the database-backed command boundary.
17. Bootstrap, import, replay, and approved repair use the same versioned identity
    transition component as normal commands.
18. A new database populates guard rows through bootstrap event append; generated
    SQL is limited to versioned, verified upgrade backfills.
19. Event-history promotion reconstructs destination reservations, and
    snapshot-only promotion cannot silently lose aliases.
20. The guard and idempotency tables are excluded from generic snapshot conversion
    and cannot be maintained through direct UI CRUD.
21. The same normalized name may be reserved independently in global and different
    trusted tenant scopes, while a duplicate within one scope is rejected.
22. Historical global creations with missing or invalid authorization provenance
    are quarantined rather than converted into permanent reservations.
23. Bootstrap preflight reports all reservation and scope conflicts before the
    first mutation.
24. Explicit identity release has event-backed deletion semantics that can be
    reproduced during rebuild.
25. Promotion accounts for the non-reconstructible idempotency ledger and fences
    `ALLOW_MULTIPLE` writes across any unprotected retry horizon.
26. Explicit release covers every normalizer version participating in dual-write
    or fails before appending its event or deleting any binding.
27. Identities that reference scoped catalog values encode the resolved scope and
    normalized value, and a resolution-rule change uses normalizer migration.

## Settled Decisions

- The authoritative check belongs in the database-backed command append path.
- UUIDs remain surrogate storage IDs; semantic uniqueness is separate.
- Projection and UI checks are helpful but never authoritative.
- Creation-policy entries are per birth event type; owner and identity rows are
  per actual aggregate instance and are maintained by a shared synchronous
  identity transition component.
- New databases populate the guard tables by importing bootstrap events. A
  generated SQL file is an optional, versioned upgrade artifact, never a
  hand-maintained registry or runtime maintenance mechanism.
- Event history is the preferred promotion source. Snapshot-only promotion of an
  identity-protected group requires a validated reservation manifest so aliases
  and lifecycle cannot be lost.
- The guard tables have no direct CRUD UI and are not asynchronous projections.
- Semantic uniqueness is scoped. Global and tenant-local reference values, and
  values belonging to different tenants, may share a normalized name because
  their trusted scope tuples differ; only duplicates within one scope conflict.
- Explicit release removes the named active reservation rows at every normalizer
  version participating in dual-write and records one versioned audited event;
  incomplete version coverage fails closed and `RELEASED` is not a binding status.
- Scoped catalog references are canonicalized as resolved scope/value tuples, not
  bare display names. A change to resolution semantics is a normalizer-version
  migration.
- Idempotency ledger entries are request facts, not event-derived state. In-place
  identity rebuilds retain them, while cross-database promotion fences
  `ALLOW_MULTIPLE` writes until active retry protection is preserved or drained.
- Semantic identity and request idempotency are separate mechanisms.
- Create is not upsert, restore, or update.
- Identity remains reserved after delete by default.
- Every create event must explicitly declare uniqueness or intentional multiplicity.
- Coarse command authorization belongs to Light Gateway logical-endpoint policy.
  Light Portal owns role permissions and rules and publishes them through the
  config server; static `values.yml` is not the policy source.
- Java command handlers do not duplicate endpoint invocation policy by parsing
  `admin`, `org-admin`, or `host-admin`, but trusted host, target, owner,
  lifecycle, version, and uniqueness checks remain command-side invariants.
- Combined host/global commands use scope-specific endpoints where practical;
  otherwise one fail-closed CEL decision binds role, requested scope, and trusted
  host. `accessRuleLogic: any` must not separate those required conditions.
- Trusted scope derivation and effective gateway policy qualification are
  prerequisites for enforcement, not parallel workstreams.
- The reservation key is scope, aggregate type, schema version, and
  `identity_hash` together; equal digests within one such key are one identity.
- Idempotency keys are bound to the authenticated principal, not only the tenant.
- Identity binding (`CURRENT`/`ALIAS`) and entity lifecycle (`ACTIVE`/`RETIRED`)
  are separate concerns on separate tables. Lifecycle is stored once per
  aggregate; conflict responses read it from the owner row.
- One *current binding* per aggregate per identity schema version.
- Binding changes fan out across every schema version participating in
  dual-write; lifecycle changes never fan out at all.
- Every versioned artifact — fingerprint, lock encoding, normalizer — needs a
  mixed-version transition protocol, and it must work in **both** directions:
  old nodes reading new data as well as new nodes reading old. Rolling
  deployments run both versions at once, so a version bump is never a swap, and
  read capability always ships before write capability.
