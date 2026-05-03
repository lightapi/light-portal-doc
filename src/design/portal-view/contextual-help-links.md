# Contextual Help Links

`portal-view` has many pages, generated forms, task flows, and admin tables.
Even with the task-oriented navigation work, users still need page-specific and
form-specific help when they are making a decision or filling a field. This
document proposes a contextual help-link model for pages and forms.

## Problem

Users often need help at the exact point where they are working:

- what this page is for
- when to use this form
- what required fields mean
- which optional fields matter
- what permissions or ownership rules apply
- what happens after submit
- how this page fits into a larger task

Today, help is usually outside the UI context. Users must know where to look,
which document applies, and which page or form name maps to the screen in front
of them.

## Design Goals

- Add a clear help entry point to every major page and generated form.
- Keep help content close to the product documentation source of truth.
- Avoid bloating the `portal-view` application bundle with documentation.
- Allow documentation-only updates without rebuilding `portal-view`.
- Make help links declarative so page, form, and task metadata can drive them.
- Keep link identifiers stable even if routes or component names change.
- Support future documentation search, related topics, and task-specific help.
- Preserve the ability to run the app locally with a configurable docs base URL.

## Non-Goals

- Do not build a full documentation authoring system inside `portal-view`.
- Do not duplicate long user guides in component source files.
- Do not block a page or form rollout because full documentation is missing.
- Do not use contextual help as a replacement for better labels, validation, or
  field-level error messages.

## Documentation Location Decision

The help content should live in `light-portal-doc`. `portal-view` should store
only metadata that points to the relevant help page.

Recommended split:

```text
light-portal-doc
  src/help/portal-view/
    pages/
    forms/
    tasks/
    concepts/

portal-view
  page registry, task registry, and form metadata with help ids or help paths
```

### Why `light-portal-doc`

Pros:

- Keeps user-facing documentation in the documentation repo.
- Allows documentation changes without rebuilding or redeploying `portal-view`.
- Avoids increasing the app bundle with markdown content.
- Supports documentation search, navigation, publishing, and review workflows.
- Allows the same help content to be linked from support tickets, onboarding,
  release notes, and external docs.
- Fits the existing pattern where portal-view design docs already live in
  `light-portal-doc`.

Cons:

- Requires stable published URLs.
- Requires a configurable docs base URL for local and deployed environments.
- Can drift from UI behavior unless we add link validation and ownership rules.

### Why Not `portal-view/docs`

Pros:

- Easy to review UI and docs in one PR.
- Help content can be tightly coupled to the component version.
- Local development does not need a separate docs deployment.

Cons:

- Documentation-only changes require app rebuilds and deployments.
- Large markdown content can bloat the frontend repo and build context.
- It is harder to provide a proper documentation navigation/search experience.
- It encourages implementation notes and user help to mix in the same repo.

Recommendation: use `light-portal-doc` for content and keep `portal-view`
limited to stable link metadata.

## Help Content Structure

Create a user-facing help tree separate from design docs:

```text
src/help/portal-view/
  pages/
    api-admin.md
    api-detail.md
    instance-admin.md
    schedule-admin.md
  forms/
    create-api.md
    update-api.md
    create-client.md
    update-instance.md
  tasks/
    mcp-onboard-api.md
    register-standalone-mcp-server.md
  concepts/
    ownership-and-positions.md
    hosts-and-user-hosts.md
    api-versioning.md
```

Use page-level help for screen orientation and form-level help for submission
semantics. Use concept help for reusable explanations that should not be copied
into many page/form documents.

## URL Strategy

Help URLs should be stable and human-readable.

Recommended public URL shape:

```text
/help/portal-view/pages/api-admin
/help/portal-view/forms/create-api
/help/portal-view/tasks/mcp-onboard-api
/help/portal-view/concepts/ownership-and-positions
```

Do not make the public URL depend on React route internals or component names.
If a route changes from `/app/api` to another route later, the help URL should
not need to change.

`portal-view` should build the absolute link from a runtime config value:

```text
PORTAL_DOC_BASE_URL=https://doc.lightapi.net
```

or for Vite:

```text
VITE_PORTAL_DOC_BASE_URL=https://doc.lightapi.net
```

Local development can point to a local docs server:

```text
VITE_PORTAL_DOC_BASE_URL=http://localhost:3000
```

## Metadata Contract

Use a stable help id or help path in the app metadata. A help path is more
direct and easier to validate.

Page registry example:

```ts
{
  id: "api-admin",
  title: "API Admin",
  route: "/app/apis",
  helpPath: "/help/portal-view/pages/api-admin",
}
```

Task registry example:

```ts
{
  id: "mcp-onboard-api",
  title: "Onboard API to MCP Gateway",
  helpPath: "/help/portal-view/tasks/mcp-onboard-api",
}
```

Form metadata example:

```json
{
  "formId": "createApi",
  "helpPath": "/help/portal-view/forms/create-api",
  "actions": []
}
```

If we need indirection later, we can change to `helpId` and resolve it through a
small registry:

```ts
{
  helpId: "forms.create-api"
}
```

Start with `helpPath` because it is simple, transparent, and works well with
static documentation.

## Portal UI Behavior

Each page and generated form should have a small help action in a predictable
location.

Recommended behavior:

- open help in a new browser tab
- use an external-link icon or help icon with an accessible label
- keep the help action near the page title or form title
- if a form is opened inside a task shell, prefer form-specific help first and
  show task help as a secondary link
- if no specific help exists yet, fall back to the nearest page or concept help

Example resolution order for a form opened from a task:

1. form `helpPath`
2. current task `helpPath`
3. current page `helpPath`
4. generic portal help landing page

Do not render a broken link. If a help path is missing, hide the action or show
the fallback help link.

## Generated Forms

Generated forms should support a top-level `helpPath` field in `Forms.json`.
The renderer can read it and show a help action in the form header.

For example:

```json
{
  "formId": "createSchedule",
  "helpPath": "/help/portal-view/forms/create-schedule",
  "schema": {},
  "form": []
}
```

Field-level help can be added later, but it should not be the first step. Many
field descriptions can stay in the JSON schema title/description. Use
field-level help only for fields where a short description is not enough, such
as security, ownership, deployment, or advanced configuration fields.

Possible future field shape:

```json
{
  "key": "ownerPositionId",
  "helpPath": "/help/portal-view/concepts/ownership-and-positions"
}
```

## Task-Aware Help

The task-oriented navigation layer should support task help separately from page
or form help. A user working on the same form may need different context
depending on the task.

Example:

- `createApi` opened from "Register a new API" links to create API form help.
- `createApi` opened from "Onboard API to MCP Gateway" can also link to MCP
  onboarding task help.

The UI should pass task context through existing task URL parameters and layout
state, then render both links when useful:

```text
Help: Create API
Related: Onboard API to MCP Gateway
```

## Authoring Guidelines

Each page help document should include:

- what the page is used for
- who can access it
- what records are visible
- common actions
- links to related forms and tasks

Each form help document should include:

- when to use the form
- what happens after submit
- required fields
- important optional fields
- ownership and permission behavior
- validation or troubleshooting notes

Keep help content user-facing. Do not put implementation details, class names,
or database internals in the main help body unless they are truly needed for an
operator.

## Validation

To prevent link drift, add a lightweight validation step once the first help
docs exist.

Validation should check:

- every `helpPath` in `portal-view` points to a markdown source in
  `light-portal-doc`
- every high-value page has page help
- every high-value form has form help
- no help path uses a route-specific or component-specific unstable name

This can start as a script in `light-portal-doc` or a shared CI check that
accepts both repo paths.

## Rollout Plan

### Phase 1: Documentation Structure

- Create `src/help/portal-view/pages`.
- Create `src/help/portal-view/forms`.
- Create `src/help/portal-view/tasks`.
- Create `src/help/portal-view/concepts`.
- Add placeholder help pages for the high-value admin pages and forms.

### Phase 2: App Metadata

- Add optional `helpPath` to `pageRegistry.ts`.
- Add optional `helpPath` to `taskRegistry.ts`.
- Add optional top-level `helpPath` to generated form metadata.
- Add a docs base URL runtime config.

### Phase 3: UI Components

- Add a reusable help-link component.
- Render page help near page titles.
- Render form help in the generated form header.
- Render task help in the task navigation shell.
- Add fallback behavior when a specific help link is missing.

### Phase 4: Coverage And Validation

- Add help paths for all self-service owner-scoped admin pages.
- Add help paths for all high-value create/update forms.
- Add a validation script for help path coverage and broken links.
- Add missing docs over time as pages move into the task-oriented model.

## Initial Scope

Start with the pages and forms most likely to be used by self-service users:

- API Admin and API Detail
- create/update API
- create/update API Version
- App Admin
- create/update App
- OAuth Client and Client Token
- create/update Client
- create Client Token
- Instance Admin and relationship pages
- create/update Instance
- create Instance API
- create/update Instance API Path Prefix
- create Instance App
- create Instance App API
- Schedule Admin
- create/update Schedule
- Workflow Definition
- create/update Workflow Definition

Then expand to admin-only pages after their ownership and access model is clear.

## MVP Decisions

Use these decisions for the first implementation.

### Missing Help Links

Do not hide the help action when a specific page, form, or task help path is
missing. Fall back to the generic portal-view help landing page:

```text
/help/portal-view/index
```

This keeps the UI consistent. A missing specific help page should degrade to
general help instead of making the help affordance disappear.

### Help Presentation

Open help in a new browser tab for the MVP. Do not build an embedded markdown
viewer, side drawer, or iframe-based documentation panel in the first version.

This keeps `portal-view` small and avoids adding documentation rendering,
iframe, routing, and panel-state complexity to the app. A side panel can be
revisited later if users need in-page help while editing long forms.

### JSON Schema Descriptions

Do not auto-generate full form help pages from JSON schema descriptions. Schema
titles and descriptions are best used for inline labels, helper text, or
field-level tooltips.

Form-level help should explain why the form exists, when to use it, what
happens after submit, and how the form fits into a larger workflow. It should
not simply repeat field types and required flags.

### Documentation Versioning

Use latest documentation URLs for the MVP. Do not introduce release-versioned
help URLs in the first implementation.

The portal will likely support both cloud SaaS deployments and enterprise
on-premise deployments. SaaS users normally interact with the latest deployed
portal, but enterprise customers may run older portal versions for a longer
period. Versioned docs are therefore a good future requirement, but they should
not block the first help-link rollout.

Keep `helpPath` values relative and version-neutral:

```text
/help/portal-view/forms/create-api
```

Then versioning can be introduced later by changing only the configured docs
base URL:

```text
PORTAL_DOC_BASE_URL=https://doc.lightapi.net/v2.0
```

This keeps the app metadata stable while allowing SaaS to use latest docs and
on-premise builds to point at version-specific documentation.

## Future Enhancements

### In-Page Help Drawer

Add an optional in-page help drawer after the `helpPath` metadata is stable and
the first new-tab implementation has proven useful.

The drawer should be opt-in, not the default for every form. Long or complex
configuration forms can declare:

```json
{
  "helpPath": "/help/portal-view/forms/update-instance",
  "inPageHelp": true
}
```

When enabled, the UI can render a right-side drawer that displays the help
document through an iframe or a lightweight markdown renderer. This avoids
constant tab switching for complex forms while keeping the MVP simple.

### Field-Level Help Paths

Add field-level help paths sparingly for complex fields and architectural
concepts. Standard fields should continue to use JSON schema titles,
descriptions, helper text, or tooltips.

Example future field metadata:

```json
{
  "key": "ownerPositionId",
  "helpPath": "/help/portal-view/concepts/ownership-and-positions"
}
```

The UI can render a small help icon next to the field label when a field-level
`helpPath` exists. Good candidates include ownership, security, OAuth token
exchange, deployment target, transport configuration, and workflow definition
fields.

### Versioned Documentation

Add release-versioned documentation when multiple portal versions must be
supported at the same time, especially for on-premise enterprise deployments.

The relative `helpPath` values should remain unchanged. The deployment or build
configuration should select the versioned docs base URL:

```text
SaaS/latest:
PORTAL_DOC_BASE_URL=https://doc.lightapi.net

On-premise v2.0:
PORTAL_DOC_BASE_URL=https://doc.lightapi.net/v2.0
```

This gives cloud deployments a simple latest-docs experience and gives
enterprise deployments a path to version-matched help without changing
`portal-view` metadata.

## Recommendation

Store user-facing help content in `light-portal-doc` and add declarative
`helpPath` metadata in `portal-view`. This keeps documentation maintainable and
publishable while allowing every page, form, and task to provide context-aware
help from the UI.
