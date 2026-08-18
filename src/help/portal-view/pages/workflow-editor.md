# Workflow Editor

Use Workflow Editor to create, validate, test, version, and publish workflow
definitions. The Help button on the editor opens this page in a new tab.

## Define the workflow contract

The form fields write directly into the YAML definition. For a new workflow,
start with:

- **DSL Version**, **Namespace**, **Name**, **Version**, **Title**, and
  **Summary** for the top-level `document` object
- **Evaluation Language** for `evaluate.language`; workflow-backed MCP tools
  currently require `cel`
- **Input Schema** and **Output Schema** for inline JSON Schema documents
- categories and tags selected from the portal reference tables

For example, enabling Input Schema creates this structure in the YAML editor:

```yaml
input:
  schema:
    format: json
    document:
      type: object
      additionalProperties: false
      required:
        - customerId
      properties:
        customerId:
          type: string
```

## Add workflow tasks

Use the Step Palette to select a task type, enter a task name, and add it to the
workflow. New definitions use the `do` task list. The editor inserts each task
into the existing task list instead of creating a competing `steps` section.

The palette includes Ask, Assert, HTTP, OpenAPI, JSON-RPC, OpenRPC, gRPC, MCP,
Rule, Agent, child Workflow, Fork, Switch, Condition, Set, Export, and Wait
starters. A Condition starter is a named switch skeleton, and an Export starter
combines a minimal `set` task with its task-level `export` mapping. Step IDs keep
their entered letter case, so names such as `loadCustomerContext` round-trip
unchanged.

Use the YAML editor for task-specific settings that are not exposed by a form.
The Visual Graph reflects the task structure and lets you inspect the resulting
flow. Parallel work is represented by a `fork` task with named branches.

After inserting or selecting a fork in the Steps list or Visual Graph, use the
**Fork Branches** panel to rename its branches or add another branch. New
branches start with a minimal `set` task that can be replaced with the intended
call or other task configuration. Branch names must be unique and may contain
letters, numbers, underscores, and hyphens. The editor keeps at least two
branches in a fork.

For an endpoint call, select **Endpoints** in Reference Type and choose an
eligible capability. The list includes granted and requestable endpoint Tools
and labels each one with its access state. The editor generates an executable
`call: http` task with a logical `lightapi://` URI plus the exact Tool ID,
capability, version, LightAPI digest, and environment pin. It never stores an
environment URL in workflow YAML.

You may insert requestable or pending Tools and save the draft. Select
**Request Tool Access**, review the grouped exact pins and usage locations,
enter a justification, and submit the request. The built-in **Grant Tools to
Workflow** process assigns one approval task to the `genai-admin` role. The
first administrator who claims it can approve or reject the complete Tool set
from the normal Human Tasks page. Approval is atomic: if any Tool changed or
became ineligible, no grants are created and the request becomes stale.

The editor polls only while an approval is pending and displays the request and
approval workflow instance IDs. After the transaction commits, the status
changes to **GRANTED** and testing becomes available. A rejection or stale
request remains visible so the author can update the draft and submit a new
request. Tool Admin's Workflow Access dialog is intentionally read-only except
for revoking existing grants.

## Validate and test

**Validate** first parses the YAML in the browser and then performs server-side
draft validation. Missing grants are warnings, so an incomplete draft can be
saved while approval is pending. **Test** and **Publish Version** use execution
validation instead and fail closed unless every referenced Tool ID,
capability, version, digest, and requested environment matches an active grant.

Use **Test** to start a fully granted draft with test input and inspect
processes, tasks, assignments, audit records, and final output in the Runtime
Test panel.

## Import, save, and publish

- **Import** loads a YAML, YML, or JSON workflow file into the editor.
- **Export** downloads the current definition as YAML.
- **Save** stores the current draft.
- **Publish Version** makes a saved version immutable and available according
  to its catalog and ownership settings.
- **Create New Version** copies a published version into a new editable draft.

Publishing a definition is separate from making it visible in the Workflow
Catalog. Enable catalog visibility only when the workflow should be discoverable
by other authorized portal users.
