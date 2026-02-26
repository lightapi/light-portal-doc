# MCP Registry Design for AI Gateway

This document outlines the registration and management strategy for Model Context Protocol (MCP) tools within the AI Gateway.

## Registration Strategy: The Hybrid Model

For a robust and scalable AI Gateway, the recommended approach is a **Hybrid Model**: **Register the MCP Server as the primary entity, but manage and expose the Tools individually.**

This approach balances the technical requirements of connectivity with the operational requirements of governance, security, and performance.

---

### 1. Register the Server (The "Connection" Layer)

The MCP Server should be treated as the **source of truth** and the primary unit of connectivity.

*   **Centralized Configuration:** Authentication (API keys, OAuth), base URLs, transport protocols (SSE or Stdio), and environment variables are defined at the server level.
*   **Connectivity Management:** A single server acts as a wrapper around related APIs. Registering tools individually would create significant overhead and redundant connections.
*   **Lifecycle & Health Monitoring:** If an MCP server goes down, all its tools become unavailable. It is more efficient to monitor health and availability at the server level.
*   **Dynamic Discovery:** The MCP protocol includes a `tools/list` capability. By registering the server, the gateway can automatically sync and discover new tools when the server is updated, eliminating the need for manual registration of every new function.

### 2. Expose Tools Individually (The "Governance" Layer)

While the gateway connects to the *server*, it should expose and manage *tools* as individual objects. This is crucial for:

*   **Granular Permissions (RBAC):** Access control can be applied at the tool level. For example, a "Finance" team might be granted access to a `get-invoice` tool but restricted from a `modify-ledger` tool, even if both reside on the same ERP server.
*   **Context Window Optimization:** Large Language Models (LLMs) have limited context windows. Sending all 50 tools from a large server to an LLM wastes tokens and increases the "lost in the middle" effect. The Gateway should allow for the activation of specific subsets of tools for a given AI session or agent.
*   **Rate Limiting & Cost Control:** High-compute or high-cost tools (e.g., `generate-video`) can be rate-limited or billed differently compared to lightweight tools (e.g., `get-weather`).
*   **Safety & Compliance:** Metadata can be attached to individual tools to flag them as `Read-Only`, `Destructive`, or `Sensitive`, enabling specific security flows (like "Human-in-the-loop" approvals) for risky operations.

---

## Recommended Architecture: The "Catalog" Pattern

The implementation should follow a "Catalog" or "App Store" pattern:

1.  **Provider/Server Registration:** An admin registers a server (e.g., "The GitHub MCP Server") with its credentials.
2.  **Automated Discovery:** The Gateway calls the server's `list_tools` method and populates a tool catalog.
3.  **Governance & Activation:** Admins "enable" specific tools for specific model configurations or user groups.
4.  **Routing Layer:** When a model requests a tool, the Gateway resolves the request to the owning Server and handles the underlying communication.

---

## Comparison of Approaches

| Feature | Individual Registration | Group (Server) Registration | **Recommended: Hybrid** |
| :--- | :--- | :--- | :--- |
| **Management** | Extremely difficult (manual entry for every tool) | Easy (single connection) | **Optimal** (Auto-sync tools from server) |
| **Security** | Granular (Tool-level RBAC) | Coarse (All-or-nothing access) | **Granular** (Policy per tool) |
| **LLM Context** | Precise | Potential for bloating | **Precise** (Selectable subsets) |
| **Maintenance** | High (Breaks if tool name changes) | Low | **Low** (Unified lifecycle) |
| **Connectivity** | Redundant connections | Efficient | **Efficient** (One connection, many tools) |

---

## Data Model & Schema Design

The AI Gateway leverages the existing API registry schema used by `light-gateway`, with specific enhancements to accommodate the unique requirements of the MCP protocol.

### Conceptual Mapping

| MCP Concept | light-gateway Table | Mapping Strategy |
| :--- | :--- | :--- |
| **MCP Server** | `api_t` | Represents the top-level service (e.g., "Postgres MCP Server"). |
| **Server Instance** | `api_version_t` | Manages the connectivity parameters and the overall tool manifest. |
| **MCP Tool** | `api_endpoint_t` | Each tool is registered as an individual endpoint belonging to an MCP version. |
| **Tool Permissions**| `api_endpoint_scope_t`| Handles RBAC and scope-based access to specific tools. |

### Core Tables & Enhancements

To support MCP, the following schema adjustments are implemented:

#### 1. API Version (Server Connection)
The `api_version_t` table is enhanced to store transport-level configurations for stdio or SSE connections.

```sql
ALTER TABLE api_version_t ADD COLUMN transport_config TEXT;
-- JSON Example for transport_config: 
-- {"transport": "stdio", "command": "npx", "args": ["-y", "@mcp/server-google"]}
```

#### 2. API Endpoint (Tool Definition)
The `api_endpoint_t` table acts as the tool registry. We relax the traditional HTTP method constraints and add fields for MCP tool metadata.

```sql
-- Allow 'call' as a valid operation for MCP tools
ALTER TABLE api_endpoint_t DROP CONSTRAINT api_endpoint_t_http_method_check;
ALTER TABLE api_endpoint_t ADD CHECK ( http_method IN ( 'delete', 'get', 'patch', 'post', 'put', 'call' ) );

-- Store the Tool Schema (for LLM validation) and Metadata (for safety flags)
ALTER TABLE api_endpoint_t ADD COLUMN tool_schema TEXT;   -- JSON Schema of the tool inputs
ALTER TABLE api_endpoint_t ADD COLUMN tool_metadata TEXT; -- e.g., {"destructive": true, "read_only": false}
```

### Full Registry Schema Reference

```sql
-- API Definition (The MCP Server)
CREATE TABLE api_t (
    host_id                 UUID NOT NULL,
    api_id                  VARCHAR(16) NOT NULL,
    api_name                VARCHAR(128) NOT NULL,
    api_desc                VARCHAR(1024),
    api_status              VARCHAR(32) NOT NULL,
    active                  BOOLEAN NOT NULL DEFAULT TRUE,
    PRIMARY KEY (host_id, api_id)
);

-- API Version (The Connection/Transport)
CREATE TABLE api_version_t (
    host_id                 UUID NOT NULL,
    api_version_id          UUID NOT NULL,
    api_id                  VARCHAR(16) NOT NULL,
    api_version             VARCHAR(16) NOT NULL,
    api_type                VARCHAR(7) NOT NULL,    -- 'mcp', 'openapi', etc.
    transport_config        TEXT,                   -- MCP-specific connection data
    spec                    TEXT,                   -- Full tool manifest (optional)
    active                  BOOLEAN NOT NULL DEFAULT TRUE,
    PRIMARY KEY(host_id, api_version_id),
    FOREIGN KEY(host_id, api_id) REFERENCES api_t(host_id, api_id) ON DELETE CASCADE
);

-- API Endpoint (The Individual Tool)
CREATE TABLE api_endpoint_t (
    host_id              UUID NOT NULL,
    endpoint_id          UUID NOT NULL,
    api_version_id       UUID NOT NULL,
    endpoint             VARCHAR(1024) NOT NULL,  -- Tool Name
    http_method          VARCHAR(10),             -- 'call' for MCP
    endpoint_name        VARCHAR(128) NOT NULL,
    endpoint_desc        VARCHAR(1024),
    tool_schema          TEXT,                    -- Input parameter validation
    tool_metadata        TEXT,                    -- Safety and cost metadata
    active               BOOLEAN NOT NULL DEFAULT TRUE,
    PRIMARY KEY(host_id, endpoint_id),
    FOREIGN KEY(host_id, api_version_id) REFERENCES api_version_t(host_id, api_version_id) ON DELETE CASCADE
);
```

---

## Tool Metadata & Synchronization

Populating the `api_endpoint_t` table involves coordinating data from the MCP Server with operational policies defined within the AI Gateway.

### Sources of Metadata

The metadata for each tool is synthesized from three primary sources:

#### 1. Standard MCP Server Response (Automated)
When the Gateway performs a `tools/list` call, the MCP server provides the baseline technical definition for each tool.
- **Source Fields:** `name`, `description`, `inputSchema`.
- **Mapping:** These are mapped directly to `endpoint`, `endpoint_desc`, and `tool_schema` respectively.

#### 2. Gateway Operational Enrichment (Manual/Policy)
Since the standard MCP protocol does not include operational flags (like safety or cost), the AI Gateway manages these in the `tool_metadata` JSON column.
- **Administrative Enrichment:** Platform admins use the Gateway UI to tag specific tools. Common tags include:
    - `destructive: true`: Triggers a warning or confirmation flow.
    - `human_approval_required: true`: Places the request in a queue for manual sign-off.
    - `cost_tier: "high"`: Used for rate-limiting or internal billing.
- **Heuristic Auto-Tagging:** The Gateway can automatically infer metadata based on patterns. For example, any tool starting with `get_` or `list_` is auto-flagged as `read_only: true`.

#### 3. Protocol Extensions (Custom)
The MCP specification allows for additional properties in the tool object. If a custom MCP server includes an extra `metadata` or `annotations` block, the Gateway's synchronization logic can be configured to capture and store these directly.

---

### Synchronization Workflow

The following lifecycle ensures the Gateway’s registry remains accurate:

1.  **Connection**: The Gateway establishes a connection to the server using the `transport_config`.
2.  **Discovery (Sync)**: The Gateway calls `tools/list` and performs an "upsert" for all tools found.
    - Existing tools have their `tool_schema` and `endpoint_desc` updated.
    - New tools are created with a default `active` status and baseline `tool_metadata`.
3.  **Review**: An administrator reviews the newly discovered tools in the Gateway dashboard.
4.  **Governance Policy**: The administrator "enables" the tool for specific roles and configures any required safety metadata (e.g., flagging the `drop_table` tool as `destructive`).
5.  **LLM Execution**: When a model calls the tool, the Gateway uses the stored `tool_schema` for pre-flight validation and the `tool_metadata` to enforce security policies.
