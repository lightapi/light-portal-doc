# Token Exchange

This document outlines the design decisions and implementation details for supporting multiple token exchange flows in the `oauth-kafka` module.

## Comparison of Detection Methods

When implementing token exchange (RFC 8693), the server must determine which identity provider (IdP) issued the `subject_token` to verify it correctly and map claims.

| Method | Explanation | Pros | Cons | Recommended For |
| :--- | :--- | :--- | :--- | :--- |
| **JWT Peek (`iss`)** | Server decodes the token header/body without verification to read the `iss` claim. | Zero client configuration; Uses standard parameters. | Token is parsed twice; Sensitive to malformed tokens. | Public OIDC providers (Azure, Okta, Google). |
| **Custom URNs** | Client sends a specific `requested_token_type` (e.g. `urn:networknt:msal`). | Explicit and unambiguous; Follows standard extensibility. | Clients must know the specific URNs for each flow. | Mixed heterogeneous token types (SAML vs JWT). |
| **`subject_issuer`** | Client passes an extra `subject_issuer` parameter in the request. | Clean API; Works with "opaque" (non-JWT) tokens. | Non-standard parameter; Redundant for self-describing JWTs. | Opaque tokens or overlapping issuers. |
| **Client Context** | Server maps the `client_id` of the caller to a specific flow. | Highly secure; Enforces strict per-client policy. | High management overhead; Inflexible for multi-source clients. | Rigid, security-conscious B2B integrations. |

## Implementation Strategy

Our implementation in `ProviderIdTokenPostHandler` uses a hybrid approach:

1. **`requested_token_type`**: Primary differentiator. We support `msal` (default) and `internal`.
2. **Modular Handlers**: Logic is delegated to `handleMsalTokenExchange` and `handleInternalTokenExchange`.
3. **Internal Flow**: Uses `jose4j` for transparent decoding of internal JWTs and verifies against host-specific keys.

## Recommendation

For the current `light-portal` ecosystem:

- **JWT Peek (`iss`)** is recommended for external OIDC providers (like MSAL) as it provides the best balance of user experience (no extra parameters) and reliability.
- **`requested_token_type`** should be used for internal service-to-service exchanges where the flow is known and should be explicit.
- **Client Context** should be considered for high-security environments where the server must dictate exactly which token sources are allowed for a given client.

## Future Considerations

- Implement automated issuer discovery if the number of external providers grows.
- Support "opaque" token exchange by integrating with introspection endpoints of external IdPs.
