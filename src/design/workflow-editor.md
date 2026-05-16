# Workflow Editor

## Purpose

The Workflow Editor is the generic Portal authoring surface for
`light-workflow` definitions. It should replace the raw textarea-only workflow
definition experience with a structured editor that still preserves YAML as the
canonical workflow definition stored in `wf_definition_t.definition`.

The editor is reusable. It can be opened from the Workflow Definition page,
embedded in the Skill Workspace, or used by future task-specific authoring
flows such as API onboarding, scheduled live tests, and remediation playbooks.

## Design Boundary

`light-workflow` owns workflow execution, task state, retries, waiting human
tasks, and audit events. The Portal editor authors definitions and starts test
runs, but it must not implement its own workflow runtime.

The gateway remains the runtime tool execution path. Workflow steps that invoke
tools should reference gateway-visible tools or endpoint descriptions and then
execute through the same runtime path used by agents.

The editor should not duplicate endpoint contracts. API, MCP, JSON-RPC, gRPC,
and other endpoint details belong in LightAPI descriptions, OpenAPI/OpenRPC
documents, protobuf metadata, or the portal endpoint catalog. Workflow tasks
reference those descriptions and provide step-level wiring, guards, exports,
and error handling.

## Current State

The current Portal implementation already has the persistence and generic CRUD
surface needed for a first editor:

- `wf_definition_t` stores `namespace`, `name`, `version`, and `definition`.
- `workflow-command` exposes create, update, delete, and start workflow
  commands.
- `workflow-query` exposes workflow definition reads.
- `portal-view` has a Workflow Definition table and generic create/update
  forms whose `definition` field is a YAML textarea.

The first Workflow Editor can therefore be an incremental UI improvement over
the existing definition CRUD and start workflow command.

## Goals

- Keep workflow YAML as the canonical persisted artifact.
- Provide a readable step outline or graph next to the YAML editor.
- Validate definitions before save and before test runs.
- Let users discover and reference endpoint descriptions, gateway tools,
  skills, rules, and human task types from a side panel.
- Support workflow definition create, update, import, export, and start-test
  flows.
- Make the editor embeddable so skill authoring can use the same workflow
  authoring component with skill-specific constraints.
- Preserve owner scoping and existing Portal command/query conventions.

## Non-Goals

- Do not execute workflow logic in Portal View.
- Do not make skills the workflow runtime.
- Do not store workflow YAML in `skill_t`.
- Do not require a visual drag-and-drop graph before the editor is useful.
- Do not copy full API contracts into workflow steps when endpoint
  descriptions can be referenced.
- Do not fork or embed the Apache KIE Serverless Logic Web Tools as the first
  implementation path. They are useful reference material for CNCF Serverless
  Workflow concepts, but they are tightly coupled to the strict upstream spec
  and would be expensive to adapt for Light-Fabric agentic extensions.

## Authoring Model

The editor should maintain two synchronized representations:

| Representation | Purpose |
| --- | --- |
| YAML source | Canonical text saved to `wf_definition_t.definition`. |
| Parsed view model | UI-only representation used for step outline, validation, references, and property panels. |

All saves should serialize from the YAML source or from a parsed model that
round-trips to the same specification format. If the visual editor changes a
step, it should update the YAML and keep the YAML visible.

The editor should support progressive enhancement:

1. YAML editor plus parsed step outline.
2. Step palette and property panel that edit YAML safely.
3. Read-only graph preview.
4. Drag-and-drop graph editing once round-trip behavior is reliable.

## Implementation Architecture

The recommended implementation is a custom React editor built from focused
building blocks:

| Component | Recommended library | Responsibility |
| --- | --- | --- |
| Source editor | CodeMirror 6 with JSON/YAML extensions | Edit YAML/JSON, validate against the Light-Fabric workflow schema, provide autocomplete, lint markers, folding, and hover help. |
| Visual graph | React Flow / xyflow | Render workflow states as nodes and transitions as edges, with custom node components for agentic task types. |
| Property panels | Schema-backed React forms, optionally JSONForms | Edit selected node/task properties without forcing users to hand-edit every YAML field. |
| State manager | Existing portal state pattern or Zustand if a local editor store is needed | Hold the canonical workflow document, parsed model, diagnostics, selected node, dirty state, and test run state. |

The workflow YAML or JSON document remains the source of truth. CodeMirror edits
parse into the editor store. The parsed workflow model is then projected into
React Flow nodes and edges. React Flow edits update the same model and then
serialize back to the YAML document.

This avoids adding a second large browser editor runtime to `portal-view`,
which already uses CodeMirror for Markdown and OpenAPI JSON/YAML editing. It
also avoids fighting a visualizer that only understands the strict CNCF
Serverless Workflow schema, while still letting Portal define first-class
visual treatments for Light-Fabric task types such as `agent`, `mcp`, `ask`,
`assert`, `rule`, `switch`, and future LLM or approval-oriented steps.

CodeMirror should use a custom JSON Schema derived from the CNCF Serverless
Workflow schema plus Light-Fabric agentic extensions. For JSON definitions,
use a CodeMirror 6 JSON Schema integration such as `codemirror-json-schema` to
provide linting, autocomplete, and hover details. For YAML definitions, reuse
the existing portal-view CodeMirror YAML setup where possible and add schema
validation through a YAML language-server bridge or equivalent worker-backed
integration. The goal is Monaco-like schema assistance without Monaco's bundle
cost.

React Flow should not own the persisted shape. It owns layout, selection, edge
creation, and node interaction. The persisted workflow definition should remain
independent of the canvas library so a future editor or CLI can read the same
definitions.

Recommended sync behavior:

1. Parse CodeMirror content into a typed workflow model when the YAML is valid.
2. Preserve text edits and show problems when YAML is invalid; do not destroy
   the user's in-progress text.
3. Project valid workflow models to React Flow nodes and edges.
4. Let graph edge changes update transition targets in the model.
5. Let property-panel changes update the model through schema-aware controls.
6. Serialize model changes back into the YAML document using stable formatting.
7. Keep conflict handling explicit when source edits and graph edits race.

Mermaid can be used for documentation or a lightweight read-only preview, but
it is not the long-term authoring surface. JSONForms can be useful inside
property panels, but it should not replace the graph/source editor combination.

## Layout

Recommended first layout:

| Region | Contents |
| --- | --- |
| Header | Namespace, name, version, owner, active state, save, validate, import, export, and test actions. |
| Left panel | Step outline, problems, references, and search. |
| Main panel | YAML editor with syntax highlighting and parse markers. |
| Right panel | Selected step properties, input/output/export preview, and endpoint/tool metadata. |
| Bottom panel | Test input, validation results, workflow events, waiting tasks, and output. |

The generic Workflow Definition page can use the full layout. The Skill
Workspace can embed the same editor with a narrower reference scope and a
skill-aware validation profile.

## Step Palette

The editor should understand the task types defined by the Light-Fabric
agentic workflow design:

| Step type | Use |
| --- | --- |
| `ask` | Pause for human input, approval, or missing values. |
| `assert` | Validate context, API results, or business rules. |
| `http` / `openapi` | Invoke HTTP endpoints directly or through cataloged descriptions. |
| `jsonrpc` / `openrpc` | Invoke JSON-RPC methods directly or through OpenRPC descriptions. |
| `grpc` | Invoke cataloged gRPC methods. |
| `mcp` | Invoke gateway-visible MCP tools, resources, or prompts. |
| `rule` | Delegate complex checks to Light-Rule. |
| `agent` | Delegate a bounded task to an agent worker. |
| `switch` / `condition` | Branch based on workflow context or task output. |
| `set` / `export` | Move task results into workflow context. |
| `wait` | Represent a durable wait, timeout, or externally completed task. |

The palette should create minimal valid YAML fragments. Users can then edit the
full YAML when advanced options are needed.

## Reference Panel

The editor should help authors reference existing catalog objects instead of
typing fragile identifiers by hand:

- workflow definitions and versions,
- LightAPI endpoint descriptions,
- API endpoints and tool projections,
- gateway-visible MCP tools,
- rule definitions,
- agent definitions,
- skills and skill-linked tools when the editor is embedded in the Skill
  Workspace.

For generic workflow authoring, the reference panel can show all objects the
current user is allowed to read. For skill authoring, it should filter tools to
the skill's linked tools and flag references outside that set.

## Validation

Validation should run in layers:

| Layer | Checks |
| --- | --- |
| Syntax | YAML parses, document shape is valid, and duplicate keys are rejected when possible. |
| Specification | Required workflow fields, step IDs, task type structure, branch targets, exports, and inputs are valid. |
| Catalog references | Referenced endpoint descriptions, tools, rules, agents, and child workflows exist and are active. |
| Security | Sensitive or destructive steps have required approval, visibility, and ownership metadata. |
| Skill embedding | Workflow tool calls are linked through `skill_tool_t` when editing a workflow-backed skill. |
| Runtime diagnostics | Optional gateway `tools/list` checks compare cataloged tool names with deployed gateway availability. |

Runtime diagnostics should be separate from persistence validation. A workflow
definition can be saved before a gateway is reachable, but the editor should
make missing runtime executability visible before test or deployment.

## Test Runner

The editor should support a test panel that starts a workflow instance through
the existing workflow start command and then reads instance events and task
state through the workflow query APIs.

The test panel should support:

- JSON workflow input,
- start run,
- event stream or polling view,
- current context and output preview,
- waiting task completion for `ask` or approval steps,
- assertion and rule failure display,
- gateway or endpoint call failure display,
- rerun with the same input.

The test runner is a client of `light-workflow`; it does not execute workflow
steps in the browser.

## Skill Workspace Integration

Phase 3.5 skill authoring should embed the Workflow Editor rather than create a
second skill-specific workflow UI.

Recommended integration:

1. The Skill Workspace has a Workflow tab.
2. The tab lets the user choose `none` or `workflow-backed`.
3. In workflow-backed mode, the user can select an existing workflow definition
   or create a draft definition.
4. The link is stored in `skill_workflow_t`.
5. The editor reference panel filters tool references to the tools linked by
   `skill_tool_t`.
6. Validation rejects or warns on workflow tool calls not present in the
   skill's allowed tool set.
7. The Test tab starts the linked workflow with sample JSON input and displays
   the same workflow events used by the generic editor.

This keeps the skill as a discovery and guidance artifact while `light-workflow`
owns deterministic orchestration.

## Data And API Changes

The first generic editor can reuse existing workflow definition APIs. Later
phases should add editor-friendly endpoints only when they remove real UI
complexity.

Phase B adds the validation endpoint and keeps the reference catalog composed
from existing read models. A single combined catalog endpoint remains optional
if the multiple list queries become noisy or slow.

| API or table | Purpose |
| --- | --- |
| `validateWfDefinition` | Server-side validation using the workflow query service parser and, later, the same schema as `light-workflow`. |
| `formatWfDefinition` | Optional canonical formatting if the workflow parser supports round-trip formatting. |
| Existing catalog queries | Fetch endpoint, tool, rule, agent, and workflow labels for the reference panel. |
| `getWorkflowReferenceCatalog` | Optional future consolidation into one reference-panel query. |
| `startWorkflow` | Start an editor test run for the saved workflow definition with sample JSON input. |
| Workflow runtime read models | Refresh process, task, task assignment, worklist, and audit-log projections for the current workflow instance. |
| `completeTask` | Complete a waiting `ask` or human task from the editor test panel by emitting a `TaskInfoUpdatedEvent`. |
| `skill_workflow_t` | Link skills to workflow definitions without embedding workflow YAML in skills. |
| `saveSkillWorkspace` | Composite command that saves skill metadata, taxonomy, tool links, workflow links, and optional draft workflow updates from one workspace action. |

Server-side validation should be authoritative. Client-side validation is useful
for responsiveness but should not be the only guard before saving or testing a
workflow definition.

## Phased Implementation

### Phase A: Structured YAML Editor

- Add a generic Workflow Editor component and route.
- Replace create/update workflow definition textarea navigation with the editor
  where practical.
- Keep YAML visible and canonical.
- Reuse the existing portal-view CodeMirror editor stack with the Light-Fabric
  workflow schema for YAML/JSON validation, autocomplete, hover help, folding,
  and parse markers.
- Parse YAML client-side to render a step outline and problems panel.
- Add import/export and basic validation before save.

### Phase B: Catalog-Aware Authoring

- Add a reference panel for endpoint descriptions, tools, rules, agents, and
  workflow definitions.
- Add a step palette that inserts valid YAML snippets.
- Add schema-backed property panels for selected steps. Use dropdowns for
  catalog references and constrained enums instead of free-text fields where
  Portal already has authoritative labels.
- Add server-side validation through `validateWfDefinition`.
- Add runtime diagnostics that compare MCP tool references with gateway
  `tools/list` or the Rust agent `/diagnostics/tools` endpoint when a gateway
  target is selected.

### Phase C: Test And Worklist Integration

- Add a test runner panel backed by `light-workflow` start and query APIs.
- Show workflow events, current task state, waiting human tasks, assertions,
  and final output.
- Let users complete `ask` tasks from the test panel.
- Link failed test runs to remediation tasks or worklist entries.

Phase C uses the existing Portal workflow command/query boundary. The editor
starts a test run through `workflow/startWorkflow`, then refreshes
`getProcessInfo`, `getTaskInfo`, `getTaskAsst`, `getWorklist`, and
`getAuditLog` for the returned `wfInstanceId`. The test panel completes a
waiting human task through `workflow/completeTask`, which preserves the
structured response in the event data and materializes the task as completed
through the existing `TaskInfoUpdatedEvent` projection.

The panel should expose remediation links instead of silently creating
production work. Failed process or task rows can open a prefilled remediation
task form, and task assignments can jump to the workflow worklist with the
current workflow instance context.

### Phase D: Visual Graph Editing

- Add a React Flow graph preview after the outline is stable.
- Represent Light-Fabric task types with custom React Flow nodes and explicit
  transition edges.
- Add drag-and-drop graph editing only after YAML/model round-trip behavior is
  reliable.
- Keep YAML as the source of truth even when visual editing is enabled.

## Recommendation

Build the generic Workflow Editor before the Skill Workspace embeds workflow
authoring. The skill UI should provide context and constraints, while the
workflow editor provides YAML editing, step preview, validation, and test runs
for every workflow authoring use case in Portal.
