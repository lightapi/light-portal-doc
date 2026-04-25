# OAuth Audit

The OAuth services keep authorization codes and refresh tokens as operational state. These rows are short lived and are now written directly to `auth_code_t` and `auth_refresh_token_t` instead of being created through the general event store. This avoids high-volume login and refresh-token churn in `event_store_t` and `outbox_message_t`.

Audit and login history are recorded separately in append-oriented OAuth audit tables.

## Goals

- Show administrators who is currently online.
- Show a user the last login time and session history.
- Track refresh-token rotation and rejected refresh attempts.
- Preserve enough history for support and security review without storing raw secrets.
- Keep the hot login and token-refresh path simple and transactional.

## Tables

`auth_session_t` stores one row per login session. It is the current and historical session summary.

- `session_id` identifies the browser/device session.
- `login_ts`, `last_refresh_ts`, `logout_ts`, and `expires_ts` describe the session lifetime.
- `status` is `ACTIVE`, `LOGGED_OUT`, `EXPIRED`, or `REVOKED`.
- `refresh_count` is incremented on each successful refresh-token rotation.
- `ip_address`, `user_agent`, and `device_id` are optional request context fields.

`auth_session_audit_t` stores append-only auth audit entries.

- `LOGIN_SUCCEEDED`
- `LOGIN_FAILED`
- `AUTH_CODE_ISSUED`
- `AUTH_CODE_CONSUMED`
- `REFRESH_TOKEN_ISSUED`
- `REFRESH_TOKEN_ROTATED`
- `REFRESH_TOKEN_REJECTED`
- `LOGOUT`
- `SESSION_EXPIRED`
- `SESSION_REVOKED`

`auth_refresh_token_t.session_id` links the currently valid refresh token to the session that owns it. This removes ambiguity when the same user is logged in from multiple browsers or devices.

Audit rows keep `session_id` as data, but do not use a hard foreign key to `auth_session_t`. Audit history must remain groupable by session even if operational session rows are later archived or removed.

## Login Flow

When `/oauth2/{providerId}/code` authenticates the user:

1. Insert the authorization code into `auth_code_t`.
2. Insert an `ACTIVE` session into `auth_session_t`.
3. Insert `LOGIN_SUCCEEDED` and `AUTH_CODE_ISSUED` audit rows.
4. Include the `session_id` in the auth code row so the token exchange can attach the refresh token to the same session.

Failed logins write `LOGIN_FAILED` with the available host, provider, client, request metadata, and failure reason.

## Authorization Code Exchange

When `grant_type=authorization_code` succeeds:

1. Delete the consumed auth code from `auth_code_t`.
2. Insert the refresh token into `auth_refresh_token_t` with the auth code's `session_id`.
3. Insert `AUTH_CODE_CONSUMED` and `REFRESH_TOKEN_ISSUED` audit rows.

## Refresh Token Rotation

When `grant_type=refresh_token` succeeds, the service performs one transaction:

1. Insert the replacement refresh token.
2. Delete the previous refresh token with its expected aggregate version.
3. Update `auth_session_t.last_refresh_ts` and increment `refresh_count`.
4. Insert `REFRESH_TOKEN_ROTATED` with the old and new token ids.

If a refresh token is missing, invalid, or belongs to the wrong client, the service writes `REFRESH_TOKEN_REJECTED` when enough context is available. Raw refresh-token values must not be stored in audit metadata.

## Admin Revocation

Administrators can kick out a user by revoking the user's current refresh token. Operationally, deleting the refresh token is enough to stop the session from renewing once the current access token expires. The audit/session model adds explicit session state to that behavior.

The revocation operation must run as one transaction:

1. Find the refresh token row and its `session_id`.
2. Delete the refresh token from `auth_refresh_token_t`.
3. Update `auth_session_t`:
   - `status = 'REVOKED'`
   - `logout_ts = CURRENT_TIMESTAMP`
   - `end_reason = 'ADMIN_REVOKED'`
4. Insert `SESSION_REVOKED` into `auth_session_audit_t`.

The database patch provides `revoke_auth_session_by_refresh_token(host_id, refresh_token, admin_user, reason)` for this workflow. Admin screens should call the revoke operation instead of issuing a plain refresh-token delete when the intent is to kick out a logged-in user.

If the refresh token has no `session_id`, the operation still deletes the token and returns `NULL`. This preserves backward compatibility with refresh-token rows created before session tracking.

## Admin Queries

Current online users:

```sql
SELECT *
FROM auth_session_t
WHERE status = 'ACTIVE'
  AND (expires_ts IS NULL OR expires_ts > CURRENT_TIMESTAMP);
```

User login history:

```sql
SELECT *
FROM auth_session_t
WHERE host_id = $1
  AND user_id = $2
ORDER BY login_ts DESC;
```

Session duration:

```sql
SELECT
    login_ts,
    COALESCE(logout_ts, last_refresh_ts, CURRENT_TIMESTAMP) - login_ts AS duration
FROM auth_session_t
WHERE host_id = $1
  AND session_id = $2;
```

## Retention

`auth_session_t` can be retained longer than operational token tables. `auth_session_audit_t` should use a retention policy appropriate for the deployment, for example 90 days or one year. Retention jobs should delete audit rows by `event_ts` and optionally archive them before deletion.
