# MSAL Auth: Cookie SameSite

The `cookieSameSite` property in the `msal-auth` (and `msal-exchange` / `stateless-auth`) configuration maps directly to the `SameSite` attribute in HTTP `Set-Cookie` headers. It controls whether the browser should send session cookies (such as `accessToken` and `csrf`) along with cross-site requests. This is a foundational browser security mechanism designed to protect against Cross-Site Request Forgery (CSRF) and govern cross-origin tracking.

## Configuration Options

You can configure this property in your handler's configuration file (e.g., `msal-auth.yml`):

```yaml
cookieSameSite: None
```

The gateway maps this property directly to the standard HTTP options (case-sensitive as `None`, `Lax`, or `Strict`):

- **`None`**: The browser sends the cookie with *both* cross-site and same-site requests. 
  - *Requirement*: Modern browsers mandate that if `SameSite=None`, the cookie **must** also be marked as `Secure` (meaning `cookieSecure: true`). If you set `None` with `Secure: false`, browsers like Chrome and Edge will silently block the cookie.
- **`Lax`**: The cookie is not sent on cross-site API requests (e.g., AJAX/Fetch), *except* for top-level navigations (like a user clicking a standard link to your site from another site). This is the default behavior of modern browsers if the `SameSite` attribute is missing entirely.
- **`Strict`**: The cookie is sent *only* if the request originates from the exact same site that set the cookie. Cross-site requests will never include the cookie.

## Why Default to `None`?

In modern microservice and Single Page Application (SPA) architectures, the frontend UI and the backend API Gateway are frequently hosted on different origins, especially during development. 

For example:
- **Frontend SPA**: `http://localhost:3000` (Local React/Angular dev server)
- **Backend Gateway**: `https://api.dev.mycompany.com` (or `https://localhost:8443`)

Because the ports and/or domains don't match, the browser considers API requests between them as "cross-site". If `cookieSameSite` defaulted to `Lax` or `Strict`, the browser would refuse to send the authentication cookies when the local UI calls the backend API, leading to immediate `401 Unauthorized` errors out of the box.

Defaulting to `None` provides a seamless developer experience for decoupled SPAs. To safely allow `None`, `light-fabric` pairs this behavior with robust **Double Submit Cookie CSRF** protections (requiring the `X-CSRF-TOKEN` header). This ensures that even though the browser attaches the cookie cross-origin, an attacker cannot successfully forge a state-changing request because they cannot read or supply the necessary CSRF header token.
