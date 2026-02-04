# OAuth 2.0 State Parameter Design

This document outlines the design, generation, and flow of the `state` parameter within the LightAPI OAuth 2.0 architecture.

## Overview

The `state` parameter is an opaque value used by the client to maintain state between the request and callback. In the OAuth 2.0 Authorization Code Flow, its primary and critical function is to prevent **Cross-Site Request Forgery (CSRF)** attacks.

## Workflow

The flow involves three parties:
1.  **Client**: The application requesting access (e.g., Light Portal).
2.  **Authorization Server UI**: The front-end login interface (e.g., Login View).
3.  **Authorization Service**: The backend service validating credentials and issuing codes.

### Step-by-Step Flow

1.  **Generation (Client Side)**
    *   The User initiates a login action on the **Client**.
    *   The **Client** generates a cryptographically strong random string (the `state`).
    *   The **Client** stores this `state` locally (e.g., in a secure, HTTP-only cookie or Session Storage) bound to the user's current session.
    *   The **Client** redirects the browser to the **Authorization Server UI** (`login-view`), appending the `state` as a query parameter.
    
    ```
    GET https://login.lightapi.net/?client_id=...&response_type=code&state=xyz123...
    ```

2.  **Preservation (Authorization Server UI)**
    *   The **Authorization Server UI** (`login-view`) loads and parses the query parameters.
    *   It **must not** modify or validate the `state`. Its sole responsibility is preservation.
    *   When the user submits credentials (username/password) or selects a social provider, the UI passes the `state` exactly as received to the backend **Authorization Service**.

3.  **Authorization (Authorization Service)**
    *   The backend service authenticates the user.
    *   Upon success, it generates an Authorization Code.
    *   It constructs the redirect URL back to the **Client**.
    *   It **must** append the *exact same* `state` value received from the UI to this redirect URL.

    ```
    HTTP/1.1 302 Found
    Location: https://portal.lightapi.net/authorization?code=auth_code_abc&state=xyz123...
    ```

4.  **Verification (Client Side)**
    *   The **Client** receives the callback request.
    *   It extracts the `state` from the URL parameters.
    *   It retrieves the stored `state` from its local session.
    *   It compares the two values:
        *   **Match**: The request is valid. Proceed to exchange the code for a token.
        *   **Mismatch**: The request is potentially malicious (CSRF likely). **Reject the request** and show an error.

## Security Requirements

*   **Uniqueness**: The `state` must be unique per authentication request.
*   **Entropy**: It must be a cryptographically random string (high entropy) to be unguessable.
*   **Binding**: It must be bound to the user's specific browser session on the client side.

## Responsibility Matrix

| Component | Responsibility | Action |
| :--- | :--- | :--- |
| **Portal (Client)** | **Owner** | Generate, Store, Verify. |
| **Login View (UI)** | **Carrier** | Receive, Preserve, Forward. |
| **Auth Service** | **Echo** | Receive, Echo back in Redirect. |

## References
*   [RFC 6749 Section 10.12 (Cross-Site Request Forgery)](https://datatracker.ietf.org/doc/html/rfc6749#section-10.12)
