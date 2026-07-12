# Instance Clone

## Context

One portal database can serve several runtime environments. For example, the
`portal-bff` service can have separate instances for these environment tags:

| Deployment | `env_tag` | Example instance |
| --- | --- | --- |
| `portal-config-loc` | `loc` | `portal-bff-loc` |
| `portal-config-dev` | `dev` | `portal-bff-dev` |
| `light-portal-install` | `demo` | `portal-bff-demo` |

Creating the second and third instances manually is error-prone because an
instance is the root of a bounded configuration graph, not one row in
`instance_t`. Instance Admin should offer a **Clone Instance** action that
copies the current active state of this graph and lets the administrator change
the target identity and environment-specific configuration.

This is a same-host operation. Cross-host or cross-database copying remains an
event-promotion/import concern.

## Goals

- Clone an active instance and its selected active children with one command.
- Require a target instance name and environment tag while allowing other
  instance fields to be overridden.
- Generate ordinary create events so replay produces the same target graph.
- Remap owned aggregate identifiers while preserving references to shared host
  catalog entities.
- Bind preview and execution to the same source graph and normalized request.
- Store the complete event/outbox batch atomically and make retries idempotent.
- Show every source configuration override and let the user copy, replace, or
  omit it without exposing values unnecessarily.
- Optionally clone deployment definitions and selected files.
- Create a new current configuration snapshot as the last event in the clone
  transaction when requested.
- Report durable projection and snapshot status after command acceptance.

## Non-goals

- Copy raw historical events or preserve source aggregate versions.
- Copy an existing configuration snapshot, runtime registration, deployment
  execution, audit timestamp, or soft-deleted row.
- Copy OAuth client owners, OAuth clients, client secrets, client tokens, or
  authorization grants.
- Automatically infer which values are environment-specific.
- Perform a cross-host or cross-database promotion.
- Split one logical clone across independently committed event batches.

## Current State

`instance-command` already declares `cloneInstance`. Its handler currently
emits `InstanceClonedEvent` with a bare `targetInstanceId` aggregate subject.
Normal Instance aggregates use `hostId|instanceId`, so the placeholder event is
not compatible with the normal Instance stream.

`InstanceDeploymentPersistenceImpl.cloneInstance` currently discovers related
historical events and logs them but does not create a target. There are also
older direct-SQL clone helpers near the promotion implementation. The new
implementation must replace and remove these incomplete paths. It must not
replay source history or copy projection rows directly.

## Clone Boundary

### Included graph

Only active projection rows are clone candidates:

```text
instance_t
├── entity_tag_t                  entity_type = 'instance'
├── entity_category_t             entity_type = 'instance'
├── instance_property_t
├── instance_file_t               selected explicitly
├── instance_api_t
│   ├── instance_api_property_t
│   └── instance_api_path_prefix_t
├── instance_app_t
│   ├── instance_app_property_t
│   └── instance_app_api_t
│       └── instance_app_api_property_t
└── deployment_instance_t         selected explicitly
    └── deployment_instance_property_t
```

Instance tag and category associations are copied by default using the existing
tag/category IDs and the new target instance ID.

### Explicit exclusions

The following rows are not cloned:

- `config_snapshot_t` and every `snapshot_*` row;
- `runtime_instance_t`;
- `deployment_t` and deployment execution history;
- `auth_client_owner_t`, `auth_client_t`, `auth_client_token_t`, secrets, and
  grants, even when an OAuth owner references the source instance;
- event-store, outbox, notification, and dead-letter rows from the source;
- inactive children, deletion metadata, source aggregate versions, audit users,
  and audit timestamps;
- deployment job IDs, IP addresses, ports, and execution status.

After cloning, the UI offers **Create OAuth Client** for the target. OAuth
material must be created or associated through its normal audited workflow.

## Authorization and Transport

Planning and execution both require `portal.w`. The server applies host,
owner-user, and owner-position authorization; the row button is not an
authorization boundary.

- Administrators may clone any visible source, including a read-only source.
- Non-administrators may clone only a source they own and may not clone a
  read-only source.
- A non-administrator becomes the target owner and cannot override ownership.
- An administrator may select the target owner user or position.

Planning, value reveal, execution, and status lookup use POST bodies. Clone
data must never be placed in a `/portal/query?cmd=...` URL, browser history, or
proxy query string. Responses carrying configuration data use
`Cache-Control: no-store`.

## Frozen Version 1 Protocol

Phase 0 freezes the initial wire contract as follows:

| Operation | Kind | Service/action/version |
| --- | --- | --- |
| Plan | Query | `lightapi.net/instance/planInstanceClone/0.1.0` |
| Reveal one property value | Query | `lightapi.net/instance/revealInstanceCloneValue/0.1.0` |
| Execute | Command | `lightapi.net/instance/cloneInstance/0.1.0` |
| Status | Query | `lightapi.net/instance/getInstanceCloneStatus/0.1.0` |

All four operations use POST RPC envelopes and require `portal.w`. Public JSON
uses the camel-case field names shown in this document. CloudEvent extension
names must satisfy the lowercase CloudEvents wire-name rule:

| Meaning | CloudEvent extension |
| --- | --- |
| Clone correlation | `clonerequestid` |
| Root instance | `rootinstanceid` |
| Accepted graph revision | `instancegraphrevision` |
| Redact payload in diagnostics | `sensitivepayload` |

Every clone event has the first three extensions. Property and file events also
set `sensitivepayload=true`. Ordinary graph mutation events have
`rootinstanceid` and `instancegraphrevision` but no clone request ID.

The initial status vocabulary is `ACCEPTED`, `PROJECTED`, `SNAPSHOT_READY`, and
`FAILED_DLQ`. The public error codes frozen for version 1 are:

- `SOURCE_PROJECTION_LAGGING`;
- `SOURCE_VALUE_INVALID_FOR_CURRENT_SCHEMA`;
- `PLAN_DEPENDENCY_CHANGED`;
- `CLONE_LIMIT_EXCEEDED`;
- `IDEMPOTENCY_KEY_REUSED`;
- `CONCURRENCY_CONFLICT`;
- `TARGET_LOGICAL_IDENTITY_CONFLICT`.

### Canonical encoding and HMACs

The canonical format identifier and limit-policy version are both
`instance-clone-v1`. Normalization occurs before encoding: UUIDs are lowercase,
enumerations use their documented uppercase token, integers use minimal base-10
form, strings use Unicode NFC without implicit trimming, and null is distinct
from an empty string.

The encoder writes an ordered sequence of typed fields. Each field contains a
one-byte type tag, a four-byte unsigned big-endian byte length, and the value
bytes. Strings use UTF-8, booleans use `0` or `1`, and collections include their
count followed by their members. Maps are not encoded directly; each contract
defines a field order or converts the map to a sorted record list. Graph rows
sort by entity type and stable source identity. Property selectors sort by
scope, source parent identities, property ID, and expected aggregate version.

`sourceGraphDigest`, `catalogSchemaDigest`, `planHash`, and the ledger
`request_hash` use HMAC-SHA-256 with distinct domain strings. A value digest is
itself an HMAC over its stable selector and raw value before it enters a graph
record. The domain strings are:

| Artifact | HMAC domain string |
| --- | --- |
| Property/file value digest | `lightapi.instance-clone.value.v1` |
| Source graph digest | `lightapi.instance-clone.source-graph.v1` |
| Catalog schema digest | `lightapi.instance-clone.catalog-schema.v1` |
| Plan hash | `lightapi.instance-clone.plan.v1` |
| Ledger request hash | `lightapi.instance-clone.request.v1` |

The wire/storage representation is:

```text
v1.<keyId>.<base64url-without-padding>
```

`keyId` matches `[A-Za-z0-9_-]{1,32}`. The raw HMAC key and unkeyed value
digests are never stored or returned. Query and command processes must use the
same active key ID and key. Key rotation invalidates outstanding previews unless
the old key remains explicitly configured for verification.

## Instance Graph Revision

`instance_t.aggregate_version` is insufficient for clone consistency because
each child aggregate has its own version. Add a root graph revision:

```sql
CREATE TABLE instance_graph_revision_t (
    host_id             UUID NOT NULL,
    instance_id         UUID NOT NULL,
    accepted_revision   BIGINT NOT NULL DEFAULT 0,
    projected_revision  BIGINT NOT NULL DEFAULT 0,
    accepted_ts         TIMESTAMPTZ,
    projected_ts        TIMESTAMPTZ,
    PRIMARY KEY (host_id, instance_id),
    FOREIGN KEY (host_id) REFERENCES host_t(host_id) ON DELETE CASCADE,
    CHECK (accepted_revision >= 0 AND projected_revision >= 0),
    CHECK (projected_revision <= accepted_revision)
);

CREATE INDEX instance_graph_revision_lag_idx
  ON instance_graph_revision_t(host_id, instance_id)
  WHERE accepted_revision <> projected_revision;
```

The revision row is command-side coordination state and may exist before the
corresponding `InstanceCreatedEvent` projects, so it intentionally has no
foreign key to `instance_t`. Instance deletion retains its revision tombstone
for replay and idempotency; an explicit retention job may remove old tombstones.

During the staged rollout, an instance created after the Phase 1 backfill but
before graph-aware writers deploy can temporarily have no revision row. Planning
remains read-only and treats that missing row as the baseline
`accepted_revision=0, projected_revision=0`. Execution and ordinary graph
commands acquire the graph advisory lock first, then insert the missing baseline
row with `ON CONFLICT DO NOTHING` before locking and updating it. Before clone is
enabled, a reconciliation pass repeats the idempotent backfill and requires zero
remaining instances without revision rows.

Every command that creates, updates, deletes, locks, or unlocks an instance or
one of the included child entities must:

1. acquire the same transaction-scoped advisory lock derived from
   `(host_id, root_instance_id)`;
2. increment `accepted_revision` in the same transaction that appends its
   event/outbox batch;
3. attach `rootInstanceId` and `instanceGraphRevision` to each event's metadata.

After the corresponding projection transaction succeeds, the consumer advances
`projected_revision`. A clone can execute only when the source
`accepted_revision` equals `projected_revision`. If not, it returns
`SOURCE_PROJECTION_LAGGING`; the caller retries after the projection catches up.

The preview response contains the projected graph revision and an opaque
`sourceGraphDigest`. The digest is an HMAC over canonical, sorted active rows,
including entity type, identity, aggregate version, and a digest of each value.
It must not expose a reusable unsalted hash of a secret.

## API

### Plan

`planInstanceClone` is a non-mutating POST query. `cloneRequestId` is optional
on the first call. The server generates one when absent; subsequent preview
calls reuse it so proposed IDs remain stable while the user edits selections.

```json
{
  "host": "lightapi.net",
  "service": "instance",
  "action": "planInstanceClone",
  "version": "0.1.0",
  "data": {
    "hostId": "...",
    "cloneRequestId": "...",
    "sourceInstanceId": "...",
    "targetInstanceName": "portal-bff-demo",
    "targetEnvTag": "demo",
    "targetEnvironment": "demo",
    "targetServiceId": "com.networknt.portal.gateway-1.0.0",
    "targetProductVersionId": "...",
    "includeFiles": false,
    "fileSelections": [],
    "includeDeployments": false,
    "deploymentSelections": [],
    "createSnapshot": true,
    "propertySelections": [
      {
        "scopeType": "INSTANCE",
        "sourceParentIds": {
          "instanceId": "..."
        },
        "propertyId": "...",
        "expectedAggregateVersion": 2,
        "action": "REPLACE",
        "replacementValue": "https://local.localhost/#/app/dashboard"
      }
    ]
  }
}
```

`targetInstanceName` and `targetEnvTag` are required. `targetEnvironment`
defaults to `targetEnvTag`, and `targetServiceId` defaults to the source service
ID. `targetProductVersionId` defaults to the source product version. The
resolved snapshot lookup tuple `(host, serviceId, environment)` is shown in
preview. For the `loc`, `dev`, and `demo` BFF instances, environment and
environment tag should normally have the same value.

Optional instance overrides include description, zone, region, line of
business, resource name, business name, topic classification, and ownership
when the caller is an administrator.

### Property selector

Property choices are an array, not a map keyed by configuration/property name.
The stable selector is:

```text
scopeType + sourceParentIds + propertyId + expectedAggregateVersion
```

Supported scopes are `INSTANCE`, `INSTANCE_API`, `INSTANCE_APP`,
`INSTANCE_APP_API`, and `DEPLOYMENT_INSTANCE`. The server resolves source IDs
through the immutable target ID mapping. Actions are:

- `COPY`: copy the source value server-side;
- `REPLACE`: validate and use `replacementValue`;
- `OMIT`: do not create the target override, allowing lower-precedence
  configuration to apply.

The default is `COPY` for every included active override. A stale selector or a
selector outside the source graph fails planning or execution.

Both `COPY` and `REPLACE` are validated against the current property schema,
value type, and constraints during planning and again during execution.
`COPY` does not grandfather a source value merely because it was valid when it
was originally saved. If a copied source value violates the current schema,
planning returns `SOURCE_VALUE_INVALID_FOR_CURRENT_SCHEMA` for that selector
and blocks execution until the user chooses `REPLACE` with a valid value or
`OMIT`.

For `OMIT`, planning validates the resulting effective target configuration.
It fails if omission would leave a required property missing or would expose an
invalid lower-precedence value.

### Sensitive values

The property inventory always returns property metadata but does not return raw
values by default. It includes configuration name, property name, scope,
`valueType`, parent display identity, aggregate version, and `valueState`.

`COPY` never requires the raw value to leave the server. A user who needs to
inspect a value uses a separate audited POST reveal action with the same owner
and `portal.w` checks. Until reliable sensitivity metadata exists, every value
is masked initially. Reveal responses are not cached or logged.

Files are also metadata-only during preview. File content is copied server-side
only after explicit selection. A `Cert` selection requires an additional
confirmation; no certificate or file content appears in preview responses.

### Reveal

`revealInstanceCloneValue` reveals one property value, never file or
certificate content. It accepts the stable property selector plus the plan
correlation and source digest:

```json
{
  "host": "lightapi.net",
  "service": "instance",
  "action": "revealInstanceCloneValue",
  "version": "0.1.0",
  "data": {
    "hostId": "...",
    "cloneRequestId": "...",
    "sourceInstanceId": "...",
    "sourceGraphDigest": "v1.primary.<base64url>",
    "selector": {
      "scopeType": "INSTANCE",
      "sourceParentIds": { "instanceId": "..." },
      "propertyId": "...",
      "expectedAggregateVersion": 2
    }
  }
}
```

The server reauthorizes the actor and rejects a stale or out-of-graph selector.
The response contains only the selector, value type, and selected raw value,
sets `Cache-Control: no-store`, and is never logged. The audit record contains
the actor, host, source instance, selector, timestamp, and outcome without the
value.

### Plan response

The response contains:

- `cloneRequestId` and deterministic proposed target IDs;
- source instance version, graph revision, and opaque graph digest;
- `catalogSchemaDigest` over the current schemas and constraints referenced by
  the plan;
- `planHash`, an HMAC over the canonical request, graph digest, schema digest,
  target mapping, and limit-policy version;
- property, file, deployment, tag, and category inventories;
- event counts and serialized event-byte estimates by entity type;
- resolved snapshot lookup identity;
- validation errors and warnings.

Planning is read-only; it does not create a request-ledger row. The plan hash
binds the later execution to exactly the previewed graph and choices.

### Execute

`cloneInstance` is a POST command containing the complete normalized plan plus
the returned `sourceGraphDigest` and `planHash`:

```json
{
  "host": "lightapi.net",
  "service": "instance",
  "action": "cloneInstance",
  "version": "0.1.0",
  "data": {
    "hostId": "...",
    "cloneRequestId": "...",
    "planHash": "...",
    "sourceGraphDigest": "...",
    "catalogSchemaDigest": "...",
    "sourceInstanceId": "...",
    "targetInstanceId": "...",
    "targetInstanceName": "portal-bff-demo",
    "targetEnvTag": "demo",
    "targetEnvironment": "demo",
    "targetServiceId": "com.networknt.portal.gateway-1.0.0",
    "targetProductVersionId": "...",
    "includeFiles": false,
    "fileSelections": [],
    "includeDeployments": false,
    "deploymentSelections": [],
    "createSnapshot": true,
    "propertySelections": []
  }
}
```

The server canonicalizes the request, recomputes the graph digest and plan
hash, and rejects any mismatch. It also recomputes `catalogSchemaDigest`, which
covers the current schemas and value-type constraints of every referenced
configuration property. A schema change after preview returns
`PLAN_DEPENDENCY_CHANGED` and requires a new preview. Client-provided target or
child IDs that do not match the deterministic mapping are rejected.

The immediate response is `ACCEPTED`, not completed. It contains the clone
request ID, target instance ID, transaction ID, terminal event ID, event counts,
and status URL/action.

### Status

`getInstanceCloneStatus` accepts `hostId` and `cloneRequestId` in a POST query
and returns one of:

- `ACCEPTED`: the event/outbox batch committed but has not projected;
- `PROJECTED`: the clone projected successfully without a requested snapshot;
- `SNAPSHOT_READY`: the clone and requested current snapshot projected;
- `FAILED_DLQ`: the complete projection transaction rolled back and its events
  were moved to the dead-letter queue.

The response never returns copied values or file content.

## Durable Idempotency Ledger

Add a command-side ledger:

```sql
CREATE TABLE instance_clone_request_t (
    host_id              UUID NOT NULL,
    clone_request_id     UUID NOT NULL,
    request_hash         VARCHAR(128) NOT NULL,
    source_instance_id   UUID NOT NULL,
    source_graph_digest  VARCHAR(128) NOT NULL,
    catalog_schema_digest VARCHAR(128) NOT NULL,
    target_instance_id   UUID NOT NULL,
    target_instance_name VARCHAR(126) NOT NULL,
    target_service_id    VARCHAR(512) NOT NULL,
    target_env_tag       VARCHAR(16),
    target_product_version_id UUID NOT NULL,
    transaction_id       UUID NOT NULL,
    terminal_event_id    UUID NOT NULL,
    snapshot_id          UUID,
    clone_status         VARCHAR(32) NOT NULL DEFAULT 'ACCEPTED',
    event_count          INTEGER NOT NULL,
    payload_bytes        BIGINT NOT NULL,
    result_summary       JSONB NOT NULL DEFAULT '{}'::jsonb,
    error_code           VARCHAR(64),
    error_message        VARCHAR(2048),
    requested_by         UUID NOT NULL,
    created_ts           TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_ts           TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (host_id, clone_request_id),
    FOREIGN KEY (host_id) REFERENCES host_t(host_id) ON DELETE CASCADE,
    CHECK (clone_status IN (
      'ACCEPTED', 'PROJECTED', 'SNAPSHOT_READY', 'FAILED_DLQ'
    )),
    CHECK (event_count >= 0),
    CHECK (payload_bytes >= 0),
    CHECK (jsonb_typeof(result_summary) = 'object'),
    CHECK (clone_status <> 'SNAPSHOT_READY' OR snapshot_id IS NOT NULL)
);

CREATE INDEX instance_clone_request_target_id_idx
  ON instance_clone_request_t(host_id, target_instance_id);

CREATE INDEX instance_clone_request_target_identity_idx
  ON instance_clone_request_t(
    host_id, target_service_id, target_env_tag, target_product_version_id
  );

CREATE UNIQUE INDEX instance_clone_request_transaction_uk
  ON instance_clone_request_t(host_id, transaction_id);

CREATE INDEX instance_clone_request_status_idx
  ON instance_clone_request_t(host_id, clone_status, updated_ts);
```

`request_hash` is computed over the normalized execute request, using digests
rather than storing replacement values in `result_summary`. Repeating the same
`cloneRequestId` and request hash returns the existing status and result.
Reusing an ID with different input returns `IDEMPOTENCY_KEY_REUSED`.

`ACCEPTED` is the only persisted starting status and is therefore the schema
default, although application inserts should still set it explicitly for
clarity. `error_message` is a redacted diagnostic capped at 2048 characters by
the column type. When `createSnapshot=true`, the deterministic `snapshot_id` is
known and retained while the request is `ACCEPTED` and, if projection fails,
`FAILED_DLQ`; the constraint enforces the reverse invariant that
`SNAPSHOT_READY` can never have a null snapshot ID.

The ledger insert and event/outbox append occur in the same command
transaction. A browser timeout therefore has an unambiguous status lookup.

`target_instance_id` is deterministically derived from `cloneRequestId`, so a
unique constraint on `(host_id, target_instance_id)` would add no protection
beyond the primary key and is intentionally omitted. The actual instance
logical uniqueness rule is `(host_id, service_id, env_tag,
product_version_id)`. `instance_name` is not unique; a duplicate name produces
a preview warning rather than a conflict.

Clone is an administrative operation with low expected volume, so the first
release retains ledger rows indefinitely. An `ACCEPTED` or recoverable
`FAILED_DLQ` row must never be removed. If later volume requires archival,
terminal rows may be compacted only into a permanent tombstone containing
`host_id`, `clone_request_id`, `request_hash`, target ID, and final status.
Clone request IDs are never reusable, even after the target is hard-deleted.

## Identity Mapping

The fixed UUIDv5 namespace is
`a4594c48-03f3-54f1-83c2-106aa1e7ce67`, derived from the DNS namespace and
`lightapi.net/instance-clone/v1`. The UUID name is a concatenation of
length-prefixed UTF-8 components, where `lp(value)` is the decimal UTF-8 byte
length, `:`, and the value. Entity IDs use:

```text
lp("instance-clone-id-v1") + lp(cloneRequestId) +
lp(entityType) + lp(each stable source identity component)
```

Event IDs use `lp("instance-clone-event-v1")`, the clone request ID, and the
eight-digit zero-padded event sequence. Entity-type tokens are the uppercase
names in the identity table. For the golden fixture request
`00000000-0000-0000-0000-000000000001` and source instance
`00000000-0000-0000-0000-000000000002`, the target `INSTANCE` ID is
`e0196b37-d81d-5d66-878d-d23457949457`; event sequence 1 is
`578e7c91-0225-53de-8106-c68ca56dc411`.

The server applies this mapping to `cloneRequestId`, entity type, and source
identity:

| Entity | Target identity |
| --- | --- |
| Instance | UUIDv5 of request and source instance |
| Instance file | UUIDv5 of request and source file |
| Instance API | UUIDv5 of request and source instance API |
| Instance app | UUIDv5 of request and source instance app |
| Deployment instance | UUIDv5 of request and source deployment instance |
| New snapshot | UUIDv5 of request, `SNAPSHOT`, and target instance ID |
| Property override | Target parent identity plus existing `property_id` |
| API path prefix | Target instance API ID plus existing path prefix |
| App/API link | Target app ID plus target API ID |

Event IDs are also deterministic by clone request and event sequence. This
supports diagnosis and protects against accidental duplicate construction;
the ledger remains the authoritative idempotency mechanism.

References to `product_version_id`, `api_version_id`, `app_id`, `app_version`,
`property_id`, `pipeline_id`, `tag_id`, and `category_id` are reused because
they identify shared host catalog entities. All target aggregates begin at
version `1`.

## Ordered Event Batch

Generate ordinary events in foreign-key order:

1. `InstanceCreatedEvent`
2. `EntityTagCreatedEvent` for selected instance tags
3. `EntityCategoryCreatedEvent` for selected instance categories
4. `ConfigInstanceCreatedEvent` for included instance properties
5. `ConfigInstanceFileCreatedEvent` for selected files
6. `InstanceApiCreatedEvent` for each API
7. `InstanceApiPathPrefixCreatedEvent` for each path prefix
8. `ConfigInstanceApiCreatedEvent` for included API properties
9. `InstanceAppCreatedEvent` for each app
10. `ConfigInstanceAppCreatedEvent` for included app properties
11. `InstanceAppApiCreatedEvent` for each app/API association
12. `ConfigInstanceAppApiCreatedEvent` for included association properties
13. `DeploymentInstanceCreatedEvent` for selected deployment definitions
14. `ConfigDeploymentInstanceCreatedEvent` for included deployment properties
15. `ConfigSnapshotCreatedEvent` when `createSnapshot` is true

Every event carries `cloneRequestId`, `rootInstanceId`, and
`instanceGraphRevision` metadata. Replaying the batch reconstructs the target
graph.

The new path never emits `InstanceClonedEvent`. Clone audit and idempotency come
from the ledger plus correlation metadata; no clone audit event consumes or
bypasses the target Instance aggregate stream. The first release retains a
deprecated replay-compatible dispatcher because only the current local database
has been verified to contain zero historical events. Remove the dispatcher and
constant only after every target database and exported fixture has been scanned.

## Transactional Execution

`CloneInstance` cannot use the standard `AbstractCommandHandler` sequence,
which enriches input and later opens a separate event-store transaction. Add a
dedicated clone orchestration/provider operation with connection-aware nonce,
revision, ledger, and event-persistence APIs.

Execution uses this sequence:

1. Authorize the caller and canonicalize the request.
2. Start a `SERIALIZABLE` database transaction.
3. Acquire source and target graph advisory locks in stable UUID order, then
   acquire a logical-target advisory lock derived from `(host_id, service_id,
   env_tag, product_version_id)`.
4. Look up the idempotency-ledger row. Return the existing result for an
   identical request; reject a changed request.
5. Require source `accepted_revision = projected_revision`.
6. Read the complete selected active graph in the transaction and recompute
   its digest and plan hash.
7. Validate target uniqueness, catalog references, selections, limits, and
   every expected child aggregate version.
8. Allocate the next target graph revision and reserve all user nonces using
   the same connection.
9. Build the deterministic event array and choose one transaction ID.
10. Insert the ledger row, event-store rows, and outbox rows using that
    connection and transaction ID.
11. Attempt to commit. Return `ACCEPTED` only after commit succeeds. On SQLSTATE
    `40001`, roll back and retry the complete transaction with a bounded retry
    count. If retries are exhausted, return HTTP `409 Conflict` with
    `CONCURRENCY_CONFLICT`, `retryable: true`, and no accepted clone result.
    The rolled-back attempt must leave no ledger, event-store, outbox, revision,
    or nonce reservation behind. Other transient database-unavailability
    failures return HTTP `503 Service Unavailable`; they never return
    `ACCEPTED`.

All instance and child mutation commands must adopt the same graph lock and
revision protocol before clone is enabled. Without it, clone cannot promise a
stable graph.

All commands that create an instance or change its service ID, environment tag,
or product version should also use the same logical-target lock. Within clone,
that lock plus the command-side ledger prevents two concurrent clone requests
from reserving the same logical target while the first remains unprojected.

Do not generate child events from the `InstanceClonedEvent` projection handler
and do not use the old direct-copy SQL helpers. Both approaches bypass command
validation and can leave event history inconsistent with projections.

## Projection and Snapshot Completion

The existing outbox assigns one transaction ID to an inserted event array, and
the database consumer processes all events with that transaction ID in offset
order inside one projection transaction. The clone design relies on this
contract.

`ConfigSnapshotCreatedEvent`, when requested, is always last. It therefore sees
all earlier target rows and creates the new current snapshot in the same
projection transaction. There is no separate snapshot job in the first
release.

After the transaction projects successfully, a transaction-outcome hook:

- advances the target `projected_revision`;
- sets the clone ledger to `PROJECTED` or `SNAPSHOT_READY`;
- records only counts, IDs, and timing.

If any clone event fails, the consumer rolls back the complete transaction,
moves the complete batch to the DLQ, and sets the ledger to `FAILED_DLQ` using
the transaction ID. Replaying a repaired DLQ transaction can advance the same
ledger to success without appending another clone batch.

## Validation

Before append, validate:

- source exists, is active, is caught up, and is visible to the caller;
- graph revision, graph digest, catalog schema digest, plan hash, and all
  selected aggregate versions still match preview;
- target IDs match the deterministic mapping and are unused;
- `(host_id, service_id, env_tag, product_version_id)` is unique;
- referenced catalog, tag, category, property, API version, app, and pipeline
  rows exist and are active;
- file selections remain unique by target instance and configuration phase;
- target app/API links refer to children in the same target instance;
- both copied and replacement values pass the current schema and value-type
  validation, and omitted values leave a valid effective target configuration;
- deployment overrides satisfy deployment constraints;
- event count and serialized-byte limits are not exceeded.

### Logical target collisions

`instance_name` is a display field and is not unique in the current schema.
The enforced logical identity is `(host_id, service_id, env_tag,
product_version_id)`, including the separate null-environment-tag rule.

Under the logical-target lock, clone checks both `instance_t` and non-failed
clone-ledger rows for this tuple. This prevents concurrent clone-versus-clone
requests from both appending while one projection is still pending. A soft-
deleted instance continues to reserve the tuple under the current database
indexes; clone rejects it and directs the user to the normal reactivation flow.

Command-side checks against `instance_t` remain best-effort because it is an
asynchronous projection. A concurrent non-clone `createInstance` command that
was accepted but has not projected may not yet be visible. The database unique
constraint is therefore the final authority: if such a cross-command race
survives command validation, one projection transaction succeeds and the other
complete transaction becomes `FAILED_DLQ`. The status response reports
`TARGET_LOGICAL_IDENTITY_CONFLICT`; it must not leave a partial clone.

## Clone Policy

| Data | Default | Policy |
| --- | --- | --- |
| Instance properties | Copy | User may replace or omit each override |
| APIs, apps, links, and properties | Copy | Preserve topology with remapped parent IDs |
| Tags and categories | Copy | Reuse shared tag/category IDs |
| Files | Exclude | User selects each file; `Cert` needs confirmation |
| Deployment definitions | Exclude | User selects and reviews each definition |
| OAuth clients and credentials | Never | Create through the OAuth workflow afterward |
| Runtime instances | Never | Ephemeral registration state |
| Snapshots | Never copy | Optionally create a new current snapshot |
| `current` | `false` | Avoid changing the default instance implicitly |
| `readonly` | `false` | Target is customizable even from read-only source |
| Ownership | Current caller | Administrator may explicitly override |

### Deployment selections

Each included deployment definition is addressed by
`sourceDeploymentInstanceId`. The preview exposes and lets the user override:

- target deployment service ID;
- system environment and runtime environment;
- pipeline ID;
- owner position;
- each deployment property through the normal stable property selector.

The target receives a new deployment instance ID. `platform_job_id`, IP address,
port, and execution identifiers are cleared, and `deploy_status` is always
`NotDeployed`.

## Size and Resource Limits

Planning calculates both event count and serialized event bytes before values
are appended. Recommended initial configurable limits are:

```text
maxEvents = 2000
maxSerializedEventBytes = 16 MiB
maxSingleFileBytes = 4 MiB
```

These defaults must be benchmarked and may be lowered by an operator. The
estimate accounts for both event-store and outbox payloads. A plan exceeding a
limit returns `CLONE_LIMIT_EXCEEDED` with counts and the limiting category. The
user can omit files or deployments and preview again.

The first release does not chunk an oversized clone because independently
committed chunks violate the atomic-clone guarantee.

## Portal UI

Add a `ContentCopyIcon` row action to
`/app/instance/InstanceAdmin`. It is enabled according to the source ownership
and read-only rules, but the server always reauthorizes.

The Clone Instance form contains:

- read-only source identity and graph revision;
- target name, environment tag, environment, service ID, and instance fields;
- searchable property inventory grouped by scope;
- `COPY`, `REPLACE`, and `OMIT` actions for every property;
- explicit file selection with certificate warnings;
- explicit deployment selection and per-deployment overrides;
- Create Snapshot option;
- event-count and byte estimates;
- **Preview** and **Clone** actions.

Any form change invalidates the previous `planHash` and disables **Clone** until
preview succeeds again. The form never embeds clone input in a URL.

After `ACCEPTED`, the UI polls status by `cloneRequestId`. It navigates or
enables **Open Instance**, **Open Configuration**, and **Create OAuth Client**
only after `PROJECTED` or `SNAPSHOT_READY`. `FAILED_DLQ` displays the safe error
code, correlation ID, and recovery guidance without property or file values.

For the `loc`, `dev`, and `demo` BFF use case, administrators can locate and
replace properties such as:

- `statelessAuth.redirectUri`
- `statelessAuth.denyUri`
- `statelessAuth.cookieDomain`
- OAuth redirect URI settings
- CORS allowed origins
- virtual-host names
- portal reset/sign-in host

The generic selector UI remains product-neutral. Product-specific suggestions
may be added later as metadata, but clone correctness never depends on a
curated property list.

## Sensitive Logging and Audit

Every clone event is necessarily stored in the event store and outbox, but raw
values must not be copied into application logs. Before enabling clone:

- replace full CloudEvent trace logging in the common command handler with an
  ID/type/subject summary for sensitive events;
- replace database-consumer error logging of complete payloads with bounded,
  redacted diagnostics;
- mark clone property/file events as sensitive in event metadata;
- exclude property values, replacement values, file contents, certificates,
  tokens, and secrets from the ledger, notifications, metrics, and status API;
- audit value-reveal operations separately.

Structured clone logs contain only host, request ID, source and target IDs,
caller, graph revision, event counts, byte counts, duration, transaction ID,
status, and safe error code.

## Implementation Plan

1. Add `instance_graph_revision_t`, shared graph-lock/revision handling, and the
   logical-instance-identity lock to the relevant instance and child mutation
   command/projection paths.
2. Add `instance_clone_request_t`, transaction outcome updates, and status
   query support.
3. Add provider queries that return the complete active clone graph, current
   property schemas, and canonical graph/schema HMAC digests without logging
   values.
4. Add POST `planInstanceClone`, value-reveal, and status query contracts with
   server-side ownership authorization.
5. Replace `CloneInstance` with the dedicated `SERIALIZABLE` transactional
   orchestration path and connection-aware nonce/event append.
6. Add deterministic ID/event builders and the ordered ordinary create-event
   batch. Stop emitting `InstanceClonedEvent`; remove historical-event discovery
   and unused direct-SQL clone helpers. Retain only the temporary compatibility
   dispatcher until the fleet-wide history gate permits its removal.
7. Add transaction-aware projection completion/DLQ ledger updates and place
   snapshot creation last in the same transaction.
8. Redact common command and database-consumer payload logging.
9. Add the Instance Admin form, generic selector tables, previews, limits,
   status polling, and post-clone actions.

## Test Plan

### State and mapping

- Clone a graph containing every included child type and compare source and
  target after applying the deterministic mapping.
- Verify tags/categories copy, while OAuth owners, clients, secrets, tokens,
  runtime instances, old snapshots, and deployment executions do not.
- Verify inactive and soft-deleted rows are absent.
- Replay the emitted events into empty projections and obtain the same target.

### Consistency and idempotency

- Change each child type after preview and verify graph revision/digest rejects
  execution.
- Verify execution rejects while accepted and projected source revisions differ.
- Race a child mutation against clone and verify the shared lock serializes
  them or the serializable transaction retries/fails safely.
- Execute identical requests concurrently and verify one event transaction.
- Retry the same request ID and hash and return the original result.
- Reuse a request ID with changed input and receive
  `IDEMPOTENCY_KEY_REUSED`.
- Verify a serialization retry does not reserve duplicate nonces or events.
- Exhaust serialization retries and verify HTTP `409`,
  `CONCURRENCY_CONFLICT`, and no committed ledger/event/revision/nonce state.
- Verify a transient database outage returns HTTP `503`, never `ACCEPTED`.
- Race two clones with the same logical target tuple and verify the logical
  lock/ledger rejects one before event append.
- Race clone with a non-clone instance creation and verify at most one projects;
  any loser becomes `FAILED_DLQ` with `TARGET_LOGICAL_IDENTITY_CONFLICT` and no
  partial graph.

### Security and authorization

- Verify plan, reveal, execute, and status enforce host and ownership scope.
- Verify only administrators can clone read-only sources or override ownership.
- Verify raw properties/files never occur in URLs, clone logs, status, ledger,
  notifications, or DLQ diagnostics.
- Verify COPY works without revealing a value and that reveal is audited and
  returned with `no-store`.
- Verify ambiguous property names at different scopes are independently
  selectable.
- Tighten a property schema after the source value was saved and verify `COPY`
  returns `SOURCE_VALUE_INVALID_FOR_CURRENT_SCHEMA` until the user selects a
  valid `REPLACE` or `OMIT`.
- Change a referenced property schema after preview and verify execution returns
  `PLAN_DEPENDENCY_CHANGED` and requires another preview.

### Projection and recovery

- Force failure on every event group and verify the whole projection
  transaction rolls back and status becomes `FAILED_DLQ`.
- Replay the repaired transaction and verify status advances without new
  source events.
- Verify status remains `ACCEPTED` before projection completion.
- Verify a requested snapshot is last, current, and retrievable using target
  `serviceId` and environment tag before status becomes `SNAPSHOT_READY`.

### Policy and limits

- Verify files are excluded by default, selected files preserve phase and
  metadata, and certificates require confirmation.
- Verify deployments are excluded by default and selected definitions apply
  overrides, clear operational fields, and use `NotDeployed`.
- Verify replacements pass schema/value validation and affect only the target.
- Verify copied values are revalidated against the current schema and omitted
  values still produce a valid effective target configuration.
- Verify duplicate instance names produce a warning, while duplicate logical
  identity tuples are rejected or resolved by the projection/DLQ contract.
- Verify `current=false`, `readonly=false`, and target ownership defaults.
- Verify event-count, total-byte, and single-file limits at the boundary and
  return `CLONE_LIMIT_EXCEEDED` without writes.

## Design Decisions

- Clone is state-based and event-producing; it never replays history or copies
  projections directly.
- A root graph revision, opaque graph digest, and plan hash bind preview to
  execution.
- The plan also binds the current referenced property schemas; `COPY` and
  `REPLACE` are both revalidated at plan and execution time.
- A durable request ledger provides idempotency and asynchronous status.
- Property selectors use scope, parent identity, property ID, and expected
  version; names are display fields only.
- Values are copied server-side and masked by default.
- Files and deployments are explicit user selections and default to excluded.
- OAuth material and runtime/deployment execution state are never cloned.
- Snapshot creation is the last event in the same projection transaction.
- The new path never emits `InstanceClonedEvent`; its compatibility dispatcher
  remains for one release unless a fleet-wide history scan proves immediate
  removal safe.
- Administrators may clone read-only sources; targets are writable by default.
- Oversized clones fail planning rather than losing atomicity through chunks.
- `ACCEPTED` is returned only after a successful commit; exhausted serialization
  retries return a retryable conflict with no committed clone state.
- Logical target uniqueness follows `(host_id, service_id, env_tag,
  product_version_id)`, not instance name or deterministic target UUID.
