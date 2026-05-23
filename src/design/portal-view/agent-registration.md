# AI Agent Registration In Task Center

## Status

Initial Task Center implementation is available. The first version uses the
existing API-version and agent-definition commands with backend validation
guardrails. A dedicated composite registration command remains a later
automation enhancement.

## Context

Light Portal treats an AI agent as an API. The API record provides the stable
catalog identity, ownership, display name, marketplace metadata, and lifecycle.
The API version record provides the deployable version identity. The agent
definition record is an agent-specific profile extension for the same API
version.

The current data model already reflects this relationship:

- `api_t` owns the logical API and display name.
- `api_version_t` owns the API version identity.
- `agent_definition_t.agent_def_id` stores the same UUID as
  `api_version_t.api_version_id`.
- `agent_definition_t` stores model and runtime profile fields such as
  `model_provider`, `model_name`, `api_key_ref`, `temperature`, and
  `max_tokens`.
- Agent query paths join `agent_definition_t` to `api_version_t` and `api_t`
  to expose the effective agent metadata.

The registration UX should make this model explicit. Operators should not have
to understand the table split. They should see one task: register an AI agent.

## Goals

- Add a focused Task Center flow named `Register AI Agent`.
- Register the agent first as an API and API version.
- Create the agent definition profile using the same ID as the API version.
- Keep event sourcing and replay clean by using domain events instead of direct
  table writes.
- Avoid duplicating mutable display name fields between `api_t` and
  `agent_definition_t`.
- Allow skills, tools, memory, access control, and deployment links to be added
  after the base agent is registered.

## Non-Goals

- Do not create a second standalone agent registry independent from APIs.
- Do not make `AgentDefinitionCreatedEvent` create `api_version_t`.
- Do not make `ApiVersionCreatedEvent` directly write `agent_definition_t`
  unless the event schema is intentionally expanded later.
- Do not require all skill and tool assignments during the initial registration.
- Do not replace the existing `Manage GenAI Assets` task. That task remains the
  broader maintenance flow.

## Identity Model

The agent identity is the API version identity.

```text
api_t
  host_id
  api_id
  api_name              # canonical agent display name

api_version_t
  host_id
  api_version_id        # canonical agent definition id
  api_id
  api_version
  api_type = "agt"      # or accepted legacy value "agent"

agent_definition_t
  host_id
  agent_def_id          # same value as api_version_t.api_version_id
  model_provider
  model_name
  api_key_ref
  temperature
  max_tokens
```

`agent_definition_t` should remain a profile extension. It should not duplicate
the agent name. Reads can continue to expose `agentName`, but the value should
come from `api_t.api_name`.

### API Type

Use `agt` as the canonical API type for AI agents if the reference data uses the
short code model. During migration, command handlers and queries can accept
both `agt` and `agent` to avoid breaking existing test data or early records.

The Portal UI should display this as `Agent` and submit the canonical value.
Database columns use snake case such as `api_type`; event payloads and command
requests use camel case such as `apiType`. The mapper must preserve this
translation and normalize agent type values consistently.

When registering an agent against an existing API, the backend must validate the
existing API-version family. A logical API should not mix unrelated version
types. If the selected `api_t` already has active versions, they must all be
agent versions before an `agt` version can be added. The reverse should also be
enforced: once an API has an active agent version, non-agent API versions should
not be added under the same `api_id`.

## Event Model

The Task Center flow should produce two domain events for the required base
registration:

1. `ApiVersionCreatedEvent`
2. `AgentDefinitionCreatedEvent`

The two-event design is preferred because these are two separate domain facts:

- an API version exists and can participate in the API catalog;
- that API version has an agent runtime profile.

This should not be modeled as two direct table writes from one handler. The
event processor should continue to populate projection tables during normal
processing and replay.

### Event Order

`ApiVersionCreatedEvent` must be persisted and projected before
`AgentDefinitionCreatedEvent`, because `agent_definition_t` has a foreign key
to `api_version_t`.

```text
Register AI Agent
  -> ApiCreatedEvent, if the logical API does not already exist
  -> ApiVersionCreatedEvent
  -> AgentDefinitionCreatedEvent
  -> optional AgentSkillCreatedEvent events
  -> optional access-control events
```

The minimum required sequence for an existing API is:

```text
ApiVersionCreatedEvent
AgentDefinitionCreatedEvent
```

### Aggregate IDs

`ApiVersionCreatedEvent` keeps the API version aggregate identity:

```json
{
  "aggregateType": "ApiVersion",
  "subject": "<apiVersionId>",
  "data": {
    "hostId": "<hostId>",
    "apiId": "<apiId>",
    "apiVersionId": "<apiVersionId>",
    "apiVersion": "1.0.0",
    "apiType": "agt"
  }
}
```

`AgentDefinitionCreatedEvent` uses the same UUID for its aggregate identity:

```json
{
  "aggregateType": "AgentDefinition",
  "subject": "<apiVersionId>",
  "data": {
    "hostId": "<hostId>",
    "agentDefId": "<apiVersionId>",
    "apiVersionId": "<apiVersionId>",
    "modelProvider": "openai",
    "modelName": "gpt-4.1",
    "apiKeyRef": "secret://openai/default",
    "temperature": 0.7,
    "maxTokens": 4096
  }
}
```

The event utility should continue to accept either `agentDefId` or
`apiVersionId` for AgentDefinition aggregate ID calculation, but the canonical
payload should include both during migration and treat them as equal.

## Task Center Flow

Add a Task Center definition:

```text
id: register-ai-agent
title: Register AI Agent
category: API Marketplace or Portal Administration
roles: user, admin
keywords: agent, ai, genai, model, skill, tool
```

The task should guide the operator through a narrow registration path. It is
different from `Manage GenAI Assets`, which is a broad maintenance task for
agents, skills, tools, memory, and session history.

### Steps

| Step | Required | Route | Purpose |
| --- | --- | --- | --- |
| Create or select API | Yes | `/app/form/createApi` or API selector | Establish the logical API record and canonical agent name. |
| Create agent API version | Yes | `/app/form/createApiVersion?apiType=agt` | Create `api_version_t` with agent API type and return `apiVersionId`. |
| Configure agent profile | Yes | `/app/form/createAgentDefinition` or `/app/genai/AgentDefinition` | Create `agent_definition_t` with `agentDefId = apiVersionId`. |
| Assign skills | No | `/app/genai/AgentSkill` | Attach curated skills to the agent. |
| Review tools | No | `/app/genai/Tool` or `/app/genai/SkillTool` | Confirm agent-invokable tools through skill-tool assignments. |
| Configure access | No | `/app/access/rolePermission` | Restrict who can invoke or manage the agent. |
| Link runtime instance | No | `/app/instance/InstanceApi` | Attach the agent API version to a deployed runtime or gateway if needed. |

### Task Context

The task context should carry IDs from one step to the next:

```json
{
  "hostId": "<hostId>",
  "apiId": "<apiId>",
  "apiVersionId": "<apiVersionId>",
  "agentDefId": "<apiVersionId>",
  "serviceId": "<serviceId>",
  "providerId": "<modelProvider>",
  "apiType": "agt"
}
```

When the API version step completes, `apiVersionId` should be copied to
`agentDefId` automatically before launching the agent definition step.

### Incomplete Registration Handling

If the UI calls `createApiVersion` and then fails before `createAgentDefinition`
is processed, the system can contain an agent API version without an agent
definition. This is an incomplete registration, not a valid runnable agent.

The UI and query layer should treat these rows explicitly:

- Agent list views should be able to detect agent API versions missing matching
  `agent_definition_t` rows by left joining `api_version_t` to
  `agent_definition_t`.
- The row should be shown as `Incomplete` or `Profile missing`, not as a ready
  agent.
- The primary action should be `Complete profile`, prefilled with
  `agentDefId = apiVersionId`.
- A secondary action can delete or deactivate the orphaned API version if the
  operator abandons the registration.
- Runtime catalog reads should not expose incomplete agents as executable.

This requirement makes the UI-orchestrated implementation safe enough for the
first Task Center version. The long-term backend command should still create the
version and profile in one ordered command to reduce orphan creation.

## Frontend Design

### Phase 1: Task Registry Only

The first implementation can add a Task Center entry that reuses existing pages
and forms:

- `createApi`
- `createApiVersion`
- `createAgentDefinition`
- `AgentSkill`
- `SkillTool`
- `rolePermission`
- `InstanceApi`

This is low risk and aligns with the current task-oriented navigation model.

The `createApiVersion` form should support prefilled `apiType=agt` from the
task route. The form completion handler should save returned `apiVersionId` into
the task context.

The `createAgentDefinition` form should accept `apiVersionId` or `agentDefId`
from task context and submit both values, with `agentDefId` equal to
`apiVersionId`.

### Phase 2: Dedicated Registration Wizard

After the flow is validated, add a dedicated wizard route such as:

```text
/app/genai/register-agent
```

The wizard can reduce clicks by combining API version and agent profile fields
on one page while still submitting separate commands or a composite command.

Recommended sections:

- API identity: API name, API ID, status, owner.
- Version identity: version, service ID, environment tag, target host.
- Model profile: provider, model, API key reference, temperature, max tokens.
- Optional skills: selected skill IDs.
- Optional deployment: instance or gateway link.

### Secret Reference Selection

`apiKeyRef` is a secret reference, not a secret value. The UI should not ask
operators to paste raw provider keys into the agent definition form.

The preferred control is a selector populated from the configured secret
catalog, config-server reference data, or vault integration available to the
current host. The selected value should be stored as a reference such as:

```text
secret://openai/default
```

If manual entry is temporarily supported, it should be an advanced path with
validation. The command should reject values that look like raw API keys and
should accept only approved reference schemes.

### Secure Default Access

The access-control step is optional for registration completeness, but runtime
execution must be secure by default. A newly registered agent should not be
publicly invokable just because the API version and profile exist.

Default behavior:

- management is limited to the creator, owner, or admin roles according to the
  existing ownership model;
- runtime invocation is denied until an explicit role, scope, policy, or runtime
  assignment grants access;
- skill and tool assignment does not override access control;
- if no access policy exists, the gateway or agent runtime should treat the
  effective execution policy as deny-all.

## Backend Command Options

### Option 1: UI-Orchestrated Existing Commands

The Task Center flow calls existing commands in sequence:

1. `createApi`, if a new API is needed.
2. `createApiVersion`.
3. `createAgentDefinition`.
4. Optional `createAgentSkill` events.

This is the recommended initial implementation. It avoids changing command
handler infrastructure and uses existing event types.

This option must include incomplete-registration handling. Without that, a
browser failure or second-command validation error can leave an agent API
version without an agent definition. That state is repairable, but the UI must
surface it clearly and runtime catalog reads must ignore it.

### Option 2: Composite Register Command

Add a composite command such as:

```text
lightapi.net/genai/registerAiAgent/0.1.0
```

The command would validate the combined request and emit ordered events:

1. `ApiVersionCreatedEvent`.
2. `AgentDefinitionCreatedEvent`.
3. Optional `AgentSkillCreatedEvent` events.

This improves user experience for automation and API consumers, but it requires
the command layer to support a multi-event result in one request. The command
must not bypass event processing or write projection tables directly.

The initial composite command should require an existing `apiId`. Keeping API
creation as a separate command keeps the backend contract smaller and preserves
the existing API ownership workflow. A later full registration command can add
`ApiCreatedEvent` if automation needs to create the logical API and agent
version in one request.

### Recommendation

Start with Option 1 only if incomplete registrations are visible and repairable.
Prioritize Option 2 before exposing a one-click production registration wizard,
because it gives the backend one validation boundary for the API version and
agent profile.

## Validation Rules

Command handlers should enforce these rules server-side:

- Agent API versions must use `apiType = agt` or an accepted compatible value.
- New writes should use canonical `agt`. Legacy `agent` should be accepted only
  for migration, import, or replay compatibility.
- A logical API should not mix active agent and non-agent API versions.
- `agentDefId` must equal `apiVersionId` when both are present.
- The referenced API version must exist before creating the agent definition.
- The referenced API version must belong to the same `hostId`.
- The referenced API version must have agent API type.
- `modelProvider` and `modelName` are required for creation.
- `apiKeyRef`, when present, must be a secret reference and not a raw provider
  key.
- `temperature`, when provided, must be in the supported provider range.
- `maxTokens`, when provided, must be positive.
- Optional skill IDs must reference active skills in the same host scope.

The UI should guide the user, but the command and persistence layers should
remain authoritative.

## Query And Display

Agent list and detail views should display a joined projection:

| Field | Source |
| --- | --- |
| `agentDefId` | `agent_definition_t.agent_def_id` |
| `apiVersionId` | same value as `agentDefId` |
| `agentName` | `api_t.api_name` |
| `apiId` | `api_version_t.api_id` |
| `apiVersion` | `api_version_t.api_version` |
| `apiType` | `api_version_t.api_type` |
| `serviceId` | `api_version_t.service_id` |
| `envTag` | `api_version_t.env_tag` |
| `targetHost` | `api_version_t.target_host` |
| `modelProvider` | `agent_definition_t.model_provider` |
| `modelName` | `agent_definition_t.model_name` |
| `apiKeyRef` | `agent_definition_t.api_key_ref` |

The Agent Definition page should make the API identity read-only once selected.
Mutable profile fields should remain editable through
`AgentDefinitionUpdatedEvent`.

## Delete And Update Semantics

Updating the API name should update the visible agent name because the display
name comes from `api_t.api_name`.

Updating the API version should not implicitly update model settings. Model
profile changes should use `AgentDefinitionUpdatedEvent`.

Deleting or deactivating the API version should cascade or hide the agent
definition through the existing API-version relationship. Explicit
`AgentDefinitionDeletedEvent` remains useful when the operator wants to disable
the agent profile while keeping the API version.

## Migration Notes

- Existing rows that use `api_type = agent` can remain readable while the UI
  moves toward canonical `agt`.
- Projection builders can normalize legacy `agent` events to `agt` in
  `api_version_t` after the migration window. Event streams remain immutable,
  but new command writes should use only `agt`.
- Existing task contexts may carry either `apiVersionId` or `agentDefId`.
  Task utilities should normalize both values to the same ID.
- Documentation and form labels should say `Agent API version id` where the ID
  is exposed.
- Import/export and event replay should preserve event order for agent
  registration bundles.

## Implementation Plan

1. Add `Register AI Agent` to `portal-view/src/tasks/taskRegistry.ts`.
2. Add help content under `src/help/portal-view/tasks/register-ai-agent.md`.
3. Ensure `createApiVersion` can be launched with `apiType=agt`.
4. Ensure form completion stores `apiVersionId` into task context.
5. Ensure `createAgentDefinition` can prefill `agentDefId` from
   `apiVersionId`.
6. Add server-side validation that `agentDefId == apiVersionId`.
7. Add compatibility handling for `agt` and `agent` API type values.
8. Add incomplete-registration detection and repair actions for agent API
   versions that do not have a matching agent definition.
9. Add secure-by-default invocation checks for agents with no explicit access
   policy.
10. Add integration tests for the two-event registration sequence.
11. Add a composite `registerAiAgent` command for API-version plus profile
    creation.

## Resolved Recommendations

- Persist `agt` as the canonical API type after migration. Keep `agent` readable
  for replay, import, and old data, but reject new command writes using
  `agent` after the migration window.
- Put `Register AI Agent` under `API Marketplace` initially because the agent is
  registered as an API and should be discoverable through the API catalog. If a
  dedicated `GenAI Assets` category is added later, the task can move there
  without changing the backend model.
- Keep skill assignment optional. An agent can be useful as an LLM-only worker,
  and required skill assignment would block simple conversational agents.
- The first composite command should require an existing API and emit
  `ApiVersionCreatedEvent` plus `AgentDefinitionCreatedEvent`. Keep
  `ApiCreatedEvent` separate until automation needs a full create-everything
  command.

## Decision Summary

Register AI agents through a Task Center flow that starts from API and API
version registration. Create `api_version_t` first, then create
`agent_definition_t` with `agentDefId` equal to `apiVersionId`. Use two domain
events for the two required facts, keep projection writes behind event
processing, reject mixed API-type families, treat incomplete version-only
registrations as repairable but non-runnable, default runtime invocation to
deny-all, and make the broader skill/tool/access setup optional follow-up steps.
