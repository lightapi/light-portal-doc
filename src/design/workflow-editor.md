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
| Source editor | CodeMirror 6 with JSON/YAML extensions | Edit YAML/JSON, provide immediate parse diagnostics, folding, and lint markers, and display authoritative server validation results. |
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

CodeMirror should continue to provide immediate YAML parse diagnostics while
the server applies the canonical Agentic Workflow JSON Schema. The browser may
later use schema-derived autocomplete and hover information, but it must not
carry an independently maintained schema or become the authoritative validator.
This keeps validation behavior consistent for editor actions and AI-generated
drafts without adding a large schema-validation runtime to `portal-view`.

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

## Canonical Schema Ownership And Distribution

The canonical schema is
`workflow-specification/schema/workflow.yaml`. It is a Draft 2020-12 JSON
Schema expressed as YAML and identifies the supported Agentic Workflow DSL
with its `$id`. Its local `$ref` values resolve through `#/$defs`, so runtime
validation does not require network access.

`workflow-query` should carry an immutable copy at
`src/main/resources/schema/workflow-1.0.3.yaml`. A neighboring manifest should
record at least:

- the schema `$id` and DSL version;
- the SHA-256 digest of the exact bundled bytes;
- the source repository and full source commit;
- the pinned upstream Open Workflow commit and digest.

A synchronization script copies the schema and provenance from an explicit
`workflow-specification` checkout and regenerates the manifest. A verification
test recomputes the digest and rejects a missing, malformed, or mismatched
resource. Schema updates must therefore be deliberate code changes reviewed
with their source commit and conformance evidence.

Production code must not fetch the schema from GitHub, follow the moving
`master` branch, or fall back to a remote copy. Remote retrieval introduces
startup availability, latency, supply-chain, and version-drift risks. GitHub
may be used by CI to detect an available specification update, but the running
service always uses its bundled resource.

The schema is loaded and compiled once by a thread-safe
`WorkflowSchemaValidator`. The validator verifies the manifest and schema
identity during initialization. A missing or invalid schema prevents schema
validation from reporting success.

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

The YAML cursor, Steps list, and Visual Graph share one selected top-level
workflow step. Moving the cursor anywhere inside a `do` item selects that step
in the other views. When a step is selected, the palette offers insertion
immediately before or after it; with the cursor outside a recognized step, it
appends to the workflow. Invalid or incomplete YAML must not cause an
unstructured text insertion. If the selected anchor is no longer present, the
editor reports the stale selection instead of silently appending. Step identity
and container priority are shared by the cursor, Steps list, Visual Graph, and
insertion path, including `name`/`id`-shaped and map-shaped legacy containers.
An explicit fork-branch insertion target remains active while the YAML cursor
moves and is cleared only after insertion, a different explicit selection, or
the user chooses **Top level**.

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

Phase B uses the existing validation endpoint and keeps the reference catalog
composed from existing read models. A single combined catalog endpoint remains
optional if the multiple list queries become noisy or slow.

| API or table | Purpose |
| --- | --- |
| `validateWfDefinition` | Authoritative YAML, bundled JSON Schema, runtime-profile, and reference validation. Returns stable problem locations plus the schema id and digest. |
| `formatWfDefinition` | Optional canonical formatting if the workflow parser supports round-trip formatting. |
| Existing catalog queries | Fetch endpoint, tool, rule, agent, and workflow labels for the reference panel. |
| `getWorkflowReferenceCatalog` | Optional future consolidation into one reference-panel query. |
| `startWorkflow` | Start an editor test run for the saved workflow definition with sample JSON input. |
| Workflow runtime read models | Refresh process, task, task assignment, worklist, and audit-log projections for the current workflow instance. |
| `completeTask` | Complete a waiting `ask` or human task from the editor test panel by emitting a `TaskInfoUpdatedEvent`. |
| `skill_workflow_t` | Link skills to workflow definitions without embedding workflow YAML in skills. |
| `saveSkillWorkspace` | Composite command that saves skill metadata, taxonomy, tool links, workflow links, and optional draft workflow updates from one workspace action. |

Server-side validation is authoritative. Client-side parsing remains useful for
responsiveness, but it is not sufficient before validating, saving, testing, or
publishing a workflow definition. Those editor actions fail closed when the
validation endpoint or bundled schema is unavailable; the UI must not translate
an unavailable validator into a successful result.

### Validation Pipeline

`validateWfDefinition` applies checks in a stable order so authors see syntax
and structural failures before runtime-specific findings:

1. Reject a blank definition, malformed YAML, duplicate mapping keys, and a
   non-object root.
2. Apply the stricter AI-authoring and runtime policy checks first when that
   profile is requested, so repair guidance prioritizes actionable policy and
   authorization failures over JSON Schema `oneOf` branch detail.
3. Convert the safely parsed YAML value to a Jackson tree and validate it with
   the bundled Draft 2020-12 schema.
4. Normalize, de-duplicate, and cap schema failures into deterministic problems
   containing severity, instance path, schema path or keyword, and message.
5. Apply the remaining Light runtime capability checks, including supported
   expression languages, task kinds, call variants, and transports.
6. Validate authorization-filtered Tool references and durable Tool pins.

Schema acceptance and runtime executability are distinct. The JSON Schema
defines a valid Agentic Workflow document; runtime checks may still reject a
schema-valid feature that the deployed Light Workflow runtime does not execute.
Policy and authorization checks must therefore remain after schema validation
rather than being replaced by it.

The response includes `schemaId`, `schemaVersion`, and `schemaDigest` when the
bundled schema loads, even when the definition fails. A schema-load failure is
returned as a normal blocking validation problem with empty identity fields so
the Portal fails closed. Policy problems retain priority; schema problems are
sorted, de-duplicated, and capped so repeated validation produces stable,
bounded output. The Portal problems panel should show the instance path and
message without exposing Java implementation details.

### AI-Assisted Authoring

Ask AI uses the same bundled schema snapshot and `WorkflowSchemaValidator` as
the Validate button. A validation-equivalent prompt form strips annotation-only
JSON Schema fields such as descriptions, titles, comments, examples, and
defaults while retaining every constraint and `$ref`; it is placed in the
trusted system-message prefix with the full schema's id and digest. User intent,
existing definitions, and authorization-filtered Tool descriptions remain
bounded, sanitized data in a separate user message; Tool descriptions and their
schemas are never treated as instructions.

The preferred model response contains the workflow definition as a JSON object
inside the existing authoring result envelope. The server validates that object
and serializes it to canonical YAML only after it passes. Providers that support
strict structured output may receive the workflow schema as the `definition`
subschema, but local deterministic validation is still mandatory because
provider capabilities and supported JSON Schema keywords vary.

Schema text is part of the complete prompt budget. The generator must bound the
assembled schema, authoring context, existing definition, approved operations,
and requested output against the selected model's context window; the existing
authoring-context byte limit alone is not enough. A provider may cache the
static schema prefix, but correctness cannot depend on prompt caching.

After the first model response, the server applies canonical schema, runtime,
policy, and Tool-authorization validation. It may make one bounded repair
request containing the same schema identity, the rejected candidate, and a
limited deterministic error list. A second failure rejects the draft rather
than looping or returning an invalid proposal. If the repair prompt does not fit
the complete prompt budget, the original validation failure is returned instead
of replacing it with a prompt-size error.

Authoring provenance records the workflow schema id, digest, bundled schema
version, prompt-template version, source Tool schema digests, model, request
digest, and generated-definition digest. Human review and the existing
post-approval definition-digest check remain required.

## Schema Validation And AI Authoring Implementation Plan

Status: implemented on 2026-08-14 across `workflow-query`, `workflow-command`,
and `portal-view`. The stages below remain the maintenance and verification
contract for future schema upgrades.

### S1: Pin The Resource

Owners: `workflow-specification`, `workflow-query`, `workflow-command`.

- Add the versioned schema and manifest under `workflow-query` resources.
- Add the explicit synchronization script and digest verification test.
- Run the existing `workflow-specification` Draft 2020-12 and fixture
  conformance checks before accepting a synchronized update.

Gate: the service test suite proves the resource is valid Draft 2020-12, has the
expected `$id`, contains only resolvable local references, and matches the
manifest digest.

### S2: Make Validation Schema-Backed

Owner: `workflow-query`.

- Add the singleton `WorkflowSchemaValidator` and compile the resource once.
- Invoke it from `ValidateWfDefinition` after safe YAML parsing. Run the
  AI-profile and authorization checks first so bounded repair feedback retains
  actionable policy failures ahead of schema branch diagnostics.
- Return stable schema locations, keywords, messages, and schema identity.
- Replace tests that accept legacy `steps`-only or incomplete documents with
  canonical fixtures, while retaining explicit rejection coverage for those
  old shapes.

Gate: every valid specification fixture passes, every invalid fixture fails,
and targeted tests independently cover schema-invalid/runtime-valid and
schema-valid/runtime-unsupported definitions.

### S3: Enforce The Editor Boundary

Owner: `portal-view`.

- Display server schema paths in the existing Problems panel.
- Make Validate, Save, Test, and Publish stop when authoritative validation is
  unavailable or returns a schema error.
- Keep immediate browser YAML diagnostics, but do not duplicate the canonical
  validator or schema copy in the frontend bundle.

Gate: component tests prove schema errors are visible and no persistence or test
request is sent after a failed or unavailable authoritative validation.

### S4: Ground And Validate Ask AI

Owners: `workflow-query`, `portal-view`.

- Add the compact pinned schema and identity to the trusted prompt prefix.
- Bump the prompt-template version and enforce a complete prompt budget.
- Prefer a structured workflow object, validate it locally, serialize it to
  YAML, and allow at most one validation-guided repair.
- Add schema identity to authoring provenance and display it in the review
  dialog.

Gate: tests capture the prompt's exact schema id and digest, reject an invalid
first and repaired response, accept a valid repaired response, preserve Tool
authorization boundaries, and verify the applied YAML against the same bundled
validator.

### S5: Persistence Admission Hardening

Owner: `workflow-command`.

The editor validation call protects the normal UI path but is not a security
boundary for direct command callers. Create, update, and publish commands apply
the identical schema snapshot before persistence alongside their existing Tool,
runtime, and AI-authoring admission rules. Without a shared Maven artifact, the
command service carries the same generated resource and manifest through the
same synchronization process; the parity gate compares the two bundled schema
identities and bytes to prevent drift. Definition conformance failures remain
client input errors, while failure to load or compile the bundled schema is a
logged server error and must never be attributed to the submitted definition.

Gate: command tests reject schema-invalid definitions without relying on a prior
Portal query call, and a cross-repository check proves query and command schema
ids and digests are identical.

### Persisted Legacy Workflow Rollout

Enabling canonical admission is intentionally a compatibility break for stored
definitions that use legacy roots such as `steps`, `tasks`, or `states` instead
of the specification's required `document` and `do` roots. Those definitions
remain readable, but the editor reports them as invalid and publish admission
rejects an unchanged legacy draft. Owners can update a draft by replacing its
definition with canonical YAML; after that update passes validation, it can be
published normally.

Before enabling this enforcement in an environment with existing workflow
data, inventory persisted definitions by host, workflow id, and version using
the same pinned schema digest deployed to query and command services. Notify
owners of invalid drafts, migrate or re-author each definition, and validate
the replacement through the editor before publishing. Existing published
versions should remain immutable for auditability; create a new canonical
version instead of rewriting published history. The rollout gate is zero
unresolved legacy drafts that are expected to be published, plus an explicit
owner disposition for every remaining invalid stored definition.

### Known Debt: Secret Keyword Screening On Existing Definitions

The authoring guard screens `existingDefinition` with the secret *key* pattern
in addition to the secret *value* pattern, and it matches anywhere in the text.
Any definition that merely mentions a word such as `authorization` — an HTTP
header name, an `authorizationPolicy` field, or the word inside a free-text
`description` — is refused with
`WORKFLOW_AUTHORING_SECRET_IN_EXISTING_DEFINITION` even though it carries no
credential. This is pre-existing behaviour rather than a regression from
schema-backed validation: the guard has always applied the key pattern to the
whole definition with a substring match, so tightening the pattern's anchoring
did not change which definitions are refused.

The debt is that a keyword screen is the wrong instrument for a document body.
Key-name matching is appropriate where a key name is being inspected, which is
the sanitizer's per-key path; for definition text only the value pattern
distinguishes an actual credential from a field name. Resolving this means
screening `existingDefinition` with the value pattern alone, and it must be
taken as its own change with its own test coverage, because relaxing a guard
that currently fails closed is a security-relevant decision that should not
ride along with an unrelated fix. Until then, authors revising a definition
that names an authorization concept must strip the wording or start from a new
draft.

## Phased Implementation

### Phase A: Structured YAML Editor

- Add a generic Workflow Editor component and route.
- Replace create/update workflow definition textarea navigation with the editor
  where practical.
- Keep YAML visible and canonical.
- Reuse the existing portal-view CodeMirror editor stack for YAML parsing,
  folding, and parse markers, and display authoritative schema findings returned
  by the server.
- Parse YAML client-side to render a step outline and problems panel.
- Add import/export and basic validation before save.

### Phase B: Catalog-Aware Authoring

- Add a reference panel for endpoint descriptions, tools, rules, agents, and
  workflow definitions.
- Add a step palette that inserts valid YAML snippets.
- Add schema-backed property panels for selected steps. Use dropdowns for
  catalog references and constrained enums instead of free-text fields where
  Portal already has authoritative labels.
- Complete schema-backed server validation through `validateWfDefinition`.
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

Phase D adds the graph as a projection of the parsed YAML model, not a separate
persisted representation. The graph reads `steps`, `tasks`, `states`, or `do`
containers and renders one custom React Flow node per detected step. Node
styling reflects the Light-Fabric task type, and the graph can overlay runtime
task status from the Phase C test-run read models when the workflow task id
matches a graph step id.

Explicit transition fields such as `next`, `then`, `to`, and `transition`
become solid graph edges. Ordered fallback edges are shown as dashed edges so
authors can distinguish model transitions from inferred sequence. Creating an
edge in React Flow updates the source step's transition in YAML, and deleting an
explicit edge removes that transition target from YAML. Dragging nodes changes
only the authoring layout in the browser session; it does not mutate the saved
workflow definition.

The graph must continue to tolerate partial or invalid authoring states. If the
YAML cannot be parsed into a known workflow container, the editor keeps the
source editor and validation panels usable and shows an empty graph state rather
than blocking authoring.

## Recommendation

Build the generic Workflow Editor before the Skill Workspace embeds workflow
authoring. The skill UI should provide context and constraints, while the
workflow editor provides YAML editing, step preview, validation, and test runs
for every workflow authoring use case in Portal.
