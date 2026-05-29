# SID and Host Verification

## Problem

GitHub issue https://github.com/lightapi/portal-service/issues/39 reports that
`config-server` accepted a valid JWT whose service identity did not match the
requested service configuration.

The reported token contains:

```json
{
  "iss": "urn:com:networknt:oauth2:v1",
  "aud": "urn:com.networknt",
  "cid": "019e2825-146d-7a00-b0e8-3671158bb32a",
  "scp": ["portal.r", "portal.w"],
  "host": "01964b05-552a-7c4b-9184-6857e7f3dc5f",
  "sid": "com.networknt.light-gateway-1.0.0"
}
```

The request used a different service id:

```text
serviceId=com.networknt.ai.gateway-1.0.0
```

The token is cryptographically valid, but it must not authorize access to a
different service's configuration. Signature, issuer, audience, and scope
validation prove that the token is valid; they do not prove that the token is
valid for the requested `host` and `serviceId`.

The security contract for runtime service tokens is now:

```text
token.host == requested host context
token.sid == requested service context
token.env == requested environment context, when envTag is present
```

For config-server, the requested host context is the `host` query parameter.
For controller registry registration, the requested host context is the
controller's configured `hostId`, because `service/register` does not carry a
separate `hostId`.

## Original Gaps

### Rust `portal-service/apps/config-server`

The Rust config server verifies the bearer token through `JwtVerifier` and binds
the decoded claims into each handler:

```rust
async fn get_configs(
    State(state): State<AppState>,
    _claims: Claims,
    Query(query): Query<ConfigQuery>,
) -> Response
```

The handlers then read `host` and `service_id` from the query and call the read
model. They did not compare token `host` with `query.host`, and did not compare
token `sid` with `query.service_id`.

Affected endpoints:

```text
GET /config-server/configs
GET /config-server/certs
GET /config-server/files
```

### Java `light-config-server`

The Java config server routes the same three endpoints through the `default`
chain, which includes `JwtVerifyHandler`. The Light-4j security handler stores
the verified `JwtClaims` in `AUDIT_INFO` under `Constants.SUBJECT_CLAIMS`.

The business handlers then read `host` and `serviceId` from query parameters
and call the database helpers. They did not compare token `host` with request
`host`, and did not compare token `sid` with request `serviceId`.

Affected handlers:

```text
ConfigsGetHandler
CertsGetHandler
FilesGetHandler
```

### Related Controller Registry Behavior

The controller registry paths already perform service identity binding during
runtime registration, but they must use the same strict `sid` and `host`
contract as config-server.

The registry request carries `serviceId` in the `service/register` payload. It
does not carry a separate `hostId`; registry writes are scoped to the
controller's configured host id. The integration token must carry both `sid`
and `host`. The registration must be rejected before the runtime instance is
stored when the token has no `sid`, a blank `sid`, or a `sid` that differs from
the requested `serviceId`. It must also be rejected when the token has no
`host`, a blank `host`, or a `host` that differs from the configured controller
host id.

`sub` is not an acceptable fallback for registry authorization. It can still be
used by other OAuth flows as the subject, but the registry authorization check
must bind the explicit service authorization claim:

```text
token.sid == register.params.serviceId
token.host == controller.config.hostId
```

In `controller-rs`, this rule belongs in `ServiceJwtVerifier::validate`, before
`handle_socket` persists the runtime instance. In Java `light-controller`, it
belongs in `ServiceJwtValidator.validateServiceToken`, called by
`MicroserviceEndpoint.register` with the requested `serviceId`.

The controller implementations should check `env` when the request provides
`envTag`, but that check is an additional constraint. It does not replace the
mandatory `sid` to `serviceId` comparison or the mandatory `host` to controller
`hostId` comparison.

## Security Requirement

For any controller registry request or config-server request that asks for a
service-scoped resource with `serviceId`, the token must contain a `sid` claim
equal to that requested `serviceId`.

For any config-server request with a `host` query parameter, the token must
contain a `host` claim equal to that requested `host`.

For any controller registry `service/register` request, the token must contain
a `host` claim equal to the controller's configured `hostId`.

For any config-server request or controller registry `service/register` request
with a non-blank `envTag`, the token must contain an `env` claim equal to that
requested `envTag`.

The request should be rejected when:

- `serviceId` is present and non-blank, but token `sid` is missing.
- `serviceId` is present and non-blank, but token `sid` is blank.
- `serviceId` is present and non-blank, but token `sid` differs from it.
- `host` is present and non-blank, but token `host` is missing.
- `host` is present and non-blank, but token `host` is blank.
- `host` is present and non-blank, but token `host` differs from it.
- `envTag` is present and non-blank, but token `env` is missing.
- `envTag` is present and non-blank, but token `env` is blank.
- `envTag` is present and non-blank, but token `env` differs from it.

The request may continue to use the existing product-level path when no
`serviceId` is supplied. Product-level requests are not service-scoped and
should not be forced to match `sid` until the product-level authorization model
is explicitly designed.

The same exception does not apply to controller registry registration because
`service/register` always carries a requested `serviceId`.

## Goals

- Prevent one service token from downloading another service's config, certs,
  or files.
- Prevent one service token from registering a runtime instance for another
  service id.
- Implement the same authorization rule in Rust `config-server` and Java
  `light-config-server`.
- Implement the same authorization rule in Rust `controller-rs` and Java
  `light-controller`.
- Keep existing JWT signature, issuer, audience, and scope checks unchanged.
- Keep the rule local to config-server handlers, because only they know the
  requested `host` and `serviceId`.
- Return a clear authorization failure before any database lookup is executed.

## Implemented Behavior

The implementation applies the same authorization contract in all four runtime
paths:

```text
token.host == requested host context
token.sid == requested service context
```

The implemented paths are:

```text
controller-rs/src/auth.rs
light-controller/src/main/java/com/networknt/controller/auth/ServiceJwtValidator.java
portal-service/crates/internal-auth/src/lib.rs
portal-service/apps/config-server/src/main.rs
light-config-server/src/main/java/com/networknt/configserver/util/ServiceIdAuthorizationUtil.java
```

For Rust `controller-rs`, `ServiceJwtVerifier::validate` now requires a
non-blank `sid` and compares it to the registration `serviceId`. It also
requires a non-blank `host` and compares it to the controller `hostId`. When
registration includes `envTag`, it requires token `env` and compares it to that
`envTag`.

For Java `light-controller`, `ServiceJwtValidator.validateServiceToken` applies
the same checks when `MicroserviceEndpoint.register` passes the requested
`serviceId`.

For Rust config-server, `internal-auth::Claims` now exposes explicit optional
`sid`, `host`, and `env` fields. The `configs`, `certs`, and `files` handlers
call `authorize_request_context` before invoking the read model.

For Java `light-config-server`, `ServiceIdAuthorizationUtil` extracts verified
claims from `AUDIT_INFO` and applies the same host and SID checks before
`ConfigsGetHandler`, `CertsGetHandler`, or `FilesGetHandler` calls the database
helper.

The focused implementation tests cover missing and mismatched `host`, missing
and mismatched `sid`, missing and mismatched `env` when `envTag` is requested,
blank values, whitespace trimming, and case-sensitive identifier comparison.

## Non-Goals

- Do not replace JWT verification middleware.
- Do not redesign OAuth token issuance.
- Do not require `sid` for product-level requests that do not carry
  `serviceId`.
- Do not require `env` when the request omits `envTag`.
- Do not trust request headers such as `X-Service-Id` as a substitute for the
  JWT claim.
- Do not use `sub` as a fallback for service-scoped controller registry or
  config-server authorization.

## Token Contract

Trusted service tokens used for config-server startup access should include:

```json
{
  "host": "<host-id>",
  "sid": "<service-id>",
  "env": "<optional-environment>"
}
```

`sid` is the runtime service id that the token is allowed to bootstrap. For
example:

```json
{
  "sid": "com.networknt.ai.gateway-1.0.0"
}
```

`sid` must be treated as a reserved authorization claim. It should be generated
from trusted client configuration or a trusted token request path, not from
unvalidated caller input.

## Request Contract

For service-scoped requests:

```text
GET /config-server/configs?host=...&serviceId=com.networknt.ai.gateway-1.0.0&envTag=dev
GET /config-server/certs?host=...&serviceId=com.networknt.ai.gateway-1.0.0&envTag=dev
GET /config-server/files?host=...&serviceId=com.networknt.ai.gateway-1.0.0&envTag=dev
```

The authorization rule is:

```text
token.host == request.host
token.sid == request.serviceId
```

The comparisons should trim surrounding whitespace but should otherwise be exact
and case-sensitive. Host ids and service ids are identifiers, not display names.

For requests without `serviceId`, the SID rule is not applied:

```text
GET /config-server/configs?host=...&productId=lg&productVersion=1.5.1&envTag=dev
```

Those requests should continue through the existing product-level behavior, but
the host binding rule still applies:

```text
token.host == request.host
```

For any request with a non-blank `envTag`, including product-level requests,
the environment binding rule also applies:

```text
token.env == request.envTag
```

## Recommended Design

Add a small config-server authorization helper in both implementations, and
tighten the controller registry validators to use the same `sid` binding rule.

The helper should accept the decoded JWT claims and the parsed query object, and
return either:

- success when there is no service-scoped request or the `sid` matches
- an authorization response when the request is service-scoped and invalid

Pseudo logic:

```text
requestedHost = trim(query.host)
tokenHost = trim(claim.host)
if tokenHost is empty:
    reject 403

if tokenHost != requestedHost:
    reject 403

requestedServiceId = trim(query.serviceId)
if requestedServiceId is not empty:
    tokenServiceId = trim(claim.sid)
    if tokenServiceId is empty:
        reject 403

    if tokenServiceId != requestedServiceId:
        reject 403

requestedEnvTag = trim(query.envTag)
if requestedEnvTag is not empty:
    tokenEnv = trim(claim.env)
    if tokenEnv is empty:
        reject 403

    if tokenEnv != requestedEnvTag:
        reject 403

allow
```

Run this check before `getSnapshotConfigs`, `getSnapshotCerts`,
`getSnapshotFiles`, or any live config query helper.

For controller registry registration, `serviceId` is not optional and the
expected host is the controller's configured `hostId`. The same comparisons
should run after signature, issuer, and audience validation and before any
runtime instance lookup or persistence. A valid `sub` with a missing `sid` must
still be rejected, and a token with no `host` must also be rejected.

### Response Status

Use `403 Forbidden` for SID or host-binding failures.

The JWT has already passed authentication. The failure is authorization: the
token is valid but not allowed to access the requested host or service
configuration or environment.

Suggested response body:

```text
Token sid does not match requested serviceId
Token host does not match requested host
Token env does not match requested envTag
```

Avoid echoing the full token or all claims in the response. Logging the
requested `host`, token `host`, requested `serviceId`, and token `sid` at warn
level is useful for operations. When `envTag` is present, also log requested
`envTag` and token `env`.

## Controller Implementation

### Rust `controller-rs`

`ServiceJwtVerifier::validate` now makes service registration read only
`claims.sid`, trims it, rejects blank or missing values, and compares it with
`ServiceRegistrationParams.service_id`.

The same validation path requires `claims.host`, trims it, and compares
it with `Settings.host_id`. Do not fall back to `claims.sub` for registry
authorization.

When `ServiceRegistrationParams.env_tag` is present and non-blank, the same
validation path requires a non-blank `claims.env` and compares it with the
requested `envTag`.

The WebSocket registration tests cover:

- a token with `sid` and no `sub` still registers
- a token with matching `sub` but missing `sid` is rejected
- a token with matching `sub` but mismatched `sid` is rejected
- a token with missing or mismatched `host` is rejected
- a request with `envTag` and missing or mismatched token `env` is rejected

### Java `light-controller`

`ServiceJwtValidator.validateServiceToken` now requires `sid` when
`MicroserviceEndpoint.register` passes a requested `serviceId`, and compares it
with that `serviceId`.

The validator also requires `host` and compares it with
`ControllerRuntimeConfig.hostId`. Do not fall back to `JwtClaims.getSubject()`
for registry authorization.

When `envTag` is present and non-blank, the validator also requires `env` and
compares it with that `envTag`.

The registration test token builders now include `sid` and `host` for normal
service JWTs. Regression tests cover missing and mismatched `sid`, plus missing
and mismatched `host`, plus missing and mismatched `env` when `envTag` is
requested.

## Rust Config-Server Implementation

### Claims

`internal-auth::Claims` now exposes `sid` and `host` as explicit optional
fields:

```rust
pub sid: Option<String>,
pub host: Option<String>,
pub env: Option<String>,
```

This keeps the authorization path readable and avoids treating `sid` and
`host` as generic extension claims. They are first-class authorization claims
for config-server and controller runtime access.

### Handler Flow

Each handler uses `claims` rather than `_claims`:

```rust
async fn get_configs(
    State(state): State<AppState>,
    claims: Claims,
    Query(query): Query<ConfigQuery>,
) -> Response {
    if let Err(response) = authorize_request_context(
        &claims,
        &query.host,
        query.service_id.as_deref(),
        query.env_tag.as_deref(),
    ) {
        return response;
    }

    ...
}
```

The shared helper is:

```rust
fn authorize_request_context(
    claims: &Claims,
    requested_host: &str,
    requested_service_id: Option<&str>,
    requested_env_tag: Option<&str>,
) -> Result<(), Response>
```

Apply the helper to:

```text
get_configs
get_certs
get_files
```

### Rust Tests

The helper tests cover:

- allows a matching `sid`
- allows a matching `host`
- allows an absent `serviceId`
- rejects missing `host`
- rejects mismatched `host`
- rejects missing `sid` when `serviceId` is present
- rejects mismatched `sid`
- allows absent `envTag`
- rejects missing `env` when `envTag` is present
- rejects mismatched `env`
- trims surrounding whitespace
- preserves case-sensitive matching

If the handlers are tested directly, add endpoint-level regressions that prove
mismatched `host` or `sid` returns `403` before the read model is called.

## Java Config-Server Implementation

### Claims Source

The Light-4j `JwtVerifyHandler` places the verified claims in:

```java
Map<String, Object> auditInfo =
    exchange.getAttachment(AttachmentConstants.AUDIT_INFO);

JwtClaims claims =
    (JwtClaims)auditInfo.get(Constants.SUBJECT_CLAIMS);
```

The shared helper in `light-config-server` is:

```text
com.networknt.configserver.util.ServiceIdAuthorizationUtil
```

Implemented API:

```java
public static String authorizeRequestContext(
    HttpServerExchange exchange,
    String requestedHost,
    String requestedServiceId,
    String requestedEnvTag
)
```

```java
public static String authorizeRequestContext(
    JwtClaims claims,
    String requestedHost,
    String requestedServiceId,
    String requestedEnvTag
)
```

The exchange overload extracts verified claims from `AUDIT_INFO`. The claims
overload is used by focused unit tests. Both methods return `null` on success
or a short error message when the request must be rejected with `403`.

### Handler Flow

At the top of each handler, after reading query parameters and before calling
the DB helper:

```java
String authorizationError =
    ServiceIdAuthorizationUtil.authorizeRequestContext(exchange, host, serviceId, envTag);
if (authorizationError != null) {
    exchange.setStatusCode(StatusCodes.FORBIDDEN);
    exchange.getResponseSender().send(authorizationError);
    return;
}
```

Apply the helper to:

```text
ConfigsGetHandler
CertsGetHandler
FilesGetHandler
```

### Java Tests

Focused unit tests cover:

- allows matching `sid`
- allows matching `host`
- allows blank `serviceId`
- rejects missing claims when `host` is present
- rejects missing `host`
- rejects mismatched `host`
- rejects missing claims when `serviceId` is present
- rejects missing `sid`
- rejects mismatched `sid`
- allows blank `envTag`
- rejects missing `env` when `envTag` is present
- rejects mismatched `env`
- trims surrounding whitespace
- remains case-sensitive

Handler-level coverage can be added later if the test harness can cheaply inject
`AUDIT_INFO`. The first implementation relies on focused helper tests plus the
existing handler request coverage.

## Token Issuance Check

This change depends on runtime service tokens carrying `sid` for service-scoped
startup access and controller registry registration. Before deploying the
authorization check broadly, verify the Light OAuth token path used by runtime
services.

For long-lived or trusted `client_credentials` runtime tokens:

- token custom claims should include `host`
- token custom claims should include `sid`
- token custom claims may include `env`, but must include `env` for runtimes
  that call config-server or controller with `envTag`

If a runtime cannot mint a token with `host` and `sid`, it should fail early
during token setup rather than be allowed to call config-server or register
with controller using a broader token.

## Backward Compatibility

This is a security-tightening change. It can break clients that currently call
config-server with a `serviceId` or register with controller while using a
token that has no `host` or `sid`. It can also break clients that pass
`envTag` while using a token with no matching `env`.

Recommended rollout for deployments that do not already mint service tokens
with `host` and `sid`:

1. Verify runtime token issuance includes `host` and `sid`. Verify `env` is
   included whenever the runtime sends `envTag`.
2. Enable the rule by default in Rust and Java, because config-server returns
   sensitive config and cert material and controller registry defines runtime
   service identity.
3. For one release, monitor explicit warning logs on host or SID failures.
4. Update local and enterprise runtime token setup docs so service tokens carry
   `host` and `sid`.

If a temporary compatibility switch is required, make it explicit and narrow:

```yaml
enforceSidHostMatch: true
```

Do not silently ignore mismatches in production deployments.

## Error Handling

Use `403 Forbidden` for:

- missing `sid` with requested `serviceId`
- mismatched `sid`
- missing `host` with requested `host` or controller `hostId`
- mismatched `host`
- missing `env` with requested `envTag`
- mismatched `env`
- missing decoded claims in Java after the security chain has supposedly run

Use existing `401 Unauthorized` behavior for:

- missing Authorization header
- invalid token signature
- invalid issuer or audience
- expired token

This keeps authentication failures separate from service authorization failures.

## Observability

On rejection, log:

```text
requestedServiceId
tokenSid
requestedHost
tokenHost
envTag
tokenEnv
endpoint
```

Do not log the full JWT.

The log should make the exact issue visible:

```text
Token sid com.networknt.light-gateway-1.0.0 does not match requested serviceId com.networknt.ai.gateway-1.0.0
Token host 01964b05-552a-7c4b-9184-6857e7f3dc5f does not match requested host 01964b05-552a-7c4b-9184-6857e7f3dc5e
Token env dev does not match requested envTag prod
```

## Validation Checklist

After implementation, validate these cases against Rust and Java config-server:

```text
sid=A, serviceId=A => 200
sid=A, serviceId=B => 403
sid missing, serviceId=A => 403
host=H1, request host=H1 => 200
host=H1, request host=H2 => 403
host missing, request host=H1 => 403
sid=A, serviceId omitted, productId/productVersion supplied, host matches => existing behavior
env=dev, envTag=dev => 200
env=dev, envTag=prod => 403
env missing, envTag=dev => 403
env missing, envTag omitted => existing behavior
invalid JWT => 401
missing JWT => 401
```

Also verify the three endpoint families:

```text
/config-server/configs
/config-server/certs
/config-server/files
```

Validate the same service identity cases against Rust and Java controller
registry registration:

```text
token sid=A, register serviceId=A => registered
token sid=A, register serviceId=B => registration rejected
token sid missing, register serviceId=A, token sub=A => registration rejected
token sid blank, register serviceId=A => registration rejected
token host=H1, controller hostId=H1 => registered
token host=H1, controller hostId=H2 => registration rejected
token host missing, controller hostId=H1 => registration rejected
token env=dev, register envTag=dev => registered
token env=dev, register envTag=prod => registration rejected
token env missing, register envTag=dev => registration rejected
token env missing, register envTag omitted => existing behavior
invalid JWT => registration rejected
```

Focused verification commands used during implementation:

```text
cargo test -p config-server authorize_request_context
cargo test microservice_registration_rejects
cargo test microservice_registration_uses_jwt_env_when_request_omits_env_tag
mvn -q -Dtest=ControllerWebSocketIntegrationTest#rejectsMicroserviceJwtWhenHostClaimIsMissing+rejectsMicroserviceJwtWhenHostClaimDiffersFromControllerHostId+rejectsMicroserviceJwtWhenSidIsMissing+rejectsMicroserviceJwtWhenSidDiffersFromServiceId+rejectsMicroserviceJwtWhenEnvClaimIsMissingAndEnvTagIsRequested+rejectsMicroserviceJwtWhenEnvClaimDiffersFromEnvTag+registersMicroserviceWhenEnvTagAndEnvClaimAreOmitted test
mvn -q -Dtest=ServiceIdAuthorizationUtilTest test
```

## Open Questions

No open questions for SID, host, and environment binding in this phase.
