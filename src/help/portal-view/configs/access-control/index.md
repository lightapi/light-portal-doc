# Access Control

The Access Control configuration defines the global policies for request authorization and response filtering in the gateway. The configuration resides in `access-control.yml` and is managed through the portal-view interface and config server.

The gateway uses a shared access-control runtime (implemented in `light-pingora`) that applies to both **HTTP API access control** and **MCP router access control**.

## Overview of Configuration Properties

| Property | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| **[enabled](./enabled.md)** | Boolean | `false` | Global switch to enable or disable access-control checking and response filtering. |
| **[accessRuleLogic](./access-rule-logic.md)** | String | `"any"` | Rule execution logic (`any` or `all`) when multiple `req-acc` rules are matched. |
| **[defaultDeny](./default-deny.md)** | Boolean | `true` | Fallback policy when no authorization rules are defined for a requested endpoint. |
| **[defaultInclude](./default-include.md)** | Boolean | `false` | Fallback policy for response row filtering when a user's claims do not match any rules. |
| **[skipPathPrefixes](./skip-path-prefixes.md)** | Array of String | `[]` | List of path or tool name prefixes that bypass access control checking and filtering. |

---

## HTTP API Access Control vs. MCP Router Access Control

The properties configured in `access-control.yml` affect HTTP API traffic and Model Context Protocol (MCP) tools in complementary ways.

### 1. HTTP API Access Control
For regular HTTP API traffic, the access control runtime operates in the gateway handler chain:
* **Request Authorization (`req-acc`)**: Evaluates Celsius (CEL) expressions and role-based policies before forwarding the request to downstream services.
* **Response Filtering (`res-fil`)**: Modifies the downstream HTTP response (filtering out unauthorized JSON fields/columns or rows) before returning the response to the client.

### 2. MCP Router Access Control
For MCP traffic, the router leverages the same runtime but adapts the phases specifically for JSON-RPC tool calls (`tools/call`):
* **Request Authorization (`req-acc`)**: Runs prior to invoking the downstream HTTP or local MCP tool. If authorized, the tool is called.
* **Response Filtering (`res-fil`)**: Evaluates row and column filters on the JSON payload contained within the MCP result (`structuredContent` and text content) before delivering it back to the AI agent.
* **System Operations**: Standard MCP lifecycle requests (e.g., `initialize`, `tools/list`) bypass access control and are handled directly by the router.
