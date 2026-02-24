# Mutliple Environment


This document outlines the necessary changes to configure portal view to work dynamically across different environments (sdx, dev, non-prod, prod) using environment-specific configuration.

## 1. Environment Variables Setup

### Create .env File

Create environment-specific .env files in project root:

```
# Environment variables
# VITE_BASE_PATH is used as the base URL prefix for API calls.
VITE_BASE_PATH=/bff/admin/
# VITE_PORTAL_URL is the full absolute URL where the frontend static files are served
VITE_PORTAL_URL=https://sdx.lightapi.net/bff
```

### Required Environment Variables

*   **VITE_BASE_PATH:** Defines the sub-path where your application is deployed.
*   **VITE_PORTAL_URL:** The API endpoint base URL.

### Benefits of .env Configuration

*   Switch environments without code changes
*   Maintain a single codebase for all environments

## 2. Vite Configuration Changes

**File:** `vite.config.js`
**Location:** Project root

**Required Change:**

```javascript
import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');

  return {
    plugins: [react()],
    base: env.VITE_BASE_PATH || "/",
    // ... other configurations
  };
});
```

### Why This Change is Necessary?

**The Problem Without `base` Configuration**

When your application is deployed to a sub-path rather than the domain root, all asset references break.

| Deployment Scenario | Required `base` Value |
| :--- | :--- |
| `https://example.com/` | `"/"` (default) |
| `https://example.com/portal/`| `"/portal/"` |
| `https://example.com/app/v2/` | `"/app/v2/"` |

### What `base` Affects

The `base` configuration controls how Vite prefixes:

*   Static asset URLs (JavaScript, CSS, images, fonts)
*   Client-side routing paths
*   Public folder references

### Example: Without vs With `base`

**Without `base` Configuration:**

*   App hosted at: `https://example.com/portal/`
*   Vite generates: `<script src="/assets/index.js">`
*   Browser requests: `https://example.com/assets/index.js`
*   Result: 404 Not Found ❌

**With `base`: "/portal/":**

*   App hosted at: `https://example.com/portal/`
*   Vite generates: `<script src="/portal/assets/index.js">`
*   Browser requests: `https://example.com/portal/assets/index.js`
*   Result: Success ✅

## 3. React Router Configuration Changes

**File:** `App.tsx`
**Location:** `src/App.tsx`

**Required Change:**

```jsx
import { BrowserRouter } from 'react-router-dom';

function App() {
  const basename = import.meta.env.VITE_BASE_PATH || "/";

  return (
    <BrowserRouter basename={basename}>
      {/* Your app routes and components */}
    </BrowserRouter>
  );
}

export default App;
```

### What `basename` Does

The `basename` prop tells React Router the base URL prefix for all routes in your application.

### Routing Behavior Comparison

| Scenario | Without basename | With basename="/portal" |
| :--- | :--- | :--- |
| `<Link to="/dashboard">` | Navigates to `/dashboard` | Navigates to `/portal/dashboard` |
| `path="/settings"` matches | `/settings` | `/portal/settings` |
| `useNavigate("/login")` | Goes to `/login` | Goes to `/portal/login` |

### Why It's Required

When your app is hosted at a sub-path (e.g., `https://example.com/portal/`), React Router needs to know that `/portal` is the deployment prefix, not part of your route definitions.

**Without `basename`:**
1.  You define `<Route path="/dashboard" />`
2.  User visits `/portal/dashboard`
3.  React Router sees `/portal/dashboard` → no match → **Route Not Found ❌**

**With `basename="/portal"`:**
1.  React Router strips `/portal` from the URL
2.  Sees `/dashboard` → matches your route → **Success ✅**

## 4. API Call Configuration

### Current Behavior Issue

Without a configured base URL, the browser constructs API request URLs relative to the current page origin.

**Example:**

*   App running at: `https://example.com/portal/dashboard`
*   API call: `fetch('/api/users')`
*   Browser sends request to: `https://example.com/api/users`

This may work in some cases but breaks when:

*   API is hosted on a different domain/subdomain
*   API has a different base path
*   Cross-environment consistency is needed

### Solution: Custom Fetch Wrapper

**File:** `src/utils/fetchClient.js`

```javascript
const BASE_URL = import.meta.env.VITE_API_BASE_URL || "";

/**
 * Custom fetch wrapper with automatic base URL prefixing
 * @param {string} endpoint - API endpoint path (e.g., '/api/users')
 * @param {Object} options - Fetch options (method, headers, body, etc.)
 * @returns {Promise} - Response JSON
 */
async function fetchClient(endpoint, options = {}) {
  const url = `${BASE_URL}${endpoint}`;

  const defaultHeaders = {
    "Content-Type": "application/json",
  };

  const config = {
    ...options,
    headers: {
      ...defaultHeaders,
      ...options.headers,
    },
  };

  const response = await fetch(url, config);

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }

  return response.json();
}

export default fetchClient;
```

### Usage Example

```javascript
import fetchClient from './utils/fetchClient';

// GET request
const users = await fetchClient('/api/users');

// POST request
const newUser = await fetchClient('/api/users', {
  method: 'POST',
  body: JSON.stringify({ name: 'John Doe', email: 'john@example.com' }),
});

// With custom headers
const data = await fetchClient('/api/protected', {
  headers: {
    'Authorization': `Bearer ${token}`,
  },
});
```

### Benefits

*   **Consistency:** All API calls use the same base URL
*   **Environment flexibility:** Different API endpoints per environment
*   **Maintainability:** Single place to update API configuration
*   **Error handling:** Centralized response validation

## 5. Build and Deployment Steps

**Step 1: Change the .env variables for specific environment (sdx, dev, prod etc.)**

```
VITE_BASE_PATH=/ (base path)
VITE_PORTAL_URL=https://example.com (endpoint URL)
```

**Step 2: Build**

```bash
npm run build
```
```
