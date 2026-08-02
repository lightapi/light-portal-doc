# Global And Tenant Entity Scope

## Status

Proposed design for discussion.

## Decision Summary

Use `host_id IS NULL` as the storage representation for a global row when one
table intentionally contains both global and host-scoped definitions. Use a
non-null `host_id` for a host-owned row. Do not add a second `common` flag to
represent the same scope decision.

Treat scope, ownership, visibility, and enablement as different concepts:

- `host_id IS NULL` means the platform owns one global definition.
- `host_id = ?` means one host owns the definition.
- a visibility or publication field says who may discover an owned definition;
  it does not change its ownership or identity scope.
- a host registration, installation, or binding says that a host may use a
  global definition; global visibility alone never grants runtime use.

For entities that are always global, omit `host_id` entirely. For entities that
are always tenant-bound, keep `host_id NOT NULL`. Nullable `host_id` is for the
specific case where the same definition type genuinely supports both scopes.

Apply these choices to the two motivating entities as follows:

- Make `llm_model_t` a global-only canonical model catalog and remove
  `host_id`. Keep `llm_model_registration_t` host- and environment-scoped and
  reference the global `model_id`.
- Keep executable `wf_definition_t` rows host-scoped. Add an immutable global
  workflow template/version catalog and install or fork a selected template
  into `wf_definition_t`. This preserves the existing workflow runtime foreign
  keys and prevents a global edit from changing tenant execution behavior.

## Context

Light Portal currently contains two apparent patterns for shared entities:

1. a populated `host_id` plus `common = 'Y'`, represented by rules;
2. nullable `host_id`, where null means global and non-null means host-specific,
   represented by reference tables, categories, and tags.

The implementations show that these are not equivalent encodings. The rule
pattern mixes the owner of a row with its cross-host visibility. The reference
pattern uses the row scope itself as the source of truth.

This decision also has to work with event aggregate identities, semantic
uniqueness, soft deletion, snapshot export, authorization, foreign keys, and
effective catalog queries. Choosing a convention based only on the shape of one
DDL table would leave those contracts ambiguous.

## Terminology

| Term | Meaning |
| --- | --- |
| Global definition | Platform-owned reusable definition with no tenant owner. |
| Host definition | Definition owned and mutable within one `host_id`. |
| Published definition | Owned definition made discoverable beyond its owner. Publication is visibility, not global ownership. |
| Registration | Host decision to enable a global reference entity, optionally for an environment. |
| Installation | Host-local, version-pinned operational copy of a global template. |
| Override | Host row that intentionally replaces selected behavior of a global definition in an effective read model. |
| Effective catalog | Deterministic composition of global rows, host rows, registrations, and environment bindings for one caller. |

## Current Implementation Findings

### `rule_t` Is A Hybrid Model

`portal-db/postgres/ddl.sql` currently defines all of the following:

- nullable `host_id`, documented as null for a global rule;
- `common CHAR(1)`, used by queries as a shared-visibility flag;
- `PRIMARY KEY (rule_id)`;
- partial global and host indexes that also include `rule_id`.

The primary key on `rule_id` already makes the partial identity indexes
redundant for that identifier. A global rule and a tenant rule cannot reuse the
same `rule_id`, even though the partial indexes imply that scope-specific reuse
was intended.

The list and label queries use conditions such as:

```sql
host_id = :host_id OR common = 'Y'
```

This means a row can remain owned by Host A while being returned to Host B. It
is shared by a visibility flag, not global by scope. Other paths use
`host_id IS NULL` for global rules or for related rule test cases. Snapshot
export also determines global scope with `host_id IS NULL`, not `common = 'Y'`.

Consequently, the following states are possible and do not have one consistent
meaning across the code:

| `host_id` | `common` | Possible interpretation |
| --- | --- | --- |
| null | `N` | Structurally global but hidden by common-based queries. |
| null | `Y` | Global and shared. |
| Host A | `N` | Host A private rule. |
| Host A | `Y` | Host A-owned rule published to every host. |

Event aggregate identity is derived as `hostId|ruleId` when `hostId` exists and
as `ruleId` otherwise. That identity follows nullable-host scope rather than the
`common` flag. The projection primary key, however, remains only `rule_id`.
These contracts can disagree.

The rule pattern therefore should not be copied to new entity families. If
tenant-owned rules must be publishable, that requirement should be modeled as
visibility or publication with explicit moderation and mutation authority.

### `ref_table_t` Uses Nullable Host Scope

`ref_table_t` uses:

```text
host_id IS NULL  -> global reference table
host_id = ?      -> host-specific reference table
```

It has a globally unique surrogate `table_id` and partial semantic unique
indexes:

```sql
UNIQUE (table_name)          WHERE host_id IS NULL
UNIQUE (host_id, table_name) WHERE host_id IS NOT NULL
```

This permits the same semantic name in global, Host A, and Host B scope while
rejecting duplicates within each scope. Child `ref_value_t` rows reference the
globally unique `table_id`, so they inherit scope from the parent without
repeating a nullable host column.

Host-aware list and label queries compose:

```sql
host_id = :host_id OR host_id IS NULL
```

Snapshot export uses the same representation for `host`, `global`, and `both`
selection. Event aggregate identity also distinguishes `hostId|tableId` from a
global `tableId`.

This is the more internally consistent existing model. It still has gaps that
must not be copied blindly:

- current by-ID reads use `table_id` without a host/scope visibility predicate;
- update projections can change `host_id`, effectively moving an entity between
  scopes instead of requiring a controlled publish or clone operation;
- a combined list returns both rows when a host and global row have the same
  semantic name, but it does not define shadowing or deduplication;
- global creation and mutation require an explicit platform-admin authorization
  policy, not merely a client-supplied flag;
- OR predicates should be backed by suitable indexes or implemented as
  `UNION ALL` when query plans require it.

These are handler and policy issues, not reasons to add a duplicate `common`
scope flag.

### `llm_model_t` Is Currently Host-scoped

The current model table has:

```sql
PRIMARY KEY (host_id, model_id)
UNIQUE (host_id, provider_type, physical_model_id)
```

`llm_model_registration_t` references it with:

```sql
FOREIGN KEY (host_id, model_id)
  REFERENCES llm_model_t(host_id, model_id)
```

The persistence resource descriptor, list query, fresh query, label query, and
command reference validation also treat models as host-scoped. Therefore the
current implementation does not yet support one platform catalog referenced by
registrations from many hosts.

### `wf_definition_t` Is An Operational Host Entity

`wf_definition_t` currently has `host_id NOT NULL`, a composite primary key,
and host-scoped semantic uniqueness. `process_info_t` and `skill_workflow_t`
reference `(host_id, wf_def_id)`. Runtime queries join workflow definitions on
the same host.

This is more than a catalog display constraint. It ensures that running
processes and skill mappings resolve a workflow owned by the same tenant. A
simple change from `host_id NOT NULL` to nullable would not let a composite
foreign key reference a global row: SQL null equality does not make
`(tenant_host, wf_def_id)` match `(NULL, wf_def_id)`.

Workflow definitions also contain executable behavior. Allowing tenants to run
one mutable global row directly would let a platform edit alter future tenant
executions without an explicit adoption decision.

## Options

### Option A: Host-owned Row With `common = Y/N`

The row always has an owner host. `common = 'Y'` makes it visible to other
hosts.

#### Advantages

- Preserves the original author or owning tenant.
- Allows tenant-authored content to be published without copying its body.
- Can support a marketplace submission model when publishing is moderated.
- Keeps a concrete owner for support, attribution, and update responsibility.

#### Disadvantages

- It does not represent a platform-global entity; it represents a tenant-owned
  public entity.
- Scope is ambiguous when code also treats null host as global.
- A tenant owner can affect every consumer unless publication separates the
  public version from the editable source.
- Tenant deletion, suspension, migration, or cloning creates unclear behavior
  for globally visible data.
- Host-based row-level security, foreign keys, exports, and joins need special
  exceptions for `common = 'Y'`.
- `common` does not say whether it means discoverable, selectable, executable,
  editable, or inherited.
- Every query must remember both ownership and common-visibility rules.
- It is easy for a by-ID lookup or relationship join to bypass the intended
  visibility rule.
- Changing `common` can silently change cross-tenant impact without changing
  the entity's aggregate scope.

#### Appropriate Use

Use this concept only when the domain explicitly supports tenant-authored
content publication. Model it with names such as `visibility_scope`,
`publication_status`, and `owner_host_id`, or with a separate publication row.
Do not call the published row global and do not reuse `common` as its
authorization policy.

### Option B: Nullable `host_id`

Null means a platform-global definition; a value means a host definition.

#### Advantages

- One authoritative column defines scope.
- Aligns naturally with partial unique indexes and scoped semantic identity.
- Aligns with current reference, category, tag, snapshot, and aggregate-ID
  conventions.
- Global rows are independent of any tenant lifecycle.
- Host and global creation can have distinct authorization policies.
- Scope is easy to expose as a derived API field.
- Child rows can inherit scope from a globally unique parent ID.
- Host-specific and global definitions can reuse a semantic name when the
  effective-catalog policy allows it.

#### Disadvantages

- Null must be treated deliberately in keys, joins, predicates, ORM mappings,
  and test fixtures.
- PostgreSQL uniqueness with null requires partial unique indexes or an
  explicit normalized scope key.
- A composite foreign key containing tenant `host_id` cannot directly refer to
  a global parent row.
- Combined reads can produce both host and global rows with the same semantic
  identity unless precedence is defined.
- A bare by-ID query can expose a row outside the caller's effective scope if
  globally unique IDs are treated as authorization.
- Moving a row between null and non-null scope is dangerous and should not be a
  normal update.

#### Appropriate Use

Use nullable `host_id` for definition metadata that is safe to read or
reference directly in both scopes and whose relationships use globally unique
surrogate IDs. It is especially suitable for taxonomy and reference data.

### Option C: Separate Global Definition And Host Adoption Tables

The definition is global. A registration, installation, or binding records the
host's decision to use it.

#### Advantages

- Separates shared knowledge from tenant authorization and lifecycle.
- Supports host- and environment-specific restrictions without duplicating the
  global definition.
- Provides a natural place for approval, status, pinned version, overrides,
  rollout, and audit fields.
- Avoids nullable-parent composite foreign-key problems.
- Makes global retirement different from deleting a tenant adoption.
- Works well for runtime-sensitive entities.

#### Disadvantages

- Adds a table and lifecycle operations.
- Queries must join definition and adoption state.
- Deletion and compatibility rules must account for references from many hosts.
- Template installation may require version pinning or copying when global
  changes must not propagate immediately.

#### Appropriate Use

Use this for global definitions whose availability or behavior must be approved
per host or environment. LLM registrations are this pattern. Workflow template
installation is a safer variation for executable workflow behavior.

## Comparison

| Concern | Host plus `common` | Nullable `host_id` | Definition plus adoption |
| --- | --- | --- | --- |
| Represents platform ownership | No | Yes | Yes |
| Represents tenant publication | Yes, but ambiguously | No; add visibility separately | Yes, with a publication layer |
| Single scope source of truth | No when null is also allowed | Yes | Yes |
| Tenant lifecycle independent from global row | No | Yes | Yes |
| Per-host enablement | Not inherently | Not inherently | Yes |
| Environment enablement | Not inherently | Not inherently | Yes |
| Runtime safety | Weak | Depends on entity | Strongest |
| Database uniqueness | Often contradictory | Clear with partial indexes | Clear per table |
| Existing snapshot alignment | Weak | Strong | Strong when both tables are exported |
| Best fit | Published tenant content | Simple dual-scope metadata | Runtime-governed shared definitions |

## Recommendation

### General Rule

Choose scope from domain ownership, not from UI visibility:

| Entity behavior | Storage recommendation |
| --- | --- |
| Always global | No `host_id` column. |
| Always host-owned | `host_id NOT NULL`. |
| Definition may independently be global or host-owned | Nullable `host_id`; null is global. |
| Global definition needs host approval or configuration | Global definition plus host registration/binding. |
| Global executable template must not change tenant behavior automatically | Immutable global versions plus host installation/copy. |
| Tenant-owned content may be publicly discovered | Keep owner host and add explicit publication/visibility state. |

Do not use `common` as a generic scope field. If the product needs publication,
replace it over time with a vocabulary that says what is being granted:

```text
owner_host_id
visibility_scope = PRIVATE | PORTAL | PUBLIC
publication_status = DRAFT | PENDING | PUBLISHED | WITHDRAWN
```

Published content should have platform moderation and an immutable published
revision or snapshot. Consumers should not execute a tenant's mutable draft.

### Scope Contract

For mixed global and host definition tables:

1. `host_id` is immutable after creation.
2. Global create/update/delete requires a global platform-admin endpoint policy.
3. Host scope comes from authenticated context, never an arbitrary request body.
4. APIs return a derived `scope` value of `GLOBAL` or `HOST` and provenance.
5. IDs are globally unique surrogate identifiers.
6. Semantic uniqueness is scope-aware through partial unique indexes.
7. By-ID reads enforce `host_id IS NULL OR host_id = :trusted_host`.
8. By-ID mutations require exact scope and mutation authority.
9. A host list composes global and its own rows only.
10. Global and host rows with the same semantic key use an entity-specific,
    documented precedence rule; they are never deduplicated accidentally.
11. A scope change is publish, clone, install, or withdraw—not an update of
    `host_id`.
12. Soft delete preserves scope and identity reservations.

### Effective Read Policy

Three read modes should be explicit:

```text
GLOBAL_ONLY  -> host_id IS NULL
HOST_ONLY    -> host_id = :trusted_host
EFFECTIVE    -> host_id = :trusted_host OR host_id IS NULL
```

When host override semantics exist, resolve them deterministically. For example:

```sql
SELECT *
FROM (
  SELECT item.*,
         ROW_NUMBER() OVER (
           PARTITION BY semantic_key
           ORDER BY CASE WHEN host_id = :host_id THEN 0 ELSE 1 END
         ) AS precedence
  FROM item
  WHERE active = TRUE
    AND (host_id = :host_id OR host_id IS NULL)
) effective
WHERE precedence = 1;
```

If the entity does not support override, return both rows with scope provenance
or reject the conflicting semantic identity. Do not silently invent override
behavior in a generic query helper.

## LLM Model Decision

### Target Model

`llm_model_t` should be the platform-owned canonical catalog:

```text
llm_model_t
  model_id                  global PK
  provider_type
  canonical_model_id
  model_family
  model_version
  lifecycle_status
  token limits
  modalities
  operations
  declared capabilities
  aggregate version and audit fields
```

It should not have `host_id` or `common`. Only platform catalog administrators
may mutate it. All authenticated tenants may browse active catalog entries,
subject to any product-level catalog visibility policy.

`llm_model_registration_t` remains the tenant adoption record:

```text
llm_model_registration_t
  host_id
  model_registration_id
  model_id                  FK -> llm_model_t(model_id)
  environment
  regions
  data classifications
  capability restrictions
  lifecycle status
```

The uniqueness rule remains one registration for a canonical model in a host
and environment unless a later requirement introduces named registration
profiles.

Global model metadata must not absorb provider-account-specific values. Azure
deployment names, Bedrock inference-profile or regional identifiers, private
OpenAI-compatible endpoints, local Ollama tags, account quota groups, and secret
references belong to Provider Deployment, Account, and Credential records. A
canonical upstream identifier may be stored in the catalog only when it is
stable across accounts.

### Why Not Nullable Host For Models

Nullable host is technically workable, but it is unnecessary if all model
definitions are curated globally. Allowing tenant model rows would recreate two
questions that Registration and Deployment already answer: which tenant may use
the model and what physical provider target it calls.

If a future requirement permits tenant-private custom model definitions, first
decide whether they are genuinely new catalog identities or merely private
Deployments of a generic provider-compatible model. If true tenant catalog
definitions are required, either add nullable host scope with explicit effective
catalog semantics or use a separate custom-model table. Do not add `common`.

### Required LLM Migration

1. Establish the canonical identity rule, including provider-aware identifiers.
2. Deduplicate existing host model rows into global catalog rows.
3. Create a stable old `(host_id, model_id)` to new `model_id` mapping.
4. Remap every Registration before changing its foreign key.
5. Replace the composite Registration foreign key with `model_id` only.
6. Remove `host_id` from the model projection and its uniqueness constraints.
7. Make model list, fresh, and label queries global rather than host-filtered.
8. Make Registration reference validation resolve a global active model.
9. Restrict model commands to platform catalog administrators while keeping
   Registration commands host-authorized.
10. Update CloudEvent aggregate identity, snapshots, taxonomy assignments,
    forms, Marketplace reads, and dynaselect endpoints.
11. Prevent hard removal while active registrations reference a model; use
    lifecycle deprecation and retirement.

## Workflow Definition Decision

### Target Model

Workflow definitions are executable and tenant-customizable. Use a template
plus installation model rather than making the current operational table
nullable:

```text
wf_template_t
  wf_template_id             global PK
  namespace
  name
  version
  immutable definition
  lifecycle/publication status
  taxonomy and audit fields
  UNIQUE(namespace, name, version)

wf_definition_t
  host_id                    existing tenant scope
  wf_def_id
  source_wf_template_id      nullable provenance FK
  source_template_version    nullable pinned version
  tenant-owned definition
  existing ownership, catalog, taxonomy, and audit fields
```

An Install action copies a selected immutable template version into a new
host-scoped `wf_definition_t` row. A Fork action does the same but explicitly
allows tenant customization. Tenant-authored workflows have null template
provenance.

This keeps existing `(host_id, wf_def_id)` foreign keys from `process_info_t`
and `skill_workflow_t`. It also ensures an update to a global template never
changes a tenant workflow or an in-flight process implicitly.

If storage duplication becomes material, the installation table may instead
pin an immutable template revision and runtime processes may reference that
installation. That is a larger schema migration and should not be introduced
until its operational value outweighs the simpler copy-on-install model.

### Workflow Lifecycle

1. A platform curator publishes an immutable global template version.
2. A host administrator browses the global Workflow Marketplace.
3. The administrator installs or forks a version into the host.
4. Host-specific validation, secrets, tools, Agents, Policies, and environment
   bindings are resolved before activation.
5. Process instances reference only the installed host definition.
6. A new global version creates an upgrade opportunity, not an automatic
   mutation.
7. Upgrade produces a reviewed new host definition version and leaves existing
   process history resolvable.

## Guidance For Other Entities

| Entity family | Recommended pattern |
| --- | --- |
| Categories and tags | Nullable `host_id`; effective read composition. |
| Reference tables and relation types | Nullable `host_id`; child values inherit parent scope. |
| Rules | Global rule templates plus host bindings, or host-owned rules plus explicit publication. Retire `common` as scope. |
| LLM models | Global-only definition plus host/environment Registration. |
| Provider Accounts, Deployments, Credentials | Host-scoped; never global. |
| LLM Aliases, Routes, Policies, Bindings | Host/environment-scoped unless a separate global template requirement is approved. |
| Workflow templates | Global immutable versions. |
| Executable workflow definitions | Host-scoped installation or fork. |
| Reusable schemas | Nullable scope for safe definitions, or template plus installation when tenant lifecycle differs. |
| Skills and tools | Global immutable templates plus host projection/binding when execution depends on tenant APIs or credentials. |

## Authorization Requirements

Global visibility must not imply global mutation or runtime permission.

- Light Gateway logical-endpoint policy authorizes global catalog mutations.
- Command handlers derive host scope from authenticated context.
- Global commands remove host ownership only after the global branch is
  authorized; a request flag alone is insufficient.
- Query handlers distinguish public catalog reads, authenticated effective
  reads, and administrative reads.
- A global by-ID read is allowed only according to that entity's visibility
  policy.
- Host rows are readable and mutable only within the trusted host unless a
  separately authorized platform operation applies.
- Registrations, installations, and bindings require host administration even
  when the referenced definition is global.
- Runtime queries consume only active host adoption and environment binding
  state, never the global catalog alone.

## Event And Projection Requirements

The event model must use the same scope truth as the projection:

- global aggregate IDs exclude host identity;
- host aggregate IDs include the trusted host or use a globally unique ID with
  a separately persisted trusted scope;
- `common` or visibility never changes aggregate identity;
- a publish/install/clone operation emits a different event from an update;
- projection replay cannot move an aggregate between global and host scope;
- snapshot `global`, `host`, and `both` selection follows definition scope and
  exports adoption rows in their host scope;
- semantic uniqueness reservations use `(scope_type, scope_id, identity)` even
  when the projection physically represents global scope as null.

## Verification Matrix

Every global-capable entity should have contract tests for:

| Scenario | Expected result |
| --- | --- |
| Global and Host A use the same semantic name | Allowed when entity policy supports overrides or parallel definitions. |
| Host A creates the same semantic name twice | Rejected. |
| Host B reads effective catalog | Global plus Host B; never Host A private rows. |
| Host B reads Host A row by guessed UUID | Not found or forbidden according to the API disclosure policy. |
| Tenant administrator requests global create | Rejected unless the global endpoint policy explicitly authorizes it. |
| Global row is updated through a host mutation path | Rejected. |
| Host row attempts to change `host_id` to null | Rejected; use publish/install workflow. |
| Global definition is soft-deleted while active adoptions exist | Rejected or moved through an explicit retirement policy. |
| Effective catalog contains a host override and global default | Deterministic documented precedence. |
| Snapshot exports `global` | Only global definitions and their global-owned children. |
| Snapshot exports `host` | Only that host's definitions and adoption rows. |
| Event replay occurs out of order | Scope remains unchanged and aggregate version remains monotonic. |

For LLM Models, additionally verify registrations from two hosts can reference
the same global `model_id` while their Accounts, Deployments, Credentials,
Policies, and gateway publications remain isolated.

For Workflows, verify that installing the same template into two hosts creates
independent host definitions and that publishing a newer template version does
not alter either installed definition or an existing process.

## Migration Order

1. Adopt this scope vocabulary and classify each candidate entity as
   global-only, host-only, mixed definition, registered, or installed template.
2. Add source-grounded tests for current behavior before schema migration.
3. Separate ownership, visibility, and enablement fields in APIs and forms.
4. Fix scoped by-ID reads and prohibit scope-changing updates in existing
   nullable-host entities.
5. Implement the LLM global catalog migration and Registration foreign key.
6. Add immutable workflow templates and Install/Fork operations while retaining
   the operational host table.
7. Migrate rules away from `common` scope ambiguity. Preserve tenant publication
   only if it is an explicit product requirement.
8. Align event identities, semantic uniqueness, snapshots, taxonomy, and
   promotion for every migrated entity.
9. Add effective catalog endpoints with explicit scope and provenance.
10. Update portal-view so users can distinguish Browse, Register, Install,
    Publish, Fork, and Edit actions.

### LLM Catalog Cutover

Treat the `llm_model_t` migration as a coordinated maintenance cutover. Pause
LLM model commands and projection consumers, back up the database, apply the
global-catalog patch, deploy the matching command/query/persistence services and
portal UI, and then resume processing. The patch deliberately aborts if host
copies disagree, if a model uses host-scoped taxonomy, or if registrations
would collide after deduplication; curate those records and rerun the patch.

Take a post-migration projection baseline before retiring the old deployment.
A from-zero replay that includes pre-cutover host-scoped model streams also
needs the one-time old-to-canonical model-id mapping produced during migration;
without that mapping, two historical streams for the same provider model can
attempt to recreate duplicate global rows.

## Consequences

The platform gains one consistent meaning for global ownership and avoids
copying the ambiguous rule model. LLM Models become a true platform catalog,
while tenant use remains controlled by Registration and Deployment data.
Workflow templates become reusable without weakening the tenant boundary or
allowing mutable platform content to alter execution unexpectedly.

The cost is that global sharing is not implemented by one generic flag. Some
entity families need a registration, binding, installation, or publication
table because their runtime and ownership semantics are different. That extra
structure is intentional: it makes cross-tenant impact explicit and auditable.

## Related Designs

- [Portal Catalog Scope](../catalog-scope.md)
- [Entity Creation Uniqueness](../entity-creation-uniqueness.md)
- [Multi-Tenant](../multi-tenant.md)
- [LLM Gateway Topology Per Host And Environment](./llm-gateway-topology.md)
