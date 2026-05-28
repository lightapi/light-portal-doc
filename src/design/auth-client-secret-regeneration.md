# Auth Client Secret Regeneration

## Problem

An OAuth auth client receives a `client_id` and `client_secret` when it is
created. The clear text `client_secret` is intentionally a one-time value. The
database projection stores only a verifier value in `auth_client_t.client_secret`
so the clear secret cannot be recovered later.

This is secure, but it creates an operational problem. Users can miss the
one-time response, close the page, or forget to copy the secret into their
deployment system. Once that happens, the portal needs a way to issue a new
secret without weakening the storage model.

## Current State

The current create flow in `oauth-command` generates both values in
`CreateClient`:

- `clientId`: generated UUID.
- `clientSecret`: generated random/base64 UUID value.
- `clientSecretEncrypted`: generated with
  `HashUtil.generateStrongPasswordHash(clientSecret)`.

The read model stores the verifier in `auth_client_t.client_secret`. The update
flow does not update `client_secret`, which is correct because normal client
metadata updates should not rotate credentials.

The Auth Client page currently supports:

- creating a client through the create form,
- creating tokens for an existing client,
- updating client metadata,
- deleting a client.

## Options

### Option 1: Delete And Recreate The Client

This works only as a workaround and should not be the product design.

Problems:

- It changes `client_id`, so every downstream service, runtime config, token
  request, and automation script must be updated.
- It creates avoidable downtime because the old credential is removed before the
  new one can be distributed.
- It loses the continuity of the auth client record and makes audit history
  harder to read.
- It can leave related state confusing, especially provider-client mappings,
  client tokens, and owner relationships.
- It trains users to use a destructive operation for a credential-management
  problem.

### Option 2: Add A Regenerate Secret Action

This is the recommended option.

The client record and `client_id` remain stable. Only the secret verifier is
replaced. The clear text value is returned once in the command response and is
never stored in a recoverable form.

Benefits:

- Keeps existing client ownership, provider link, service references, and audit
  continuity.
- Avoids unnecessary delete/recreate events.
- Matches common OAuth client-management behavior.
- Enables a focused UI flow with explicit warning, confirmation, copy action,
  and audit trail.

## Decision

Add a dedicated "Regenerate Secret" action on the Auth Client page.

Do not reuse delete/recreate as the normal path. Do not add a recoverable
encrypted-secret store. The portal should continue treating client secrets as
one-time credentials.

## Command API

Add a new command action:

```text
lightapi.net/oauth/regenerateClientSecret/0.1.0
```

Suggested request:

```json
{
  "hostId": "01964b05-552a-7c4b-9184-6857e7f3dc5f",
  "clientId": "019e6235-1966-7322-bbcd-1cb432b5bb88",
  "aggregateVersion": 11,
  "ownerPositionId": "optional-position-id",
  "reason": "optional user supplied reason"
}
```

`aggregateVersion` is required. Secret regeneration modifies the existing Client
aggregate, so the command must use the same optimistic concurrency pattern as
other update commands. If the submitted version is stale, the command should fail
with a refresh/retry response instead of silently rotating a secret against an
older client view.

Suggested response:

```json
{
  "hostId": "01964b05-552a-7c4b-9184-6857e7f3dc5f",
  "clientId": "019e6235-1966-7322-bbcd-1cb432b5bb88",
  "clientSecret": "new-one-time-secret",
  "aggregateVersion": 12,
  "rotatedTs": "2026-05-28T14:22:00Z"
}
```

The clear `clientSecret` is response-only. It must not be included in the event
payload, logs, audit payloads, read-model query responses, or notification
payloads.

## Event Design

Add a new event type:

```text
ClientSecretRegeneratedEvent
```

Use the existing Client aggregate. The aggregate id should be derived from
`hostId` and `clientId`, the same way `ClientUpdatedEvent` is derived.

Event data should contain only non-recoverable secret material:

```json
{
  "hostId": "01964b05-552a-7c4b-9184-6857e7f3dc5f",
  "clientId": "019e6235-1966-7322-bbcd-1cb432b5bb88",
  "clientSecretEncrypted": "PBKDF2 verifier",
  "reason": "optional user supplied reason"
}
```

The command handler should keep two payloads:

- event payload: safe to persist and replay,
- response payload: includes the one-time clear secret.

This separation is important. If the current create-client event still includes
the clear `clientSecret`, harden `CreateClient` at the same time so the clear
secret is returned to the UI but not stored in `event_store_t`.

## Projection Behavior

Add persistence handling for `ClientSecretRegeneratedEvent`.

The projection should update only credential-related fields:

```sql
UPDATE auth_client_t
SET client_secret = ?,
    update_user = ?,
    update_ts = ?,
    aggregate_version = ?
WHERE host_id = ?
  AND client_id = ?
  AND active = TRUE
  AND aggregate_version < ?;
```

`update_user` and `update_ts` should come from standard CloudEvent metadata
rather than from user-editable event data. The event payload can include an
optional `reason`, but the actor performing the rotation must be taken from the
authenticated command context and persisted through the event metadata used by
the existing projection framework.

No database schema change is required for the first implementation. The existing
`auth_client_t.client_secret` column can continue storing the PBKDF2 verifier.
The existing `update_user`, `update_ts`, and `aggregate_version` fields are
enough to show that the client changed.

Optional future projection fields:

- `secret_update_user`
- `secret_update_ts`
- `secret_version`

Only add these if the UI needs to display secret rotation metadata separately
from normal client metadata updates.

## UI Design

Add a row action on the Auth Client page:

```text
Regenerate Secret
```

Enable it only when the current user can modify the client. Use the same owner
and `oauth-client-admin` rules as update/delete.

Recommended flow:

1. User clicks the row action.
2. Portal shows a confirmation dialog explaining that the old secret will stop
   working for future client authentication.
3. User confirms.
4. Portal calls `regenerateClientSecret`.
5. Portal shows a modal with:
   - `clientId`,
   - new `clientSecret`,
   - copy buttons for each field,
   - a "copied" acknowledgement before closing.
6. Portal refreshes the table row after the dialog closes.

The modal must make it clear that the secret is shown once. After it closes, the
secret cannot be recovered. If the user loses it again, they must regenerate
again.

## Token And Runtime Impact

Regenerating the client secret changes future client authentication. Existing
issued access tokens remain valid until their normal expiration unless token
revocation is implemented separately.

OAuth servers may cache client credential records to avoid database lookups on
every token request. The implementation must make the cache behavior explicit:

- Prefer subscribing to `ClientSecretRegeneratedEvent` and evicting the affected
  `(hostId, clientId)` credential entry immediately.
- If event-driven eviction is not available, use a short and documented cache TTL
  so the new secret starts working and the old secret stops working within an
  acceptable window.
- Add an integration test or operational runbook check for the cache behavior,
  because the command can succeed while token requests still use a stale cached
  verifier.

Current Java `oauth-kafka` behavior does not require client-secret cache
invalidation. Its token handler validates client secrets through
`PortalDbProvider.queryClientByClientId`, and its signing handler uses
`ClientUtil.queryClientByClientId`, which delegates to the same provider method.
The current `AuthPersistenceImpl.queryClientByClientId` implementation performs
a direct SQL lookup from `auth_client_t`. The `CacheStartupHookProvider` entries
in `oauth-kafka` config are commented out and there is no active client
credential cache in that service path.

If a future `oauth-kafka` deployment enables a client credential cache, it must
evict the affected `(hostId, clientId)` entry on `ClientSecretRegeneratedEvent`.
It should also evict on client delete and any future event that changes the
stored verifier or active state.

If the secret is being rotated because of compromise, the UI should guide the
user to review existing client tokens and revoke long-lived tokens if needed.
This should be a separate action, not an implicit side effect of secret
regeneration.

Secret regeneration should also emit an owner/admin notification. The event
should not include the clear secret, but it should notify the client owner and,
where appropriate, host or organization admins that a credential was rotated.
This gives the owner a chance to detect unexpected rotations or client takeover
attempts.

## Security Requirements

- Generate the secret with the same or stronger entropy as create-client.
- Store only a verifier generated by `HashUtil.generateStrongPasswordHash`.
- Never persist the clear secret in `event_store_t`, `auth_client_t`, logs,
  notifications, or audit detail payloads.
- Return the clear secret only in the immediate command response.
- Require write scope and the same ownership checks as update/delete.
- Allow regeneration only for active clients.
- Treat repeated clicks as separate rotations. If the response is lost, the
  previous clear secret cannot be recovered; the user must regenerate again.

## Implementation Checklist

`oauth-command`:

- Add `RegenerateClientSecret` command handler.
- Add `regenerateClientSecretRequest` and action metadata to `spec.yaml`.
- Require `aggregateVersion` and reject stale commands with a refresh/retry
  error.
- Generate `clientSecret` and `clientSecretEncrypted`.
- Build an event payload without the clear secret.
- Customize the response to include the clear secret once.
- Add handler tests that assert the event data excludes `clientSecret`.

`light-portal`:

- Add `CLIENT_SECRET_REGENERATED_EVENT` to `PortalConstants`.
- Update `EventTypeUtil` so the event maps to the Client aggregate id.
- Add `PortalDbProvider` dispatch for the new event type.
- Add `AuthPersistence.updateClientSecret`.
- Add persistence tests for monotonic replay and active-client checks.
- Add a side effect or notification processor entry so the client owner and
  relevant admins are notified when a secret is regenerated.

`light-oauth`:

- Verify whether client credential lookup is cached.
- If cached, evict `(hostId, clientId)` on `ClientSecretRegeneratedEvent` or
  document and test the maximum TTL for stale secret acceptance.
- Confirm old secret rejection and new secret acceptance after cache invalidation
  or TTL expiry.

`oauth-kafka`:

- Keep the current direct DB-backed client credential lookup, or add event-driven
  cache invalidation before enabling a client credential cache.
- If caching is introduced, evict `(hostId, clientId)` on
  `ClientSecretRegeneratedEvent` and client deletion.
- Add a regression test or operational check proving old secret rejection and new
  secret acceptance without waiting for process restart.

`oauth-query`:

- Prefer masking or omitting `clientSecret` from query responses. Query APIs
  should not return the stored verifier as if it were a usable secret.

`portal-view`:

- Add the row action and confirmation/result modal to `AuthClient.tsx`.
- Reuse ownership checks already used by update/delete.
- Add copy-to-clipboard handling and a copied acknowledgement.
- Refresh the table after a successful rotation.

`light-portal-doc`:

- Add user help for the Auth Client page explaining one-time secret display and
  regeneration.

## Test Plan

- Create client still returns a one-time secret and stores only a verifier.
- Regenerate secret returns a new one-time secret and updates only the verifier.
- Regenerate secret with a stale `aggregateVersion` fails and asks the user to
  refresh.
- Old secret fails client authentication after regeneration.
- New secret succeeds client authentication after regeneration.
- OAuth server cache invalidation or TTL behavior is verified.
- Existing metadata, owner mapping, provider mapping, and `client_id` remain
  unchanged.
- Unauthorized users cannot regenerate secrets for clients they do not own.
- Client owner or admin notification is emitted without leaking the secret.
- Replaying an older regeneration event does not overwrite a newer verifier.
- The UI does not expose stored verifier values from query responses.
