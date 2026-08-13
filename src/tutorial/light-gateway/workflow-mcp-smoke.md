# Create the workflow MCP smoke tool from the portal

This tutorial creates the `workflow-mcp-smoke` workflow and exposes it as the
`workflow_mcp_smoke` MCP tool. Create both resources through the portal UI. Do
not insert rows into `wf_definition_t`, `tool_t`, or
`workflow_tool_binding_t`.

Light Portal uses event sourcing. The command services append domain events,
and the query-side projector derives the database read models from those
events:

```text
Create Workflow Definition
  -> WorkflowDefinitionCreatedEvent
  -> wf_definition_t

Create Tool with Execution Placement = workflow
  -> ToolCreatedEvent
  -> tool_t
  -> workflow_tool_binding_t
```

The workflow binding is part of the tool creation contract. There is no
separate **Create Workflow Tool Binding** page.

## Prerequisites

- Sign in to the portal and select the host where the smoke tool will run.
- Use an account that can administer workflow definitions and GenAI tools.
- Make sure `light-workflow`, the portal command service, the portal query
  service, PostgreSQL, and the event projector are running.
- Download the versioned
  [workflow-mcp-smoke definition](./examples/workflow-mcp-smoke.yaml).

The host must not already contain an active workflow with this identity:

```text
namespace: light-demo
name: workflow-mcp-smoke
version: 1.0.0
```

It must also not contain an active tool named `workflow_mcp_smoke` that was
inserted by an older SQL fixture. A projection-only record has no aggregate
history and cannot safely be replaced with the normal Create command. Start
with a clean database or have an administrator quarantine/remove the legacy
fixture before following this tutorial. Do not use the normal Update or Delete
buttons to repair projection-only data.

## Workflow definition

The importable YAML is maintained with this tutorial and is included below so
the rendered mdBook and downloadable asset cannot drift apart:

```yaml
{{#include examples/workflow-mcp-smoke.yaml}}
```

## 1. Create the workflow definition

1. In the portal sidebar, expand **Workflow Admin** and select
   **Wf Definition**.
2. Select **Create New WfDefinition**.
3. In **Workflow Editor**, select **Import** and open
   `workflow-mcp-smoke.yaml`.
4. Confirm the editor populated these values:

   | Field | Value |
   | --- | --- |
   | Namespace | `light-demo` |
   | Name | `workflow-mcp-smoke` |
   | Version | `1.0.0` |
   | Publish in Workflow Catalog | Enabled |

   The Host ID comes from the signed-in user's selected host. Leave the
   Workflow Definition ID empty; the command service generates it.
5. Select **Validate** and resolve any reported errors.
6. Select **Save** once. A successful save displays **Workflow definition
   saved** and assigns a Workflow Definition ID.
7. Record the generated Workflow Definition ID as `<wfDefId>`. You will use it
   when creating the tool.
8. Return to **Wf Definition**, refresh the table, and use **Update** to confirm
   that the saved definition can be loaded. This also confirms that the event
   and projection have reached the same aggregate version.

Do not immediately submit the same Create form again while waiting for the
projection. Refresh the list instead.

## 2. Create the workflow-backed tool and binding

1. In the sidebar, expand **GenAI Admin** and select **Tool**.
2. Select **Create New Tool**.
3. Enter the following tool values. Fields not listed here can remain empty.

   | Field | Value |
   | --- | --- |
   | Name | `workflow_mcp_smoke` |
   | Description | `Run a deterministic read-only workflow and return the supplied message.` |
   | Routing Domain | `Workflow` |
   | Semantic Namespace | `workflow-smoke` |
   | Semantic Description | `Qualify workflow-backed MCP execution.` |
   | Lifecycle Status | `active` |
   | Read Only | Enabled |
   | Idempotent | Enabled |
   | Destructive | Disabled |
   | Human Approval Required | Disabled |
   | Version | `1.0.0` |
   | Execution Placement | `workflow` |
   | Schema Digest | `sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa` |

   `Implementation Type` is not required for a workflow-placed tool. The
   workflow binding, rather than a Java class, REST endpoint, script, or MCP
   server, identifies its execution target.

4. After selecting `workflow`, the **Workflow Binding** structured-data field
   appears. Enter the following JSON, replacing `<wfDefId>` with the ID from
   step 1:

   ```json
   {
     "wfDefId": "<wfDefId>",
     "workflowVersion": "1.0.0",
     "definitionDigest": "sha256:5197cc8e1ef611ef736c6d033ffdbab19137318bbadf61ea16b906d114ad81c8",
     "schemaDigest": "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
     "invocationMode": "sync",
     "syncWaitMs": 20000,
     "totalDeadlineMs": 30000,
     "executionClass": "interactive",
     "resultTextMode": "compact-json",
     "idempotencyPolicy": {
       "kind": "derived",
       "inFlightDedupMs": 30000,
       "resultReplayMs": 0
     },
     "delegationPolicy": {
       "maximumDelegationDepth": 0
     },
     "responsePolicyDigest": "sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
     "runtimeBounds": {
       "maximumTaskAttempts": 4,
       "maximumNestedCalls": 1,
       "maximumParallelism": 1,
       "maximumRequestBytes": 65536,
       "maximumIntermediateBytes": 262144,
       "maximumResultBytes": 131072,
       "maximumCostUnits": 0
     },
     "policyDigest": "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
   }
   ```

5. If the structured-data editor shows an **Apply** action, select it before
   submitting the form. A tab marked with `*` still has unapplied edits and the
   portal will refuse to submit it.
6. Submit **Create Tool Form** once.
7. Record the generated Tool ID as `<toolId>`. The command service uses this as
   the stable tool reference unless one was explicitly supplied. It also
   generates the binding ID because `bindingId` was omitted from the JSON.
8. Return to **Tool**, refresh the table, and open **Update Tool** for
   `workflow_mcp_smoke`. Confirm that:

   - Execution Placement is `workflow`.
   - Stable Tool Reference equals `<toolId>`.
   - Workflow Binding contains `<wfDefId>` and a generated `bindingId`.
   - The tool is active.

The four digest values above are the pinned values used by this smoke fixture
and its shipped light-gateway configuration. They are contract identifiers,
not a suggestion to use repeated placeholder digests for production tools. If
the workflow, schemas, or policies change, generate and deploy new matching
digests instead of reusing these values.

For a synchronous binding, the portal requires a read-only, non-destructive,
headless tool: **Read Only** must be enabled while **Destructive** and
**Human Approval Required** remain disabled. The Workflow Binding Schema
Digest must exactly match the top-level Schema Digest.

## 3. Point light-gateway at the generated identities

The database identities are generated by the event-sourced Create commands,
so do not keep the fixed `22000000-...` IDs from the old SQL fixture.

Open
`portal-config-loc/all-in-lt/light-gateway-rust/config/mcp-router.yml` and find
the `workflow_mcp_smoke` entry. Update only these identity fields:

```yaml
workflowBinding:
  stableToolRef: <toolId>
  workflowDefinitionId: <wfDefId>
```

Keep the workflow version, schemas, digests, timeouts, result mode, and budget
aligned with the values entered in the portal. Reload or restart light-gateway
after changing its configuration.

The light-gateway file is runtime configuration, not a light-portal
projection. Updating it does not replace the requirement to create the portal
entities through commands/events.

## 4. Verify the smoke path

1. In **Workflow Admin > Wf Definition**, confirm that
   `workflow-mcp-smoke` has exactly one active row and that **Update** opens it
   without an aggregate-version error.
2. In **GenAI Admin > Tool**, confirm that `workflow_mcp_smoke` has exactly one
   active row and that **Update Tool** shows the workflow binding.
3. From a terminal on the Docker host, set a valid portal authorization value.
   Keep the `Bearer ` prefix:

   ```bash
   export LIGHT_PORTAL_AUTHORIZATION='Bearer eyJhbGciOiJSUzI1NiIsImtpZCI6IkFacDAyVzZqZGNxWHpxTkk2MVlaelEifQ.eyJpc3MiOiJ1cm46Y29tOm5ldHdvcmtudDpvYXV0aDI6djEiLCJhdWQiOiJ1cm46Y29tLm5ldHdvcmtudCIsInN1YiI6IjAxOTY0YjA1LTU1MzItN2M3OS04Y2RlLTE5MWRjYmQ0MjFiOCIsImV4cCI6MTc4NjYyMjU0MywianRpIjoiRkMxM0ZmYzNUMm0zLXlMT1RHc3NHQSIsImlhdCI6MTc4NjYyMTk0MywibmJmIjoxNzg2NjIxODIzLCJ2ZXIiOiIxLjAiLCJjaWQiOiJmN2Q0MjM0OC1jNjQ3LTRlZmItYTUyZC00YzU3ODc0MjFlNzIiLCJzY3AiOlsicG9ydGFsLnIiLCJwb3J0YWwudyJdLCJjbGllbnRfaWQiOiJmN2Q0MjM0OC1jNjQ3LTRlZmItYTUyZC00YzU3ODc0MjFlNzIiLCJzY29wZSI6InBvcnRhbC5yIHBvcnRhbC53IiwiY3NyZiI6IjNFS3lmUkxpVFBtTFM2QXVIMEZNcGciLCJlaWQiOiJzaDM1IiwiZW1sIjoic3RldmUuaHVAbGlnaHRhcGkubmV0IiwiaG9zdCI6IjAxOTY0YjA1LTU1MmEtN2M0Yi05MTg0LTY4NTdlN2YzZGM1ZiIsInJvbGUiOiJhY2NvdW50LW1hbmFnZXIgYWRtaW4gZ2l0aHViLXJlYWRlciBob3N0LWFkbWluIG1jcC1yZWFkZXIgdXNlciIsInVpZCI6IjAxOTY0YjA1LTU1MzItN2M3OS04Y2RlLTE5MWRjYmQ0MjFiOCIsInV0eSI6IkUifQ.D47-XR66YEdm_KLr8sgNyKxmuXeLtqjMv0h4AIhf8w5ph0T-l4Cgyc2GIP76finZjy04OguEeAfN_qqAqQu2sLb-OOTo3-WekSmmKQAX5yJLKZJup8DbShNydhTES4GklgLVltF86Cj5npJBtj8VF3Kptd67gdrZ8TF-7o9DvLjD8Umv2kz1vjijCX0J5xyjjX8HFC7cOGsHd8gKieGTZfVykTcJlZMjbzU3zlYIIjYlkmpLrQDai56eJF7wKr-CoXV3Gg3fXjUK7wsLfo1nbBLr0I20qMdXAJLYnfoXszaN3ZYGKl27W-Hh6X5iITFrTD92XavAVU24QEltjJzk7A'
   ```

   Then query light-gateway directly through its published HTTPS port with MCP
   `tools/list`:

   ```bash
   curl -skS --max-time 40 \
     -H "Authorization: $LIGHT_PORTAL_AUTHORIZATION" \
     -H "Content-Type: application/json" \
     -H "Accept: application/json, text/event-stream" \
     -H "MCP-Protocol-Version: 2026-07-28" \
     -H "MCP-Method: tools/list" \
     --data-binary '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{"_meta":{"io.modelcontextprotocol/protocolVersion":"2026-07-28","io.modelcontextprotocol/clientInfo":{"name":"workflow-smoke","version":"1"},"io.modelcontextprotocol/clientCapabilities":{}}}}' \
     https://localhost/mcp
   ```

   Confirm that the response advertises a tool whose `name` is
   `workflow_mcp_smoke`.
4. Invoke the advertised tool with a `tools/call` request:

   ```bash
   curl -skS --max-time 40 \
     -H "Authorization: $LIGHT_PORTAL_AUTHORIZATION" \
     -H "Content-Type: application/json" \
     -H "Accept: application/json, text/event-stream" \
     -H "MCP-Protocol-Version: 2026-07-28" \
     -H "MCP-Method: tools/call" \
     -H "MCP-Name: workflow_mcp_smoke" \
     --data-binary '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"workflow_mcp_smoke","arguments":{"message":"hello from workflow MCP"},"_meta":{"io.modelcontextprotocol/protocolVersion":"2026-07-28","io.modelcontextprotocol/clientInfo":{"name":"workflow-smoke","version":"1"},"io.modelcontextprotocol/clientCapabilities":{}}}}' \
     https://localhost/mcp
   ```

5. Confirm that the response has `isError: false`, contains the supplied
   message, and includes:

   ```json
   {
     "executedBy": "light-workflow"
   }
   ```

For repeatable regression coverage against `portal-config-loc` or a
development `light-portal-install` deployment, run the corresponding
`light-portal-test` lane:

```bash
cd /home/steve/workspace/light-portal-test
make workflow-mcp
```

## Troubleshooting

### The workflow Create event goes to the DLQ

Check for an older projection-only row with the same host, namespace, name,
and version. Do not edit the new event payload. Remove or quarantine the
invalid legacy fixture, then use the supported event replay flow so the valid
`WorkflowDefinitionCreatedEvent` builds the projection.

### The tool Create event goes to the DLQ

Check for an older projection-only `workflow_mcp_smoke` tool or binding before
retrying. Also confirm that `<wfDefId>` identifies an active workflow at
version `1.0.0`; the projector rejects a workflow binding whose referenced
definition/version is unavailable.

### The Create Tool form rejects the binding

Verify all of the following:

- `wfDefId` is a UUID.
- All four digests start with `sha256:` and contain 64 lowercase hexadecimal
  characters.
- The binding and top-level Schema Digest values are identical.
- `invocationMode` is `sync` and `executionClass` is `interactive`.
- The tool is read-only, non-destructive, and does not require human approval.
- Structured-data edits were applied before the form was submitted.

### `tools/list` still shows the old IDs

Update the light-gateway `mcp-router.yml` entry with the IDs generated by the
portal and restart or reload light-gateway. Do not change projection-table IDs
to match the old configuration.
