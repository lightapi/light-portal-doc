# Claim Org Role Bootstrap

## Problem

The Claim Org action lets a signed-in user create an organization and its default host from the profile menu. The `createOrg` form captures the organization owner, default subdomain, host description, and host owner. The backend create-org flow then creates the organization, the default host, and user-host membership rows in one transaction.

That transaction is not sufficient for a usable tenant. A new host membership without role assignments can leave the owner unable to authorize after switching to the newly claimed host. The user profile/login query joins roles through `role_user_t` by the current `user_host_t.host_id`; if the current host has no active role rows for that user, role-dependent reads can return no user context.

The Claim Org bootstrap must create the minimum administration roles and assignments for the default host at the same time as the organization and host.

## Current Flow

The current UI entry point is the Claim Org menu in `portal-view/src/components/Header/ProfileMenu.tsx`, which routes to `/app/form/createOrg` through `portal-view/src/contexts/UserContext.tsx`.

The `createOrg` form is defined in `portal-view/src/data/Forms.json`. It posts the `host/createOrg` action and includes:

- `domain`
- `orgName`
- `orgDesc`
- `orgOwner`
- `subDomain`
- `hostDesc`
- `hostOwner`

The form help text already says that creating the default host assigns the host owner the `host-admin` role. Existing UI comments also assume that the organization owner can update and delete the organization because the user has the `org-admin` role.

On the projection side, `HostOrgPersistenceImpl` has separate handlers for:

- `createOrg`, which writes `org_t`
- `createHost`, which writes `host_t`
- `createUserHost`, which writes `user_host_t`

Access control data is projected by `AccessControlPersistenceImpl` into:

- `role_t`
- `role_user_t`
- `role_permission_t`

The `role_user_t` table has a foreign key to `(host_id, role_id)` in `role_t`, so role rows must exist before the user-role assignments are inserted.

## Goals

1. A claimed organization must be immediately usable by the selected organization owner and host owner.
2. The default host must receive deterministic administrative roles.
3. The role assignments must be created in the same command transaction as the organization, host, and user-host membership.
4. The event stream and projections must remain replayable and idempotent.
5. The implementation must use the canonical role IDs already used by the portal data: `org-admin` and `host-admin`.

## Non-Goals

This design does not introduce a new global organization-role table. Existing roles are host-scoped through `role_t.host_id`, so the organization administrator role for a claimed organization is represented as a role on the default host.

This design also does not merge organization and host administration into one broad role. Organization ownership and host ownership are separate responsibilities, and the system should grant both roles only when the same user is selected for both owner fields.

## Role Model

For the default host created during Claim Org:

| Role ID | Assigned To | Purpose |
| --- | --- | --- |
| `org-admin` | `orgOwner` | Manage organization metadata, billing, and owner transfer for the claimed domain. |
| `host-admin` | `hostOwner` | Manage the default host, membership, infrastructure, and host-level API deployment setup. |

If `orgOwner` and `hostOwner` are the same user, that user receives both roles.

The two roles should stay separate. `org-admin` should not implicitly include all host administration permissions. If an organization owner also needs to administer the default host, the command should grant that user both `org-admin` and `host-admin` explicitly.

The implementation should not use the current Java constant value `HOST_ADMIN_ROLE = "hostAdmin"` for this bootstrap. The canonical role ID in portal role data and UI task IDs is `host-admin`. The constant should be corrected or a new canonical constant should be introduced before it is used by bootstrap code.

## Command Transaction

The Claim Org command should validate and persist these facts atomically:

1. Create `org_t` for `domain`.
2. Create the default `host_t` for `(domain, subDomain)`.
3. Create `user_host_t` rows for the selected owners on the default host.
4. Switch the selected `hostOwner` to the new host by emitting `UserHostSwitchedEvent`.
5. Create or reactivate `role_t` rows for `org-admin` and `host-admin` on the default host.
6. Assign `org-admin` to `orgOwner` in `role_user_t`.
7. Assign `host-admin` to `hostOwner` in `role_user_t`.
8. Seed the required `role_permission_t` rows for these roles when endpoint-based authorization is enforced for the target admin APIs.

All rows should share the command's audit fields where possible: `update_user`, `update_ts`, and the event aggregate version metadata. Inserts should use the same idempotent create/reactivate pattern already used by role and role-user projections.

## Event Shape

The preferred event-sourcing shape is a single command producing multiple atomic events in one transaction:

1. `OrgCreatedEvent`
2. `HostCreatedEvent`
3. `UserHostCreatedEvent` for `orgOwner`, if needed
4. `UserHostCreatedEvent` for `hostOwner`, if different
5. `UserHostSwitchedEvent` for `hostOwner`
6. `RoleCreatedEvent` for `org-admin`
7. `RoleCreatedEvent` for `host-admin`
8. `RoleUserCreatedEvent` for `orgOwner` and `org-admin`
9. `RoleUserCreatedEvent` for `hostOwner` and `host-admin`
10. `RolePermissionCreatedEvent` events for the required endpoint permissions, if endpoint permission seeding is part of the command

The events must be written atomically by the command side. Each emitted event must reserve and carry its own user nonce because `event_store_t` enforces uniqueness on `(user_id, nonce)`. Projection replay can then use the existing individual projection handlers. This matches the existing atomic-event design direction while keeping the Claim Org user gesture transactional.

Claim Org emits `UserHostSwitchedEvent` for the host owner after creating the selected host owner's `user_host_t` membership. The master OAuth host tenant login boundary allows this safely: light-oauth validates the portal client under the configured OAuth host, then stores `auth_session_t`, `auth_code_t`, and `auth_refresh_token_t` rows with tenant `host_id` plus master `auth_host_id`.

The target login/session design is documented in [Master OAuth Host Tenant Login](./master-oauth-host-tenant-login.md). It keeps OAuth provider/client rows on the master host while storing tenant-host claims and sessions for the user's current host.

If the current command service still emits one composite `createOrg` event, the projection may temporarily perform the role bootstrap as part of that composite handler. That should be treated as a compatibility step, not the long-term event model.

## Permission Bootstrap

Creating `role_t` and `role_user_t` rows gives the user role identity on the new host. It does not automatically grant endpoint access if the request path is protected by `role_permission_t`.

The authoritative role-permission catalog should live with the command service as static, versioned metadata, for example `default-role-permissions.yml`. The Claim Org command reads that catalog and emits the required `RolePermissionCreatedEvent` events. This keeps the authorization bootstrap in the event stream, so projection replay produces the same state without depending on seed SQL.

The chosen source must be deterministic and replayable. It must also account for the fact that `role_permission_t` references `api_endpoint_t` through `(host_id, endpoint_id)`. Permission rows can only be inserted after the target host has the corresponding endpoint rows.

Event importer assets such as `events.json` can mirror the same catalog for environment bootstrap and repair, but they should not be the only source of truth for permissions created by an interactive Claim Org command.

Initial SQL seed files should not own the final role-permission state. Seed SQL is useful for bootstrapping a local database, but event-sourced permission state must be represented by events so replay and promotion remain deterministic.

If endpoint rows are not available during Claim Org, the command should still create the roles and role-user assignments, then schedule or trigger a follow-up permission bootstrap once the endpoint catalog exists. That follow-up must emit the same `RolePermissionCreatedEvent` facts that would have been emitted synchronously.

## UI Contract

The `createOrg` form should require both owners:

- `orgOwner`
- `hostOwner`

The current form requires `hostOwner` but not `orgOwner`. Since the backend persistence expects `orgOwner`, the form schema and command service request schema should mark both owner fields required and reject blank values through static schema validation.

The Claim Org command creates the selected host owner's membership for the new default host and switches that owner's current host in the same transaction. The portal must not bootstrap duplicate OAuth provider/client rows on every tenant host.

When automatic switching is enabled, the UI success path should tell the host owner to log out and log in again so the browser session receives the new tenant-host and role claims.

## Owner Transfer

Owner transfer role behavior is intentionally deferred. Claim Org bootstrap grants the initial `org-admin` and `host-admin` assignments, but later changes to `org_t.org_owner` or `host_t.host_owner` should not automatically remove or transfer those roles until the access policy is defined.

There are valid cases where more than one user should keep the same administrative role. For example, a new organization owner may need `org-admin` while the previous owner remains an administrator during handoff, support, or shared ownership. Automatically deleting the old owner's `RoleUser` assignment can remove access that was granted intentionally through another path.

When this policy is revisited, the implementation should decide separately:

1. Whether changing `orgOwner` should grant `org-admin` to the new owner.
2. Whether changing `hostOwner` should grant `host-admin` to the new owner.
3. Whether the old owner should retain the role, lose it, or require an explicit UI choice.
4. How to distinguish a bootstrap-created role assignment from an independently granted role assignment.

Until then, `UpdateOrg` and `UpdateHost` should remain metadata updates only. Any role changes after Claim Org should use the existing role-user administration flow.

## Backfill

Existing claimed organizations may already have a default host and `user_host_t` rows without the corresponding admin role bootstrap.

A one-time repair should:

1. Find active hosts whose organization and host owner users exist.
2. Ensure `org-admin` and `host-admin` exist in `role_t` for each host.
3. Ensure the organization owner has `org-admin`.
4. Ensure the host owner has `host-admin`.
5. Seed required role permissions if the endpoint catalog is present.

The repair must be idempotent and should only activate missing or soft-deleted bootstrap rows. It should not remove custom roles or overwrite existing role assignments.

## Validation

A focused validation set should cover:

- Claim Org creates `org_t`, `host_t`, and `user_host_t` rows.
- Claim Org creates `org-admin` and `host-admin` rows in `role_t` for the default host.
- Claim Org assigns `org-admin` to `orgOwner`.
- Claim Org assigns `host-admin` to `hostOwner`.
- The same user can receive both roles when `orgOwner == hostOwner`.
- After Claim Org switches the host owner to the claimed host, the current-host user query returns the claimed user with active roles on the next login.
- Replaying the events does not duplicate rows or downgrade active rows.
- Permission bootstrap either creates the expected `role_permission_t` rows or records a deterministic follow-up when endpoint rows are not present.
- Claim Org switches the selected host owner's current host during creation after the master OAuth host login boundary is implemented.
- The UI tells the host owner to log out and log in again after Claim Org switches the current host.

## Resolved Decisions

1. Claim Org creates the selected host owner's user-host membership and switches that owner to the new host during the same command transaction.
2. `org-admin` and `host-admin` should remain separate roles. A user who needs both capabilities should receive both roles explicitly.
3. The authoritative role-permission catalog should live as command-side static metadata, with importer assets kept in sync for bootstrap and repair.

## Remaining Follow-up

The implementation still needs to define the exact `org-admin` and `host-admin` endpoint permission sets. That catalog should be reviewed with the host and organization command/query API surface before implementation starts.

The owner-transfer role policy also remains open. The system should decide whether owner changes imply role grants, role revokes, both, or neither before adding role side effects to `UpdateOrg` or `UpdateHost`.
