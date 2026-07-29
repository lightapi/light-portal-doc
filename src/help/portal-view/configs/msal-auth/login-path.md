# MSAL Auth: Login Path

The `loginPath` property specifies the endpoint where the Single Page Application (SPA) submits a Microsoft Entra ID token to establish a gateway session.

## Configuration Options

```yaml
loginPath: /auth/ms/login
```

## Usage

When the `msal-auth` handler receives a `POST` matching this exact path:
1. It expects a valid Microsoft Entra ID token in the `Authorization: Bearer` header.
2. It validates the token using the `security-msal.yml` configuration.
3. If valid, it generates a fresh CSRF token and responds with the `accessToken` and `csrf` cookies using `Set-Cookie` headers.

The request body is optional. A zero-length request is accepted even when a
shared client sets `Content-Type: application/json`.

This path **must** also be mapped in `handler.yml` to trigger the `msal-auth` handler.

```yaml
chains:
  bff:
    - cors
    - msal-auth

paths:
  - path: /auth/ms/login
    method: POST
    exec:
      - bff
  - path: /auth/ms/login
    method: OPTIONS
    exec:
      - bff
```

Keep `OPTIONS` routed through a chain with CORS before `msal-auth`.
