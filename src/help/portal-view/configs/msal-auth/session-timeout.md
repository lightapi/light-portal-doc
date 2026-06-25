# MSAL Auth: Session Timeout

The `sessionTimeout` property specifies the default expiration time (in seconds) for the session cookies, if the provided Microsoft Entra ID token lacks an explicit `exp` claim.

## Configuration Options

```yaml
sessionTimeout: 3600
```

## Usage

When a user logs in via the `/auth/ms/login` endpoint, the gateway parses the Microsoft Entra ID token and looks for the `exp` (expiration) claim.
- If the token contains a valid `exp` claim, the cookies are set to expire exactly when the Entra ID token expires.
- If the token lacks an `exp` claim, the `sessionTimeout` value is used as a fallback to calculate the expiration duration.

When the cookies expire, the browser will stop sending them. To maintain uninterrupted access, the SPA is responsible for silently refreshing the Entra ID token via MSAL.js and calling `/auth/ms/login` again before the cookies expire.
