# Host-scoped Workflow publication and MCP routing

Status: proposed design, 2026-09-25. No implementation or live qualification is implied by this document.

## Decision

Portal keeps the editable and published copy of each Workflow definition. It deploys an immutable definition version to the customer's Workflow through a Host-scoped Gateway MCP Tool. Workflow validates the body and digest and stores the deployed version in its own `workflow_ops` operational schema. Portal does not connect to a customer database. Remove the local `workflow-projection-sync` SQL bridge after MCP publication and migration are working.

All Workflow runtimes register with controller-rs using service ID `com.networknt.workflow-1.0.0`. The public Gateway keeps one `/mcp` entry point. For a Workflow Tool call, it derives the Host from verified caller identity, obtains connected Workflow nodes for that Host and service ID over its existing controller WebSocket, and dispatches to an eligible node. The Tool argument `hostId` is checked against the verified Host and never selects a destination on its own.

Multiple Workflow runtimes for a Host form **one replica group** only when they share the same definition catalog and operational store. The MCP router may round robin across healthy replicas in such a group. Independently stored Workflow deployments are separate targets and cannot safely be pooled by Host alone.

## Current source behavior and gaps

- The Workflow Editor saves and publishes definitions through Portal commands; its published editing copy is in Portal's `configserver.wf_definition_t`. The current Editor publish command has no target runtime selection.
- The local Compose `workflow-projection-sync` copies definitions into `operations.workflow_ops.wf_definition_t` using PostgreSQL access. This is unsuitable when Portal and Workflow belong to different networks and operators.
- Process Info calls `workflow_list_processes` through Gateway MCP. Workflow start and process administration read Workflow's operational store.
- Gateway's registry client already sends `discovery/lookup` on its controller connection. The current discovery subscription contains service ID, optional environment tag, and protocol, but no Host ID. Controller currently filters connected nodes by those existing fields, so the result is not safe as a tenant route.
- MCP router currently resolves a Tool's fixed `targetHost` or `serviceId`/`envTag`. Its discovery-node selector chooses the first usable HTTPS node, or the first usable HTTP node; it does not round robin.
- Controller registration persists runtime identity in `runtime_instance_t`. A persisted row is not proof of a live connection. Routing must use controller's current connected state as well as registered ownership.

## Ownership and data flow

| Concern | Authority |
| --- | --- |
| Drafts, editing history, Portal publication state | Portal event-backed definition records |
| Client Tool ACL | Gateway |
| Runtime registration and connected-node discovery | Controller, backed by `runtime_instance_t` and live sessions |
| Deployed immutable definitions, process state, tasks, audit | Workflow `workflow_ops` |
| Runtime service configuration | Config Server snapshots |

```mermaid
sequenceDiagram
    participant UI as Portal UI
    participant P as Portal
    participant G as Gateway /mcp
    participant C as Controller
    participant W as Workflow replica group
    UI->>P: Publish saved definition version
    P->>P: Freeze and retain version
    P->>G: workflow_publish_definition (Host, ID, body, digest)
    G->>G: Verify caller and Host; apply Tool ACL
    G->>C: discovery/lookup (Host, Workflow service ID)
    C-->>G: Connected eligible nodes
    G->>W: Publish immutable version
    W->>W: Validate and persist in workflow_ops
    W-->>G: Definition ID and accepted digest
    G-->>P: Acknowledged result
    P-->>UI: Portal publication and deployment status
```

The same Host-scoped discovery and dispatch applies to start, Process Info, and task operations. Controller discovers and reports runtime nodes; Gateway performs client authorization. Controller discovery is not an alternate client-facing Workflow ACL.

## Host-scoped discovery contract

Extend controller's discovery lookup/subscription with a required `hostId` **for tenant-routed Workflow lookups**. Preserve the existing unscoped contract only for callers that are independently authorized to use it; a Gateway Workflow route must never fall back to unscoped discovery.

Example request on Gateway's existing controller connection:

```json
{
  "method": "discovery/lookup",
  "params": {
    "hostId": "<verified-host-uuid>",
    "serviceId": "com.networknt.workflow-1.0.0",
    "protocol": "https"
  }
}
```

Controller authorizes the Gateway's right to discover this Host, filters registration ownership by Host and service ID, then returns only connected and eligible nodes. The response includes runtime instance ID, registered address/protocol, and a registration generation or equivalent identity marker. A route cannot be synthesized from a caller-supplied address. Zero eligible nodes means unavailable; malformed or cross-Host results fail closed. The discovery response should not contain credentials.

Gateway can issue a lookup for each Tool call over its existing controller connection. No additional target cache is required for the initial design. A later subscription optimization must retain the same Host authorization and invalidation semantics. Lookup failure must not reuse a route from another Host.

## MCP router dispatch

Mark the native Workflow Tool family as Host-scoped discovery targets. After Gateway authenticates the caller and applies its existing Tool ACL, the router:

1. Derives the Host ID from verified identity and rejects a conflicting `hostId` in arguments.
2. Looks up `hostId + com.networknt.workflow-1.0.0` through controller.
3. Filters for connected, compatible Workflow nodes and a permitted transport.
4. Chooses a node by round robin within the Host's **eligible replica group**.
5. Dispatches with the required Gateway-to-Workflow authentication and original user context, preserving the operation's idempotency key.

Do not use the request's definition ID or process ID as a substitute for Host authorization. A UUID is an object identifier, not a tenant route. The discovery URL must come from controller's verified registration, not from Tool arguments. Existing Gateway and Workflow token verification remains in force; this design does not introduce mTLS or a second Workflow ACL policy engine.

The initial transport is HTTPS to a customer DMZ Gateway that exposes the internal Workflow MCP service under the customer's network policy. If a customer has no inbound route, a controller-mediated request/response relay over its persistent runtime WebSocket is a separate transport extension. Controller currently supports runtime commands and discovery, not a general Workflow MCP relay. Such a relay needs bounded payloads, correlation, timeout and disconnect handling, and preservation of Gateway's authenticated context.

## Replica eligibility and round robin

Round robin is safe for Workflow operations only if every selected replica observes the same deployed definitions, process records, task state, and idempotency ledger. The simplest qualifying deployment uses multiple Workflow processes sharing the same `workflow_ops` schema and artifact store, with compatible runtime configuration. Publication then persists once to the shared store; every replica reads the same immutable version.

Controller registration should identify a Workflow replica group or operational-store identity. Gateway must only round robin within one verified group for a Host. If a Host has nodes from different groups, routing fails as ambiguous until a target-selection and process-affinity contract is designed. Connection health, protocol compatibility, and deployment readiness govern eligibility; a mere registration row is insufficient.

Round robin advances per Host and group among eligible nodes. A retry may reach another replica, so publication, start, and task mutations must be idempotent across the shared store. A lost response after dispatch is **unconfirmed**, not proof that the operation failed. The client must retry with the same key or query status before creating a new operation.

## Definition publication and version lifecycle

The Editor first saves a draft in Portal. Publication freezes that exact Portal version and calls a new `workflow_publish_definition` administrative MCP Tool through Gateway. Its request contains Host ID, immutable `wfDefId`, logical name/namespace, version, definition body, digest, and an idempotency key. Workflow validates the pinned schema and digest, then inserts the version transactionally into `workflow_ops`. Replaying the same ID and digest succeeds without mutation; the same ID with different content fails. The response acknowledges the stored ID and digest.

Portal must record two distinguishable states: **published in Portal** and **deployed to Workflow**. A timeout or disconnected target leaves deployment pending or unconfirmed, with safe retry. A Portal publish command must not claim that Workflow accepted the version until its acknowledgment is verified. Reconciliation can compare the Portal publication record with a Workflow catalog/list or status Tool.

Each version has a distinct immutable definition ID. New publication does not overwrite an older body. A separate current/startable pointer selects the default for *new* starts; explicit starts pinned to an older version follow the product's startability policy. Preserve older versions while any active, waiting, or auditable process depends on them. Retirement and deletion require a separate retention rule and dependency check.

## Required implementation work

1. Add Host ownership to controller discovery lookup/subscription and response authorization, including live-connection filtering and tests that reject cross-Host discovery.
2. Add Host-scoped Workflow target resolution and per-Host round robin in MCP router; verify argument Host, connected-node and group eligibility, and no unscoped fallback.
3. Define customer DMZ Gateway registration/address and the Gateway-to-Gateway/Workflow authentication contract. Add controller relay later only if outbound-only connectivity is required.
4. Add immutable, idempotent Workflow definition publication and catalog/status Tools, with Gateway ACL and Workflow validation/storage.
5. Update Portal publication command, event-backed deployment status, Editor messages, and reconciliation. Preserve Portal's editing copy.
6. Qualify a shared-store replica group for start, Process Info, task commits, and publication under round robin, including disconnect and lost-response cases.
7. Remove `workflow-projection-sync` and its SQL/FDW deployment wiring only after existing definitions have been migrated and the new publication path is qualified.

## Acceptance criteria

- A Host A caller cannot discover, publish to, start on, or inspect Host B's Workflow, even by changing Tool arguments.
- Portal retains its immutable published version and reports deployment separately from Portal publication.
- Workflow rejects a mismatched digest or a conflicting reuse of a definition ID; replay of an identical publication succeeds.
- Two connected replicas sharing one operational store can alternate calls without missing definitions, processes, tasks, or idempotency results.
- An unavailable controller or empty/ambiguous eligible group fails closed with a retryable availability result where appropriate.
- Publication, start, Process Info, and task operations work through the selected Host's Gateway route; the SQL projection bridge is absent from the qualified deployment.
