# Endpoint Tools and Workflow Access

## Status

Implemented for the REST/HTTP first slice, with qualification still pending.
MCP and JSON-RPC palette builders remain later protocol extensions of the same
identity and grant model. Authentication metadata must explicitly resolve to
`type: none`; authenticated, unspecified-authentication, or
Portal-policy-protected HTTP endpoints remain fail-closed until delegated
credential support is implemented.

## Purpose

Light Portal imports API versions, derives their endpoints, and projects those
endpoints as Tools. A Tool adds the descriptions, schemas, examples, safety
metadata, and testing information needed by agents and workflow authors.

This design defines:

- how endpoint identity works across REST, MCP, and hybrid APIs;
- how an API endpoint becomes an enriched Tool;
- where workflow access is granted;
- how the Workflow Editor lists permitted Tools; and
- how a Tool is added as a call inside a fork branch.

The related designs are [Agent Skill And API Endpoint Discovery](../agent-skill-tool-discovery.md),
[Workflow Editor](../workflow-editor.md), and
[Workflow Version and Publication](./workflow-version-publication.md).

## Decision Summary

1. `api_endpoint_t.endpoint_id` remains the internal UUID identity used by
   database relationships.
2. `api_endpoint_t.endpoint` is the canonical protocol-native endpoint key.
3. The endpoint key is unique within a host and API version.
4. Every workflow-callable API endpoint has one endpoint-backed Tool.
5. The Tool owns the enriched LightAPI consumption document.
6. Workflow access is granted from `/app/genai/Tool`.
7. API Admin and Service Endpoint may provide bulk or contextual actions, but
   they use the same Tool workflow grant.
8. A workflow invoking a Tool is independent from a Tool implemented by a
   workflow. These are different relationships.
9. The Workflow Editor lists only Tools granted to the current workflow.
10. Runtime authorization uses the Tool grant and refuses to bypass endpoint
    access controls: protected endpoints are not callable in the first slice.

## Capability Flow

```text
API Version
  -> API Endpoint
       -> endpoint-backed Tool
            -> LightAPI description, validation, and tests
            -> workflow access grant
                 -> Workflow Editor palette
                      -> call task in a workflow or fork branch
```

The API version is the contract source. The endpoint is the runtime operation.
The Tool is the consumable capability. The workflow grant decides whether a
workflow may use that capability.

## Endpoint Identity

### Internal identity

The Portal database continues to use the existing UUID:

```text
host_id + endpoint_id
```

Permissions, rules, Tool mappings, and other relational data reference this
UUID. It is not typed into workflow YAML.

### Natural identity

The endpoint's natural identity is:

```text
host_id + api_version_id + endpoint
```

The database must enforce this identity with a unique constraint:

```sql
UNIQUE (host_id, api_version_id, endpoint)
```

`endpoint` is an opaque, protocol-native key. Consumers do not parse one API
type as though it were another.

| API type | Endpoint key example |
| --- | --- |
| REST/OpenAPI | `/customers/{customerId}/preferences@get` |
| MCP tool | `getCustomerPreferences@call` |
| Hybrid/JSON-RPC | `lightapi.net/customer/getPreferences/0.1.0` |

Endpoint producers must generate a deterministic canonical value:

- REST uses the normalized templated path and lowercase HTTP method.
- MCP uses the exact tool name and `call` operation.
- Hybrid uses `host/service/action/version`.

Changing the canonical endpoint key defines a different operation.

### Portable capability identity

LightAPI uses a qualified `endpointId` for agent, workflow, and cross-document
references. It is separate from the database UUID and protocol-native endpoint
key.

Examples:

```text
customer-api/customer.preferences.get
customer-mcp/getCustomerPreferences
light-portal/customer.getPreferences
```

The Tool stores this value as `capabilityRef`. An API version must not contain
two endpoints with the same `capabilityRef`.

## API Endpoint and Tool Responsibilities

### API endpoint

`api_endpoint_t` owns the parsed API contract and runtime identity:

- API version relationship;
- protocol-native endpoint key;
- HTTP method and path where applicable;
- generated input and response schemas;
- source protocol and lifecycle; and
- the internal endpoint UUID used by access control.

### Tool

`tool_t` is the agent- and workflow-facing capability projection. An
endpoint-backed Tool keeps its `endpoint_id` relationship and adds:

- Tool name and description;
- portable `capabilityRef`;
- enriched LightAPI endpoint document;
- safety and idempotency metadata;
- examples and test definitions;
- semantic discovery metadata;
- validation status and document digest; and
- workflow access status.

For an endpoint-backed Tool, the Tool and endpoint have a one-to-one
relationship within an API version.

## LightAPI Enrichment

The Tool uses the
[LightAPI Description Specification](https://github.com/agentic-workflow/lightapi-description-specification)
as its complete consumption contract.

The Portal generates a `profile: endpoint` document from the API endpoint and
allows the Tool administrator to enrich it. The document includes only the
sections relevant to the operation, including:

- `info` and source provenance;
- protocol invocation details;
- authentication and environments;
- logical input schema and wire request mapping;
- result schema, success cases, failures, and output extraction;
- examples and fixtures;
- safety, confirmation, and idempotency;
- capability classification and tags; and
- agent progressive-disclosure metadata.

Generated HTTP operations always carry explicit authentication metadata.
OpenAPI security requirements produce a protected `custom` marker, while an
operation that is public after applying operation-level overrides produces
`type: none`. Imported LightAPI operations without an explicit `none` contract
remain protected.

Example:

```yaml
lightapi: 0.1.0
profile: endpoint
info:
  title: Get Customer Preferences
  namespace: customer-api
  version: 1.0.0
operations:
  getCustomerPreferences:
    endpointId: customer-api/customer.preferences.get
    protocol: http
    method: GET
    endpoint: /customers/{customerId}/preferences
    metadata:
      portalEndpoint: /customers/{customerId}/preferences@get
    safety:
      destructive: false
    idempotency:
      safeToRetry: true
    input:
      schema:
        type: object
        required: [customerId]
        properties:
          customerId:
            type: string
```

Tool save validates the LightAPI schema and endpoint relationship. A dedicated
**Validate** action and the richer **Test** workspace remain follow-up work.
Testing will let the administrator select an environment and run an example or
test sequence. Privileged, destructive, or confirmation-required operations
must not run without the required approval.

## Workflow Access Grant

Workflow access belongs to the Tool because the Tool is the reviewed,
validated, and testable capability.

The grant is stored separately from descriptive LightAPI metadata:

```text
workflow_tool_grant_t
  host_id
  grant_id
  tool_id
  wf_def_id
  workflow_version             optional
  tool_version
  lightapi_digest
  allowed_environments
  aggregate_version
  active
  update_user
  update_ts
```

`wf_def_id` identifies the workflow allowed to use the Tool. When
`workflow_version` is present, the grant applies only to that immutable
workflow version. The Tool version and LightAPI digest pin the reviewed
capability contract.

There is one active grant aggregate for each Tool/workflow pair.
`workflow_version` is mutable scope on that aggregate: null applies to all
versions and a value narrows it to one version. Definition-wide and
version-specific grants therefore cannot coexist for the same Tool/workflow.

The grant is created and changed through Portal commands and events. Projection
tables are never edited directly.

Suggested commands:

- `grantWorkflowTool`
- `updateWorkflowToolGrant`
- `revokeWorkflowTool`

Suggested events:

- `WorkflowToolGrantedEvent`
- `WorkflowToolGrantUpdatedEvent`
- `WorkflowToolRevokedEvent`

## Separate Invocation Directions

Two relationships must remain distinct:

| Relationship | Meaning |
| --- | --- |
| Tool implemented by Workflow | Calling the Tool starts a selected published workflow. |
| Workflow granted Tool | A workflow call task may invoke the selected Tool. |

The second relationship does not depend on how the workflow starts. A
workflow has the same Tool grant whether it was started by an agent, user,
scheduler, API, or another workflow.

## Portal User Experience

### API Admin

From `/app/service/admin`, an administrator selects an API version and can:

- generate or refresh endpoint-backed Tools; and
- open the Tool catalog filtered to that API version.

### Service Endpoint

From `/app/serviceEndpoint`, an administrator can:

- inspect the protocol-native endpoint and generated schemas;
- open its mapped Tool;
- see the Tool's persisted validation status; and
- grant selected endpoint Tools through the same Tool grant command.

This page does not maintain a second workflow-access flag.

### Tool

From `/app/genai/Tool`, an administrator can:

- review and enrich the LightAPI document;
- see save-time validation results;
- select one workflow or workflow version;
- grant or revoke workflow access; and
- see which workflows currently use the Tool.

A dedicated **Validate** action and downstream **Test** workspace remain a
follow-up; this slice does not present save-time validation as execution test
evidence.

The normal action is named **Workflow Access**. It is not part of
`executionPlacement`, because execution placement describes how the Tool itself
is implemented.

## Workflow Editor Palette

The Workflow Editor queries a workflow-aware catalog:

```text
getWorkflowCallableTool(hostId, wfDefId, workflowVersion, environment)
```

The query returns only Tools whose grants and contracts are active and valid.
Each result contains enough trusted data to create a task:

- `toolId` and Tool version;
- `capabilityRef`;
- the grant's allowed environments and resolved/runtime-selected environment;
- API name and version;
- protocol-native endpoint key;
- protocol, method, and invocation mapping;
- input and result schemas;
- safety metadata; and
- LightAPI digest.

The palette groups results by API and API version. Users search by Tool name,
endpoint, capability, tags, or description.

Selecting a Tool creates the protocol-specific call task. The author does not
type an endpoint UUID, URL, method, or Tool name manually.

For REST/HTTP, the generated task carries logical path inputs plus query,
header, and body mappings. The runtime resolves those templates from workflow
context and applies them to the downstream request after resolving the physical
endpoint from the pinned LightAPI operation. The resolved URI must retain the
Portal API version target's scheme, host, and effective port. Absolute and
protocol-relative LightAPI endpoints that select another authority fail before
dispatch.

## Fork Branch Editor

When a fork step is selected, the property panel provides:

- editable fork step ID;
- editable branch names;
- **Add Branch** and **Remove Branch** actions;
- branch validation; and
- an **Add Step** action for each branch.

Branch names must be unique within the fork. Renaming a branch updates the YAML
key without changing the tasks inside that branch.

Choosing **Add Step** opens the normal step palette. Choosing a call task opens
the workflow-callable Tool selector described above. After selection, the
editor inserts the generated call beneath that branch and refreshes the YAML,
outline, and graph from the same parsed workflow model.

## Runtime Authorization

Before invoking the downstream operation, the workflow runtime resolves the
Tool and evaluates:

1. the workflow-to-Tool grant;
2. the pinned Tool version and LightAPI digest;
3. Tool and endpoint lifecycle state;
4. the selected environment;
5. the endpoint URI from the validated LightAPI operation and selected
   environment; and
6. whether authentication explicitly resolves to `type: none`, and whether the
   endpoint has active scope/rule configuration or role, group, user, position,
   or attribute permission rows.

A missing, revoked, inactive, or mismatched grant fails before a downstream
request is sent. In the first REST/HTTP slice, non-`none` or missing LightAPI
authentication or active endpoint scope/rule/RBAC/ABAC permission configuration
also fails closed.
Grant creation performs the same scope, rule, role, group, user, position, and
attribute checks, so an operator receives an explicit rejection instead of a
grant that later disappears from the callable catalog. Portal and runtime
operation selection both match endpoint ID, HTTP protocol, method, lifecycle,
and explicit unauthenticated status, then choose the first operation by key.
Grant validation sources the method from the linked Portal endpoint rather than
the Tool's optional `apiMethod` metadata; a missing endpoint method is reported
as a distinct validation error.
Delegated credential resolution is required before those protected endpoints
can be enabled.

The workflow identity authorizes use of an unprotected Tool. A later delegated
credential extension must preserve the initiating agent or user in the
execution and audit context before protected endpoints are callable.

## Pending Qualification Criteria

- The database enforces one canonical endpoint key per host and API version.
- REST, MCP, and hybrid endpoint producers generate deterministic keys.
- Every endpoint-backed Tool has an endpoint UUID and portable capability
  reference.
- The Tool LightAPI document validates against the supported specification
  version.
- Tool enrichment is preserved when generated endpoint fields are refreshed.
- Workflow access can be granted and revoked only through Portal events.
- Tool workflow access is independent from workflow-backed Tool execution.
- The callable-Tool query returns only Tools granted to the selected workflow.
- The Workflow Editor creates call tasks from trusted Tool data.
- Fork branches can be added, removed, and renamed from the property panel.
- A call can be added to any fork branch through the same Tool palette.
- Runtime execution rejects unavailable or unauthorized Tool calls before any
  downstream effect.
- Agent-, user-, scheduler-, API-, and workflow-started executions enforce the
  same workflow Tool grant.
