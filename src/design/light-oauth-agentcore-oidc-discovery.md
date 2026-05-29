# Light OAuth and OAuth Kafka AgentCore OIDC Discovery

## Problem

Issue https://github.com/lightapi/portal-service/issues/44 asks whether
`portal-service/apps/light-oauth` can support AWS AgentCore JWT inbound
authorization.

The current Rust `light-oauth` service and the Java `oauth-kafka` service can
mint RS256 JWT access tokens and serve provider keys from:

```text
GET /oauth2/{providerId}/keys
```

That is enough for internal services that are configured with an explicit
`jwksUrl`, but it is not enough for AWS AgentCore or AWS API Gateway HTTP JWT
authorizers. Those integrations discover the issuer metadata first, then use
the published `jwks_uri` to fetch signing keys.

The linked AWS AgentCore document requires a discovery URL ending in
`/.well-known/openid-configuration`, and validates configured audiences,
clients, scopes, and required claims against the JWT. The API Gateway debugging
document shows the same class of failure: without a valid OIDC discovery
endpoint, AWS cannot create or use the JWT authorizer correctly. The Authgear
OIDC guide summarizes the metadata fields expected by OIDC clients, including
`issuer`, `authorization_endpoint`, `token_endpoint`, `jwks_uri`,
`response_types_supported`, and signing algorithms.

## Current Rust Behavior

The Rust service currently has these relevant routes:

```text
POST /oauth2/{providerId}/code
POST /oauth2/{providerId}/token
GET  /oauth2/{providerId}/keys
```

The service has static token issuer and audience settings:

```yaml
jwtIssuer: ${jwt_issuer}
jwtAudience: ${jwt_audience}
```

Default values are URNs:

```yaml
jwt_issuer: "urn:com:networknt:oauth2:v1"
jwt_audience: "urn:com.networknt"
```

Generated access tokens currently include:

```text
iss: configured issuer
aud: configured audience
cid: client id
scp: array of scopes
```

The service does not currently publish:

- `/.well-known/openid-configuration`
- `/oauth2/{providerId}/.well-known/openid-configuration`
- an external/public issuer URL
- OIDC-compatible `client_id` and `scope` token claims
- a discovery document that maps the issuer to the existing JWKS endpoint

## Current Java Behavior

The Java implementation in `oauth-kafka` has the same public OAuth shape:

```text
GET  /oauth2/{providerId}/code
POST /oauth2/{providerId}/code
POST /oauth2/{providerId}/token
GET  /oauth2/{providerId}/keys
GET  /oauth2/{providerId}/deref/{token}
POST /oauth2/{providerId}/signing
```

The route mapping lives in:

```text
src/main/resources/config/handler.yml
```

The handler list and local values live in:

```text
src/main/resources/config/values.yml
```

The current JWKS handler is:

```text
src/main/java/com/networknt/oauth/handler/ProviderIdKeysGetHandler.java
```

It queries the provider by id, returns the `jwk` JSON from the database, and
returns `404` when the provider cannot be found. It does not publish discovery
metadata.

The Java token handler is:

```text
src/main/java/com/networknt/oauth/handler/ProviderIdTokenPostHandler.java
```

Its token claim helpers currently emit Light-specific claims:

```text
cid: client id
scp: array of scopes
```

The signing endpoint already emits `client_id` for signed custom payloads:

```text
src/main/java/com/networknt/oauth/handler/ProviderIdSigningPostHandler.java
```

However, that endpoint still needs the same reserved-claim behavior if it is
used for AgentCore-facing tokens, because its custom payload is applied after
the initial `client_id` claim.

The Java OpenAPI document also only exposes `/{providerId}/keys`; it has no
discovery route:

```text
src/main/resources/config/openapi.yaml
```

## Gaps

### 1. Missing OIDC Discovery

AWS AgentCore expects a discovery URL matching:

```text
^.+/\.well-known/openid-configuration$
```

Both `light-oauth` and `oauth-kafka` only expose
`/oauth2/{providerId}/keys`. AWS does not know how to discover that
provider-specific JWKS URL unless the OAuth service publishes a metadata
document with `jwks_uri`.

### 2. Issuer Is Not a Public HTTPS URL

The default issuer is a URN. AgentCore discovery expects the discovery URL to
point to an issuer URL, and the decoded token `iss` must match the issuer
metadata. API Gateway JWT authorizers have the same practical requirement.

For enterprise deployments, the issuer should be the externally reachable URL
seen by AWS, not the container DNS name or localhost address.

### 3. Token Claims Do Not Match AgentCore Names

AgentCore validates:

- `aud` against `allowedAudience`
- `client_id` against `allowedClients`
- `scope` against `allowedScopes`

Current Rust and Java token flows expose the client as `cid` and scopes as
`scp`. That is useful for existing Light consumers but does not satisfy AWS
claim names by default.

### 4. Provider and Tenant Addressing Is Ambiguous

The existing JWKS route is provider-scoped. OIDC discovery commonly uses the
issuer base URL plus `/.well-known/openid-configuration`, but `light-oauth`
supports multiple providers. We need an explicit rule for how a discovery URL
selects a provider.

### 5. Public URL Construction Is Not Configurable

The service runs behind gateways, Docker networks, and potentially AWS-facing
domains. Discovery metadata must publish public URLs such as:

```text
https://oauth.example.com/oauth2/{providerId}/keys
```

It must not publish internal URLs such as:

```text
https://light-oauth:6881/oauth2/{providerId}/keys
```

### 6. JWKS and Signing Key Consistency Needs a Test Contract

Tokens are signed with rows from `auth_provider_key_t`, while `/keys` returns
the provider `jwk` from `auth_provider_t`. The implementation should guarantee
that the JWT header `kid` is present in the returned JWKS for the same provider.
That guarantee matters more once external AWS services cache the discovery and
JWKS responses.

## Goals

- Let AWS AgentCore use Rust `light-oauth` or Java `oauth-kafka` as a JWT
  bearer token issuer.
- Publish OIDC-compatible discovery metadata for each provider in both
  implementations.
- Keep existing `/oauth2/{providerId}/keys` and Light-specific `cid`/`scp`
  claims working.
- Avoid exposing internal Docker or Kubernetes service names in public metadata.
- Keep issuer, audience, and discovery URLs deterministic across environments.
- Add tests that prove discovery, JWKS, and signed token claims line up.

## Non-Goals

- Do not implement full OIDC identity-provider behavior in the first phase.
- Do not add dynamic client registration.
- Do not replace existing explicit `jwksUrl` verification used by internal
  services.
- Do not remove Light-specific token claims.
- Do not solve AgentCore outbound OAuth credential providers in this change.

## Recommended Design

Add provider-scoped OIDC discovery to Rust `light-oauth` and Java
`oauth-kafka`, and make token output compatible with both Light and AWS
AgentCore.

### Routes

Add the provider-scoped route first:

```text
GET /oauth2/{providerId}/.well-known/openid-configuration
```

This avoids ambiguity because the route contains the provider identifier. The
issuer for this route should be:

```text
{publicIssuerBaseUrl}/oauth2/{providerId}
```

The discovery URL becomes:

```text
{publicIssuerBaseUrl}/oauth2/{providerId}/.well-known/openid-configuration
```

The JWKS URI becomes:

```text
{publicIssuerBaseUrl}/oauth2/{providerId}/keys
```

Optionally add a root route for a configured default provider:

```text
GET /.well-known/openid-configuration
```

Only enable the root route when `defaultProviderId` is configured. Otherwise,
return `404` to avoid publishing metadata for the wrong tenant or provider.

### Discovery Document

Return `application/json` and a compact OIDC-compatible document:

```json
{
  "issuer": "https://oauth.example.com/oauth2/AZZRJE52eXu3t1hseacnGQ",
  "authorization_endpoint": "https://oauth.example.com/oauth2/AZZRJE52eXu3t1hseacnGQ/code",
  "token_endpoint": "https://oauth.example.com/oauth2/AZZRJE52eXu3t1hseacnGQ/token",
  "jwks_uri": "https://oauth.example.com/oauth2/AZZRJE52eXu3t1hseacnGQ/keys",
  "response_types_supported": ["code"],
  "grant_types_supported": [
    "authorization_code",
    "password",
    "refresh_token",
    "client_credentials",
    "urn:ietf:params:oauth:grant-type:token-exchange"
  ],
  "token_endpoint_auth_methods_supported": [
    "client_secret_basic",
    "client_secret_post"
  ],
  "scopes_supported": ["portal.r"],
  "claims_supported": [
    "iss",
    "aud",
    "exp",
    "iat",
    "nbf",
    "jti",
    "client_id",
    "scope",
    "cid",
    "scp"
  ],
  "subject_types_supported": ["public"],
  "id_token_signing_alg_values_supported": ["RS256"]
}
```

`id_token_signing_alg_values_supported` is included for compatibility because
many discovery consumers expect it, even if `light-oauth` does not issue ID
tokens yet. The design should document this as discovery compatibility metadata,
not as a promise that ID-token grant flows are complete.

### Configuration

Add explicit public URL configuration:

```yaml
oidcDiscoveryEnabled: ${oidc_discovery_enabled:true}
publicIssuerBaseUrl: ${public_issuer_base_url}
defaultProviderId: ${default_provider_id:}
```

Example local values:

```yaml
public_issuer_base_url: "https://localhost:6882"
default_provider_id: "AZZRJE52eXu3t1hseacnGQ"
```

Example enterprise values:

```yaml
public_issuer_base_url: "https://oauth.customer.example.com"
default_provider_id: "AZZRJE52eXu3t1hseacnGQ"
```

When `publicIssuerBaseUrl` is configured, generated token `iss` should default
to:

```text
{publicIssuerBaseUrl}/oauth2/{providerId}
```

Keep `jwtIssuer` for backward compatibility. If both are set, use a strict rule:

1. If `jwtIssuer` is set to a non-default value, keep using it and make
   discovery `issuer` equal to that value.
2. If `jwtIssuer` is absent or equal to the current default URN, use the
   provider-scoped public issuer URL.
3. Log a startup warning if discovery is enabled but the issuer is not an
   HTTPS URL, unless running in local development.

### Token Claim Compatibility

Extend `JwtClaims` without removing existing fields:

```text
cid: existing Light client id claim
scp: existing Light scope array claim
client_id: OIDC/AWS client id claim
scope: OIDC/AWS space-delimited scope claim
```

For a client token, emit:

```json
{
  "client_id": "019c9273-2663-7a9e-82f4-94f9f5f79c3a",
  "scope": "portal.r",
  "cid": "019c9273-2663-7a9e-82f4-94f9f5f79c3a",
  "scp": ["portal.r"]
}
```

For user grants, also emit a stable `sub` value. Prefer the portal user id if
the token represents a user; otherwise use the client id for client credentials
tokens. Keep the existing `uid` and `uty` claims.

Reserved claim names from request `extra_claims` must not override:

```text
iss, aud, exp, iat, nbf, jti, kid, client_id, scope, cid, scp, sub
```

If an AgentCore runtime is configured with required custom claims, support them
through existing client `custom_claim` configuration or a new allowlisted static
claim configuration. For example, a customer that wants Cognito-like access
token semantics could configure:

```json
{
  "token_use": "access"
}
```

Do not hard-code Cognito-specific claims globally unless the Light token
contract explicitly adopts them.

### Scope Source

The token endpoint already resolves requested scope against the configured
client scope. Discovery can publish a conservative `scopes_supported` value:

- Use a configured `oidcScopesSupported` list when set.
- Otherwise publish the union of active client scopes for the provider.
- If querying client scopes is not added in phase 1, omit
  `scopes_supported` or publish a configured static list.

For AgentCore, the critical runtime behavior is that the token includes the
space-delimited `scope` claim expected by `allowedScopes`.

### JWKS Response

Keep:

```text
GET /oauth2/{providerId}/keys
```

Add response headers:

```text
Content-Type: application/jwk-set+json
Cache-Control: public, max-age=300
```

Five minutes is a reasonable starting cache TTL. It limits repeated AWS fetches
while keeping key rotation practical. If existing clients depend on
`application/json`, `application/jwk-set+json` remains JSON-compatible; test the
known internal verifier before changing this header.

Add tests that assert:

- a token signed for provider `P` has a `kid`
- `/oauth2/P/keys` returns a JWKS containing that `kid`
- discovery `jwks_uri` returns that same key set

### AgentCore Configuration Example

An AgentCore runtime should be configured with the provider-scoped discovery
URL:

```json
{
  "customJWTAuthorizer": {
    "discoveryUrl": "https://oauth.customer.example.com/oauth2/AZZRJE52eXu3t1hseacnGQ/.well-known/openid-configuration",
    "allowedClients": ["019c9273-2663-7a9e-82f4-94f9f5f79c3a"],
    "allowedAudience": ["urn:com.networknt"],
    "allowedScopes": ["portal.r"]
  }
}
```

The token must then contain:

```json
{
  "iss": "https://oauth.customer.example.com/oauth2/AZZRJE52eXu3t1hseacnGQ",
  "aud": "urn:com.networknt",
  "client_id": "019c9273-2663-7a9e-82f4-94f9f5f79c3a",
  "scope": "portal.r"
}
```

If the customer wants `allowedAudience` to be the AgentCore runtime or an API
identifier instead of `urn:com.networknt`, make `jwtAudience` environment
specific and align it with the AgentCore authorizer configuration.

## Implementation Plan

### Phase 1: Discovery Metadata

- Rust: add `publicIssuerBaseUrl`, `oidcDiscoveryEnabled`, and
  `defaultProviderId` to `ServerConfig`.
- Java: add `publicIssuerBaseUrl`, `oidcDiscoveryEnabled`,
  `defaultProviderId`, and optional `oidcScopesSupported` to `OAuthConfig`.
- Rust: add provider-scoped discovery route in `apps/light-oauth/src/main.rs`.
- Java: add `ProviderIdOpenIdConfigurationGetHandler` and register it in
  `handler.yml` and `values.yml`.
- Java: add the provider-scoped discovery path to `openapi.yaml` and explicitly
  mark it as a public endpoint (`security: []`) so the endpoint remains public
  if `JwtVerifyHandler` is included in the route chain.
- Build discovery URLs from the public issuer base URL and provider id.
- Return `404` if discovery is disabled or the provider does not exist.
- Add tests for discovery JSON shape and URL construction.
- Update local/dev config examples with a public issuer base URL.

### Phase 2: AgentCore Claim Compatibility

- Rust: add `client_id`, `scope`, and `sub` to `JwtClaims`.
- Java: update `ProviderIdTokenPostHandler` claim builders:
  `mockCcClaims`, `mockBsClaims`, and `mockAcClaims`.
- Keep `cid` and `scp` in both implementations.
- Add a reserved-claim guard for flattened/custom claims in both
  implementations.
- Java: decide whether `ProviderIdSigningPostHandler` should use put-if-absent
  behavior for reserved claims, or document that the signing endpoint is for
  trusted callers that control the full JWT payload.
- Add tests that decode a generated token and assert AgentCore claim names.
- Add a sample AgentCore authorizer configuration to docs/config notes.

### Phase 3: JWKS and Rotation Contract

- Add tests proving the token `kid` is available in `/keys`.
- Decide whether `/keys` should return `application/jwk-set+json` immediately
  or stay `application/json` for one release.
- Add `Cache-Control` with a short TTL.
- Add an operational check that warns if the current signing key is missing
  from the published provider JWKS.
- Java: keep `ProviderIdKeysGetHandler` behavior aligned with the Rust
  `/keys` endpoint, including status codes and cache headers.

### Phase 4: Optional Root Discovery

- Add `GET /.well-known/openid-configuration` only when `defaultProviderId` is
  configured.
- Make the root metadata identical to the provider-scoped metadata for the
  default provider.
- Document that multi-provider enterprise deployments should prefer
  provider-scoped discovery URLs.

## Java Implementation Notes

The Java implementation should stay structurally close to the existing
`oauth-kafka` handler model.

Add a new handler:

```text
src/main/java/com/networknt/oauth/handler/ProviderIdOpenIdConfigurationGetHandler.java
```

Register it in `handler.yml`:

```yaml
- path: '/oauth2/{providerId}/.well-known/openid-configuration'
  method: 'GET'
  exec:
    - default
    - openidConfigurationGet
```

*Note: Ensure that this endpoint is marked with `security: []` in `openapi.yaml`
so that the endpoint remains public if `JwtVerifyHandler` is included in the route
chain (which may happen in enterprise overrides).*

Register the handler alias in `values.yml`:

```yaml
- com.networknt.oauth.handler.ProviderIdOpenIdConfigurationGetHandler@openidConfigurationGet
```

Extend `oauth.yml` and `OAuthConfig`:

```yaml
oidcDiscoveryEnabled: ${oauth.oidcDiscoveryEnabled:true}
publicIssuerBaseUrl: ${oauth.publicIssuerBaseUrl:}
defaultProviderId: ${oauth.defaultProviderId:}
oidcScopesSupported: ${oauth.oidcScopesSupported:}
```

Use `Config.getInstance().getJsonObjectConfig(OAuthConfig.CONFIG_NAME,
OAuthConfig.class)` or the local equivalent pattern already used by the token
handler to load this configuration.

The discovery handler should:

- read `{providerId}` from `exchange.getQueryParameters()`
- return `404` when discovery is disabled or the provider lookup fails
- build `issuer`, `token_endpoint`, `authorization_endpoint`, and `jwks_uri`
  from `publicIssuerBaseUrl` plus `/oauth2/{providerId}`
- return `application/json`
- avoid using `Host` or `X-Forwarded-*` headers as the default source of the
  public issuer URL

For token claims, change Java helper methods as follows:

```text
mockCcClaims:
  cid, scp, client_id, scope, sub=clientId

mockBsClaims:
  cid, scp, client_id, scope, sub=clientId

mockAcClaims:
  uid, uty, cid, scp, client_id, scope, sub=userId
```

Keep existing Java tests for legacy claims, and add new tests that decode the
JWT and assert `client_id`, `scope`, and `sub`.

## Validation Checklist

For a customer-facing AgentCore setup, validate:

```text
curl -k https://oauth.customer.example.com/oauth2/{providerId}/.well-known/openid-configuration
curl -k https://oauth.customer.example.com/oauth2/{providerId}/keys
```

Then decode a minted token and confirm:

- `iss` equals discovery `issuer`
- discovery URL ends with `/.well-known/openid-configuration`
- discovery `jwks_uri` is externally reachable by AWS
- JWT header `kid` exists in the JWKS
- `aud` matches AgentCore `allowedAudience`
- `client_id` matches AgentCore `allowedClients`
- `scope` contains each required AgentCore `allowedScopes` entry
- token is signed with `RS256`
- certificate chain for the public issuer URL is trusted by AWS

For API Gateway HTTP authorizer deployments, enable the equivalent of
`FailOnWarnings` so discovery failures fail deployment loudly.

## Security Notes

- Do not derive public issuer URLs from untrusted request headers by default.
  Use explicit configuration. If proxy headers are supported later, trust them
  only behind a configured gateway.
- Prefer HTTPS public issuer URLs. Local development can allow localhost and
  self-signed certificates, but enterprise AgentCore setup should use a public
  CA trusted by AWS.
- Do not let custom token claims override reserved claims.
- Keep short-lived access tokens for AgentCore invocation unless the customer
  has a specific long-lived service token use case.
- Keep client secrets out of browser flows. Use backend-mediated token exchange
  or confidential clients where needed.
- **CORS**: While AgentCore calls the discovery endpoint server-to-server, if
  any SPAs need to read this metadata, ensure that the provider-scoped and optional
  root discovery paths are placed on a handler chain that includes `cors`
  (since `cors` is not in the `default` chain by default in `oauth-kafka`), and
  ensure `cors.yml` allows `GET` on these paths.

## Resolved Questions

- **Should `jwtAudience` remain a single string, or should `light-oauth` support
  multiple audiences in `aud` for AgentCore plus existing Light services?**
  *Resolution*: Support either a string or an array of strings for `aud`, but keep
  the default as the existing single string. The current Rust issuer and verifier
  are string-shaped and may fail to decode tokens if `aud` becomes an unconditional array.
  Update the verifiers and tests to support an array before enabling multi-audience
  output by default.
- **Should `auth_client_t.client_id` remain the only client identifier, or do we
  need an external client alias for customers that cannot use UUID client ids in
  AWS configuration?**
  *Resolution*: Keep it as the only identifier for Phase 1 to reduce scope. If AWS
  AgentCore restricts UUID formats, a client alias feature can be proposed in Phase 2.
- **Should the service expose OAuth 2.0 Authorization Server Metadata at
  `/.well-known/oauth-authorization-server` in addition to OIDC discovery?**
  *Resolution*: No, OIDC discovery (`openid-configuration`) is sufficient for AgentCore
  and most standard OIDC consumers.
- **Should discovery include only configured scopes, or query active client scopes
  dynamically per provider?**
  *Resolution*: Use a static configured list (`oidcScopesSupported`) for Phase 1.
  Querying active scopes dynamically could introduce performance overhead for discovery.
- **Should key rotation update `auth_provider_t.jwk` transactionally with
  `auth_provider_key_t`, or should `/keys` be generated directly from
  `auth_provider_key_t`?**
  *Resolution*: They must be updated transactionally or `/keys` should generate
  its payload directly from `auth_provider_key_t`. Serving mismatched JWKS metadata
  will break token verification. Generating directly from `auth_provider_key_t`
  is the most reliable design. The dynamic JWKS must include every active public
  verification key that can validate currently valid tokens (including current,
  previous rotation keys, and long-lived keys if long-lived tokens are still issued).
  It must never expose private key material.

## Source Links

- GitHub issue: https://github.com/lightapi/portal-service/issues/44
- AWS AgentCore OAuth and JWT inbound auth:
  https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-oauth.html
- AWS API Gateway OIDC JWT authorizer debugging:
  https://loige.co/debugging-api-gateway-http-oidc-jwt-authorizer/
- OIDC discovery field overview:
  https://www.authgear.com/post/well-known-openid-configuration/
