# System Integration

System integrations must preserve the same identity and tenant boundaries as
interactive portal workflows. The integration token is not only an access
credential; it is also the source of audit metadata, event metadata, row
filtering, and host scoping.

## Command Side

The command side uses event sourcing. Every accepted command writes one or more
domain events, and those events are later projected into query-side tables.
Because events become the durable system of record, command calls need a stable
user identity and host identity.

For command APIs, use an authorization code token whenever possible. The token
must contain the real portal user id so command handlers can derive the correct
`userId`, host, nonce, and CloudEvent metadata. This is the preferred path for
browser flows, operator tools, and integrations that can act on behalf of a
known user.

If the integration has no user session in the request context, do not submit
anonymous command events. First onboard a real user in the system for the
integration actor or service account. That user becomes the durable audit
principal for the commands emitted by the integration.

After the user is onboarded, create an auth client for the integration and set
custom claims that carry the command identity:

```json
{
  "host": "<host-id>",
  "elm": "<integration-user-email>",
  "uid": "<integration-user-id>",
  "uty": "<user-type>"
}
```

The `uid` claim must reference the onboarded user. The `host` claim must match
the tenant boundary where commands are allowed to run. The `elm` and `uty`
claims should match the onboarded user's email and user type so downstream
authorization, audit, and support workflows can identify the actor without
guessing.

For an integration auth client whose type is trusted, the client application can
call Light OAuth with the `client_credentials` grant type when the auth client
has these custom claims configured. Light OAuth issues a token that carries the
custom claims, allowing the token to act as an id-token-like access token for
command APIs, similar to the user-bearing token produced by the authorization
code grant. This path is only acceptable for trusted client types because the
client, not an interactive browser session, is asserting the user and host
identity through the auth client configuration.

Command-side integration rules:

- Prefer an authorization code token tied to the real interactive user.
- Use a dedicated onboarded integration user only when no user session exists.
- For non-session integrations, use a trusted auth client with custom claims and
  request the token from Light OAuth with `grant_type=client_credentials`.
- Do not use a token that lacks a usable `userId`/`uid` for event-sourced
  commands.
- Do not allow non-trusted clients to mint user-bearing command tokens from
  client credentials.
- Keep host ownership explicit; never infer host scope from the client id alone.
- Treat the auth client and custom claims as deployment configuration, not as a
  substitute for user onboarding.

## Query Side

The query side serves read models built from command-side events and operational
tables. Query APIs do not create domain events, do not allocate command nonces,
and should not mutate event-sourced state.

Query integrations still need authorization and tenant scoping. The request
token must provide enough identity to determine the host and the effective user
or service account. For user-scoped reads, use the same authorization code token
or integration-user token described for the command side so row and column
filters can apply consistently.

If authorization code flow is not available for a query integration, the
`client_credentials` flow is acceptable only for auth clients whose type is
trusted. The token must carry `host`, `sid`, and, when environment-specific data
is requested, `env`. Here `sid` is the service id for the gateway, agent, or
other Light-Fabric runtime calling portal-query. Query handlers must compare
these claims with the requested `hostId`, `serviceId`, and optional `envTag`
before returning service-scoped data.

Light-Fabric ecosystem components such as gateways and agents may use a
long-lived token for query-side access when the token was issued through this
trusted `client_credentials` path. That access is not general portal read
access. It is limited to query endpoints built for those runtime components,
such as gateway, agent, discovery, or catalog endpoints, and those endpoints
must enforce the claim match before returning data.

For host-scoped or service-level reads, a client token can be used only when the
auth client type is trusted and the token carries the required host, service,
and environment claims. The query service should apply the same host boundary as
the command side and return only data visible to that actor. A missing user
session may reduce the allowed result set, but it must not broaden access.

Query-side integration rules:

- Read from projected/query tables; do not write command events from query
  handlers.
- Resolve host scope from the validated token claims and request parameters.
- When authorization code flow is unavailable, accept `client_credentials` only
  from auth clients whose type is trusted.
- Require `host` and `sid` token claims; require `env` when the endpoint or
  request is environment-scoped.
- Match token `host`, `sid`, and optional `env` to requested `hostId`,
  `serviceId`, and optional `envTag`.
- Allow long-lived Light-Fabric runtime tokens only on endpoints designed for
  gateways, agents, and similar ecosystem components.
- Do not use long-lived runtime tokens for broad user-facing query access.
- Apply user, role, position, group, attribute, and fine-grained filters when
  the endpoint requires them.
- Use the onboarded integration user for auditability when a human user is not
  present.
- Keep query tokens least-privileged; read-only integrations should not receive
  command scopes.
