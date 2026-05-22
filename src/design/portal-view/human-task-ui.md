# Human Task UI

`ask` is the workflow task type that pauses execution for human input. The
runtime can now create `task_asst_t` and `worklist_t` rows when an `ask` task
waits, so `portal-view` needs a generic human-task interface that lets an
assigned user open the task, provide the requested answer, and resume the
workflow.

This document proposes the portal UI and service contracts for that interface.

## Current State

The workflow engine persists waiting ask tasks in `task_info_t`. The ask
configuration is stored in `task_info_t.task_output.ask`, and the workflow
runtime context remains on `process_info_t.context_data`.

The assignment layer is separate:

- `worklist_t` represents a user/category worklist.
- `task_asst_t` represents a concrete task assignment.
- Role assignment is resolved by the workflow runtime into one task assignment
  per active user in the role.

The Worklist page can show assigned tasks, but it does not yet provide a
generic input screen for the user to approve or enter data.

## Goals

- Provide one generic page for all human-input workflow tasks.
- Render the input controls from the ask task definition, not from a
  workflow-specific page.
- Let users open tasks from the Worklist page.
- Keep assignment, claim, completion, and authorization checks on the service
  side.
- Support role-assigned tasks where multiple users may receive the same work.
- Resume the workflow through the existing `completeTask` command.
- Keep the UI useful for approval tasks first while leaving room for richer
  object-input tasks.

## Non-Goals

- Do not create a custom approval page for each workflow.
- Do not make every workflow task human-actionable; only `ask` tasks use this
  interface.
- Do not expose raw database rows directly to the page.
- Do not overload the engine `locked` field for human claims; that field is
  already used by the workflow executor as a worker lease.
- Do not replace the existing Worklist administration page in the first phase.

## User Flow

The primary flow is:

```text
Worklist
  -> open assigned task
  -> Human Task detail
  -> render prompt and input controls from ask metadata
  -> submit answer
  -> completeTask command
  -> workflow executor resumes the process
```

For a simple approval workflow, the user sees the prompt and two action buttons
derived from the ask options. For structured input, the same page renders a
schema-driven form.

The runtime flow for a role-assigned ask task is:

1. The workflow executor creates one `task_asst_t` row per assignee and keeps
   the parent `task_info_t` row waiting for input.
2. The assigned user opens the row from Worklist.
3. `getHumanTask` loads the assignment, task state, workflow metadata, and
   process context into one stable page payload.
4. The user submits an answer through `completeTask`.
5. `completeTask` validates assignment ownership, locks the parent task row,
   records the result, and deactivates or cancels sibling assignments in the
   same transaction.
6. The workflow executor observes the completed ask task and resumes the
   process with the submitted answer.

## Route Design

Add a human task detail route:

```text
/app/workflow/HumanTask
```

The route should accept `taskAsstId` and task context through query parameters
or router state:

```text
/app/workflow/HumanTask?taskAsstId=...&taskId=...
```

The Worklist page should route to this detail page for actionable task rows.
Worklist administration actions such as create, update, and delete worklists
should remain separate from human task completion.

If a dedicated inbox page is needed later, add:

```text
/app/workflow/HumanTasks
```

That page can list only actionable assigned tasks, while the existing Worklist
page can remain the administrative view of worklist definitions.

## Data Model Decisions

`task_info_t` remains the canonical workflow engine task state. Its `locked`
column must stay reserved for executor leasing. Human task claims must not set
`task_info_t.locked = 'Y'`, because that would make the executor treat the row
as worker-owned runtime work.

Useful existing `task_info_t` fields for the human task page are:

- `status_code`: parent task state. Waiting ask tasks should be open for input;
  completed ask tasks should be read-only.
- `deadline_ts`: optional due or expiry timestamp to show in the UI.
- `locking_user` and `locking_role`: possible global claim metadata if claim is
  implemented, but not a replacement for assignment-level authorization.
- `task_output`: source of the ask metadata.
- `result_code`: submitted answer envelope after completion.

`task_asst_t` remains the assignment layer. The current `active` flag and
`unassigned_reason` can hide completed assignments from Worklist, but they are
too loose to represent claim, release, expiry, and reporting states cleanly.
Add an explicit assignment status early in development so the query and command
contracts are built on the final assignment state model:

```sql
ALTER TABLE task_asst_t
  ADD COLUMN status_code VARCHAR(16) NOT NULL DEFAULT 'ASSIGNED',
  ADD COLUMN claimed_by VARCHAR(126),
  ADD COLUMN claimed_ts TIMESTAMP WITH TIME ZONE,
  ADD COLUMN claim_expires_ts TIMESTAMP WITH TIME ZONE;
```

Recommended assignment statuses:

| Status | Meaning |
| --- | --- |
| `ASSIGNED` | Visible and actionable for the assignee. |
| `CLAIMED` | Claimed by one assignee and locked from sibling submissions. |
| `COMPLETED` | Completed by this assignee. |
| `RELEASED` | Previously claimed and returned to the pool. |
| `CANCELLED` | No longer actionable because the parent task ended elsewhere. |
| `EXPIRED` | No longer actionable because the task or claim timed out. |

Keep `active` as a fast visibility/backward-compatibility flag. Use
`status_code` for business state and audit/reporting semantics.

## Query Contract

The UI should not assemble a human task by calling several generic table
queries. Add a normalized query action such as `getHumanTask`.

Request:

```json
{
  "hostId": "...",
  "taskAsstId": "..."
}
```

Response:

```json
{
  "hostId": "...",
  "taskAsstId": "...",
  "taskId": "...",
  "processId": "...",
  "wfInstanceId": "...",
  "wfTaskId": "requestApproval",
  "assignedTs": "...",
  "assigneeId": "...",
  "assignmentStatusCode": "ASSIGNED",
  "claimedBy": null,
  "claimedTs": null,
  "deadlineTs": "2026-05-23T14:30:00Z",
  "categoryCode": "approval",
  "reasonCode": "human-approval",
  "taskStatusCode": "W",
  "workflow": {
    "wfDefId": "...",
    "namespace": "light-portal",
    "name": "human-approval",
    "version": "1.0.0"
  },
  "ask": {
    "prompt": "Review the workflow request and choose a decision.",
    "mode": "approval",
    "options": [
      {
        "label": "Approve",
        "value": "APPROVED",
        "description": "Continue the request."
      },
      {
        "label": "Reject",
        "value": "REJECTED",
        "description": "Stop the request."
      }
    ],
    "required": true,
    "allowComment": true,
    "contextKeys": ["requestId", "summary"]
  },
  "contextSummary": {
    "requestId": "REQ-001",
    "summary": "..."
  },
  "context": {
    "requestId": "REQ-001",
    "summary": "..."
  }
}
```

The service should read from `task_asst_t`, `task_info_t`, `process_info_t`,
and `wf_definition_t`, then return a stable task-detail view. The UI should
treat this response as the source of truth.

The query should return a curated `contextSummary` when the ask metadata
defines `contextKeys`. It may also include the raw `context` object for
administrator troubleshooting or for workflows that have not yet declared a
curated context shape. The default user view should prefer `contextSummary`.

For a list page, add `getHumanTaskList` later. It should return only active
assignments for the current user unless the caller has an administrative
permission.

## Input Rendering

The page renders controls from `ask.mode`, `ask.options`, and `ask.schema`.

| Ask mode | Control |
| --- | --- |
| `approval` | Primary action buttons from `options`, with an optional comment field. |
| `confirm` | Yes/No control. |
| `choice` | Radio group or select from `options`. |
| `multiChoice` | Checkbox group from `options`. |
| `text` | Text area. |
| `object` | Schema-driven form from `ask.schema`. |
| `file` | Future upload control. |

If `ask.mode` is missing, default to `text`. If `approval` has no options, the
UI may render default `APPROVED` and `REJECTED` actions.

Comments should be configurable per ask task. The recommended metadata is:

```json
{
  "allowComment": true,
  "commentRequired": false
}
```

`approval` and `confirm` should default to allowing comments. Other modes can
opt in when the workflow author wants users to explain the submitted value.

## Answer Shape

Use a consistent answer envelope for `completeTask`.

```json
{
  "value": "APPROVED",
  "comment": "Looks good.",
  "submittedAt": "2026-05-22T14:30:00Z"
}
```

For object input, `value` is the submitted object:

```json
{
  "value": {
    "approvedLimit": 5000,
    "expirationDate": "2026-06-30"
  },
  "comment": "Approved with a reduced limit.",
  "submittedAt": "2026-05-22T14:30:00Z"
}
```

The workflow receives this object as the ask task output. A workflow that needs
only the selected value can export `.output.value`; a workflow that wants the
full audit envelope can export `.output`.

## Completion Command

The detail page submits through `completeTask`:

```json
{
  "host": "lightapi.net",
  "service": "workflow",
  "action": "completeTask",
  "version": "0.1.0",
  "data": {
    "hostId": "...",
    "taskId": "...",
    "taskAsstId": "...",
    "statusCode": "C",
    "completedTs": "2026-05-22T14:30:00Z",
    "response": {
      "value": "APPROVED",
      "comment": "Looks good.",
      "submittedAt": "2026-05-22T14:30:00Z"
    }
  }
}
```

The command should verify that:

- the assignment exists and is active
- the assignment status allows submission
- the current user is the assignee or has an administrative permission
- the task is an ask task
- the task is still waiting for input
- the submitted answer matches `ask.mode`, `ask.options`, and `ask.schema`

The browser may send `taskAsstId`, `taskId`, and the answer, but it must not be
trusted to identify the completing user. The command service should derive the
user id and roles from the authenticated token. A client-supplied
`completedUser` value should be ignored for normal human-task completion.

Completion must be atomic. In one database transaction:

1. Load the `task_asst_t` row and verify it belongs to the current user, unless
   the caller has an explicit administrative override permission.
2. Lock the parent `task_info_t` row, for example with `SELECT ... FOR UPDATE`.
3. Reject the command if the parent task is already completed or no longer
   waiting for input.
4. Validate the answer against the ask metadata and, for object mode, the JSON
   schema.
5. Update `task_info_t` with status `C`, `completed_ts`, `completed_user`, and
   the answer envelope in `result_code`.
6. Mark the selected assignment `COMPLETED` and inactive.
7. Mark sibling active assignments for the same `task_id` as `CANCELLED`,
   inactive, and `unassigned_reason = 'completed_by_other_user'`.

If another user completes the same parent task first, return a stale-task
conflict response, preferably HTTP `409`, and leave the duplicate submission
unapplied.

## Claim And Concurrency

Role assignment can create several active assignments for the same `task_id`.
The first user-input page should use optimistic completion with a server-side
final check: only the first valid completion succeeds, and later submissions
receive a stale-task conflict response. This proves the core flow before adding
the operational complexity of explicit claim/release commands.

For a better user experience, add an optional `claimHumanTask` command.

Recommended claim behavior:

- claim records the current user on the human-task assignment path with
  `task_asst_t.status_code = 'CLAIMED'`, `claimed_by`, and `claimed_ts`
- claim does not set `task_info_t.locked = 'Y'`
- claim expires after a short timeout or can be released
- completion still performs the final status check

The engine `locked` column should remain reserved for executor leasing. Human
claims should use either assignment-specific fields added later or
`locking_user`/`locking_role` without changing the executor lease flag.

When claim is enabled for role-assigned tasks, sibling assignment rows should
be visible as claimed or unavailable instead of letting users submit stale
answers. Live refresh should use the existing portal notification channel if
one is available. If workflow tasks need their own lightweight channel later,
prefer server-sent events before adding a separate websocket service.

## Assignment Cleanup

When a human task is completed:

- the selected assignment should no longer appear as actionable
- sibling active assignments for the same `task_id` should also disappear
- the task completion result should remain on `task_info_t`

With the current table shape, the minimal implementation can deactivate active
`task_asst_t` rows for the task and set `unassigned_reason` to `completed` or
`completed_by_other_user`. A later schema iteration can add explicit
assignment status fields if the UI needs richer assignment history.

With the recommended status column, cleanup should use structured states:

- selected assignment: `status_code = 'COMPLETED'`, `active = false`,
  `unassigned_reason = 'completed'`
- sibling assignments: `status_code = 'CANCELLED'`, `active = false`,
  `unassigned_reason = 'completed_by_other_user'`

## Authorization

Normal users should only query and complete assignments where
`task_asst_t.assignee_id` matches their user id. Administrative users may view
all assignments for the host if the workflow task endpoints allow it.

The browser should send `taskAsstId`, but the service should not trust the
browser to identify the assignee. It should resolve the current user from the
authenticated token and compare it to the assignment row.

Administrative completion on behalf of another user should require a distinct
permission, not just the ability to query workflow tasks. The command should
record both the authenticated actor and the effective completed user if
override support is added.

Recommended authorization model:

- normal completion requires the endpoint write scope and
  `task_asst_t.assignee_id = authenticated user id`
- administrative override requires `workflow.task.override`
- a host or portal administrator, such as the configured `portal.admin`, may be
  treated as satisfying the override permission if that is the established
  portal authorization convention

Use a broad scope such as `workflow.write` for access to the write endpoint if
the service defines workflow-specific scopes. If the current service only has a
portal-level write scope, keep the OAuth scope broad and enforce
`workflow.task.override` as the fine-grained application permission.

## Page Layout

The detail page should be compact and task-oriented:

- header with workflow name, task name, status, and due date if `deadlineTs` is
  present
- assignment summary with assignee and category
- prompt panel
- context panel with selected workflow/process fields
- input area rendered from ask metadata
- sticky submit actions for long forms
- error or stale-task state

The context panel should show enough data for the user to decide, but it should
not dump the full `context_data` object by default. The first phase can show
common fields and provide a collapsible raw context view for administrators.

Timeout handling should be visible as read-only metadata as soon as
`task_info_t.deadline_ts` is available. The UI can show due date or expiry
status without implying that automatic runtime timeout processing has already
been implemented.

## Error States

The page should handle these states explicitly:

- assignment not found
- assignment no longer active
- task already completed
- task is not an ask task
- ask metadata missing or invalid
- validation failed
- submit conflict because another user completed the task first
- workflow resume failed after completion

The submit conflict case should take the user back to the worklist after
showing that the task is no longer available.

## Implementation Phases

Phase 1:

- Add the `task_asst_t.status_code` migration before building the query and
  command handlers.
- Add `getHumanTask`.
- Add `/app/workflow/HumanTask`.
- Link actionable Worklist task rows to the detail page.
- Render `approval`, `choice`, `multiChoice`, `confirm`, and `text`.
- Submit through `completeTask`.
- Validate assignment ownership and ask metadata in the command layer.
- Complete the parent task and assignment cleanup in one transaction.
- Return stale-task conflicts for duplicate submissions.
- Hide completed and sibling-cancelled assignments from the worklist.

Phase 2:

- Add schema-driven `object` input.
- Add JSON schema validation on the command side.
- Add curated context metadata such as `ask.contextKeys`.

Phase 3:

- Add optional `claimHumanTask` and `releaseHumanTask`.
- Add claim expiry handling.
- Add a dedicated human task inbox.
- Add assignment history and richer audit display.
- Add live Worklist refresh for claim/completion events through the existing
  portal notification channel, with server-sent events as the fallback.
- Add file input if workflow use cases require it.

## Resolved Questions

- `task_asst_t` should gain explicit assignment status fields. `active` remains
  useful for filtering but should not be the only state model.
- The human task query should return curated context when workflow metadata
  defines it, with raw context available for administrative troubleshooting.
- Comments should be configurable. Approval and confirm modes should default to
  allowing comments.
- Timeout metadata should be visible as read-only UI state before automatic
  timeout processing is implemented.
- Administrative override should use the fine-grained permission
  `workflow.task.override`, with `portal.admin` as the broad administrator path
  if the portal authorization layer already uses it.
- Claim/release should remain Phase 3. Phase 1 should rely on optimistic
  completion and atomic duplicate-submit rejection.
- Live Worklist refresh should use the existing portal notification channel
  first. If there is no reusable channel, use server-sent events before adding a
  dedicated websocket service.
