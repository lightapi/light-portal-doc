# Workflow Version and Publication

## Status

Accepted design.

The workflow draft, publish, immutable-version, published-version selection,
and comparison flows are implemented. Publishing one or more tools to a
Gateway instance from Instance Admin is the next control-plane phase and is
specified here so that it uses the same version model.

## Purpose

Workflow definitions are authored interactively and may change many times
before they are safe to use from a tool. A tool, however, must not execute an
unreviewed moving target. It needs a stable reference that supports audit,
controlled upgrade, and rollback.

This design defines:

- how workflow identity is preserved across versions;
- when a version is mutable or immutable;
- how a tool selects a workflow version without requiring raw JSON or digest
  entry;
- how versions are compared and rolled back; and
- how the selected tool and workflow revisions eventually become Gateway
  configuration through Config Server snapshots.

## Decision Summary

1. A workflow has one stable `wfDefId` for its complete version history.
2. `(hostId, wfDefId, version)` identifies one workflow version.
3. A `DRAFT` version may be saved repeatedly without changing its version.
4. Publishing freezes the exact saved YAML and changes the version to
   `PUBLISHED`.
5. A published version cannot be edited. Further work starts as a new version
   under the same `wfDefId`.
6. Tools may bind only to published workflow versions.
7. Namespace and name are searchable display metadata, not identity keys.
8. Digests remain internal integrity evidence. Users do not enter or manage
   them on the Tool form.
9. Workflow publication and Gateway activation are separate operations.
10. A Gateway change becomes live only after Instance Admin creates a new
    configuration snapshot and selects it as current.

## Goals

- Let an author iterate frequently without creating duplicate workflow
  identities.
- Make every version used by a tool immutable and reproducible.
- Allow a tool to move forward or roll back by selecting a different published
  version under the same `wfDefId`.
- Prevent draft workflows from entering Gateway runtime configuration.
- Present workflow selection in business terms such as
  `customer/customer-360 @ 1.2.0`.
- Keep internal hashes, generated IDs, and binding JSON out of the normal user
  workflow.
- Preserve optimistic concurrency and event-sourced projection behavior.
- Reuse Config Server snapshots for deployment activation and configuration
  drift prevention.

## Non-Goals

- Publishing a workflow does not deploy it to a Gateway.
- Saving a tool does not change a live Gateway.
- The workflow version string is not generated automatically by this design.
- Namespace and name do not provide uniqueness across a workflow history.
- Digests do not replace human-readable version identity or configuration
  snapshots.
- A configuration snapshot does not replace workflow-version immutability.

## Terminology

| Term | Meaning |
| --- | --- |
| Workflow identity | Stable `wfDefId` shared by all versions of one workflow. |
| Workflow version | One YAML definition identified by `(hostId, wfDefId, version)`. |
| Draft | Mutable saved version that cannot be selected by a tool. |
| Published version | Immutable version eligible for tool binding. |
| Tool binding | Internal contract pinning a tool to `wfDefId` and `workflowVersion`. |
| Tool publication | Selection of completed tool revisions for a Gateway instance. |
| Configuration snapshot | Immutable Config Server artifact for one instance. |
| Current snapshot | Snapshot selected for delivery to the live instance. |

## Identity Model

`wfDefId` is the aggregate identity. It never changes merely because the YAML
or version changes.

```text
wfDefId: 2695cdee-cb82-4b34-a2d8-f69093c733e3
  1.0.0  PUBLISHED
  1.1.0  PUBLISHED
  1.2.0  DRAFT
```

The identity rules are:

- `hostId + wfDefId` identifies the workflow history;
- `hostId + wfDefId + version` identifies a saved revision;
- `hostId + namespace + name + version` prevents duplicate labels within a
  host, but does not replace `wfDefId`; and
- a tool stores `wfDefId` and `workflowVersion`, never namespace and name as
  its durable reference.

Keeping `wfDefId` stable preserves grouping in the editor, avoids ambiguous
namespace/name matching, and makes rollback a version-selection operation
instead of rebinding to an unrelated workflow.

## Lifecycle State Machine

| Current state | Operation | Result | Allowed |
| --- | --- | --- | --- |
| None | Create | New saved `DRAFT` | Yes |
| `DRAFT` | Save | Same version updated | Yes |
| `DRAFT` | Publish exact saved YAML | Same version becomes `PUBLISHED` | Yes |
| `DRAFT` | Bind from Tool | No change | No |
| `PUBLISHED` | Edit or overwrite YAML | No change | No |
| `PUBLISHED` | Create new version | New `DRAFT` under same `wfDefId` | Yes |
| `PUBLISHED` | Bind from Tool | Tool pins this version | Yes |

`DEPRECATED` is reserved in persistence for a future retirement operation. The
current command and UI lifecycle has no transition into that state; until one
is implemented, saved versions move only from `DRAFT` to `PUBLISHED`.

Publication must operate on the exact saved draft. If the editor contains
unsaved changes, the user must save them before publishing. This prevents the
publish command from freezing content that was never projected as a draft.

The version string is supplied by the author. Portal rejects a new draft when
the same `(hostId, wfDefId, version)` already exists. Semantic-version ordering
may be added as a UX policy later, but identity does not depend on parsing the
version as SemVer.

## Authoring Experience

### Create and save

Creating a workflow assigns a new `wfDefId` and saves version `1.0.0`, or the
version entered by the author, as `DRAFT`. The author may import YAML, use the
visual editor, ask the authoring assistant, validate, test, and save repeatedly.

### Publish

**Publish Version** performs client and server validation, asks for explicit
confirmation, and publishes the exact saved definition. After success:

- YAML and identity fields become read-only;
- graph and step-palette mutation actions are disabled;
- publication status is visible in the editor and workflow table; and
- the version becomes available in workflow-backed Tool forms.

### Create a new version

For a published version, **Create New Version** asks for a new version string,
copies the published YAML, updates its embedded version metadata where present,
and creates a draft under the same `wfDefId`. The clone is not durable until it
is saved.

### Compare versions

The editor loads the workflow's complete version history. An author selects a
base and comparison version and views them side by side as normalized YAML.
Normalization reduces noise from formatting while retaining list order and
semantic values.

The initial implementation is a side-by-side viewer. Line-level highlighting
can be added later without changing the persistence or API contract.

## Persistence Model

### Workflow aggregate head

`wf_definition_t` remains the event-backed aggregate head. It contains the
currently selected authoring version and aggregate concurrency state, including:

- `host_id` and `wf_def_id`;
- namespace, name, version, and definition;
- `lifecycle_status`;
- ownership and taxonomy metadata;
- `aggregate_version`; and
- active/update audit fields.

### Version history

`wf_definition_version_t` stores each saved version:

| Column | Purpose |
| --- | --- |
| `host_id`, `wf_def_id`, `version` | Composite version identity. |
| `namespace`, `name` | Display metadata captured with the version. |
| `definition` | Exact saved workflow YAML. |
| `lifecycle_status` | `DRAFT`, `PUBLISHED`, or `DEPRECATED`. |
| `published_by`, `published_ts` | Publication audit evidence. |
| `aggregate_version` | Event projection ordering. |
| `active`, `update_user`, `update_ts` | Projection lifecycle and audit data. |

The primary key is `(host_id, wf_def_id, version)`. A foreign key retains the
relationship to `wf_definition_t`. Published rows may not be overwritten by a
later draft or by different YAML.

`workflow_tool_binding_t` has a composite foreign key to the version table so a
binding cannot refer to an unknown workflow version. Projection validation also
requires the referenced row to be active and `PUBLISHED`.

## Command Contracts

### `createWfDefinition`

- Generates `wfDefId` when absent.
- Enriches the event payload with `lifecycleStatus: DRAFT`.
- Creates the aggregate head and initial version row.

### `updateWfDefinition`

- Uses the existing `aggregateVersion` optimistic-concurrency contract.
- Rejects changes to an already published version.
- Saves the selected version as `DRAFT`.
- Permits repeated changes to the same draft version.

### `publishWfDefinition`

- Uses the workflow update event type so existing event ordering remains
  authoritative.
- Requires the selected version to be a saved draft.
- Requires submitted YAML to equal the saved draft YAML.
- Enriches the event payload with `lifecycleStatus: PUBLISHED`.
- Records publisher and publication timestamp in the version projection.

Publishing is idempotent only for replay of the same ordered event. An
interactive attempt to publish an already published version is rejected rather
than presented as a new publication.

## Query Contracts

### `getWfDefinitionById`

Returns the aggregate head plus a `versions` collection containing definition,
lifecycle, publication, aggregate-version, and audit fields. The Workflow
Editor uses this response rather than relying on a potentially stale list row.

### `getPublishedWfDefinitionVersionLabel`

Returns selector options only for active, published workflow versions. Each
option has:

```json
{
  "value": "2695cdee-cb82-4b34-a2d8-f69093c733e3|1.2.0",
  "label": "customer/customer-360 @ 1.2.0"
}
```

The `wfDefId|version` value is a form helper, not a persisted domain identity.
It avoids maintaining two dependent selectors and is omitted before command
submission.

### `getWorkflowToolBindingOption`

Accepts `hostId` and `workflowVersionRef`. It verifies that the selected
version is published and returns trusted binding inputs:

- `wfDefId`;
- namespace and name for display;
- workflow version; and
- canonical definition digest.

Draft, inactive, malformed, and unknown selections fail closed.

## Workflow-Backed Tool Form

When `executionPlacement` is `workflow`, the form displays **Workflow
Definition** as a published-version selector. It does not display:

- raw Workflow Binding JSON;
- schema digest;
- workflow-definition digest;
- policy digest; or
- response-policy digest.

The schema-driven form submits the selected `wfDefId|version` reference. The
command service reloads that published version and constructs the internal
binding. Defaults such as invocation mode and deadlines are system-owned. The
command service derives definition, schema, and policy digests from trusted
server-side content, overriding caller-supplied values.

At projection time, Portal reloads the published version's YAML, recomputes its
canonical digest, and requires it to match the binding. The browser is
therefore not the trust boundary. Command-time selection resolution and
projection both call the same `common-util` canonical digest implementation, so
changes to YAML parsing or canonicalization cannot drift between repositories.

## Why Digests Still Exist

Configuration snapshots remove the need for users to manage digests, but do
not eliminate internal integrity requirements.

| Digest | Internal purpose |
| --- | --- |
| Definition digest | Proves the binding matches the immutable published YAML. |
| Schema digest | Pins the request/response contract used by the tool. |
| Policy digest | Identifies the server-owned workflow execution policy profile. |
| Response-policy digest | Identifies response handling and disclosure rules. |
| Snapshot/artifact digest | Verifies Config Server content delivered to an instance. |

Workflow and binding digests protect semantic admission contracts. Snapshot
digests protect a deployable configuration artifact. They operate at different
layers and should not be overloaded as version labels or activation switches.

## Tool Upgrade and Rollback

Changing a tool from workflow version `1.1.0` to `1.2.0` creates a new tool
revision with a new immutable binding. It does not alter either workflow
version. Rolling back selects `1.1.0` again and republishes the changed tool to
the target Gateway.

Existing Gateway configuration remains unchanged until a new configuration
snapshot becomes current. Existing in-flight work remains pinned to the
binding and policy admitted at start; changing the current snapshot affects
new work.

## Gateway Tool Publication

This section specifies the planned Instance Admin phase.

### Entry point

Instance Admin provides **Publish Tools** for one tool or a selected batch. The
operator chooses a registered `light-gateway` instance. Portal resolves the
current revision of every selected tool and validates that all workflow-backed
tools reference published workflow versions.

### Publication flow

```text
Select tools and Gateway instance
              |
              v
Resolve immutable tool and workflow revisions
              |
              v
Validate ownership, compatibility, and references
              |
              v
Stage managed mcp-router.yml entries
              |
              v
Create immutable configuration snapshot
              |
              v
Review snapshot comparison
              |
              v
Move the instance current pointer
```

The publication record should contain at least:

- host, environment, and Gateway instance ID;
- publication ID and operator identity;
- selected tool IDs and aggregate versions;
- workflow `wfDefId` and version for each workflow-backed tool;
- generated managed-entry keys;
- projection/event watermark;
- resulting configuration snapshot ID; and
- status, failure reason, and timestamps.

### Batch semantics

A batch is one intended Gateway configuration generation. Validation is
all-or-nothing before staging. If any selected tool is inactive, stale,
unauthorized, or bound to a non-published workflow version, no batch entries
are activated.

Property projection and snapshot creation may be asynchronous, but the
snapshot must not become current until every staged entry is present and the
snapshot comparison succeeds. Retrying the same publication ID must be
idempotent.

### Managed `mcp-router.yml` entries

Portal owns entries generated by tool publication. Their stable managed key
must be based on tool identity, not the mutable display name. Republishing a
tool updates its managed desired entry for the next snapshot; it never edits an
existing snapshot.

Removing a published tool from an instance is also a publication that removes
or disables its managed entry in the next snapshot. It does not delete the tool
or workflow definition from Portal.

## Configuration Snapshot Boundary

The Instance Admin, not the workflow editor or Tool form, creates configuration
snapshots. A snapshot captures the complete effective instance configuration,
including the generated `mcp-router.yml` entries.

The current pointer provides controlled activation:

- creating a snapshot does not make it live;
- selecting it as current affects subsequent Config Server reads;
- an invalid runtime load preserves the Gateway's last known good content; and
- rollback selects a previous immutable snapshot rather than reconstructing
  configuration from current authoring rows.

This boundary prevents configuration drift while preserving independent
workflow and tool authoring lifecycles.

## Authorization and Ownership

- Workflow creation, update, and publication require Portal write scope and
  normal owner/position authorization.
- Published-version labels are host-scoped and returned only through Portal
  query authorization.
- A user must be authorized to view a workflow before using it in a tool.
- Tool publication additionally requires permission to administer the target
  Gateway instance.
- Cross-host workflow selection and publication are never allowed.

The server revalidates host and ownership boundaries; selector filtering alone
is not authorization.

## Concurrency and Failure Handling

- Workflow mutations use `aggregateVersion` to reject stale commands.
- Version projection applies only newer aggregate events.
- A stale event must not create a new version-history row before the aggregate
  head accepts it.
- Publishing fails if the draft changed after the editor loaded it.
- Binding creation fails if the workflow version is not active and published.
- Binding projection fails if its definition digest differs from canonical
  stored YAML.
- Snapshot activation fails closed when staging is incomplete or comparison
  detects unexpected content.

Failures do not modify an immutable published version or an existing
configuration snapshot.

## Migration and Compatibility

The schema migration:

1. adds lifecycle status to `wf_definition_t`;
2. creates `wf_definition_version_t`;
3. backfills each existing workflow head as `PUBLISHED` with its current
   version and audit metadata;
4. marks the corresponding aggregate head as published;
5. adds the published-version lookup index; and
6. adds the workflow-tool-binding composite foreign key.

Existing definitions are treated as published because existing tools may
already depend on them. This prevents migration from silently turning a
runtime dependency into an editable draft.

Legacy workflow events without lifecycle status replay as published to preserve
their historical projection semantics. New create and update commands always
emit explicit lifecycle status.

The foreign key is introduced as `NOT VALID` for an existing database so rollout
is not blocked by historical binding drift. Operations must audit and repair
legacy violations before validating the constraint. Fresh databases create the
constraint normally.

Rollback removes the new binding constraint, version table, and lifecycle
column. It should be used only before new multi-version data or bindings depend
on the model.

## Observability and Audit

Audit views should answer:

- who created, changed, and published a workflow version;
- which exact YAML digest was published;
- which tools reference each published version;
- which workflow and tool revisions were included in a Gateway publication;
- which configuration snapshot contains that publication; and
- which snapshot is current or was selected during rollback.

Recommended metrics include publication validation failures, stale aggregate
conflicts, rejected draft bindings, digest mismatches, snapshot creation
latency, activation failures, and last-known-good fallback events.

## Rollout Plan

### Phase 1: Workflow lifecycle

- Apply the database migration.
- Deploy the updated Portal database provider.
- Deploy workflow command and query services.
- Deploy the Workflow Editor lifecycle and comparison UI.
- Verify existing workflows appear as published and remain readable.

### Phase 2: Tool binding UX

- Deploy published-version label and option queries.
- Deploy the Tool form without raw binding or digest inputs.
- Deploy server-derived digest handling and projection verification.
- Verify draft versions never appear in the selector.

### Phase 3: Gateway publication

- Add Instance Admin single and batch tool selection.
- Add publication manifest and status persistence.
- Generate managed `mcp-router.yml` desired entries.
- Reuse snapshot creation and YAML comparison.
- Require explicit current-pointer activation.
- Add removal, retry, failure recovery, and rollback tests.

## Acceptance Criteria

- Multiple versions share one `wfDefId` and appear as one workflow history.
- A draft can be saved repeatedly without changing its version.
- An unsaved draft cannot be published.
- Published YAML cannot be changed by the editor, command, or projection.
- Creating a new version retains the same `wfDefId`.
- Two saved versions can be compared as normalized YAML.
- Only active published versions appear on the Tool form.
- The Tool form shows no raw binding JSON or digest fields.
- Direct callers cannot use a forged definition digest.
- A tool can be rebound to an older published version for rollback.
- Tool authoring alone does not alter live Gateway configuration.
- A Gateway change becomes live only through a newly current immutable
  configuration snapshot.

## Related Documents

- [Control-Plane Policy Publication Through Config Server](./control-plane-policy-config-server.md)
- [Configuration Snapshot Output and Comparison](../portal-view/config-snapshot-output-comparison.md)
