# Light Portal Fine-Grained Authorization

## Overview

The existing fine-grained authorization model describes how Light Portal manages
access control for APIs and MCP tools owned by customers. This document applies
the same ideas to Light Portal itself.

Light Portal has two different authorization surfaces:

- the browser application, where menus, routes, tasks, and action buttons decide
  what the user can discover and click
- the backend portal handlers, where query and command services read or mutate
  tenant data

The browser must improve usability by hiding irrelevant admin menus, but it must
not be the security boundary. The security boundary must be enforced by the
gateway and by the portal query and command handlers.

## Goals

- Limit admin menus based on the user's roles, positions, groups, and
  attributes.
- Let `admin` access all eligible admin pages for data within all hosts.
- Let a `host-admin` access all eligible admin pages for data within the current
  tenant host only.
- Keep global platform administration separate from tenant administration.
- Enable request access control (`req-acc`) and response filtering (`res-fil`)
  for Light Portal hybrid handlers.
- Use `owner_user_id` and `owner_position_id` as the primary row ownership
  model for self-service admin pages.
- Keep authorization rules declarative enough that they can be managed from the
  existing rule and access-control pages.

## Non-Goals

- Do not rely on menu hiding as authorization.
- Do not make `host-admin` a global portal super admin.
- Do not replace existing host scoping with ownership scoping. Host scoping
  remains mandatory.
- Do not require every portal table to be migrated before the model can be
  rolled out.
- Do not duplicate every rule in React. React should consume an effective menu
  and capability model from the backend over time.

## Recommended Model

Use three layers.

| Layer | Purpose | Enforcement |
| --- | --- | --- |
| Menu and route visibility | Usability and discoverability | `portal-view` hides menus and blocks client routes |
| Handler request access | Decide whether a user may call a query or command service/action | light-gateway `req-acc` for `/portal/query` and `/portal/command` |
| Data scope and response filtering | Decide which tenant rows and fields the user may see or mutate | service-side owner predicates and gateway/service `res-fil` |

This keeps the user experience responsive without trusting the browser.

## Roles And Scopes

Separate page access from row scope.

| Role or claim | Meaning | Page access | Data scope |
| --- | --- | --- | --- |
| `admin` | global portal administrator | all portal admin pages | all hosts, only for global administration |
| `host-admin` | tenant administrator | tenant-safe admin pages | current `hostId` only |
| `access-admin` | tenant access-control administrator | access-control administration pages | current `hostId` only |
| `<entity>-admin` | entity-specific administrator, such as `api-admin` or `instance-admin` | pages for that entity | current `hostId`, all rows for that entity |
| `user` | self-service user | approved self-service pages | owned rows only |
| positions claim | team or org-unit membership | does not grant pages by itself unless mapped by rule | rows owned by matching effective positions |
| groups and attributes | additional authorization dimensions | rule-dependent | rule-dependent |

The important distinction is that `host-admin` is powerful inside one tenant but
must not bypass host ownership. If the current session host is
`01964b05-...`, every query and command still needs that `hostId` enforced.

## Host Admin

`host-admin` should be the standard tenant administrator role.

A `host-admin` can:

- see tenant administration menus that are safe within the current host
- query all records whose `host_id` is the current session host
- create and update tenant-scoped records for the current host
- assign ownership inside the current host when the command supports it

A `host-admin` cannot:

- access another `hostId` by changing a request payload
- manage global reference data unless explicitly granted a global role
- manage platform deployment records that are not tenant scoped
- manage access-control policy unless explicitly granted `access-admin` inside
  the current host
- bypass command-specific invariants, such as optimistic concurrency checks

Backend handlers must treat `hostId` from the request as untrusted. The trusted
tenant comes from the authenticated audit context or from a verified user-host
membership lookup.

## Access Administration

Access-control administration is separate from general tenant administration.
Changing role, group, position, attribute, row-filter, or column-filter policy
can change who may read or mutate tenant data, so it should require
`access-admin` within the current host instead of being implied by `host-admin`.

An `access-admin` can manage policy for tenant-owned APIs, apps, clients,
instances, workflows, schemas, schedules, and other tenant-scoped assets in the
current host. An `access-admin` cannot manage global platform policy unless the
user also has the global `admin` role.

This keeps `host-admin` useful for normal tenant operations while preserving
separation of duties for security policy changes.

## Platform And Tenant Deployment Pages

Deployment administration should be split into tenant deployment pages and
global platform pages.

Tenant deployment pages can be visible to `host-admin` when every operation is
scoped to the current `hostId`, such as deploying tenant APIs, checking route
health, or managing tenant client registrations.

Global platform pages must require `admin`. These pages manage shared
infrastructure, gateway clusters, physical deployment targets, shared database
configuration, or cross-host platform state. They must not be exposed through a
tenant-scoped `host-admin` rule.

## Menu Authorization

The current sidebar already supports role-based visibility with exact role
tokens and treats `admin` and `host-admin` as broad admin roles. The design
should evolve this into a backend-driven capability model.

### Phase 1: Local Menu Policy

Keep a local page registry in `portal-view`, but normalize it around page
capabilities.

```ts
{
  id: "api-admin",
  route: "/app/service/admin",
  requiredAny: ["admin", "host-admin", "api-admin", "user"],
  scope: "owner-or-host",
  entity: "api"
}
```

The UI can show:

- all admin menus for `admin`
- tenant-safe admin menus for `host-admin`
- entity menus for `<entity>-admin`
- approved self-service menus for `user`

Menus with no explicit rule inside the Administration group should not be shown
to normal users.

### Phase 2: Backend Menu Policy

Add a backend query such as:

```text
lightapi.net/portal/getEffectiveMenu/0.1.0
```

or:

```text
lightapi.net/portal/getEffectiveCapabilities/0.1.0
```

The response should contain route-level capabilities, not raw policy internals.

```json
{
  "hostId": "01964b05-552a-7c4b-9184-6857e7f3dc5f",
  "pages": [
    {
      "pageId": "api-admin",
      "route": "/app/service/admin",
      "visible": true,
      "readScope": "owned",
      "writeScope": "owned"
    },
    {
      "pageId": "instance-admin",
      "route": "/app/instance/InstanceAdmin",
      "visible": true,
      "readScope": "host",
      "writeScope": "host"
    }
  ]
}
```

The sidebar, task launcher, command palette, and route guards should consume the
same capability response.

## Request Access For Portal Handlers

Light Portal uses hybrid RPC-style endpoints:

```text
POST /portal/query
POST /portal/command
```

The request body identifies the logical handler:

```json
{
  "host": "lightapi.net",
  "service": "service",
  "action": "getApi",
  "version": "0.1.0",
  "data": {
    "hostId": "01964b05-552a-7c4b-9184-6857e7f3dc5f"
  }
}
```

For `req-acc`, the gateway must authorize the logical service id, not only the
HTTP path. The effective route key should be derived as:

```text
lightapi.net/{service}/{action}/{version}
```

Example:

```text
lightapi.net/service/getApi/0.1.0
lightapi.net/service/createApi/0.1.0
lightapi.net/role/createRolePermission/0.1.0
```

This lets the access-control registry treat portal handlers exactly like API
operations.

### Request Context

The `req-acc` rule context should include:

```json
{
  "serviceId": "lightapi.net/service/createApi/0.1.0",
  "transport": "hybrid",
  "portal": true,
  "hostId": "01964b05-552a-7c4b-9184-6857e7f3dc5f",
  "entity": "api",
  "action": "create",
  "jwt": {
    "userId": "01964b05-5532-7c79-8cde-191dcbd421b8",
    "roles": ["user", "api-admin"],
    "positions": ["team-api"],
    "groups": ["engineering"],
    "attributes": {
      "department": "platform"
    }
  },
  "requestData": {
    "hostId": "01964b05-552a-7c4b-9184-6857e7f3dc5f"
  }
}
```

Recommended built-in request rules:

| Rule | Purpose |
| --- | --- |
| `portal-admin-global` | allow `admin` for global admin handlers |
| `portal-host-admin` | allow `host-admin` only when `requestData.hostId` matches the session host |
| `portal-access-admin` | allow `access-admin` for tenant access-control handlers in the current host |
| `portal-entity-admin` | allow `<entity>-admin` for entity handlers in the current host |
| `portal-owner-read` | allow `user` to call approved read handlers; row scope is applied later |
| `portal-owner-write` | allow `user` to call approved write handlers only when ownership can be verified |

## Response Filtering For Portal Handlers

Response filtering has two jobs:

- remove rows that are outside the caller's authorized scope
- optionally remove columns the caller should not see

For list queries, service-side SQL filtering is preferred over gateway-only
filtering because it protects pagination, counts, and performance. The gateway
or common service layer can still apply `res-fil` as a defense-in-depth step.

Recommended order:

1. `req-acc` decides whether the user may call the logical handler.
2. Query handler injects host and owner predicates into SQL.
3. Query handler returns only authorized rows and an authorized total.
4. Shared query serialization or service-side `res-fil` removes rows only when
   it can also preserve authorized pagination totals.
5. Gateway `res-fil` removes sensitive fields and can perform defense-in-depth
   row removal for non-paginated responses.
6. Portal-view renders the already-authorized result.

Gateway-only row filtering must not be the primary implementation for paginated
lists. If rows are removed after the backend has already computed `total`,
`offset`, or `limit`, the grid metadata becomes inaccurate. Row predicates
belong in SQL or in shared query serialization that controls both the returned
rows and the total count. Column filtering can run in the gateway because it
does not change pagination.

For command handlers, response filtering is less important than request
authorization and command-side ownership checks. A command must verify that the
target aggregate belongs to the current host and that the caller can mutate it.

## Owner Position

The owner model should prefer explicit owner fields:

```text
owner_user_id
owner_position_id
```

`owner_user_id` is assigned from the authenticated user on create. Normal forms
should not submit it.

`owner_position_id` lets a team or org unit own a record. Users with an
effective matching position can see or manage the record when the page rule
allows owner-scoped access.

Owner assignments must always remain inside the current host. When a command
sets or transfers `owner_user_id` or `owner_position_id`, the command handler
must verify that the target user or position belongs to the trusted session
`hostId`. The browser-supplied owner value is not enough. Cross-host owner
assignment must be rejected even when the caller has `host-admin` for the
current host.

Owner changes are security-sensitive events. Create, transfer, and clear
operations for `owner_user_id` or `owner_position_id` must be written to the
audit log with the old owner, new owner, entity id, trusted host, acting user,
and logical portal service id.

For owner-scoped reads, the service predicate should be:

```sql
AND (
  owner_user_id = :currentUserId
  OR owner_position_id = ANY(:effectivePositions)
)
```

If the database dialect does not support array binding, use an `IN` list with
validated position ids. Owner-scoped tables should index host and owner columns
together, such as `(host_id, owner_user_id)` and
`(host_id, owner_position_id)`, so owner predicates remain efficient.

Rows with both owner fields null are unassigned legacy rows. They should be
visible only to all-scope roles such as `admin`, `host-admin`, or an applicable
`<entity>-admin` until ownership is assigned.

### Effective Positions

The JWT may contain direct positions, but direct positions are not always enough.
The service should resolve effective positions from:

- direct position claims in the token
- `user_position_t`
- position inheritance rules when enabled

The effective set should be computed in one shared utility and reused by query
and command handlers. Existing `OwnerScopeUtil` is the right direction for query
handlers; it should become the standard path rather than a page-specific helper.

Position inheritance should not be recursively expanded inside every portal
query. Materialize the transitive closure in a table such as
`position_closure_t` and refresh it when position relationships change, or cache
the user's flat effective-position set in session state and invalidate it when
membership changes. The query layer should receive a bounded, validated list of
effective positions.

## Command Authorization

Commands need stronger checks than queries because they mutate state.

Every tenant-scoped command should verify:

- the requested `hostId` is the authenticated session host, unless the caller is
  a global `admin`
- the target aggregate exists in that host for update/delete commands
- owner-scoped users own the target through `owner_user_id` or
  `owner_position_id`
- entity admins and host admins are still limited by host
- owner transfer is explicit and restricted
- target owners for `owner_user_id` and `owner_position_id` belong to the
  trusted session host
- owner transfer is audit logged with old and new owner values

Recommended command scopes:

| Scope | Meaning |
| --- | --- |
| `own:create` | user can create records owned by self and optional owner position |
| `own:update` | user can update records they own |
| `own:delete` | user can delete records they own if the entity allows it |
| `host:read` | user can read all rows in the current host |
| `host:write` | user can mutate all rows in the current host |
| `global:admin` | user can operate across hosts for platform administration |

## Portal Access-Control Registry

The access-control registry should support portal handlers as first-class
endpoints.

Proposed endpoint identity:

| Field | Value |
| --- | --- |
| `apiId` | `PORTAL` or `light-portal` |
| `apiVersion` | portal release version or `1.0.0` for the logical control plane |
| `endpoint` | `lightapi.net/{service}/{action}/{version}` |
| `httpMethod` | `POST` |
| `endpointPath` | `/portal/query` or `/portal/command` |
| `sourceProtocol` | `hybrid` |

This allows the existing Role Permission, Group Permission, Position Permission,
Attribute Permission, Row Filter, and Column Filter pages to manage portal
handler access without a separate policy store.

The portal-handler catalog should be generated from service annotations and
`spec.yaml` metadata during build or deployment. Manual registration may be used
only as an override for descriptions, classifications, or temporary exclusions.
Generation prevents drift when handlers are added, renamed, or removed.

## Example Policies

### Host Admin Can Manage Tenant APIs

Request rule:

```yaml
ruleId: portal-host-admin-current-host
ruleType: req-acc
description: Allow host-admin to call tenant handlers for the current host.
conditions:
  - conditionId: role-host-admin
    variableName: jwt
    propertyPath: roles
    operatorCode: CS
    conditionValues:
      - conditionValue: host-admin
  - conditionId: same-host
    variableName: requestData
    propertyPath: hostId
    operatorCode: EQ
    conditionValues:
      - conditionValue: "@host_id"
actions:
  - actionClassName: com.networknt.rule.FineGrainedAuthAction
```

The `@host_id` placeholder means the trusted host from the authenticated
context, not a host id supplied by the browser.

### User Can See Owned APIs

Request rule allows the list handler:

```yaml
endpoint: lightapi.net/service/getApi/0.1.0
ruleType: req-acc
roles:
  - user
  - api-admin
  - host-admin
  - admin
```

The data rule is applied in SQL:

```sql
WHERE host_id = :hostId
AND (
  :allScope = TRUE
  OR owner_user_id = :currentUserId
  OR owner_position_id IN (:effectivePositions)
)
```

### Owner Position Can Manage Team Client Apps

If a client app has:

```text
owner_position_id = api-platform-team
```

and the user has effective position:

```text
api-platform-team
```

then the user can see and update the app when the page grants owner-scoped
access. The user does not need a broad `app-admin` role.

## Handler Enablement Plan

### Phase 1: Inventory

- Register every portal query and command handler as a logical access-control
  endpoint from service annotations and `spec.yaml`.
- Classify each handler by entity, operation, and scope:
  - global admin
  - host admin
  - entity admin
  - owner scoped
  - public authenticated
- Identify handlers that cannot yet be owner scoped because the table lacks
  owner fields.

Implementation path:

- `service-command` parses `apiType: hybrid` `spec.yaml` files in
  `SpecUtil.parseSpec`.
- Hybrid handlers are stored as logical endpoints such as
  `lightapi.net/service/getApi/0.1.0`, with `httpMethod: post` and
  `endpointPath` set to `/portal/query` or `/portal/command`.
- Handler name, request schema, transport path, action, version, scope,
  operation classification, and `skipAuth` are captured in endpoint metadata.
- Existing legacy hybrid endpoint ids keyed by `logicalEndpoint@post` are reused
  during migration so policy assignments can keep the same `endpointId`.

### Phase 2: Menu And Capability Cleanup

- Normalize sidebar and task page registry roles around exact tokens.
- Treat `host-admin` as tenant admin, not global admin.
- Add route guards that use the same page capability model as the menu.
- Keep React-side hiding as usability only.

### Phase 3: Query Enforcement

- Standardize `OwnerScopeUtil` for all owner-aware query handlers.
- Pass `ownerUserId`, `ownerPositions`, and `ownerScoped` into db-provider
  query methods.
- Ensure counts and pagination are computed after host and owner predicates.
- Return owner fields only when the caller has a reason to see them.

### Phase 4: Command Enforcement

- Add common command guard helpers:
  - resolve trusted host
  - verify target aggregate host ownership
  - verify owner or all-scope access
  - enforce owner-transfer rules
  - verify transferred owner user or position belongs to the trusted host
  - audit owner changes
- Add explicit owner-transfer commands for records that need ownership changes.
- Reject requests where browser-supplied `hostId` conflicts with the trusted
  session host.

### Phase 5: Gateway `req-acc` And `res-fil`

- Update light-gateway access-control extraction for hybrid portal requests.
- Derive logical service id from `host`, `service`, `action`, and `version`.
- Build the CEL/rule context with JWT claims, trusted host, request data, and
  handler metadata.
- Run `req-acc` before forwarding to the portal handler.
- Run gateway `res-fil` for column filtering and defense-in-depth response
  filtering where endpoint filters are configured.

### Phase 6: Policy Management UI

- Reuse existing access-control pages to assign portal handler permissions.
- Add a portal-handler catalog view that lists logical handlers and their
  current permission configuration.
- Add an overview page for effective menu and data access per role or user.
- Make access-control pages require `access-admin` for tenant policy changes and
  `admin` for global policy changes.

## Recommendations

1. Use `host-admin` as the tenant administrator role and keep `admin` as global
   super admin.
2. Make every backend handler validate host scope, even when the UI already
   selected the host.
3. Prefer service-side row filtering over response-only filtering for list
   queries.
4. Use `owner_position_id` for team ownership instead of adding group ownership
   to every table.
5. Keep `owner_user_id` server-assigned and make ownership transfer explicit.
6. Validate transferred owners against the trusted host and audit all ownership
   changes.
7. Materialize or cache effective positions before query execution instead of
   recursively resolving position inheritance on every request.
8. Register portal handlers in the same access-control registry used for
   customer APIs so `req-acc` and `res-fil` are managed consistently.
9. Generate the portal-handler catalog from service annotations and `spec.yaml`,
   with manual metadata overrides only where needed.
10. Split tenant deployment pages from global platform pages.
11. Require `access-admin` for tenant access-control administration instead of
   granting it implicitly to `host-admin`.
12. Roll out one entity family at a time, starting with API, client app,
   instance, workflow, schema, and schedule pages because they already have the
   clearest ownership model.

## Design Decisions

| Question | Decision |
| --- | --- |
| Access-control administration | Require `access-admin` inside the host; do not grant it implicitly to `host-admin`. |
| Deployment pages | Split tenant deployment pages from global platform pages. Tenant pages can use `host-admin`; global platform pages require `admin`. |
| Position inheritance | Materialize `position_closure_t` or cache the effective-position set; do not recursively compute inheritance in every query. |
| Portal handler registration | Generate the catalog from service annotations and `spec.yaml`, with manual metadata overrides only. |
| Portal response filtering | Apply row filtering in SQL or shared query serialization so pagination totals remain exact. Use gateway `res-fil` mainly for column filtering and defense-in-depth checks. |
