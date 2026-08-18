# Policy-Driven Cascade Delete

Portal projection tables use soft deletion for recoverable domain state and
hard deletion for non-restorable runtime or credential state. PostgreSQL
`ON DELETE CASCADE` alone cannot implement this model because a parent soft
delete is an `UPDATE ... SET active = FALSE`, not a physical `DELETE`.

This design keeps database-level cascading, but replaces column-shape inference
with an explicit relationship policy. The trigger remains generic: table names
and actions live in data, not in PL/pgSQL branches.

## Decision

Every relationship traversed from a soft-deleted parent has one declared
action:

| Action | Delete behavior | Restore behavior | Intended use |
| --- | --- | --- | --- |
| `SOFT_DELETE` | Set the child `active = FALSE` and record cascade deletion metadata | Restore only rows retired by that parent cascade | Recoverable domain and configuration state |
| `HARD_DELETE` | Physically delete matching child rows | None | Credentials, tokens, authorization codes, and other non-restorable runtime state |
| `IGNORE` | Leave the child unchanged | None | Relationships whose lifecycle is intentionally independent |

The action is selected by an explicit policy row. The trigger must not infer a
hard delete merely because a child is missing `active` or `delete_ts`. Missing
or incomplete metadata is a deployment error, not permission to destroy data.

## Why the Current Inference Is Unsafe

The current `cascade_relationships_v` selects a relationship when both tables
have `delete_ts`. The current `smart_cascade_soft_delete()` function then
unconditionally reads and writes all of these child columns:

- `active`;
- `delete_ts`;
- `delete_user`;
- `update_ts`;
- `update_user`.

That contract is inconsistent. For example, `auth_client_token_t` has
`delete_ts` but no `active`. Projecting a `ClientDeletedEvent` therefore tries
to run an invalid dynamic statement and fails with PostgreSQL `SQLSTATE 42703`.
The projection transaction rolls back and the event is captured in the DLQ.

Adding only `active` to credential tables is not sufficient. Every reader and
authorization path would also need to filter it, and restoration could revive
credentials that should remain revoked.

## Policy Registry

Add a schema-owned table named `cascade_relationship_policy_t`. It is static
database metadata delivered by canonical DDL and forward-only upgrade patches;
it is not an event-backed Portal entity and is not editable through Portal UI.

Recommended logical contract:

```sql
CREATE TABLE cascade_relationship_policy_t (
    parent_schema       VARCHAR(63) NOT NULL DEFAULT 'public',
    parent_table        VARCHAR(63) NOT NULL,
    child_schema        VARCHAR(63) NOT NULL DEFAULT 'public',
    child_table         VARCHAR(63) NOT NULL,
    constraint_name     VARCHAR(63) NOT NULL,
    delete_action       VARCHAR(16) NOT NULL,
    restore_action      VARCHAR(16) NOT NULL DEFAULT 'NONE',
    policy_description  VARCHAR(1024),
    update_user         VARCHAR(255) NOT NULL DEFAULT SESSION_USER,
    update_ts           TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (
        parent_schema,
        parent_table,
        child_schema,
        child_table,
        constraint_name
    ),
    CHECK (delete_action IN ('SOFT_DELETE', 'HARD_DELETE', 'IGNORE')),
    CHECK (restore_action IN ('RESTORE', 'NONE')),
    CHECK (
        (delete_action = 'SOFT_DELETE' AND restore_action = 'RESTORE')
        OR (delete_action IN ('HARD_DELETE', 'IGNORE') AND restore_action = 'NONE')
    )
);
```

The registry is release-owned and authoritative: installation stages the full
canonical inventory, upserts it, and deletes rows absent from that inventory in
the same transaction. There is deliberately no runtime `enabled` switch. To
suspend traversal, a release must classify the relationship as `IGNORE` with a
reviewed rationale; an ad hoc disabled row would make replay behavior depend on
mutable environment state.

The migration removes the earlier `enabled` column. Although the canonical
view is dropped and recreated in the same transaction, this is a breaking
metadata change for external SQL consumers that selected the column directly;
reporting queries and dashboards must remove that dependency before rollout.

The foreign-key constraint name is part of the key because the same parent and
child tables can have multiple relationships with different column mappings.
The resolved relationship view must join this registry to the live PostgreSQL
catalog and obtain the composite parent/child column arrays from the referenced
constraint. A stale policy whose constraint no longer exists must fail schema
validation.

## Resolved Relationship Contract

Replace the current inference-only view with a policy-resolved view, retaining
the useful catalog-derived foreign-key mapping. Each policy row exposes at
least:

- parent and child schema/table;
- constraint name and OID;
- ordered parent and child column arrays;
- `delete_action` and `restore_action`;
- booleans for every required soft-delete column;
- the foreign key's PostgreSQL delete action.

Validation rules:

1. The named foreign-key constraint must exist and match the configured parent
   and child tables.
2. `SOFT_DELETE` requires the parent and child to have `active`, `delete_ts`,
   `delete_user`, `update_ts`, and `update_user`.
3. `HARD_DELETE` requires an `ON DELETE CASCADE` foreign key. This makes the
   physical child lifecycle explicit in both the policy and relational schema.
   Every foreign key that references the hard-deleted child must also use
   `ON DELETE CASCADE`; otherwise a retained downstream row could abort the
   parent soft-delete after earlier child mutations have already run.
4. `IGNORE` performs no child mutation.
5. A partially implemented soft-delete contract is rejected by the schema
   gate.
6. Every public foreign key whose parent has the core `active` and `delete_ts`
   lifecycle markers must be classified, regardless of the child's columns.
   Column shape validates the selected action but never removes a relationship
   from discovery, so active-only and columnless children cannot disappear from
   the reviewed inventory.
7. Unclassified candidate relationships fail the gate rather than acquiring a
   default destructive action.
8. For a `SOFT_DELETE` child, `delete_user` must be wide enough for every
   possible per-FK ownership token: `14 + 33n` characters for `n` soft parent
   relationships. Unbounded text types satisfy this rule automatically.

Consequently, adding an FK whose parent has `active` and `delete_ts` can block a
deployment when the parent lacks the remaining audit columns or the FK has no
canonical classification. That failure is intentional. Operators must complete
the parent contract or add a reviewed policy; they must not bypass validation.
The transactional installer leaves the prior validated trigger set intact.

The policy table is the authority. Column shape validates an action; it does
not select the action.

## Generic Trigger Behavior

Create a generic `smart_cascade_delete()` function and recreate
`trg_cascade_soft_ops` to call it. The old
`smart_cascade_soft_delete()` function can be removed after no triggers depend
on it.

When a parent transitions from `active = TRUE` to `active = FALSE`, the
function processes its policies in deterministic order:

```text
SOFT_DELETE
  UPDATE child
     SET active = FALSE,
         delete_ts = cascade timestamp,
         delete_user = exact per-FK cascade token set,
         update_ts = cascade timestamp,
         update_user = database user
   WHERE foreign-key columns match OLD parent values
     AND (active = TRUE OR already cascade-owned)

HARD_DELETE
  DELETE FROM child
   WHERE foreign-key columns match OLD parent values

IGNORE
  no operation
```

All statements execute inside the projection transaction. If any action fails,
the parent and all previously processed children roll back together.

The delete path must be idempotent:

- an independently inactive soft child is unchanged;
- an already cascade-owned child records an additional parent FK token once;
- a missing hard child is a successful no-op;
- replaying the same parent event does not recreate or reactivate children.

### Restore

When a parent transitions from `active = FALSE` to `active = TRUE`, only
`SOFT_DELETE` relationships with `restore_action = 'RESTORE'` participate.
Only children carrying the exact token for the restored parent FK participate.
Restoration removes only that token; a child becomes active only when its token
set is empty. This keeps a child with two inactive parents inactive until both
parents have been restored, in either restoration order. Children retired
independently never acquire a cascade token and stay inactive.

`HARD_DELETE` children are never restored. New tokens or credentials require
new domain commands and events after the parent is active again.

This is intentionally asymmetric: a reversible parent state transition can
permanently revoke a hard-delete child. That behavior is limited to explicitly
reviewed credentials and runtime authorization state, where restoration would
be a security defect. It is never inferred from missing columns.

The implementation uses `PARENT_CASCADE:` followed by comma-separated MD5
tokens derived from the parent schema, parent table, and FK constraint. Restore
removes the exact relationship token; it does not use a broad table-name match
that could erase another active cascade owner.

Rows retired before this migration carry the historical
`PARENT_CASCADE_<parent_table>_<timestamp>` marker. Restore recognizes that
exact literal table prefix, while all new deletions use per-FK tokens. This
compatibility path is required until every legacy cascade-owned row has either
been restored or retired through the new policy.

## Initial Authentication Policies

The implementation inventory must verify exact constraint names before seeding
rows. The intended actions for the known authentication relationships are:

| Parent | Child | Action | Reason |
| --- | --- | --- | --- |
| `auth_client_t` | `auth_provider_client_t` | `SOFT_DELETE` | Recoverable client/provider configuration |
| `auth_client_t` | `auth_ref_token_t` | `HARD_DELETE` | The row contains a full bearer JWT and dereference must be revoked |
| `auth_client_t` | `auth_client_token_t` | `HARD_DELETE` | Revoke non-restorable client credentials |
| `auth_provider_client_t` | `auth_code_t` | `HARD_DELETE` | Authorization codes must not survive retirement |
| `auth_provider_client_t` | `auth_refresh_token_t` | `HARD_DELETE` | Refresh tokens must be revoked, not restored |
| `auth_provider_client_t` | `auth_session_t` | `HARD_DELETE` | Provider-client retirement revokes non-restorable authorization sessions |
| `auth_provider_t` | `auth_provider_key_t` | `IGNORE` | Preserve keys across reversible host-driven retirement; runtime lookup requires an active provider and host |
| `host_t` | `auth_code_t` | `HARD_DELETE` | Revoke tenant authorization codes even when `host_id` differs from `auth_host_id` |
| `host_t` | `auth_ref_token_t` | `HARD_DELETE` | Revoke persisted bearer JWTs on host retirement |
| `host_t` | `auth_refresh_token_t` | `HARD_DELETE` | Revoke tenant refresh tokens even when `host_id` differs from `auth_host_id` |
| `host_t` | `auth_session_t` | `HARD_DELETE` | Revoke tenant sessions even when `host_id` differs from `auth_host_id` |
| `user_t` | `auth_code_t` | `HARD_DELETE` | User deactivation is a revocation boundary; redemption does not recheck `user_t.active` |
| `user_t` | `auth_refresh_token_t` | `HARD_DELETE` | User deactivation must revoke issued refresh credentials |
| `user_t` | `auth_session_t` | `HARD_DELETE` | User deactivation must revoke active authorization sessions |

These rows belong in the migration, not in conditional branches inside the
trigger.

Fifty-nine `IGNORE` relationships are also deliberate. The self-references on
`customer_t.referral_id` and `employee_t.manager_id` describe hierarchy, not
lifecycle ownership. The `user_host_t` relationships preserve recoverable
customer and employee identity details while a host membership is inactive;
membership eligibility is governed by `user_host_t.active`. Hard-deleting those
identity rows would make a later membership reactivation incomplete. These
exceptions are canonical policy decisions, not temporary disabled cascades.

Twenty-five of the `IGNORE` rows cover active-only children that do not
implement the complete five-column soft-delete audit contract. Their lifecycle
remains command-owned or independently retained; the validator makes that
decision visible rather than silently dropping them from candidate discovery.

Twenty-nine more `IGNORE` rows cover children with neither `active` nor
`delete_ts`, including immutable snapshots, audit evidence, retained message
history, and status-driven operational records. The three columnless
`auth_session_t` relationships are deliberately different: they are
`HARD_DELETE` revocation boundaries through provider-client, tenant-host, and
user ownership. The `auth_code_t` and `auth_refresh_token_t` session foreign
keys also use `ON DELETE CASCADE`, so credentials issued under a different
client or user within the same session cannot block session revocation.

Provider signing keys are the remaining deliberate exception. A host-driven
provider retirement is reversible, so it preserves keys and restores the
provider without forcing key regeneration. Both Java and Rust authentication
lookups join the provider and host and require both to be active, preventing an
inactive key from being used. A direct `AuthProviderDeletedEvent` remains a
destructive domain operation and explicitly deletes the provider keys in the
projection handler.

The `host_t` references from `auth_code_t` and `auth_refresh_token_t` are hard
revocation boundaries. In the Master-OAuth-Host flow their `host_id` is the
tenant while `auth_host_id` owns the provider-client relationship, so the
transitive provider-client cascade cannot revoke them. The equivalent `user_t`
relationships are also `HARD_DELETE` because neither redemption path rechecks
`user_t.active`.

## Event-Sourcing Semantics

The parent domain event remains the only event required for database-level
cascading. Child mutations are derived projection state and do not create
additional events. This preserves these properties:

- the event store remains the canonical source of parent intent;
- parent and child projection changes are atomic;
- replay produces the same child state under the same policy version;
- a projection failure is retained in the DLQ without mutating the canonical
  event payload.

Because policy changes can alter replay results, policy rows are release-owned
schema metadata. Historical patch files are immutable; changes require a new
forward-only patch and regression qualification against both fresh and upgraded
schemas.

## Trigger Installation

Install the parent trigger only on tables with the complete parent contract:
`active`, `delete_ts`, `delete_user`, `update_ts`, and `update_user`. A trigger
is useful only when at least one non-`IGNORE` policy names that table as a parent.

Installation must:

1. validate all policy rows;
2. reject unclassified candidate relationships;
3. drop/recreate the trigger deterministically on eligible parents;
4. verify that no trigger still calls the retired function;
5. run safely more than once.

## Operational Recovery

For a projection event already in the DLQ:

1. Deploy the canonical DDL/patch and recreate the generic triggers.
2. Verify the policy row and live resolved relationship.
3. Verify that the failed parent row remains at its pre-event aggregate version.
4. Use **Replay original** for the unchanged canonical event.
5. Confirm the parent version/active state, child revocation or retirement, and
   failure resolution.

Do not edit the DLQ payload or manually advance the parent projection.

## Alternatives Rejected

### Hard-coded table branches in the trigger

This keeps policy hidden in procedural code, requires a function edit for every
new relationship, and makes destructive behavior difficult to inventory.

### Infer hard delete from missing columns

An incomplete migration is indistinguishable from intentional hard-delete
semantics. Treating absence as authorization to delete can destroy recoverable
domain data.

### Add `active` to every child

This is unsafe unless every read and authorization path also filters `active`.
It also allows restoration of credentials that should be permanently revoked.

### Application-level table lists

Application handlers can implement the behavior, but duplicated relationship
lists drift across processors. The database already owns the foreign-key graph
and executes projection transactions, so a validated database policy is the
smaller consistency boundary.

## Acceptance Criteria

- No trigger contains hard-coded domain table names.
- Every public foreign key from a parent with `active` and `delete_ts` has an
  explicit `SOFT_DELETE`, `HARD_DELETE`, or `IGNORE` policy.
- Soft actions cannot install unless both tables satisfy the complete column
  contract.
- Hard actions cannot install unless the referenced FK is `ON DELETE CASCADE`.
- Client deletion succeeds with zero or many client-token rows and physically
  removes those rows.
- Provider/client retirement revokes authorization codes and refresh tokens.
- Tenant-host retirement revokes authorization codes and refresh tokens when
  `host_id` differs from `auth_host_id`.
- Host-driven provider retirement preserves signing keys while active-provider
  and active-host lookup guards prevent their use until restoration.
- Restore reactivates only children retired by the matching soft cascade and
  waits for every parent cascade token to clear; it never recreates
  hard-deleted state.
- Fresh-install and historical-upgrade schemas resolve to identical policies,
  views, functions, and triggers.
- Original DLQ events replay successfully after deployment without payload
  mutation.
