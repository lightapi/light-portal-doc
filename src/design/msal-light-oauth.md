# MSAL Light OAuth Integration

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

2.  **Call Your Backend:** After getting the token, instead of using it to call various protected resources, you make a single call to a dedicated endpoint on your backend (e.g., `/api/auth/token-exchange`) to initiate the session.

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
          const backendResponse = await fetch('/api/auth/token-exchange', {
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

1.  **Protect the Endpoint:** Configure your backend (e.g., Node.js/Express, ASP.NET Core) to validate the `Bearer` token from Microsoft that it receives from your React app. This ensures only authenticated users from your SPA can trigger an exchange.

2.  **Implement the Exchange Logic:**

    ```javascript
    // Example using Node.js and Axios
    const express = require('express');
    const axios = require('axios');
    const app = express();

    // This endpoint must be protected by middleware that validates the incoming Microsoft Access Token
    app.post('/api/auth/token-exchange', async (req, res) => {
      // 1. Extract the Microsoft token from the Authorization header
      // The validation should have already happened in a middleware step.
      const microsoftAccessToken = req.headers.authorization.split(' ')[1];

      // 2. Prepare the request for your second OAuth provider
      const tokenExchangeData = new URLSearchParams({
        grant_type: 'urn:ietf:params:oauth:grant-type:token-exchange',
        client_id: process.env.SECOND_PROVIDER_CLIENT_ID, // Your backend's client ID
        client_secret: process.env.SECOND_PROVIDER_CLIENT_SECRET, // Your backend's secret
        subject_token: microsoftAccessToken, // The token to exchange
        subject_token_type: 'urn:ietf:params:oauth:token-type:access_token',
        // Request scopes for the new token from the second provider
        scope: 'read:fine-grained-permissions'
      });

      try {
        // 3. Make the POST request to the second provider's token endpoint
        const response = await axios.post(
          'https://your-second-provider.com/oauth/token', // The token endpoint URL
          tokenExchangeData,
          {
            headers: {
              'Content-Type': 'application/x-www-form-urlencoded',
            },
          }
        );

        const newEnrichedToken = response.data.access_token;

        // 4. IMPORTANT: Decide what to do with the new token.
        // Option A (Recommended for SPAs): Set a secure, HttpOnly session cookie.
        // This is the most secure method as the token is not exposed to browser script.
        res.cookie('session_token', newEnrichedToken, {
          httpOnly: true,
          secure: process.env.NODE_ENV === 'production',
          sameSite: 'strict',
        });
        res.status(200).json({ status: 'success' });

        // Option B: Return the new token to the SPA.
        // The SPA would then have to manage this token and send it as a Bearer token
        // on subsequent requests to your backend.
        // res.status(200).json({ newAccessToken: newEnrichedToken });

      } catch (error) {
        console.error('Error during token exchange:', error.response?.data || error.message);
        res.status(500).json({ error: 'Failed to exchange token' });
      }
    });
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
