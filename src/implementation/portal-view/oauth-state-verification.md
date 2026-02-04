# OAuth 2.0 State Verification

This document describes the implementation of CSRF protection for the OAuth 2.0 authorization code flow in the portal-view application.

## Overview

To prevent Cross-Site Request Forgery (CSRF) attacks during the OAuth 2.0 authentication process, we implement a state parameter check. A random state string is generated before the authentication request and verified upon the callback.

## Implementation Details

### State Generation

Location: `src/components/Header/ProfileMenu.tsx`

When the user initiates the sign-in process:
1.  A random alphanumeric string is generated.
2.  This string is stored in the browser's `localStorage` under the key `portal_auth_state`.
3.  The string is appended as the `state` query parameter to the OAuth 2.0 authorization URL.

```typescript
// Generate a random state for CSRF protection
const state = Math.random().toString(36).substring(7);
localStorage.setItem('portal_auth_state', state);

const defaultUrl =
  `https://locsignin.lightapi.net?client_id=...&state=${state}`;
```

### Redirect Handling

Location: `src/App.tsx`

To ensure the `state` query parameter is preserved during the redirect from the root path (`/`) to the dashboard, a custom `RedirectWithQuery` component is used. This component handles both standard query parameters and hash-based redirects (common with certain OAuth providers or router configurations).

1.  Checks `window.location.hash` for paths (e.g., `/#/app/dashboard?state=...`).
2.  Prioritizes the hash path if present to ensure `react-router` receives the correct target.
3.  Appends existing query parameters from `useLocation().search`.
4.  Uses `useNavigate` for the redirection.

```typescript
const RedirectWithQuery = ({ to }: { to: string }) => {
  // ... logic to preserve search params and handle hash paths
  if (window.location.pathname === to) return; // Prevent loop
  // ...
  navigate(target, { replace: true });
};
```

### State Verification

Location: `src/pages/dashboard/Dashboard.tsx`

Upon successful authentication, the provider redirects the user back to the application (defaulting to the Dashboard).

1.  The application retrieves the `state` parameter from the URL query string.
2.  It retrieves the stored state from `localStorage` (`portal_auth_state`).
3.  The two values are compared:
    *   **Match:** The verification succeeds, and the `portal_auth_state` is removed from `localStorage`.
    *   **Mismatch:** The verification fails. The user is alerted and immediately logged out via `signOut` to protect the session.

```typescript
useEffect(() => {
  const searchParams = new URLSearchParams(location.search);
  const state = searchParams.get('state');

  // Check if we have a state and haven't attempted verification yet in this mount
  if (state && !verificationAttempted.current) {
    verificationAttempted.current = true;
    const storedState = localStorage.getItem('portal_auth_state');
    if (storedState === state) {
      console.log('OAuth state verified successfully.');
      localStorage.removeItem('portal_auth_state');
      // Remove state from URL to prevent re-verification
      const newSearchParams = new URLSearchParams(location.search);
      newSearchParams.delete('state');
      navigate({ search: newSearchParams.toString() }, { replace: true });
    } else {
      console.error('OAuth state mismatch. Potential CSRF attack.');
      alert('OAuth state mismatch. Potential CSRF attack. Logging out...');
      signOut(userDispatch, navigate);
    }
  }
}, [location, navigate, userDispatch]);
```

## Testing State Mismatch (Manual Steps)

To manually verify the security logout mechanism:

1.  **Ensure you are logged in** to the application.
2.  Open your browser's **Developer Tools** (F12) and go to the **Console** tab.
3.  Set a dummy "valid" state in your local storage:
    ```javascript
    localStorage.setItem('portal_auth_state', 'my_secret_state');
    ```
4.  Manually modify the URL to include a *different* state parameter.
    *   Example: `https://localhost:3000/app/dashboard?state=attackers_fake_state`
    *   *Note:* If using hash routing, ensure it is inside the hash: `https://localhost:3000/#/app/dashboard?state=attackers_fake_state`
5.  **Press Enter** to navigate.

**Expected Result:**
1.  An alert appears: **"OAuth state mismatch. Potential CSRF attack. Logging out..."**
2.  The user is immediately signed out of the application.
