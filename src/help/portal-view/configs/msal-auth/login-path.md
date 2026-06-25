# MSAL Auth: Login Path

The `loginPath` property specifies the endpoint where the Single Page Application (SPA) submits a Microsoft Entra ID token to establish a gateway session.

## Configuration Options

```yaml
loginPath: /auth/ms/login
```

## Usage

When the `msal-auth` handler receives a request (typically a `POST`) matching this exact path:
1. It expects a valid Microsoft Entra ID token in the `Authorization: Bearer` header.
2. It validates the token using the `security-msal.yml` configuration.
3. If valid, it generates a fresh CSRF token and responds with the `accessToken` and `csrf` cookies using `Set-Cookie` headers.

This path **must** also be mapped in `handler.yml` to trigger the `msal-auth` handler.

```yaml
paths:
  - path: /auth/ms/login
    method: POST
    exec:
      - msal-auth
```
