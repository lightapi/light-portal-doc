# MSAL Auth: Logout Path

The `logoutPath` property specifies the endpoint where the Single Page Application (SPA) can explicitly terminate an active session.

## Configuration Options

```yaml
logoutPath: /auth/ms/logout
```

## Usage

When the `msal-auth` handler receives a request matching this exact path, it handles the session termination by clearing the session cookies. 

Specifically, it returns `Set-Cookie` headers with a past expiration date for the `accessToken` and `csrf` cookies, ensuring the browser immediately removes them from storage.

This path **must** also be mapped in `handler.yml` to trigger the `msal-auth` handler.

```yaml
paths:
  - path: /auth/ms/logout
    exec:
      - msal-auth
```
