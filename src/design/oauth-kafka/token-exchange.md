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

Our implementation in `ProviderIdTokenPostHandler` uses **Option 4: Client Context** as the primary strategy:

1. **Database-Driven Configuration**: A new column `token_ex_type` has been added to the `auth_client_t` table to specify the supported exchange type for each client.
   ```sql
   ALTER TABLE auth_client_t ADD COLUMN token_ex_type VARCHAR(64);
   ```
2. **Supported Exchange Types**:
   - `msal`: Microsoft Authentication Library based exchange.
   - `ccac`: Client Credentials to Authorization Code exchange.
3. **Flow Determination**: Instead of relying on client-supplied parameters like `requested_token_type`, the server retrieves the `token_ex_type` from the client context in the database to decide which handler to use. This ensures that only authorized exchange types are performed for each specific client.

## Recommendation

For the `light-portal` ecosystem:

- **Option 4: Client Context** is the selected method. It provides the highest level of security by ensuring that token exchange flows are explicitly configured and restricted on a per-client basis in the database.
- **`token_ex_type`** should be populated for any client that requires token exchange functionality. Clients without this configuration will not be allowed to perform token exchange.

## Future Considerations

- Implement automated issuer discovery if the number of external providers grows.
- Support "opaque" token exchange by integrating with introspection endpoints of external IdPs.
- Extend the `auth_client_t` configuration to support multiple allowed exchange types per client if needed.
