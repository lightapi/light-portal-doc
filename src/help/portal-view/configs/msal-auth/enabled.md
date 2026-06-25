# MSAL Auth: Enabled

The `enabled` property controls whether the `msal-auth` handler is active and processing requests in the gateway.

## Configuration Options

```yaml
enabled: true
```

- **`true`**: The handler is fully active. It will intercept requests to the `loginPath` and `logoutPath`, validate sessions on protected routes, and enforce CSRF protections.
- **`false`**: The handler is effectively disabled. Even if it is listed in the execution chain in `handler.yml`, it will immediately yield control to the next handler without performing any authentication checks or modifications.

## Usage

This toggle is extremely useful for temporarily bypassing authentication in local development or test environments without having to re-write the entire `handler.yml` routing chain. 
