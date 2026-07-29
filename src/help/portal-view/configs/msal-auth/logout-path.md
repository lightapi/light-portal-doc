# MSAL Auth: Logout Path

The `logoutPath` property specifies the endpoint where the Single Page Application (SPA) can explicitly terminate an active session.

## Configuration Options

```yaml
logoutPath: /auth/ms/logout
```

## Usage

When the `msal-auth` handler receives a credentialed `POST` matching this
exact path, it handles session termination by clearing the session cookies.
Send the readable `csrf` cookie value as `X-CSRF-TOKEN` when logout CSRF
enforcement is enabled. No request body is required; a zero-length body is
also accepted with `Content-Type: application/json`.

On success it returns `204 No Content` with no body or response content type.
It also returns deletion `Set-Cookie` headers for `accessToken` and `csrf`, the
complete cookie set owned by this runtime.

This path **must** also be mapped in `handler.yml` to trigger the `msal-auth` handler.

```yaml
chains:
  bff:
    - cors
    - msal-auth

paths:
  - path: /auth/ms/logout
    method: POST
    exec:
      - bff
  # Temporary compatibility bridge for cached pre-migration clients.
  - path: /auth/ms/logout
    method: GET
    exec:
      - bff
  # Keep permanently so preflight reaches CORS before the auth handler.
  - path: /auth/ms/logout
    method: OPTIONS
    exec:
      - bff
```

The GET route is migration-only and is removed at the strict Phase 4 release
boundary after the compatibility and telemetry gates pass. After strict
enforcement, legacy mutation methods return `405`, `ERR10008`, and
`Allow: POST`. The `OPTIONS` route remains.
