# User Filter

As more portal users manage their own APIs, clients, instances, schedules, and
configuration records, giving every operator a broad `admin` role becomes too
coarse. A broad admin can see and modify records created by other admins on the
same host. This document proposes an incremental owner-scoped filtering model
for `portal-view`.

The first step is a UI-side filter based on the user recorded on each row, such
as `update_user`. This is not a complete security boundary. The same rule must
eventually be enforced in the query and command services with fine-grained
authorization from the rule engine. The UI implementation is still useful
because it improves day-to-day user experience and gives us a concrete policy
shape to move into the service layer.

## Problem

Portal admin pages were originally designed for a small set of trusted
operators. Many tables expose all host-scoped records once the user can access
the admin page.

That model creates problems as adoption grows:

- application owners need to manage their own APIs, clients, and instances
- broad admin roles expose unrelated records from other teams
- users can accidentally edit or delete records owned by another user or team
- creating one role per page, such as `api-admin` or `instance-admin`, still
  does not solve row ownership
- service-layer fine-grained authorization is not available everywhere yet

The immediate need is to let users use admin-like pages while limiting the rows
they see and act on.

## Current Experiment

`Schedule.tsx` is the first experimental page. The idea is:

- users can access the schedule admin surface
- normal users only see schedules where `updateUser` matches their user id
- global admins or schedule admins can still see all schedules
- the `updateUser` column can be hidden for normal users
- create/update/delete actions are available only on the visible set

One implementation detail matters: ownership filters must be added before the
request payload serializes the `filters` array.

```ts
const apiFilters = [];

if (ownedOnly && userId) {
  apiFilters.push({ id: "updateUser", value: userId });
}

const cmdData = {
  filters: JSON.stringify(apiFilters),
};
```

Adding the filter after `cmdData.filters` is built will not send it to the
backend.

## Design Goals

- Allow regular users to manage records they created or updated.
- Avoid giving every self-service user broad all-record admin visibility.
- Keep the admin table implementation familiar and incremental.
- Centralize the owner filter logic instead of duplicating it page by page.
- Make the UI rule match the future service-layer rule as closely as possible.
- Preserve host scoping and existing role-based page visibility.
- Avoid presenting UI-side filtering as a security boundary.

## Non-Goals

- Do not claim UI filtering is sufficient authorization.
- Do not replace service-layer rule-engine enforcement.
- Do not solve full team ownership in the first UI-only pass.
- Do not migrate every admin page in one large change.
- Do not overload `update_user` as the permanent ownership model if a better
  owner field exists or can be added.

## Ownership Model

There are several possible ownership signals. They should be treated in this
order of preference.

| Field | Meaning | Recommendation |
| --- | --- | --- |
| `owner_user_id` | explicit individual owner | best long-term user ownership field |
| `owner_position_id` | explicit position or org-unit owner | best long-term team/hierarchy ownership field |
| `create_user` | original creator | good fallback if available |
| `update_user` | last updater | useful interim fallback, but not true ownership |
| domain-specific owner, such as `operation_owner` | business owner | useful when the field is reliable and normalized |

`update_user` is acceptable for the first UI experiment because many tables
already have it. However, it has an important semantic problem: ownership moves
to whoever last updated the row. If Alice creates an API and Bob updates it,
Bob becomes the owner under an `update_user` rule.

The long-term model should add explicit owner fields where needed:

```text
owner_user_id
owner_position_id
```

`owner_group_id` is intentionally deferred. Groups are still useful for flat
team membership, but position ownership fits the portal authorization model
better when access should follow the organization hierarchy. `owner_org_id` is
also deferred because normal portal records are already scoped by `host_id`, and
`host_t` links back to `org_t` through the host domain. Add organization-level
ownership only if a future cross-host/global ownership use case requires it.

Do not add `created_by` and `updated_by` as authorization fields in Phase 4.
The existing `update_user` and `update_ts` columns remain the last-updater audit
trail. If creator audit becomes important, add `create_user` and `create_ts` as
audit fields later, not as substitutes for stable ownership.

Until explicit owner columns exist, each page should declare which field is used
for interim UI owner filtering.

## Role Model

Use one page per entity type, but separate page visibility from row scope.

| Role | Meaning | Page access | Row scope |
| --- | --- | --- | --- |
| `user` | baseline signed-in portal user | only approved self-service admin pages | owned records only |
| `admin` | global portal administrator, effectively super admin | all admin pages | all records |
| `<entity>-admin` | administrator for one entity type, such as `schedule-admin` | that entity's admin page | all records for that entity |
| `platform-admin` | deployment platform administrator if this role is kept | platform/deployment platform pages only | not a global all-record role |

Do not give every `user` account access to every admin page. Only pages that are
safe for self-service ownership should be exposed to `user`, and each of those
pages must apply the owner filter and action guards.

The `admin` role can be repurposed as the global all-record role once the
sidebar stops using it as a broad menu marker. Role checks must use exact role
tokens. A role such as `schedule-admin` must not match `admin` through substring
checks.

## Access Modes

The UI should support three access modes.

### Owner-Scoped Admin

This is the default self-service mode. The user can open admin pages, but rows
are filtered to records they own.

Example:

```text
roles: user
scope: owned
filter: updateUser = current user id
```

### All-Scope Admin

This is for operators who can see and manage every record on the current host.

Example roles:

```text
admin
schedule-admin
```

The default all-scope role is `admin`. Page-specific roles such as
`schedule-admin` can opt a user into all-record visibility for one area. Do not
use `platform-admin` as a global all-scope role because the portal already has a
Platform Admin page for deployment platform management.

### Read-Only or Support View

Some users may need to see records without modifying them. This can be added
later with separate flags:

```text
canReadAll = true
canWriteOwned = true
canWriteAll = false
```

## Proposed UI Architecture

Add a small ownership-scope helper used by admin pages.

Example shape:

```ts
type OwnershipScopeOptions = {
  roles?: string | null;
  userId?: string | null;
  ownerField: string;
  allScopeRoles?: string[];
};

type OwnershipScope = {
  ownedOnly: boolean;
  ownerFilter: { id: string; value: string } | null;
  canWriteAll: boolean;
};
```

Example usage:

```ts
import {
  applyOwnershipFilter,
  defaultAllScopeRoles,
  ownershipScope,
} from "../utils/ownershipScope";

const ownership = ownershipScope({
  roles,
  userId,
  ownerField: "updateUser",
  allScopeRoles: [...defaultAllScopeRoles, "schedule-admin"],
});

const apiFilters = applyOwnershipFilter(columnFiltersWithoutActive, ownership);
```

This helper should live near other portal navigation/task utilities or in a
small access utility module, for example:

```text
src/utils/ownershipScope.ts
```

or:

```text
src/tasks/accessScope.ts
```

The helper should not call the backend. It only computes the UI filter and UI
capabilities from the current user state.

## Sidebar Behavior

The sidebar should not use `admin` as a marker on every admin menu link. That
made the whole Administration group disappear for normal users and prevented
owner-scoped self-service pages from being reachable.

Recommended behavior:

- `admin` users see every Administration link.
- non-admin users see only Administration links explicitly marked with `user`
  or a matching entity role, such as `role: "user schedule-admin"`.
- only add `user` to a link after that page has owner-scoped filtering and
  action guards.
- remove `role: "admin"` from individual menu links.
- use exact role-token matching instead of string `includes`, so
  `schedule-admin` does not accidentally grant `admin`.

At the Phase 3 rollout point, the following Administration links are safe to
expose to `user` because the pages apply the shared owner-scope helper and
action guards:

- API Admin
- API Detail
- OAuth Auth Client and Client Token
- App Admin
- Instance Admin, Runtime Instance, and instance relationship pages
- Schedule Admin
- Workflow Definition

Configuration, platform admin, user/role admin, workflow process/task/audit
pages, and lower-volume metadata pages should remain admin-only until they have
the same owner-scope treatment or a separate support/read-only policy.

## Admin Page Behavior

For an owner-scoped user:

- add the owner filter before the query payload is serialized
- hide the owner column if it does not add useful information
- show a small scope label such as "My records"
- keep create actions available
- allow update/delete only for rows matching the ownership rule
- preserve normal table sorting, pagination, and global filter behavior

For an all-scope admin:

- do not add the owner filter
- show a scope label such as "All host records"
- show the owner/update columns
- allow existing admin actions

For a user without enough context:

- if `userId` is missing, do not run an owner-scoped query
- show a clear message that user context is required
- avoid falling back to all-record visibility

## Action-Level Guard

List filtering is not enough for a good UI. Row actions should also check the
same scope.

Example:

```ts
const canUpdateRow =
  ownership.canWriteAll ||
  row.original.updateUser === userId;
```

For rows the user cannot modify:

- hide destructive actions, or
- disable them with a tooltip explaining the scope

Even after service-layer authorization is implemented, the UI should keep these
guards so users understand why an action is unavailable.

## Phase 4 Ownership Columns

For high-value entity tables, add canonical owner columns directly on the
entity row:

```text
owner_user_id UUID NULL
owner_position_id VARCHAR(128) NULL
```

Recommended constraints where the table has `host_id`:

```text
FOREIGN KEY (host_id, owner_user_id)
  REFERENCES user_host_t(host_id, user_id)

FOREIGN KEY (host_id, owner_position_id)
  REFERENCES position_t(host_id, position_id)
```

Both owner columns should be nullable during migration. New records should get
`owner_user_id` from the authenticated user on the service side by default. Do
not trust a browser-submitted owner user id unless the caller has permission to
assign ownership.

`owner_position_id` should be optional on create. The UI can show a host
position dropdown populated from the user's allowed positions. If the user has
exactly one effective position and the page is configured for position
ownership, the UI can default to that position. If the user has multiple
positions, require an explicit choice when position ownership is desired.

For portal forms, the optional position owner field should be exposed as
`ownerPositionId` and backed by the existing position label dynaselect query.
The form action uses the `position/getPositionLabel` endpoint, which is backed
by the `queryPositionLabel` persistence method and returns the id/label pairs
needed by the select control.

Do not expose `ownerUserId` as a normal create/update form field. The command
path must derive `owner_user_id` from the authenticated user in the event
context. If an owner-transfer use case is needed later, implement it as a
separate command with explicit authorization and audit behavior.

Normal update forms may update `owner_position_id` when the page allows the
caller to choose or clear the owning position. `update_user` changes on every
update and remains audit metadata. `owner_user_id` should not change on normal
update; it changes only through an explicit owner-transfer action restricted to
the current owner, `admin`, or the relevant entity-admin role.

Existing rows should be migrated conservatively:

- if `update_user` can be resolved to a user in the host, it can be used as an
  initial `owner_user_id`
- leave `owner_position_id` null unless there is a reliable source for the
  owning position
- rows with no owner columns populated should be treated as unassigned legacy
  rows, visible only to all-scope admins until an owner is assigned

## Service-Layer Target

The UI filter is an interim step. The durable solution belongs in the query and
command services.

The service layer should eventually:

- derive user id, roles, host id, and scopes from JWT claims
- ignore client-supplied owner filters as an authorization source
- inject owner predicates into query handlers based on the authenticated user
- reject update/delete commands when the user does not own the row and lacks
  all-scope permission
- use rule-engine policies for exceptions and domain-specific ownership

Once service-side owner enforcement is implemented, the UI should no longer be
the source of authorization predicates. The service should inject the ownership
predicate from authenticated user context and rule-engine decisions.

The UI should still keep owner-aware behavior for usability:

- show "My records" or "Admin View" scope labels
- hide or show owner columns based on the user's scope
- disable update/delete actions that the current user cannot take
- optionally send a simple view hint such as `scope=owned` or `scope=all`

The service must treat any UI-supplied scope or owner filter as a hint only. It
must ignore, override, or reject filters that would expand the caller's
authorized scope.

For owner-scoped users, the service-side predicate should be an OR condition:

```text
owner_user_id = current_user_id
OR owner_position_id IN current_user_effective_positions
```

For all-scope admins, such as `admin` or the relevant entity-admin role, the
service should omit this owner predicate and return all rows within the normal
host scope.

The UI and backend should share the same policy concepts:

```text
host scope
entity type
owner field
owned-only permission
all-record permission
read vs write capability
```

Position hierarchy must be resolved by the service layer or rule engine. A JWT
claim such as `pos=ai-engineer` only grants exact-position access unless the
service expands it to effective positions from `position_t` and
`user_position_t`. If hierarchy is enabled, the effective position set should
include inherited positions according to the existing position inheritance
rules.

Rows with `owner_position_id IS NULL` are not position-owned. A user can still
see the row if `owner_user_id` matches their user id. Rows where both
`owner_user_id` and `owner_position_id` are null are unassigned legacy rows and
should not be visible to normal owner-scoped users by default.

## Rule Engine Direction

The rule engine can express policies such as:

```text
user can read API when api.owner_user_id == user.user_id
user can update API when api.owner_user_id == user.user_id
admin can read all APIs on host
admin can update all APIs on host
api-admin can read all APIs on host
api-admin can update all APIs on host
support can read all APIs but cannot update
```

For tables that do not yet have explicit ownership fields, the policy can
temporarily map ownership to `update_user`.

## Rollout Plan

### Phase 1: Fix Schedule Experiment

- Fix filter ordering so `updateUser` is included in the request.
- Use roles plus user id to decide owner-scoped vs all-scope mode.
- Add action-level guards for update/delete.
- Keep the current route behavior unchanged.

### Phase 2: Add Reusable UI Helper

- Create a shared ownership-scope helper.
- Add unit-level coverage if the repo has a practical test pattern.
- Document default all-scope roles.
- Keep owner field configurable per page.

### Phase 3: Apply To High-Value Admin Pages

Start with pages where users commonly manage their own records:

- API admin
- API detail/version admin
- OAuth clients
- client apps
- instances
- instance API links
- schedules
- workflow definitions

Then expand to lower-volume metadata pages.

Current implementation status:

- `src/utils/ownershipScope.ts` centralizes exact role matching, owner-scope
  calculation, owner filter injection, and owner-column hiding.
- Sidebar access now exposes only scoped links to `user` or matching
  entity-admin roles, while exact `admin` continues to see all Administration
  links.
- API pages use `admin` and `api-admin` for all-record scope, with `user`
  limited by `updateUser`.
- OAuth client pages use `admin` and `oauth-client-admin` for all-record scope,
  with `user` limited by `updateUser`.
- Client app pages use `admin` and `app-admin` for all-record scope, with
  `user` limited by `updateUser`.
- Instance pages use `admin` and `instance-admin` for all-record scope, with
  `user` limited by `updateUser`.
- Schedule pages use `admin` and `schedule-admin` for all-record scope, with
  `user` limited by `updateUser`.
- Workflow Definition uses `admin` and `workflow-admin` for all-record scope,
  with `user` limited by `updateUser`.
- Task/page search registries use exact role-token checks so `schedule-admin`
  or another entity-admin role does not accidentally match global `admin`,
  while exact `admin` still has global visibility.

Deferred from this phase:

- Workflow Process, Task, Worklist, Work, Audit, and Trace remain admin-only
  until their ownership rules are defined and implemented.
- Configuration and platform pages remain admin-only because their ownership
  model is not yet defined.
- User and role administration remain admin-only because exposing them to
  self-service users would require a separate delegated-administration model.

### Phase 4: Add Explicit Ownership Fields

Where `update_user` is too weak, add proper owner fields through the database
and services.

Candidate fields:

```text
owner_user_id
owner_position_id
```

Apply these first to the high-value tables that already have owner-scoped admin
pages. Keep the fields nullable during migration, default `owner_user_id` from
the authenticated user on create, and make owner transfer explicit.

Current implementation status:

- `portal-db` adds nullable `owner_user_id` and `owner_position_id` columns to
  the high-value portal tables used by the owner-scoped admin pages.
- The migration backfills `owner_user_id` from `update_user` only when
  `update_user` is already a UUID. Non-UUID audit values remain unassigned
  instead of blocking the migration.
- A database insert trigger defaults `owner_user_id` from `update_user` for new
  rows when the command path writes the authenticated user id into
  `update_user`.
- Query projections for the scoped UI pages now return `ownerUserId` and
  `ownerPositionId`, and UUID filtering recognizes `ownerUserId`.
- `portal-view` now uses `ownerUserId` for ownership checks on action controls.
  The UI no longer sends an owner filter for service-enforced pages because
  service-side scope must include both direct user ownership and position
  ownership.
- Owner-aware create/update forms expose optional `ownerPositionId` with a
  host-scoped position dynaselect backed by `queryPositionLabel`.
- Command schemas allow optional `ownerPositionId` for the owner-aware create
  and update commands. They do not accept `ownerUserId`; `owner_user_id` comes
  from the authenticated event user.
- `light-portal` persistence writes `owner_user_id` from the event user on
  create and writes `owner_position_id` from `ownerPositionId` on create/update.
- Schedule query is the first service-enforced owner-scope path. Non all-scope
  users are filtered by
  `owner_user_id = current_user_id OR owner_position_id IN effective positions`
  based on authenticated audit context.

Remaining rollout work:

- Add explicit owner-transfer commands instead of changing ownership through
  normal update forms.

### Phase 5: Enforce In Services

- Add query-side owner predicates.
- Add command-side ownership checks.
- Move policy decisions into rule-engine configuration.
- Keep the UI filters as usability hints, not authorization.

Current implementation status:

- Query-side owner predicates are implemented for Schedule, API, API Version,
  App, OAuth Client, Client Token, Instance, Instance API, Instance API Path
  Prefix, Instance App, Instance App API, Runtime Instance, and Workflow
  Definition.
- Query handlers derive scope from the authenticated audit attachment. Users
  with the global `admin` role or the entity-specific all-scope role bypass the
  owner predicate; other users are scoped by user id or effective positions.
- The UI keeps owner-aware action guards, but it does not send the owner filter
  as a request filter for service-enforced pages. That keeps position-owned rows
  visible when the service grants access by `owner_position_id`.
- The db-provider keeps backward-compatible query methods and adds owner-aware
  overloads so query services can roll forward independently.

Remaining service rollout work:

- Add command-side ownership checks before update/delete actions.
- Add explicit owner-transfer commands and audit events.
- Move the all-scope role and position hierarchy decisions from Java guards into
  rule-engine policy once the service-side rule context is ready.

## Future Improvement: Entity Access Grants

Do not introduce a generic ownership table in Phase 4. It adds query joins,
pagination complexity, and weaker referential integrity before we have a clear
sharing use case.

A generic table can be added later for secondary grants, sharing, and delegated
administration. It should supplement the canonical owner columns rather than
replace them.

Possible future shape:

```text
entity_access_t
  host_id
  entity_type
  entity_id
  principal_type   -- user, position, group, role
  principal_id
  access_level     -- owner, maintainer, viewer
```

Use this only when we need use cases such as:

- share one API with another position or group
- give support read-only access to a selected set of records
- delegate maintenance without transferring the canonical owner
- manage record-specific exceptions from an Access Admin page

## Risks And Mitigations

| Risk | Mitigation |
| --- | --- |
| UI filter is bypassed | Treat it as interim only; enforce in services next |
| `update_user` changes ownership unexpectedly | Prefer explicit owner fields; use `update_user` only as fallback |
| users lose access to records updated by operators | support owner transfer or explicit owner fields |
| inconsistent page behavior | centralize scope helper and rollout page by page |
| broad admins still need all records | define all-scope roles separately from self-service admin |
| query filters can be removed by browser tools | backend must inject authorization predicates from JWT claims |

## Recommendation

Use owner-scoped filtering as the first UI step, but centralize it immediately.
Do not copy the `Schedule.tsx` logic into every page by hand.

The recommended path is:

1. fix the schedule filter ordering
2. introduce a reusable ownership-scope helper
3. apply it to the most common self-service admin pages
4. add explicit owner fields where `update_user` is not good enough
5. enforce the same rules in query and command services through the rule engine

This gives users a safer admin experience now while creating a clear migration
path to real fine-grained authorization.
