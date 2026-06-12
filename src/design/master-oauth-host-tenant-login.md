# Master OAuth Host Tenant Login

## Problem

In a deployed portal instance, `dev.lightapi.net` is the master host for the instance. Its host ID is:

```text
01964b05-552a-7c4b-9184-6857e7f3dc5f
```

The master host owns the OAuth provider and portal client configuration:

- `auth_provider_t`
- `auth_client_t`
- `auth_provider_client_t`

Tenant hosts own user membership, roles, groups, positions, attributes, and host-scoped portal data. A user can belong to many hosts, and `user_host_t.current = TRUE` identifies which tenant host should be used for the user's login roles and JWT `host` claim.

The current light-oauth authorization code flow mixes these two meanings of host:

1. It validates the portal client against the configured master host.
2. It loads the user by the current tenant host.
3. It writes `auth_session_t` and `auth_code_t` using the user's current tenant host.

That fails after Claim Org switches the user to the newly created tenant host, because `auth_session_t`, `auth_code_t`, and `auth_refresh_token_t` currently enforce this foreign key:

```sql
FOREIGN KEY (host_id, client_id, provider_id)
REFERENCES auth_provider_client_t(host_id, client_id, provider_id)
```

The new tenant host does not and should not have duplicate OAuth provider/client rows. The FK therefore rejects login with:

```text
auth_session_t_host_id_client_id_provider_id_fkey
```

## Goals

1. Keep `dev.lightapi.net` as the single master OAuth host for the instance.
2. Allow users whose current host is a tenant host to log in through the master host's provider/client.
3. Preserve tenant-scoped JWT claims, especially the `host` claim and role claims.
4. Avoid duplicating `auth_provider_t`, `auth_client_t`, or `auth_provider_client_t` rows per tenant host.
5. Allow Claim Org to switch the host owner to the new host and require logout/login for fresh claims.
6. Keep session, auth-code, refresh-token, and audit lifecycle behavior deterministic and queryable.

## Non-Goals

This design does not introduce tenant-specific OAuth provider IDs, client IDs, redirect URIs, or BFF configuration.

This design does not change the portal UI or BFF to select a different OAuth provider per tenant host.

This design does not remove database referential integrity. The provider-client relationship should remain enforced, but it should be enforced against the master OAuth host instead of the tenant host.

## Terminology

| Term | Meaning |
| --- | --- |
| Master OAuth host | The host that owns OAuth provider/client configuration for the portal instance. In local/dev this is `01964b05-552a-7c4b-9184-6857e7f3dc5f`. |
| Tenant host | The user's current business host from `user_host_t.current`; this drives roles and tenant data access. |
| `auth_host_id` | The host ID used to validate OAuth provider/client configuration. |
| `host_id` | The tenant host ID used for session ownership, user roles, and JWT `host` claim. |

## Decision

Separate OAuth configuration host from tenant host in the OAuth runtime tables.

Keep `host_id` in `auth_session_t`, `auth_code_t`, and `auth_refresh_token_t` as the tenant/current host. Add `auth_host_id` to those tables to point to the master OAuth host that owns the provider-client mapping.

The provider-client foreign key should move from `host_id` to `auth_host_id`:

```sql
FOREIGN KEY (auth_host_id, client_id, provider_id)
REFERENCES auth_provider_client_t(host_id, client_id, provider_id)
```

Session and token lifecycle keys should remain tenant-host scoped:

```sql
auth_session_t.host_id
auth_code_t.host_id
auth_refresh_token_t.host_id
```

This preserves the current meaning of `host_id` for tenant access while allowing all OAuth configuration to live on the master host.

## Data Model

### `auth_session_t`

Add:

```sql
auth_host_id UUID NOT NULL
```

Keep:

```sql
PRIMARY KEY (host_id, session_id)
FOREIGN KEY (host_id) REFERENCES host_t(host_id)
```

Replace:

```sql
FOREIGN KEY (host_id, client_id, provider_id)
REFERENCES auth_provider_client_t(host_id, client_id, provider_id)
```

With:

```sql
FOREIGN KEY (auth_host_id, client_id, provider_id)
REFERENCES auth_provider_client_t(host_id, client_id, provider_id)
```

### `auth_code_t`

Add:

```sql
auth_host_id UUID NOT NULL
```

Keep:

```sql
PRIMARY KEY (host_id, auth_code)
FOREIGN KEY (host_id, session_id)
REFERENCES auth_session_t(host_id, session_id)
```

Replace the provider-client FK with:

```sql
FOREIGN KEY (auth_host_id, client_id, provider_id)
REFERENCES auth_provider_client_t(host_id, client_id, provider_id)
```

### `auth_refresh_token_t`

Add:

```sql
auth_host_id UUID NOT NULL
```

Keep:

```sql
PRIMARY KEY (host_id, refresh_token)
FOREIGN KEY (host_id, session_id)
REFERENCES auth_session_t(host_id, session_id)
```

Replace the provider-client FK with:

```sql
FOREIGN KEY (auth_host_id, client_id, provider_id)
REFERENCES auth_provider_client_t(host_id, client_id, provider_id)
```

### `auth_session_audit_t`

`auth_session_audit_t.host_id` should remain the tenant host for session and user queries.

Add:

```sql
auth_host_id UUID NOT NULL
```

Audit rows must distinguish the authorization server host from the tenant host from the first migration. This is required for security and compliance trails because a single database can contain multiple master hosts, and operators need to answer both questions:

- Which OAuth host authenticated the user?
- Which tenant host did the user access?

`auth_host_id` should be populated from the same value used by the session, auth code, or refresh token involved in the audit event.

### Token Endpoint Lookup Indexes

The token endpoint receives an authorization code or refresh token string. It does not receive tenant `host_id` in the standard OAuth request, so it cannot use the `(host_id, auth_code)` or `(host_id, refresh_token)` primary keys as the first lookup.

Add unique secondary indexes:

```sql
CREATE UNIQUE INDEX idx_auth_code_t_auth_code
    ON auth_code_t(auth_code);

CREATE UNIQUE INDEX idx_auth_refresh_token_t_refresh_token
    ON auth_refresh_token_t(refresh_token);
```

The token endpoint should load the row by the code or refresh token string, then validate the tenant and OAuth boundaries with the row values. This keeps the external OAuth token format unchanged and avoids embedding tenant host IDs into authorization code or refresh token strings.

## Migration

The migration should be backward compatible for existing rows.

1. Add nullable `auth_host_id` columns.

```sql
ALTER TABLE auth_session_t ADD COLUMN auth_host_id UUID;
ALTER TABLE auth_code_t ADD COLUMN auth_host_id UUID;
ALTER TABLE auth_refresh_token_t ADD COLUMN auth_host_id UUID;
ALTER TABLE auth_session_audit_t ADD COLUMN auth_host_id UUID;
```

2. Backfill existing rows. Existing valid rows used `host_id` for both meanings, so the safe default is:

```sql
UPDATE auth_session_t SET auth_host_id = host_id WHERE auth_host_id IS NULL;
UPDATE auth_code_t SET auth_host_id = host_id WHERE auth_host_id IS NULL;
UPDATE auth_refresh_token_t SET auth_host_id = host_id WHERE auth_host_id IS NULL;
UPDATE auth_session_audit_t SET auth_host_id = host_id WHERE auth_host_id IS NULL;
```

3. Set the new columns to not null.

```sql
ALTER TABLE auth_session_t ALTER COLUMN auth_host_id SET NOT NULL;
ALTER TABLE auth_code_t ALTER COLUMN auth_host_id SET NOT NULL;
ALTER TABLE auth_refresh_token_t ALTER COLUMN auth_host_id SET NOT NULL;
ALTER TABLE auth_session_audit_t ALTER COLUMN auth_host_id SET NOT NULL;
```

4. Drop the current provider-client FKs.

The exact constraint names vary by schema version. The migration should drop the existing provider-client constraints on:

- `auth_session_t`
- `auth_code_t`
- `auth_refresh_token_t`

5. Add new provider-client FKs through `auth_host_id`.

```sql
ALTER TABLE auth_session_t
    ADD CONSTRAINT auth_session_t_auth_provider_client_fk
    FOREIGN KEY (auth_host_id, client_id, provider_id)
    REFERENCES auth_provider_client_t(host_id, client_id, provider_id)
    ON DELETE CASCADE;

ALTER TABLE auth_code_t
    ADD CONSTRAINT auth_code_t_auth_provider_client_fk
    FOREIGN KEY (auth_host_id, client_id, provider_id)
    REFERENCES auth_provider_client_t(host_id, client_id, provider_id)
    ON DELETE CASCADE;

ALTER TABLE auth_refresh_token_t
    ADD CONSTRAINT auth_refresh_token_t_auth_provider_client_fk
    FOREIGN KEY (auth_host_id, client_id, provider_id)
    REFERENCES auth_provider_client_t(host_id, client_id, provider_id)
    ON DELETE CASCADE;
```

6. Add supporting indexes.

```sql
CREATE INDEX idx_auth_session_t_auth_host_client_provider
    ON auth_session_t(auth_host_id, client_id, provider_id);

CREATE INDEX idx_auth_code_t_auth_host_client_provider
    ON auth_code_t(auth_host_id, client_id, provider_id);

CREATE INDEX idx_auth_refresh_token_t_auth_host_client_provider
    ON auth_refresh_token_t(auth_host_id, client_id, provider_id);

CREATE UNIQUE INDEX idx_auth_code_t_auth_code
    ON auth_code_t(auth_code);

CREATE UNIQUE INDEX idx_auth_refresh_token_t_refresh_token
    ON auth_refresh_token_t(refresh_token);

CREATE INDEX idx_auth_session_audit_t_auth_refresh_rotation
    ON auth_session_audit_t(auth_host_id, old_refresh_token_id, client_id, provider_id, event_type, event_ts DESC);
```

## light-oauth Changes

### Authorization Code Login

In `post_code`, keep using `state.host_id` to validate the configured portal client:

```rust
let client = get_client_by_provider_client_id(state.host_id, provider_id, client_id);
```

After password verification, use two host IDs:

```rust
let auth_host_id = client.host_id; // master OAuth host
let tenant_host_id = user.host_id; // current user host
```

Persist:

```rust
AuthCode {
    host_id: tenant_host_id,
    auth_host_id,
    ...
}

AuthSession {
    host_id: tenant_host_id,
    auth_host_id,
    ...
}
```

### Authorization Code Token Exchange

When exchanging the code:

1. Load the auth code by the unique `auth_code` value.
2. Authenticate the client against the master OAuth host.
3. Verify:

```rust
code.provider_id == provider_id
code.client_id == client.client_id
code.auth_host_id == client.host_id
```

The lookup can remain by authorization code only because `auth_code_t(auth_code)` is unique. The endpoint must still validate the row after retrieval so a code issued to one client or master host cannot be exchanged by another client.

Generate access token claims from tenant data:

```rust
("host", Some(code.host_id.to_string()))
```

Create refresh tokens with:

```rust
AuthRefreshToken {
    host_id: code.host_id,
    auth_host_id: code.auth_host_id,
    ...
}
```

### Refresh Token Flow

The token endpoint should load refresh tokens by the unique `refresh_token` value. After the row is loaded, all mutation and session lifecycle operations should use the tenant `host_id` from the row.

The refresh flow must also verify that the authenticated client belongs to the same master OAuth host stored on the refresh token:

```rust
token.auth_host_id == client.host_id
token.client_id == client.client_id
token.provider_id == provider_id
```

Rotated refresh tokens must carry forward `auth_host_id`.

The JWT `host` claim must continue to come from `token.host_id`, not `token.auth_host_id`.

Refresh-token deletion and rotation should use:

```rust
host_id = token.host_id
refresh_token = token.refresh_token
```

This preserves tenant-host session ownership while allowing the token endpoint to find the row without the caller providing tenant `host_id`.

### Logout And Revocation

Logout and administrative revocation should use the tenant host from the provided token or loaded refresh-token row.

For refresh-token based logout:

1. Load the refresh token by the unique `refresh_token` value.
2. Validate `token.auth_host_id == client.host_id` when client context is present.
3. Revoke the session with `token.host_id` and `token.session_id`.
4. Delete refresh tokens and outstanding auth codes with the same tenant `host_id` and `session_id`.
5. Write audit rows with both tenant `host_id` and master `auth_host_id`.

For access-token based logout, the host claim represents the tenant host. The logout handler should use that tenant host to locate the session or refresh token state, and should not treat the master OAuth host as the tenant context.

### Password Grant

The password grant has the same host split:

```rust
let auth_host_id = client.host_id;
let tenant_host_id = user.host_id;
```

Sessions and refresh tokens should store both values.

### Client Authenticated User Grant

This grant already accepts an optional tenant host in the request. That host should remain the tenant `host_id`.

The authenticated client's host should become `auth_host_id`.

### Client Authentication

`authenticate_client` should become host-aware. The token endpoint should not load a client only by `client_id`, because `auth_client_t` is keyed by `(host_id, client_id)`.

Preferred behavior:

```rust
get_client_by_provider_client_id(state.host_id, provider_id, client_id)
```

This keeps token endpoint client authentication aligned with the authorization endpoint.

### Provider And Key Lookup

Provider and signing-key lookup should also be scoped by the configured master OAuth host.

Current provider IDs are short and not globally guaranteed across every possible master host in a shared database. Therefore the light-oauth lookup shape should be:

```rust
query_provider_by_id(state.host_id, provider_id)
query_current_provider_key(state.host_id, provider_id)
query_long_live_provider_key(state.host_id, provider_id)
```

The SQL should include `host_id = $1` as well as `provider_id = $2`. This prevents accidental cross-master-host key or provider resolution if another portal instance later stores the same provider ID in the same database cluster.

## JWT Claims

The access token must continue to identify the tenant host:

```json
{
  "host": "<tenant-host-id>",
  "role": "host-admin org-admin"
}
```

The master OAuth host should not replace the JWT `host` claim. It is an implementation detail for OAuth provider/client validation.

If operational diagnostics need visibility into the authorization host, a separate claim could be introduced later, but this is not required for the current flow and should not be added unless there is a clear consumer.

## Claim Org Behavior

With this design implemented, Claim Org can safely emit `UserHostSwitchedEvent` for the selected host owner during the same command transaction that creates:

1. `OrgCreatedEvent`
2. `HostCreatedEvent`
3. `UserHostCreatedEvent`
4. `UserHostSwitchedEvent`
5. `RoleCreatedEvent` for `org-admin`
6. `RoleCreatedEvent` for `host-admin`
7. `RoleUserCreatedEvent` for `orgOwner` and `org-admin`
8. `RoleUserCreatedEvent` for `hostOwner` and `host-admin`

The user's current browser session still has the old host claim. The UI should tell the host owner to log out and log in again after Claim Org. The next login will:

1. Authenticate through the master OAuth host.
2. Load roles from the new current tenant host.
3. Store session/code/refresh rows with tenant `host_id` and master `auth_host_id`.
4. Issue a token whose `host` claim is the new tenant host.

## Backfill And Repair

For existing databases, the schema migration backfills `auth_host_id = host_id` for existing valid OAuth rows.

For users already switched to a tenant host by an earlier Claim Org deployment, no OAuth provider/client rows should be created on the tenant host. After this design is deployed, those users should be able to log in because new session rows will reference:

```text
host_id      = tenant host
auth_host_id = master OAuth host
```

If an earlier failed login left partial session artifacts, they should be removed through existing session cleanup paths or targeted SQL cleanup before retesting.

## Validation

A focused validation set should cover:

- Existing master-host login still succeeds after migration.
- Claim Org switches the selected host owner to the new tenant host.
- The host owner can log out and log in again after Claim Org.
- New `auth_session_t` rows use tenant `host_id` and master `auth_host_id`.
- New `auth_code_t` rows use tenant `host_id` and master `auth_host_id`.
- New `auth_refresh_token_t` rows use tenant `host_id` and master `auth_host_id`.
- The JWT `host` claim is the tenant host, not the master OAuth host.
- Role claims come from the tenant host after `user_host_t.current` is switched.
- No `auth_provider_t`, `auth_client_t`, or `auth_provider_client_t` rows are created for the tenant host.
- Refresh token rotation preserves `auth_host_id`.
- Revoking a session or refresh token still works with tenant-host keys.
- Logout uses the tenant host from the token/session row and writes audit rows with `auth_host_id`.
- Existing rows migrated with `auth_host_id = host_id` still support token refresh and audit queries.
- Auth code lookup uses `auth_code_t(auth_code)` and still rejects mismatched client/provider/auth host.
- Refresh token lookup uses `auth_refresh_token_t(refresh_token)` and still rejects mismatched client/provider/auth host.
- Provider and provider-key lookup is scoped by the configured master OAuth host.

## Resolved Decisions

1. `auth_session_audit_t` must add `auth_host_id` in the first migration.
2. Provider and provider-key lookup must require the configured master OAuth host ID.
3. `auth_code_t` lookup remains by unique `auth_code`, followed by strict client, provider, and `auth_host_id` validation.
4. `auth_refresh_token_t` lookup remains by unique `refresh_token`, followed by strict client, provider, and `auth_host_id` validation.
5. Authorization code and refresh token string formats should not embed tenant host IDs in this design.
