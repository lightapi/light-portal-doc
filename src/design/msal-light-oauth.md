# MSAL Light OAuth Integration

## Token Exchange

We have a React Single Page Application(SPA) running within a corporate network using Azure AD for SSO. However, we want to use JWT tokens from another OAuth 2.0 provider Light-OAuth to issue the token with additional custom claims for fine-grained Authorization. What is the best way to do the integration? 

This is a common and powerful architectural pattern used to separate authentication from authorization, allowing you to use a central identity provider (like Azure AD) for *who the user is* and a specialized service for *what the user can do*.

The goal is to use the trusted identity established by Microsoft to "mint" a new, enriched token from your second provider.

The **best and most secure way** to achieve this is by using the **OAuth 2.0 Token Exchange Flow (RFC 8693)**. This process happens on your backend, ensuring that no sensitive client secrets or complex token logic is exposed in the React SPA.

Let's break down the architecture and the steps involved.

---

### The Recommended Architecture: Backend-Mediated Token Exchange

In this model, your React SPA's responsibility remains simple: authenticate the user with Microsoft and get a token. It then sends this token to your own backend API. Your backend is the one that communicates with the second OAuth provider to exchange the token.

Here is a diagram of the flow:

```
+-----------+     +-----------------+     +----------------+
|           | (1) |                 | (2) |                |
| React SPA |---->|  Microsoft      |---->|   React SPA    |
|           |     |  Entra ID (MSAL)|     | (has MS Token) |
+-----------+     +-----------------+     +----------------+
      |
      | (3) Sends MS Token to Backend
      v
+-----------+     +-----------------+     +----------------+
|           | (4) |                 | (5) |                |
| Your      |---->| Second OAuth    |---->|  Your          |
| Backend   |     | Provider        |     |  Backend       |
| API       |     | (Token Exchange)|     | (has New Token)|
+-----------+     +-----------------+     +----------------+
      |
      | (6) Establishes session / returns new token
      v
+-----------+
| React SPA |
| (is now   |
| authorized)|
+-----------+
```

**Why this is the best approach:**

*   **Security:** Your second provider's `client_id` and `client_secret` are kept securely on your backend, never exposed to the browser.
*   **Separation of Concerns:** The React app only worries about authenticating with Microsoft. Your backend handles the complex authorization logic.
*   **Flexibility:** You can swap out the second authorization provider without changing your entire frontend authentication flow.
*   **Standard-Compliant:** The Token Exchange grant type is an official standard designed for this exact "delegation" or "impersonation" scenario.

---

### Step-by-Step Integration Guide

Here’s how to implement this pattern.

#### Step 1: Configure Your Second OAuth 2.0 Provider

This is the most critical setup step. You need to configure your authorization provider (e.g., Auth0, Okta, Duende IdentityServer, or a custom one) to:

1.  **Trust Microsoft Entra ID (Azure AD) as an Identity Provider:** It must be able to validate the signature of the token it receives from your backend. This usually involves pointing it to Microsoft's OIDC discovery endpoint (`https://login.microsoftonline.com/{tenant-id}/v2.0/.well-known/openid-configuration`) to get the public signing keys.
2.  **Enable the Token Exchange Grant Type:** You'll need to create a new "client" or "application" within this provider for your backend API. This client must be configured to use the `urn:ietf:params:oauth:grant-type:token-exchange` grant type.
3.  **Define a User Mapping Strategy:** The provider needs to know how to link the incoming Microsoft token to a user in its own database. A common practice is to map the `oid` (Object ID) or `sub` (Subject) claim from the Microsoft token to a user profile in the second provider. This is how it knows which fine-grained permissions (claims) to add.
4.  **Define the Custom Claims:** Configure the rules that add the additional claims to the new token when the exchange is successful. For example: "If the incoming user has `oid` '123-abc', add the claims `permissions: ['create:document', 'read:report']`."

#### Step 2: Update Your React SPA Logic

Your React app's interaction with MSAL will remain largely the same, with one key difference in what you do after a successful login.

1.  **Authenticate and Acquire a Token:** Use MSAL as you normally would to log the user in and get an access token for your *own backend API*.

    ```javascript
    // msalConfig.js - Make sure you have a scope for your own backend API
    export const msalConfig = {
      auth: { /* ... */ },
      cache: { /* ... */ },
    };

    export const loginRequest = {
      scopes: ["User.Read", "api://<your-backend-client-id>/access_as_user"]
    };
    ```

2.  **Call Your Backend:** After getting the token, instead of using it to call various protected resources, you make a single call to a dedicated endpoint on your backend (e.g., `/auth/ms/exchange`) to initiate the session.

    ```javascript
    import { useMsal } from "@azure/msal-react";
    import { loginRequest } from "./msalConfig";

    function MyComponent() {
      const { instance, accounts } = useMsal();

      const handleLoginAndExchange = async () => {
        try {
          // 1. Get the MSAL token for our backend
          const response = await instance.acquireTokenSilent({
            ...loginRequest,
            account: accounts[0],
          });
          const microsoftAccessToken = response.accessToken;

          // 2. Send it to our backend for exchange
          const backendResponse = await fetch('/auth/ms/exchange', {
            method: 'POST',
            headers: {
              'Authorization': `Bearer ${microsoftAccessToken}`,
              'Content-Type': 'application/json',
            },
          });

          if (!backendResponse.ok) {
            throw new Error('Token exchange failed');
          }

          // The backend will likely set a secure HttpOnly cookie,
          // so there might be nothing else to do here.
          // Or, it might return the new token to be stored in memory.
          const { newAccessToken } = await backendResponse.json();
          console.log("Received new, enriched token from our backend!");
          // Now use this newAccessToken for subsequent API calls

        } catch (error) {
          // Handle token acquisition or exchange errors
          console.error(error);
          if (error.name === "InteractionRequiredAuthError") {
             instance.acquireTokenPopup(loginRequest);
          }
        }
      };
      // ...
    }
    ```

#### Step 3: Implement the Backend Token Exchange Endpoint

This is where the core logic resides. You'll create an endpoint that receives the Microsoft token and exchanges it.

1.  **Protect the Endpoint:** Configure your backend to validate the `Bearer` token from Microsoft that it receives from your React app. This ensures only authenticated users from your SPA can trigger an exchange.

2.  **Implement the Exchange Logic:**

    ```Java
        if (exchange.getRelativePath().equals(config.getExchangePath())) {
            // token exchange request handling.
            if(logger.isTraceEnabled()) logger.trace("MsalTokenExchangeHandler exchange is called.");

            String authHeader = exchange.getRequestHeaders().getFirst(Headers.AUTHORIZATION);
            if (authHeader == null || !authHeader.startsWith("Bearer ")) {
                setExchangeStatus(exchange, JWT_BEARER_TOKEN_MISSING);
                return;
            }
            String microsoftToken = authHeader.substring(7);

            // --- Validate the incoming Microsoft Token ---
            if(msalJwtVerifier == null) {
                // handle case where config failed to load
                throw new Exception("MsalJwtVerifier is not initialized.");
            }
            try {
                // We only need to verify it, we don't need the claims for much.
                // The second provider will do its own validation and claim mapping.
                // Set skipAudienceVerification to true if the 'aud' doesn't match this BFF's client ID.
                String reqPath = exchange.getRequestPath();
                msalJwtVerifier.verifyJwt(microsoftToken, msalSecurityConfig.isIgnoreJwtExpiry(), true, null, reqPath, null);
            } catch (InvalidJwtException e) {
                logger.error("Microsoft token validation failed.", e);
                setExchangeStatus(exchange, INVALID_AUTH_TOKEN, e.getMessage());
                return;
            }

            // --- Perform Token Exchange ---
            String csrf = UuidUtil.uuidToBase64(UuidUtil.getUUID());
            TokenExchangeRequest request = new TokenExchangeRequest();
            request.setSubjectToken(microsoftToken);
            request.setSubjectTokenType("urn:ietf:params:oauth:token-type:jwt");
            request.setCsrf(csrf); // The CSRF for the *new* token we are getting

            Result<TokenResponse> result = OauthHelper.getTokenResult(request);
            if (result.isFailure()) {
                logger.error("Token exchange failed with status: {}", result.getError());
                setExchangeStatus(exchange, TOKEN_EXCHANGE_FAILED, result.getError().getDescription());
                return;
            }

            // --- The setCookies logic is identical ---
            List<String> scopes = setCookies(exchange, result.getResult(), csrf);
            if(logger.isTraceEnabled()) logger.trace("scopes = {}", scopes);

            exchange.setStatusCode(StatusCodes.OK);
            exchange.getResponseHeaders().put(Headers.CONTENT_TYPE, "application/json");
            // Return the scopes in the response body
            Map<String, Object> rs = new HashMap<>();
            rs.put(SCOPES, scopes);
            exchange.getResponseSender().send(JsonMapper.toJson(rs));
        } else if (exchange.getRelativePath().equals(config.getLogoutPath())) {
            // logout request handling, this is the same as StatelessAuthHandler to remove the cookies.
            if(logger.isTraceEnabled()) logger.trace("MsalTokenExchangeHandler logout is called.");
            removeCookies(exchange);
            exchange.endExchange();
        } else {
            // This is the subsequent request handling after the token exchange. Here we verify the JWT in the cookies.
            if(logger.isTraceEnabled()) logger.trace("MsalTokenExchangeHandler is called for subsequent request.");
            String jwt = null;
            Cookie cookie = exchange.getRequestCookie(ACCESS_TOKEN);
            if(cookie != null) {
                jwt = cookie.getValue();
                // verify the jwt with the internal verifier, the token is from the light-oauth token exchange.
                JwtClaims claims = internalJwtVerifier.verifyJwt(jwt, securityConfig.isIgnoreJwtExpiry(), true);
                String jwtCsrf = claims.getStringClaimValue(Constants.CSRF);
                // get csrf token from the header. Return error is it doesn't exist.
                String headerCsrf = exchange.getRequestHeaders().getFirst(HttpStringConstants.CSRF_TOKEN);
                if(headerCsrf == null || headerCsrf.trim().length() == 0) {
                    setExchangeStatus(exchange, CSRF_HEADER_MISSING);
                    return;
                }
                // verify csrf from jwt token in httpOnly cookie
                if(jwtCsrf == null || jwtCsrf.trim().length() == 0) {
                    setExchangeStatus(exchange, CSRF_TOKEN_MISSING_IN_JWT);
                    return;
                }
                if(logger.isDebugEnabled()) logger.debug("headerCsrf = " + headerCsrf + " jwtCsrf = " + jwtCsrf);
                if(!headerCsrf.equals(jwtCsrf)) {
                    setExchangeStatus(exchange, HEADER_CSRF_JWT_CSRF_NOT_MATCH, headerCsrf, jwtCsrf);
                    return;
                }
                // renew the token 1.5 minute before it is expired to keep the session if the user is still using it
                // regardless the refreshToken is long term remember me or not. The private message API access repeatedly
                // per minute will make the session continue until the browser tab is closed.
                if(claims.getExpirationTime().getValueInMillis() - System.currentTimeMillis() < 90000) {
                    jwt = renewToken(exchange, exchange.getRequestCookie(REFRESH_TOKEN));
                }
            } else {
                // renew the token and set the cookies
                jwt = renewToken(exchange, exchange.getRequestCookie(REFRESH_TOKEN));
            }
            if(logger.isTraceEnabled()) logger.trace("jwt = " + jwt);
            if(jwt != null) exchange.getRequestHeaders().put(Headers.AUTHORIZATION, "Bearer " + jwt);
            // if there is no jwt and refresh token available in the cookies, the user not logged in or
            // the session is expired. Or the endpoint that is trying to access doesn't need a token
            // for example, in the light-portal command side, createUser doesn't need a token. let it go
            // to the service and an error will be back if the service does require a token.
            // don't call the next handler if the exchange is completed in renewToken when error occurs.
            if(!exchange.isComplete()) Handler.next(exchange, next);
        }
    ```

---

### What to Avoid: The Anti-Pattern

Do **not** try to perform two separate, chained OAuth flows in the frontend. This would involve:
1.  User logs in with MSAL.
2.  Your React app gets the MSAL token.
3.  Your React app then initiates a *second* redirect or popup flow with the other provider, trying to pass the MSAL token as a parameter.

This is a bad idea because:
*   **Terrible User Experience:** It can lead to multiple redirects, popups, and a confusing login process.
*   **Security Risk:** It increases the surface area for token handling in the browser and might require you to use less secure flows (like Implicit flow) on the second provider.
*   **Complexity:** Managing the state of two independent authentication libraries and their tokens in a SPA is extremely difficult and error-prone.


## Client Secret

Token exchange specification doesn't require client_id and client_secret to be sent to the second OAuth 2.0 provider to exchage the token. However, it is highly recommended to pass the client_id and client_secret from the BFF to the second OAuth 2.0 provider. The subject token along is not sufficient. 

This is a critical security aspect of the Token Exchange flow. Let's break down why.

### The "Two Questions" Security Model

When your BFF makes the token exchange request, the second OAuth provider needs to answer two fundamental security questions:

1.  **WHO IS THE USER?** (Authentication of the Subject)
    *   This question is answered by the `subject_token` (the Microsoft token).
    *   The provider validates the token's signature, issuer (`iss`), expiration (`exp`), and audience (`aud`) to confirm that it's a legitimate token for a valid user from a trusted identity provider (Microsoft).

2.  **WHO IS *ASKING* FOR THIS TOKEN?** (Authentication of the Client)
    *   This question is answered by the `client_id` and `client_secret`.
    *   This is crucial. The provider needs to know *which application* is requesting to act on the user's behalf. It's not enough that the user is valid; the application making the request must also be a known, trusted, and authorized client.

### Why the Subject Token Alone is a Security Risk

Imagine if only the `subject_token` were required. Any malicious actor or compromised service that managed to get a user's Microsoft access token could then send it to your second OAuth provider and exchange it for a new token containing your fine-grained authorization claims. This would allow them to impersonate the user within your system completely.

By requiring the `client_id` and `client_secret`, you ensure that **only your specific, trusted BFF application** is allowed to perform this exchange. The `client_secret` is the proof that the request is coming from your backend and not some other application.

---

### The Token Exchange Request Body

So, the `POST` request your `MsalTokenExchangeHandler` (the BFF) sends to your second provider's token endpoint will be `application/x-www-form-urlencoded` and must look like this:

```
grant_type=urn:ietf:params:oauth:grant-type:token-exchange
&client_id=YOUR_BFFS_CLIENT_ID_FOR_THE_SECOND_PROVIDER
&client_secret=YOUR_BFFS_CLIENT_SECRET
&subject_token=THE_MICROSOFT_ACCESS_TOKEN_FROM_THE_SPA
&subject_token_type=urn:ietf:params:oauth:token-type:access_token
&scope=permissions_for_the_new_token
```

### Configuration Checklist for your Second OAuth Provider

This means that on your second OAuth 2.0 provider, you must:

1.  **Create a Client Registration:** Create a new "Application" or "Client" specifically for your `light-gateway` BFF.
2.  **Set Client Type:** Configure this client as a **Confidential Client** (as opposed to a Public Client like a SPA), because it is capable of securely storing a secret.
3.  **Generate Credentials:** Generate a `client_id` and a `client_secret` for this BFF client.
4.  **Enable Grant Type:** Explicitly enable the `urn:ietf:params:oauth:grant-type:token-exchange` grant type for this specific client. Your provider's security policy should only allow trusted, confidential clients to use this powerful grant type.
5.  **Store Credentials Securely:** Store the generated `client_id` and `client_secret` securely in your BFF's configuration (e.g., in `secret.yml` or environment variables), where they are not exposed to the outside world.

In short:

*   The **`subject_token`** proves **who the user is**.
*   The **`client_id` and `client_secret`** prove **who your BFF is**.

Both are required for a secure delegation and token exchange process.

## Token Verification

It is necessary to verify the jwt token from Azure AD on both BFF and light-oauth based on the "Zero Trust" principle. They perform the validation for different, but equally important, reasons.

Skipping the validation on the BFF, while technically possible, is a significant security anti-pattern. Let's break down the distinct roles of each validation step.

---

### 1. The BFF's Responsibility: "Am I Talking to a Legitimate Client?"

The validation performed by your `MsalTokenExchangeHandler` in the BFF serves as a **gatekeeper for your own system**. Its purpose is to protect the BFF itself and the downstream services it communicates with.

When the BFF validates the Microsoft token, it's asking these questions:

*   **Is this token even real?** (Signature validation).
*   **Is it from an identity provider I trust?** (Checking the `iss` or "issuer" claim is from `login.microsoftonline.com/...`).
*   **Is this token actually meant for me?** (This is **CRITICAL**). The BFF must check the `aud` or "audience" claim. The `aud` should be the Client ID of your BFF application. This prevents a token that was issued for another API (like the Microsoft Graph API) from being replayed against your BFF to trick it. This is a defense against the "confused deputy" problem.
*   **Has it expired?** (Checking the `exp` or "expiration" claim).

**Why this is crucial for the BFF:**

*   **Fail Fast:** You immediately reject invalid, expired, or improperly targeted tokens. This is a better user experience and saves system resources.
*   **Denial-of-Service (DoS) Protection:** If you don't validate, your BFF becomes a dumb proxy that forwards every piece of junk it receives to your second OAuth provider. An attacker could flood your BFF with garbage tokens, causing it to swamp your authorization server with useless validation and exchange requests, potentially taking it down.
*   **Security Boundary:** The BFF is the first line of defense. It should never blindly trust any input it receives from the public internet, even from your own SPA.

---

### 2. The Second OAuth Provider's Responsibility: "Can I Issue a New Token for this Subject?"

The validation performed by the second OAuth provider is the **authoritative act of delegation**. It's the ultimate source of truth for the new, enriched token. It cannot and *must not* trust that the BFF has already performed a valid check.

When the second OAuth provider receives the `subject_token`, it asks all the same questions as the BFF, but for its own security policy:

*   **Is this token real and from a trusted issuer?** (Signature and `iss` validation). It must have Microsoft configured as a trusted external identity provider.
*   **Is this token meant for a client that is allowed to exchange it?** (It might check the `aud` claim).
*   **Is the *client making the request* (the BFF) authorized to perform a token exchange?** (This is validated via the `client_id` and `client_secret` you send in the request).
*   **How do I map this external user to an internal user?** (This is the most important unique step). It will inspect the `oid`, `sub`, `email`, or another claim from the Microsoft token to find the corresponding user in its own database.
*   **What new claims should I issue for this user?** Based on the mapped internal user, it will apply its authorization rules to mint the new token with fine-grained permissions.

### Analogy: A High-Security Building

Think of it like this:

1.  **The React SPA** is you, the visitor.
2.  **The Microsoft Token** is your government-issued driver's license.
3.  **The BFF** is the **receptionist at the front desk of the building**. They look at your driver's license (`BFF validation`) to make sure it's not expired and that your name is on the visitor list for that day (`aud` check). They protect the building from random people just walking in.
4.  **The Second OAuth Provider** is the **guard in front of the secure vault on the 10th floor**. When you get to the 10th floor, the guard doesn't just say, "Oh, the receptionist let you in, so you must be fine." No, they perform their *own, more thorough check* of your driver's license (`OAuth provider validation`), check their specific access logs (`user mapping`), and then issue you a special keycard (`new enriched token`) that only opens the specific safety deposit box you're allowed to access (`fine-grained claims`).

You wouldn't want a security system where the vault guard blindly trusts the front desk. Each layer must perform its own validation.

### Conclusion

**Do not skip the validation on the BFF.**

*   **Verify on the BFF** to protect your own application, fail fast, and prevent it from becoming a DoS vector.
*   **The Second OAuth Provider MUST verify** as its core function to securely map the user and issue an authoritative, enriched token.

The verifications are not redundant; they are a fundamental part of a layered, defense-in-depth security strategy.


## Single Page Application

There are two endpoints that the SPA should access for both token exchange and logout. 

### Login

After the SSO with Azure AD via SSO, you need to send this ID token to the backend API endpoint "/auth/ms/exchange" to establish the session with a GET request. The header is the standard authorization header with "Bearer IdToken". You will receive a response in JSON with a list of scopes that is represent the access permission. You can display them to the user for consent or simply ignore them. Along with the response body, some cookies will be set on the browser local storage to establish the session. Once the login is done, the backend will automatically renew the access token with a refresh token automatically as long as the user sending the request to the server. 


### Logout

To logout, you need to logout from the Azure AD and then send a GET request to the backend API endpoint "/auth/ms/logout" to remove session cookies. 


