# Light Workflow Tool Access Approval

## Status

Proposed.

The design reuses the Portal Workflow application, `ask` tasks, role-based
worklists, and the existing workflow Tool grant events. It changes the
authoring and approval experience but does not weaken runtime Tool grant
enforcement.

## Purpose

A workflow author currently sees only Tools that are already granted to the
workflow definition. This creates a circular authoring flow:

1. The workflow must exist before a Tool can be granted to it.
2. The author needs the Tool while constructing the workflow.
3. Granting the Tool is performed outside the Workflow Editor.
4. The author might not have Tool administration permission.
5. A Tool administrator must be given the workflow definition ID, version,
   Tool version, digest, and environments through an out-of-band conversation.

The result is a manually saved, incomplete workflow and an approval process
with poor context and weak usability.

This design introduces a built-in Light Portal workflow named **Grant Tools to
Workflow**. A workflow author starts it from the Workflow Editor. The workflow
assigns an approval task to the configured Tool approver role, applies the
approved grants through a constrained internal command, and sends an
acknowledgement task to the original author.

The related designs are:

- [Workflow Editor](../workflow-editor.md)
- [Human Task UI](../portal-view/human-task-ui.md)
- [Endpoint Tools and Workflow Access](../light-portal/endpoint-tool-workflow-access.md)
- [Workflow Version and Publication](../light-portal/workflow-version-publication.md)

## Decision Summary

1. Runtime authorization remains an explicit Tool grant scoped to one workflow
   definition. Version-scoped grants are deferred because the current active
   uniqueness key and deterministic grant identity are definition-wide.
2. Tools are not granted automatically to every workflow on a host.
3. Creating a workflow immediately persists a minimal draft and allocates its
   stable `wfDefId`.
4. The editor distinguishes requestable and pending Tools from callable Tools.
5. A pending Tool can be inserted into a draft, but it cannot be tested,
   published, or executed.
6. Access is requested by starting the built-in **Grant Tools to Workflow**
   workflow from the editor.
7. The approval `ask` task is assigned to an approver role such as
   `genai-admin`. One role assignment is visible to all active members and one
   member claims it.
8. Approval alone does not bypass command authorization. A typed completion
   action on the generic Human Task page verifies the approval and applies the
   grants in the same transaction as task completion.
9. All Tool grants in one approved request are applied atomically.
10. The editor enables testing when it observes committed grants. The author's
    acknowledgement task is informational and is not an authorization gate.

## Goals

- Keep the workflow author inside the Workflow Editor.
- Allow an author to compose a complete draft while access is pending.
- Preserve separation of duties between workflow authors and Tool approvers.
- Give approvers names, schemas, environments, safety metadata, usage
  locations, and justification instead of requiring raw ID exchange.
- Reuse the Portal Workflow Worklist and Human Task pages.
- Record the requester, approver, decision, exact Tool pins, and grant result.
- Keep the existing `workflow_tool_grant_t` projection as the runtime
  authorization authority.
- Fail closed when a Tool changes between request and approval.

## Non-Goals

- Do not grant a Tool to every workflow on the host by default.
- Do not let a pending request satisfy runtime authorization.
- Do not let the workflow service credential grant arbitrary Tool access.
- Do not treat the original author's JWT as an administrator credential after
  another user approves a task.
- Do not create a workflow-specific approval page. The generic Human Task page
  renders the approval task and dispatches its typed completion action to the
  workflow Tool access decision command.
- Do not duplicate the durable Tool grant in the access-request read model.

## Existing Platform Capabilities

The implementation can build on existing behavior:

- An `ask` task can assign work to a `roleId` or an `assigneeId`.
- A role assignment is visible to active members of that role.
- A user claims a role task before completing it.
- Completion rechecks assignment ownership and active role membership.
- The parent task records the completing user and submitted result.
- Other users cannot complete a role task after one user has completed it.
- The Portal Worklist and Human Task pages already query, claim, release, and
  complete these assignments.

The built-in workflow should use these generic facilities rather than
introducing a separate approval inbox.

## Identity Bootstrap

An access request requires a target `wfDefId`. The editor must therefore create
the workflow identity before the author needs the first Tool.

When the user chooses **New Workflow**, Portal creates a minimal valid draft
containing workflow metadata and an empty task list, then opens the editor with
the returned `wfDefId`. This is an intentional draft lifecycle operation, not a
manual save of a half-built workflow.

The `wfDefId` remains stable across versions. The initial implementation grants
access definition-wide. It removes `workflow_version` from the final
`workflow_tool_grant_t` contract and keys one active grant by
`(host_id, tool_id, wf_def_id)`. Adding version scope later requires a new
identity design, active uniqueness key, deterministic grant ID, query contract,
and runtime predicate; it is not a nullable option in this release.

This removal is limited to `workflow_tool_grant_t.workflow_version` and its
grant command/query/event contracts. It does not change
`workflow_tool_binding_t.workflow_version`, which pins a workflow-backed MCP
Tool to its implementation version and remains required.

## Authoring Flow

```text
Create or open workflow draft
  -> search granted and requestable Tools
  -> select one or more requestable Tools
  -> insert pending references into the draft
  -> start Grant Tools to Workflow
  -> continue editing while approval is pending
  -> observe grant status in the editor
  -> test and publish after every required grant is active
```

### Selecting Tools

The Reference dropdown presents Tool availability explicitly:

| Status | Meaning | Selectable | Testable |
| --- | --- | --- | --- |
| `GRANTED` | An active grant matches the Tool pin and environment. | Yes | Yes |
| `REQUESTABLE` | The Tool is discoverable and eligible for a request. | Yes | No |
| `REQUEST_REQUIRED` | The draft references the eligible Tool but no nonterminal request exists. | Yes | No |
| `PENDING_APPROVAL` | A `REQUESTED` request is waiting for an approver. | Yes | No |
| `REJECTED` | The approver rejected the request. | Existing reference only | No |
| `STALE` | Tool identity, version, digest, policy, or environment changed. | Existing reference only | No |
| `INELIGIBLE` | The Tool cannot currently be granted. | No | No |

Pending references must have a visible badge in the dropdown, workflow graph,
outline, and task property panel. The editor must not describe them as
callable.

`GRANTED` is derived only from a current active `workflow_tool_grant_t` row,
not from the terminal request status. Revoking a grant therefore immediately
returns the reference to a blocked request-required state even though the old
request remains `GRANTED` for audit.

### Discovery Versus Authorization

Showing a Tool before approval reveals its name, description, and schemas.
Discovery must therefore be authorized independently from execution.

The initial requestable catalog requires both permission to edit the target
workflow and the explicit `tool.catalog.read` permission. It returns only
eligible endpoint-backed Tools within that authorized host. This permission
allows metadata/schema discovery but grants no execution authority. A future
owner-controlled requestable flag may narrow discovery further, but the first
release does not add one.

The current callable query remains strict and returns only granted Tools. A new
workflow-reference catalog combines callable, requestable, and request-state
information for authoring.

## Starting the Access Workflow

The editor provides **Request Tool Access** after the author selects one or
more Tools. Starting the built-in workflow derives requester and tenant
identity from the authenticated request rather than trusting client-supplied
values.

The workflow input contains:

```json
{
  "requestId": "UUID",
  "hostId": "UUID",
  "targetWorkflow": {
    "wfDefId": "UUID",
    "namespace": "customer",
    "name": "customer-360",
    "version": "1.0.0"
  },
  "requester": {
    "userId": "UUID"
  },
  "justification": "Read customer context for the customer-360 workflow.",
  "tools": [
    {
      "toolId": "UUID",
      "name": "getCustomerProfile",
      "version": "1.0.0",
      "lightapiDigest": "sha256:...",
      "capabilityRef": "API0004/getCustomerProfile",
      "allowedEnvironments": ["loc", "dev"],
      "usageLocations": ["loadCustomer/profile"]
    }
  ]
}
```

Before starting the approval workflow, the server validates that:

- the target workflow draft exists and the requester may edit it;
- each Tool is discoverable and currently requestable;
- every item carries both `toolId` and `capabilityRef`, and that exact pair
  identifies the same active Tool row;
- Tool versions, capability references, and digests match current projections;
- requested environments are explicit and allowed; and
- there is no equivalent active grant or pending request.

The current workflow version is review context, not grant scope. Each
`metadata.workflowTool` pin is extended to contain `toolId`, `capabilityRef`,
Tool `version`, `lightapiDigest`, and nonempty `allowedEnvironments`. The
request must reproduce that exact identity pair and environment set. A
capability reference alone is never sufficient to choose a Tool aggregate.

The server computes and stores a canonical request digest over the immutable
approval fields. Display labels may be refreshed for presentation, but the
approved IDs, pins, environments, target workflow, and digest cannot change
inside a nonterminal request.

## Approval Workflow

The published **Grant Tools to Workflow** definition contains these logical
steps:

1. Validate and record the request.
2. Create a required approval `ask` task.
3. Assign the task to the configured Tool approver role.
4. On rejection, record the reason and notify the requester.
5. On approval, submit the typed human-task decision, which completes the task
   and applies the grant set atomically under the approver identity.
6. Record either `GRANTED` or `STALE`/`FAILED` from the decision result.
7. Create an informational acknowledgement task for the requester.

The approval task uses the generic assignment model:

```yaml
ask:
  prompt: Review the requested workflow Tool access.
  mode: approval
  assignment:
    roleId: genai-admin
    categoryCode: workflow-tool-access
    reasonCode: grant-tools-to-workflow
  options:
    - label: Approve
      value: APPROVED
    - label: Reject
      value: REJECTED
  commentRequired: true
  required: true
```

The concrete role ID is configuration. Authorization at completion is based on
an approval permission such as `genai.workflowTool.approve`, not solely on a
hard-coded display role name.

### Role Assignment Semantics

The workflow creates one role assignment, not one independent approval task
per role member. Every active member sees the assignment in the Worklist. The
first member claims it; other members then see it as claimed. Completion
records the actual approving user and makes the task unavailable to the other
members.

The generic Human Task page's typed approval renderer shows:

- requester and justification;
- target workflow name, namespace, definition ID, and current draft version
  for review context;
- each Tool name, capability, version, and digest;
- requested environments;
- safety, sensitivity, lifecycle, and endpoint policy metadata;
- workflow task or branch locations using each Tool; and
- any differences from an existing or previous grant.

## Secure Grant Application

The generic Human Task page recognizes the trusted task's typed action and
calls `workflow/decideWorkflowToolAccess/0.1.0` instead of generic
`completeTask`. This is not a workflow-specific page; it is a specialized
completion contract rendered by the existing Human Task UI.

`CompleteTask.additionalAction(...)` cannot be used for grant application
because it runs after `completeHumanTask` has committed. The database provider
must factor the existing lock, assignment, role-membership, and sibling-cancel
logic into reusable internals and expose one atomic decision operation. That
operation locks and verifies:

1. The workflow instance uses the configured published **Grant Tools to
   Workflow** definition, version, and definition digest.
2. The referenced approval task and `taskAsstId` belong to that instance and
   are active and claimed by the authenticated approver.
3. The approver still has active role membership and
   `genai.workflowTool.approve` permission.
4. The submitted answer is `APPROVE` or `REJECT`.
5. The approved request digest matches the immutable request payload.
6. The approval has not already been consumed for a different payload.
7. Each requested `toolId` and `capabilityRef` pair, Tool pin, endpoint policy,
   lifecycle, and environment set still matches current data.

For approval it completes the task, cancels sibling assignments, emits
`WorkflowToolGrantedEvent` for new or inactive deterministic grants and
`WorkflowToolGrantUpdatedEvent` for approved changes to an active grant, emits
the request decision event, projects all changes, and commits once. An already
equivalent active grant is rejected before request creation. Rejection completes
the task and request decision without grant events. Every event is attributed
to the authenticated human approver. The workflow service receives no general
grant permission.

## Atomicity And Idempotency

One approval decision covers the exact Tool set represented by the request
digest. Applying the request is all-or-nothing:

- revalidate every requested Tool first;
- insert all grant events in one transaction; and
- create no grants if any item is stale or invalid.

The operation is idempotent by `hostId + requestId + requestDigest`. Retrying
after an uncertain response returns the existing result and does not create a
second grant aggregate or advance versions twice.

If partial approval is needed, the approver rejects the original set and the
author submits a smaller request. A later design may add line-item decisions,
but partial mutation is not part of the initial implementation.

## Request State Projection

The workflow instance and human tasks are the source of orchestration truth.
The editor needs an efficient read model keyed by the target workflow and Tool.
That projection does not replace `workflow_tool_grant_t`.

Recommended request fields include:

```text
workflow_tool_access_request_t
  host_id
  request_id
  approval_wf_instance_id
  target_wf_def_id
  requester_user_id
  request_digest
  status
  decision_user_id              optional
  decision_comment              optional
  requested_ts
  decided_ts                    optional
  error_code                    optional
  error_message                 optional

workflow_tool_access_request_item_t
  host_id
  request_id
  tool_id
  capability_ref
  tool_version
  lightapi_digest
  allowed_environments
  usage_locations
  status
```

The projection is rebuildable from workflow/request events and grant results.
The actual authorization decision continues to come from an active matching
row in `workflow_tool_grant_t`.

There is no separate `applied_ts`: a `GRANTED` decision and its grant events
commit atomically, so `decided_ts` is also the application time. Generic
`update_user`/`update_ts` fields are intentionally omitted; requester and
decision actors are captured by `requester_user_id`/`decision_user_id`, while
`requested_ts`/`decided_ts` capture their corresponding transitions. A
`STALE` or `FAILED` decision also records `error_code` and `error_message`.

Recommended request states are:

```text
REQUESTED -> GRANTED
REQUESTED -> REJECTED
REQUESTED -> CANCELLED
REQUESTED -> STALE
REQUESTED -> FAILED
```

Human `ask` tasks currently have no waiting-task deadline sweeper. The first
release therefore has no automatic rejection, expiry, or acknowledgement
auto-completion promise. Those states require a separately designed runtime
deadline primitive and are deferred to hardening.

## Editor Validation And Gates

Validation depends on the operation being performed:

| Operation | Pending reference behavior |
| --- | --- |
| Edit | Allowed and visibly marked. |
| Save draft | Allowed with warnings. |
| Static definition validation | Structure and schema pass; access warning remains. |
| Test | Blocked until every referenced Tool is granted. |
| Publish | Blocked until every referenced Tool is granted and current. |
| Execute | Fails closed if a grant is absent, inactive, stale, or out of environment. |

Every `metadata.workflowTool` pin declares a nonempty
`allowedEnvironments` set. An active grant satisfies the pin only when it
contains the same `toolId`/`capabilityRef` pair and covers every declared
environment. Draft save validates the set structurally, Publish validates all
declared environments, editor Test additionally requires the selected test
environment, and Start/runtime require the actual service environment. An
undeclared deployment environment fails closed rather than inheriting access.

The editor should explain the blocking state instead of returning only a list
of unresolved capability references. Example:

```text
Testing is blocked while Tool access is pending:
- API0004/getCustomerProfile: waiting for genai-admin approval
- API0004/getCustomerPolicies: request became stale after Tool update
```

The **Test** button may remain visible but disabled, with a link to the request
status and approval workflow instance.

## Acknowledgement And Notification

After grants commit, the workflow creates an acknowledgement `ask` task
assigned directly to the original requester:

```yaml
assignment:
  assigneeId: "${ .requester.userId }"
  categoryCode: workflow-tool-access
  reasonCode: access-request-completed
```

The task summarizes granted Tools and links back to the target workflow. It is
informational:

- grants are effective before acknowledgement;
- the editor unlocks testing by querying committed grant state;
- failure to acknowledge never revokes or delays a grant; and
- an unacknowledged informational task may remain open in the first release.

The existing Portal notification channel may additionally notify the author
and approver, but notification delivery is not part of authorization.

## Rejection, Cancellation, And Staleness

### Rejection

Rejection requires a comment. Pending references remain in the draft so the
author can see exactly what is blocked, but the editor offers **Remove
Reference** and **Submit New Request** actions.

### Cancellation

The requester may cancel only before an approval decision. Deleting the draft
or removing all requested references should offer to cancel the pending
request. Cancellation does not affect existing grants.

### Staleness

The request becomes stale when any approved security-relevant value changes,
including:

- Tool version or LightAPI digest;
- endpoint identity or lifecycle;
- allowed environments; or
- endpoint authorization or policy configuration.

A stale request creates no grants. The author refreshes the Tool pins and
submits a new request. Existing active grants continue to follow their normal
digest and lifecycle validation rules.

## Authorization Model

Recommended permissions are:

| Permission | Purpose |
| --- | --- |
| `workflow.write` | Edit the target workflow draft. |
| `workflow.toolAccess.request` | Start or cancel an access request. |
| `tool.catalog.read` | Discover Tool metadata and schemas. |
| `genai.workflowTool.approve` | Claim and decide the typed task and atomically apply grants. |

The request endpoint checks `workflow.write`,
`workflow.toolAccess.request`, and `tool.catalog.read`. The typed Human Task
completion path checks current assignment and approval permission, then applies
the grants in that same transaction. Runtime continues checking the resulting
workflow Tool grant.

Passing the original user JWT through workflow execution remains necessary for
downstream endpoint authorization. It does not replace the workflow-level Tool
grant:

```text
user authorization      -> may this user access the endpoint?
workflow Tool grant     -> may this workflow invoke the capability?
approval evidence       -> did an authorized approver permit this exact grant?
```

## Audit Requirements

The audit trail must answer:

- Who requested access?
- Which workflow definition and current draft version was reviewed?
- Which exact Tool versions, digests, and environments were reviewed?
- Where were the Tools referenced in the workflow draft?
- Who claimed and completed the approval task?
- What decision and comment were submitted?
- Which grants were created and by which request?
- Did any item become stale before application?
- Was the author notified and did the author acknowledge the result?

The request digest connects the editor selection, approval task, decision command,
and emitted grant events.

## Deployment And Promotion

The built-in workflow is a versioned, published control-plane artifact. Each
environment must configure its expected workflow definition identity, version,
and digest for the typed decision allowlist.

Deployment order is:

1. Deploy schema, projection, query, and disabled decision support with an empty
   trusted-workflow identity.
2. Publish the built-in approval workflow.
3. Capture and configure its exact definition ID, version, and digest.
4. Enable the request/decision feature and its authorization policy.
5. Deploy editor support for draft identity creation, requestable Tools,
   pending-reference save behavior, and test/publication gates.

The request and decision commands must remain disabled until the trusted workflow definition
and its expected digest are configured. Promotion carries the built-in
workflow and ordinary Tool grant events through the established control-plane
promotion process; transient approval tasks are environment-local operational
state and are not promoted. Add `task_asst_t` and the two request tables to the
global snapshot export/conversion skip sets; `process_info_t` and `task_info_t`
are already skipped.

`workflow_tool_approval_evidence_t` is unrelated: it records approval evidence
for a workflow-backed MCP Tool binding keyed by `binding_id`. This design's
request aggregate is keyed by `request_id` and must not reuse that table.

## Implementation Phases

### Phase 1: Authoring And Request

- Create a minimal draft when **New Workflow** opens.
- Add the workflow-reference Tool catalog and status badges.
- Allow pending Tool references in drafts.
- Start the built-in access workflow from the editor.
- Project request and item status for editor queries.

### Phase 2: Approval And Grant Application

- Publish the built-in approval workflow.
- Assign and display the role-based approval task.
- Implement durable request digests and approval evidence.
- Implement atomic, idempotent grant application.
- Add requester acknowledgement and editor status refresh.

### Phase 3: Hardening

- Add cancellation, expiry, retry, and stale-request flows.
- Add notifications and deep links.
- Add audit reports and operational dashboards.
- Add configurable definition-wide versus version-specific approval policy.
- Consider preapproved Tool bundles for low-risk workflow namespaces while
  still materializing explicit per-workflow grants.

## Acceptance Criteria

The design is complete when:

1. A new workflow receives a stable `wfDefId` before the author selects Tools.
2. An authorized author can discover and insert a requestable Tool without Tool
   administration access.
3. The draft saves while the Tool is pending, with an explicit warning.
4. The author cannot test, publish, or execute the pending reference.
5. Starting the request creates one claimable role task visible to eligible
   approvers.
6. A non-member cannot claim or complete the approval task.
7. Approval of an unchanged request atomically creates all expected existing
   workflow Tool grants.
8. Rejection or staleness creates no grants.
9. Retrying grant application is idempotent.
10. The editor unlocks testing from committed grant state without waiting for
    acknowledgement.
11. The author receives a user-assigned acknowledgement containing a link to
    the workflow.
12. No generic task or arbitrary workflow can invoke the typed decision action.
