# Build a Customer 360 workflow-backed MCP tool

This tutorial exposes three existing REST reads as one `customer_360` MCP
tool. A Serverless Workflow definition runs the calls in parallel and appends
their responses into one ordered result array:

```text
customer_360({customerId, channel})
  -> light-gateway /mcp
  -> light-workflow
       |-- GET /customers/{customerId}
       |-- GET /customers/{customerId}/preferences?channel={channel}
       `-- GET /customers/{customerId}/policies
  -> [{profile}, {preferences}, {policies}]
```

The demo reuses `demo-customer-profile-api`; it does not deploy an MCP wrapper
for the REST API.

Create the workflow definition and tool through the Portal UI. Do not insert
rows into `wf_definition_t`, `tool_t`, `workflow_tool_binding_t`, or
`workflow_endpoint_target_t`. Light Portal is event sourced:

```text
Create Workflow Definition
  -> WorkflowDefinitionCreatedEvent
  -> wf_definition_t

Create Tool with a workflow binding and endpoints
  -> ToolCreatedEvent
  -> tool_t
  -> workflow_tool_binding_t
  -> workflow_endpoint_target_t
```

The workflow binding and its registered endpoint targets are part of the
Create Tool command. There is no separate binding or endpoint-target Create
page.

## What this simplified demo covers

- REST API aggregation without an MCP wrapper service.
- Parallel orchestration with a workflow `fork`.
- A simple append transformation into one MCP response.
- Portal command/event creation of the workflow, tool, binding, and endpoint
  registrations.
- Static `mcp-router.yml` publication for a local Light-Fabric instance.

This is an incremental demo, not the final transformer-tool implementation.
The current workflow HTTP executor calls the internal demo endpoints directly
and does not forward the MCP caller's JWT. In addition, the current
non-competing fork fails the invocation when any branch fails; it does not yet
return the required partial response. Original-JWT propagation, gateway-routed
API destinations, UI-side transformation validation, config-server
publication, and partial-error append behavior remain follow-up work.

## Prerequisites

- Start the `portal-config-loc/all-in-lt` Rust stack.
- Confirm `light-gateway`, `light-workflow`, `hybrid-command`, `hybrid-query`,
  PostgreSQL, and `demo-customer-profile-api` are healthy.
- Sign in to Light Portal and select the target host.
- Use an account that can administer workflow definitions and GenAI tools.
- Download the versioned
  [customer-360-mcp definition](./examples/customer-360-mcp.yaml).
- Confirm that the host does not already have an active workflow named
  `customer-360-mcp` at `1.0.0` or an active tool named `customer_360`.

The included demo data uses customer `CUST-1001` and channel `portal`.

## Workflow definition

The importable YAML is maintained with this tutorial and is included below so
the rendered mdBook and downloadable asset cannot drift apart:

```yaml
{{#include examples/customer-360-mcp.yaml}}
```

## 1. Review the workflow

The workflow has one non-competing fork with three GET branches. Each HTTP
task declares `metadata.endpointRef`; a workflow-backed invocation is allowed
to call only an active endpoint registered by the tool binding with the same
reference and method.

After the fork joins, `appendResponses` produces this response shape:

```json
{
  "customerId": "CUST-1001",
  "results": [
    {"source": "profile", "status": "success", "data": {}},
    {"source": "preferences", "status": "success", "data": {}},
    {"source": "policies", "status": "success", "data": {}}
  ]
}
```

The fixed order makes the append transformation predictable even though the
three calls execute concurrently.

## 2. Create the workflow definition

1. In the Portal sidebar, expand **Workflow Admin** and select
   **Wf Definition**.
2. Select **Create New WfDefinition**.
3. In **Workflow Editor**, select **Import** and open
   `customer-360-mcp.yaml`.
4. Confirm these values:

   | Field | Value |
   | --- | --- |
   | Namespace | `light-demo` |
   | Name | `customer-360-mcp` |
   | Version | `1.0.0` |
   | Publish in Workflow Catalog | Enabled |

   The selected host supplies Host ID. Leave Workflow Definition ID empty so
   the command handler generates it.
5. Select **Validate** and resolve any error.
6. Select **Save** once. Wait for **Workflow definition saved**.
7. Return to **Wf Definition**, refresh the list, and open the new row with
   **Update**. Record its generated Workflow Definition ID as `<wfDefId>`.

Opening the Update page confirms that the event and projection are both
available. Do not submit Create repeatedly while waiting for projection.

The normalized definition digest for the supplied file is:

```text
sha256:a7c1c07164110840222fd2528122d75ced9f69d4e7b7b2944ea15dddd14e10ae
```

Changing the workflow changes this digest. If you edit the definition, compute
and use the new value consistently in the tool binding and router config.

## 3. Create the tool, binding, and endpoint registrations

1. In the sidebar, expand **GenAI Admin** and select **Tool**.
2. Select **Create New Tool**.
3. Enter these values. Unlisted optional fields can remain empty.

   | Field | Value |
   | --- | --- |
   | Name | `customer_360` |
   | Description | `Read a customer profile, preferences, and policies in parallel and append the API responses.` |
   | Routing Domain | `Customer` |
   | Semantic Namespace | `customer-360` |
   | Semantic Description | `Aggregate customer context for an agent in one read-only call.` |
   | Lifecycle Status | `active` |
   | Read Only | Enabled |
   | Idempotent | Enabled |
   | Destructive | Disabled |
   | Human Approval Required | Disabled |
   | Version | `1.0.0` |
   | Execution Placement | `workflow` |
   | Schema Digest | `sha256:56cb21e48069caa1c9998ba58a3983a68b42d038b364c82b3a3620b85c3718ca` |

   `Implementation Type` is not required for a workflow-placed tool.
4. After selecting `workflow`, enter the following JSON in **Workflow
   Binding**. Replace `<wfDefId>` with the generated ID from step 2.

   ```json
   {
     "wfDefId": "<wfDefId>",
     "workflowVersion": "1.0.0",
     "definitionDigest": "sha256:a7c1c07164110840222fd2528122d75ced9f69d4e7b7b2944ea15dddd14e10ae",
     "schemaDigest": "sha256:56cb21e48069caa1c9998ba58a3983a68b42d038b364c82b3a3620b85c3718ca",
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
     "responsePolicyDigest": "sha256:36c9bb0c09a5e06a4871f9c7ad985792269eb798334c2e9715f25d441796174e",
     "runtimeBounds": {
       "maximumTaskAttempts": 8,
       "maximumNestedCalls": 1,
       "maximumParallelism": 3,
       "maximumRequestBytes": 65536,
       "maximumIntermediateBytes": 524288,
       "maximumResultBytes": 262144,
       "maximumCostUnits": 0
     },
     "policyDigest": "sha256:b5838a4852ba9937839f228e9d3e30607a58b69652e5c373fb2cb61108e87180",
     "endpoints": [
       {
         "endpointRef": "customer-360.profile",
         "endpointUri": "http://demo-customer-profile-api:8085/customers/${{ customerId }}",
         "allowedMethods": ["GET"],
         "authorizationPolicyDigest": "sha256:b5838a4852ba9937839f228e9d3e30607a58b69652e5c373fb2cb61108e87180"
       },
       {
         "endpointRef": "customer-360.preferences",
         "endpointUri": "http://demo-customer-profile-api:8085/customers/${{ customerId }}/preferences?channel=${{ channel }}",
         "allowedMethods": ["GET"],
         "authorizationPolicyDigest": "sha256:b5838a4852ba9937839f228e9d3e30607a58b69652e5c373fb2cb61108e87180"
       },
       {
         "endpointRef": "customer-360.policies",
         "endpointUri": "http://demo-customer-profile-api:8085/customers/${{ customerId }}/policies",
         "allowedMethods": ["GET"],
         "authorizationPolicyDigest": "sha256:b5838a4852ba9937839f228e9d3e30607a58b69652e5c373fb2cb61108e87180"
       }
     ]
   }
   ```

5. If the structured editor marks the JSON tab with `*`, select **Apply**.
6. Submit **Create Tool Form** once.
7. Return to **Tool**, refresh the list, and open `customer_360` with
   **Update Tool**. Record the generated Tool ID as `<toolId>` and confirm:

   - Execution Placement is `workflow`.
   - Stable Tool Reference equals `<toolId>`.
   - The binding contains `<wfDefId>` and a generated `bindingId`.
   - All three endpoint entries are present.

The command handler generates the Tool ID and binding ID. The event projector
creates all four read-model types from the one `ToolCreatedEvent`; do not fill
in any missing projection row manually.

`maximumParallelism` must be at least `3`, because the definition has three
fork branches. The binding Schema Digest must exactly match the top-level Tool
Schema Digest. A synchronous gateway binding also requires `syncWaitMs` no
greater than `20000` and `totalDeadlineMs` no greater than `30000`.

## 4. Enable the static light-gateway entry

Open
`portal-config-loc/all-in-lt/light-gateway-rust/config/mcp-router.yml`. The
local demo configuration includes a complete `customer_360` entry after the
smoke tool.

1. Set `workflowBinding.stableToolRef` and
   `workflowBinding.workflowDefinitionId` to the IDs generated by your Portal
   commands. The IDs shipped in a developer checkout are valid only for the
   database in which those Create events were produced.
2. Keep the `- name: customer_360` entry aligned under `tools:`.
3. Do not change the schemas, digests, timeouts, or budget unless you also
   update the Portal binding to match.
4. Confirm `light-gateway-rust/config/access-control.yml` contains
   `customer_360` under `skipPathPrefixes` for this local demo.
5. Restart light-gateway from `portal-config-loc/all-in-lt`:

   ```bash
   docker compose -f docker-compose.yml -f docker-compose-rust.yml restart light-gateway
   ```

Editing `mcp-router.yml` publishes runtime configuration; it does not create a
Portal entity and is not a substitute for the event-sourced steps above.

## 5. Verify from the desktop

Set a current access token, including the `Bearer ` prefix. Do not copy a
token from this tutorial:

```bash
export LIGHT_PORTAL_AUTHORIZATION='Bearer eyJhbGciOiJSUzI1NiIsImtpZCI6IkFacDAyVzZqZGNxWHpxTkk2MVlaelEifQ.eyJpc3MiOiJ1cm46Y29tOm5ldHdvcmtudDpvYXV0aDI6djEiLCJhdWQiOiJ1cm46Y29tLm5ldHdvcmtudCIsInN1YiI6IjAxOTY0YjA1LTU1MzItN2M3OS04Y2RlLTE5MWRjYmQ0MjFiOCIsImV4cCI6MTc4NjYyMjU0MywianRpIjoiRkMxM0ZmYzNUMm0zLXlMT1RHc3NHQSIsImlhdCI6MTc4NjYyMTk0MywibmJmIjoxNzg2NjIxODIzLCJ2ZXIiOiIxLjAiLCJjaWQiOiJmN2Q0MjM0OC1jNjQ3LTRlZmItYTUyZC00YzU3ODc0MjFlNzIiLCJzY3AiOlsicG9ydGFsLnIiLCJwb3J0YWwudyJdLCJjbGllbnRfaWQiOiJmN2Q0MjM0OC1jNjQ3LTRlZmItYTUyZC00YzU3ODc0MjFlNzIiLCJzY29wZSI6InBvcnRhbC5yIHBvcnRhbC53IiwiY3NyZiI6IjNFS3lmUkxpVFBtTFM2QXVIMEZNcGciLCJlaWQiOiJzaDM1IiwiZW1sIjoic3RldmUuaHVAbGlnaHRhcGkubmV0IiwiaG9zdCI6IjAxOTY0YjA1LTU1MmEtN2M0Yi05MTg0LTY4NTdlN2YzZGM1ZiIsInJvbGUiOiJhY2NvdW50LW1hbmFnZXIgYWRtaW4gZ2l0aHViLXJlYWRlciBob3N0LWFkbWluIG1jcC1yZWFkZXIgdXNlciIsInVpZCI6IjAxOTY0YjA1LTU1MzItN2M3OS04Y2RlLTE5MWRjYmQ0MjFiOCIsInV0eSI6IkUifQ.D47-XR66YEdm_KLr8sgNyKxmuXeLtqjMv0h4AIhf8w5ph0T-l4Cgyc2GIP76finZjy04OguEeAfN_qqAqQu2sLb-OOTo3-WekSmmKQAX5yJLKZJup8DbShNydhTES4GklgLVltF86Cj5npJBtj8VF3Kptd67gdrZ8TF-7o9DvLjD8Umv2kz1vjijCX0J5xyjjX8HFC7cOGsHd8gKieGTZfVykTcJlZMjbzU3zlYIIjYlkmpLrQDai56eJF7wKr-CoXV3Gg3fXjUK7wsLfo1nbBLr0I20qMdXAJLYnfoXszaN3ZYGKl27W-Hh6X5iITFrTD92XavAVU24QEltjJzk7A'
```

List tools through light-gateway's published HTTPS port:

```bash
curl -skS --max-time 45 \
  -H "Authorization: $LIGHT_PORTAL_AUTHORIZATION" \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -H 'MCP-Protocol-Version: 2026-07-28' \
  -H 'MCP-Method: tools/list' \
  --data-binary '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{"_meta":{"io.modelcontextprotocol/protocolVersion":"2026-07-28","io.modelcontextprotocol/clientInfo":{"name":"customer-360-demo","version":"1"},"io.modelcontextprotocol/clientCapabilities":{}}}}' \
  https://localhost/mcp | jq
```

Confirm that `result.tools` contains `customer_360`, then invoke it:

```bash
curl -skS --max-time 45 \
  -H "Authorization: $LIGHT_PORTAL_AUTHORIZATION" \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -H 'MCP-Protocol-Version: 2026-07-28' \
  -H 'MCP-Method: tools/call' \
  -H 'MCP-Name: customer_360' \
  --data-binary '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"customer_360","arguments":{"customerId":"CUST-1001","channel":"portal"},"_meta":{"io.modelcontextprotocol/protocolVersion":"2026-07-28","io.modelcontextprotocol/clientInfo":{"name":"customer-360-demo","version":"1"},"io.modelcontextprotocol/clientCapabilities":{}}}}' \
  https://localhost/mcp | jq
```

Confirm that `isError` is `false` and that the appended result contains:

- Profile: `Avery Chen`.
- Preferences: category `travel` and channel `portal`.
- Policy: `POL-AUTO-1001`.

The request goes directly from the desktop to `https://localhost/mcp`; no
`docker exec` is required.

To run the repeatable Hurl assertions from `light-portal-test` against
`portal-config-loc` or a development `light-portal-install` deployment:

```bash
cd /home/steve/workspace/light-portal-test
make workflow-mcp
```

## Troubleshooting

### The Create event goes to the DLQ

Check for an older active resource with the same workflow identity or tool
name. Also confirm the tool event references the active workflow ID and exact
version. Repair the bad event or legacy fixture through the supported event
replay/cleanup flow; do not insert or update projection rows.

### The tool form rejects the binding

Confirm that:

- `<wfDefId>` is a UUID belonging to the active `customer-360-mcp` definition.
- Every digest starts with `sha256:` followed by 64 lowercase hexadecimal
  characters.
- The top-level and binding Schema Digest values match.
- The tool is read-only, non-destructive, and headless for synchronous use.
- Every endpoint has `endpointRef`, `endpointUri`, and a non-empty
  `allowedMethods` array.
- The structured editor changes were applied before submission.

### The invocation says the endpoint is not registered

Compare each workflow `metadata.endpointRef` with its binding endpoint entry.
The values are case-sensitive. Also verify that `GET` is in `allowedMethods`
and that the endpoint is active on the same host and binding.

### The invocation says the definition or policy does not match

Keep the workflow version and all four digests identical between the Portal
binding and `mcp-router.yml`. Use the supplied definition without edits for
the documented digest.

### The fork exceeds the runtime budget

Set `maximumParallelism` to at least `3` in both the Portal binding and static
router entry.

### One REST call fails

The current non-competing fork fails the entire invocation. That is a known
limit of this simplified demo. Do not present it as the customer's required
partial-response behavior; that needs the planned try/error-capture extension
before failed branches can be appended beside successful responses.
