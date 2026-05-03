# Too Many Pages/Forms

The portal has accumulated many pages, generated forms, custom admin screens,
and feature-specific entry points. The sidebar can expose these pages, but it
does not help a user understand which pages are required to finish a real
business task. The MCP Gateway quick start wizard is a useful experiment, but
it also shows the limitation of a rigid linear wizard: real tasks have optional
steps, pre-existing data, and multiple valid starting points.

This document proposes a task-oriented navigation layer for `portal-view`.

## Problem

Users currently need to know the portal information architecture before they
can complete a task. For example, onboarding an API to MCP Gateway may require
some combination of:

- create or select an API
- create or select an API version
- link the API version to a gateway or sidecar instance
- select MCP tools
- configure access control
- revisit instance, API, or role administration later

The same pattern exists across other areas. A task is not a single route; it is
a sequence of related pages and forms. The current navigation model makes users
pick pages first, then infer the task process themselves.

## Current MCP Wizard Observation

The MCP Gateway wizard already has useful building blocks:

- `flowConfig.tsx` keeps step metadata in one place.
- `McpServerForm.tsx` renders a generic wizard shell.
- `useMcpPrefill.ts` can resume from URL context such as `apiId`,
  `apiVersionId`, and `instanceApiId`.
- Several steps are marked skippable.

However, the wizard is still too rigid:

- Step order is linear even when the task is naturally conditional.
- Initial step selection relies on hard-coded step numbers.
- Optional work is represented as skip buttons instead of task state.
- The wizard duplicates or wraps existing forms instead of treating existing
  pages/forms as first-class task steps.
- The solution is specific to MCP Gateway and does not help users navigate the
  rest of the portal.

## Design Goals

- Let users start from a task, not a page name.
- Keep existing pages and generated forms as the source of truth.
- Support multiple entry points into the same task.
- Detect what has already been completed and show only relevant next actions.
- Support optional, required, blocked, complete, and skipped steps.
- Preserve role-based visibility and host-specific context.
- Allow users to leave a task, return later, and continue from context.
- Make the approach reusable for MCP, API publishing, access control,
  deployment, config promotion, migration, and admin workflows.

## Non-Goals

- Do not replace every admin page with a wizard.
- Do not create a separate custom form for each task if an existing generated
  form already works.
- Do not use the sidebar as the only navigation surface.
- Do not force a strict step sequence when the data model allows safe jumping.

## Proposed Solution

Add a task-oriented navigation layer above the current pages/forms.

The main pieces are:

1. Task Center
2. Task Registry
3. Task Progress Resolver
4. Task Navigation Shell
5. Global Search and Command Palette
6. Contextual Next Actions

## Task Center

The Task Center is a page where users choose what they want to accomplish. It
should group work by intent, not by implementation table.

Example task groups:

- API Marketplace
  - Register a new API
  - Add an API version
  - Publish an API
  - Review API details
- MCP Gateway
  - Onboard an existing API to MCP Gateway
  - Register a standalone MCP server
  - Configure MCP tools
  - Configure MCP access control
- Access Control
  - Create role
  - Assign permissions
  - Configure endpoint access
- Platform Operations
  - Register controller/gateway instance
  - Link API version to instance
  - Promote configuration
- Portal Administration
  - Manage host users
  - Export/import portal data
  - Convert migration snapshot

Each task card should show:

- title
- short description
- required role
- common starting object, such as API, instance, host, or client
- progress status when the current context is known
- primary action such as Start, Continue, Review, or Fix Missing Step

## Task Registry

Introduce a registry that describes tasks and steps declaratively. This is the
generalized version of the current MCP `flowConfig.tsx`, but it should route to
existing pages/forms instead of rendering every step inside one wizard.

Example TypeScript shape:

```ts
export type TaskDefinition = {
  id: string;
  title: string;
  description: string;
  category: string;
  roles?: string[];
  keywords: string[];
  entryPoints: TaskEntryPoint[];
  steps: TaskStep[];
};

export type TaskStep = {
  id: string;
  title: string;
  description?: string;
  required: boolean;
  dependsOn?: string[];
  route: (ctx: TaskContext) => string;
  formId?: string;
  completeWhen?: TaskCompletionCheck;
  visibleWhen?: TaskVisibilityCheck;
  blockedWhen?: TaskBlockedCheck;
};
```

The task registry should live close to portal navigation code, for example:

```text
src/tasks/taskRegistry.ts
src/tasks/taskTypes.ts
src/tasks/resolvers/
src/pages/tasks/TaskCenter.tsx
src/pages/tasks/TaskDetail.tsx
```

## Page And Form Metadata

To make search and tasks work well, pages and generated forms need metadata.

For generated forms, the metadata can come from `Forms.json` plus a small
registry override when the form title is not enough.

For custom pages, add a route/page registry:

```ts
export type PageDefinition = {
  route: string;
  title: string;
  description?: string;
  category: string;
  roles?: string[];
  keywords: string[];
  entities?: string[];
};
```

This registry can feed:

- sidebar sections
- Task Center
- command palette
- page breadcrumbs
- contextual next actions

The important rule is that page/form metadata should be reused, not copied into
each wizard.

## Task Progress Resolver

A task should not blindly ask users to complete steps that are already done.
Each task can have a resolver that checks the current host and entity context.

For MCP Gateway, the resolver can check:

- API exists
- API version exists
- instance API link exists
- MCP tool configuration exists
- access control exists

The UI then marks each step:

- Complete
- Required
- Optional
- Blocked
- Skipped
- Needs review

The resolver should use existing query endpoints where possible. The first
implementation can query on page load. Later, it can cache per task/session.

## Task Navigation Shell

Instead of a full-screen wizard that owns all steps, use a task shell that can
wrap or accompany existing pages.

Recommended behavior:

- A task detail page shows the checklist and current state.
- Selecting a step navigates to the existing page/form with task context in the
  URL or router state.
- The target page shows a compact "Task" panel or return link.
- After save, the user can return to the checklist or continue to the next
  recommended step.

Example URL:

```text
/app/form/createService?task=mcp-onboard-api&returnTo=/app/tasks/mcp-onboard-api
```

This keeps existing page behavior intact while adding guided navigation.

## Global Search And Command Palette

The portal should have a global launcher. It should search tasks, pages, forms,
and entities.

Examples:

- "onboard mcp"
- "create api"
- "auth client"
- "relation type"
- "instance api"
- "export snapshot"

Search results should be role-aware and host-aware.

Result types:

- Task
- Page
- Form
- Entity
- Recent item

This is the fastest way to help expert users without forcing them through a
wizard.

## Contextual Next Actions

Detail pages should expose next actions based on the current entity.

Examples:

- API detail
  - Add version
  - Link version to gateway
  - Configure MCP tools
  - Configure access control
- Instance detail
  - Link API version
  - Configure MCP tools
  - View gateway servers
- Auth client detail
  - Assign owner
  - Review sessions
  - Review audit
- Snapshot export
  - Convert snapshot
  - Import snapshot

These actions should come from the same task registry, not from one-off buttons
hard-coded on every page.

## MCP Gateway Example

The MCP Gateway quick start can be rebuilt as a task:

```text
Task: Onboard API to MCP Gateway

Steps:
1. Select or create API
2. Select or create API version
3. Choose deployment mode
4. Link API version to gateway or sidecar instance
5. Select MCP tools
6. Configure access control
```

Step behavior:

- API selection is required unless `apiId` is already provided.
- API version is required unless `apiVersionId` is already provided.
- Spec upload is optional and only shown when creating a new API/version.
- Deployment mode is required when the version is not linked.
- Gateway selection is required only for centralized deployment.
- Tool selection is optional if users only want to register the server first.
- Access control is optional but should be shown as a recommended final step.

This task can support several entry points:

```text
/app/tasks/mcp-onboard-api
/app/tasks/mcp-onboard-api?apiId=...
/app/tasks/mcp-onboard-api?apiId=...&apiVersionId=...
/app/tasks/mcp-onboard-api?instanceApiId=...
```

The UI should not rely on fixed step numbers. It should compute visible steps
from the task context and completion state.

## Task State

Start with client-side state:

- URL query parameters for entity context
- `sessionStorage` for in-progress task context
- existing backend records for real completion state

Later, add persisted task state if needed:

- user id
- host id
- task id
- context JSON
- skipped step ids
- last active step
- updated timestamp

Persisting task state should not become the source of truth for business data.
It should only remember navigation state and user choices. Completion should be
derived from actual portal records.

## Sidebar Role

The sidebar should become smaller and more stable. It should expose major
areas, not every page/form.

Recommended sidebar sections:

- Home
- Tasks
- Marketplace
- MCP Gateway
- Operations
- Administration

Deep links should still exist, but they should be discoverable through search,
contextual actions, and task detail pages.

## Implementation Plan

### Phase 1: Inventory And Metadata

- Create page/form metadata registry.
- Add task registry types.
- Register the most-used pages and forms.
- Add global search over registered tasks/pages/forms.

### Phase 2: Task Center

- Add `/app/tasks`.
- Add task category cards.
- Add task detail checklist page.
- Implement client-side task context with URL parameters and session storage.

### Phase 3: MCP Gateway Task

- Convert the current MCP wizard flow into `mcp-onboard-api` task definition.
- Reuse existing MCP components for the pages that still need custom UI.
- Replace hard-coded step numbers with resolver-driven visible steps.
- Add return-to-task behavior after saves.

### Phase 4: Contextual Actions

- Add task actions to API detail and instance detail pages.
- Add task actions to access control and config pages where appropriate.
- Use the task registry to drive action visibility.

### Phase 5: Broader Rollout

- Add tasks for API publishing, config promotion, host/user management, and
  snapshot export/import.
- Reduce sidebar clutter once task/search usage is available.
- Add persisted task state only if session storage is not enough.

## Risks And Mitigations

| Risk | Mitigation |
| --- | --- |
| Task registry duplicates sidebar and route definitions | Reuse page/form metadata as the source for labels, roles, and keywords |
| Task state becomes stale | Derive completion from backend records, not saved task status |
| Users lose flexibility | Allow direct page navigation and command-palette search |
| Implementation grows into another wizard framework | Route to existing pages/forms wherever possible |
| Role filtering becomes inconsistent | Centralize role checks in the page/task registry |

## Recommendation

Keep the MCP Gateway wizard as a prototype, but do not build more isolated
wizards in the same style. The long-term solution should be:

- a task registry
- a Task Center
- resolver-driven progress
- global search
- contextual next actions
- reuse of existing pages and generated forms

This gives new users guided paths while still letting experienced users jump
directly to the page or form they already know.
