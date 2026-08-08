# Agent Memory Event Refactor

## Implementation Status

The development implementation now exposes a bank-first Hindsight workspace at
`/app/genai/MemoryBanks` and a bank detail workspace at
`/app/genai/MemoryBanks/:bankId`. The old flat session, user, agent, and
organization memory pages and service actions have been removed. There is no
legacy data migration or compatibility path: development databases are rebuilt
from the current DDL.

The current Hindsight table family is:

```text
agent_memory_bank_t
agent_memory_doc_t
agent_memory_unit_t
agent_memory_entity_t
agent_memory_unit_entity_t
agent_memory_entity_cooccur_t
agent_memory_link_t
agent_memory_directive_t
agent_memory_reflection_t
agent_session_history_t
```

The Portal command/event path projects current Hindsight events into these
tables. `light-agent` remains an intentional direct writer in direct-PostgreSQL
mode and is the owner of the session-history projection. The retained
Portal-command runtime mode creates session history with
`durable_session_id = sessionId`, allowing the runtime reconciler to rebuild it
from `agent_session_event_t`.

`GlobalSnapshotPersistenceImpl` treats the memory family as one explicit
`agent_memory_t` export entity. Session history is opt-in and sensitive;
co-occurrence state is derived and is not exported as authoritative state.
The `agent_memory_t` name in that export dispatch is a current compatibility
alias for the Hindsight table set, not the removed legacy table.

## Goal

Keep ownership explicit while supporting Portal administration:

```text
command/event path -> event_store_t -> db-provider replay -> Hindsight tables
```

- Portal administrators manage banks and supported bank-scoped resources
  through command events and current read-model queries.
- `light-agent` owns runtime session history and may use either the direct-PG or
  Portal-command memory store.
- derived and vector state is never presented as Portal-authored authoritative
  content.

## Non-Goals

- Do not add legacy table migration, dual reads, or compatibility writers.
- Do not convert derived caches into authoritative state unless a product
  decision requires exact cache promotion.
- Do not require every chat token or partial model response to become an event.
- Do not remove the current direct PostgreSQL path; it remains the default
  development runtime store.

## Current Portal Contract

All operations use service `lightapi.net/genai`, version `0.1.0`.

Read actions (`portal.r`) are:

```text
getAgentMemoryBanks              getFreshAgentMemoryBank
getAgentMemoryDocs               getFreshAgentMemoryDoc
getAgentMemoryUnits              getFreshAgentMemoryUnit
getAgentMemoryEntities           getFreshAgentMemoryEntity
getAgentMemoryUnitEntities       getAgentMemoryEntityCooccurrences
getAgentMemoryLinks              getFreshAgentMemoryLink
getAgentMemoryDirectives         getFreshAgentMemoryDirective
getAgentMemoryReflections        getFreshAgentMemoryReflection
getAgentSessionHistories         getAgentSessionHistoryProjection
```

Portal-enabled commands (`portal.w`) are:

```text
createAgentMemoryBank            updateAgentMemoryBank
deleteAgentMemoryBank            createAgentMemoryDoc
updateAgentMemoryDoc             deleteAgentMemoryDoc
deleteAgentMemoryUnit            createAgentMemoryEntity
updateAgentMemoryEntity          deleteAgentMemoryEntity
linkAgentMemoryUnitEntity        unlinkAgentMemoryUnitEntity
createAgentMemoryLink            updateAgentMemoryLink
deleteAgentMemoryLink            createAgentMemoryDirective
updateAgentMemoryDirective       deleteAgentMemoryDirective
deleteAgentMemoryReflection
```

The direct retain and session-history command operations remain available for
`light-agent` runtime use. They require a client-credentials token; an
authorization-code token for a logged-in Portal user is rejected by the
command handler even if it carries `portal.w`.
The three update/create operations below are deliberately absent from both the
published service action registry and the Portal until an asynchronous
embedding owner and state machine exist:

```text
updateAgentMemoryUnit            createAgentMemoryReflection
updateAgentMemoryReflection
```

Session-history commands are retained for `light-agent` runtime use only:

```text
createAgentSessionHistory        appendAgentSessionHistory
compactAgentSessionHistory       deleteAgentSessionHistory
```

### Read-model and lifecycle rules

- Every child query uses the full `(host_id, bank_id, resource key)` identity.
- List responses use `agentMemoryBanks`, `agentMemoryDocs`,
  `agentMemoryUnits`, `agentMemoryEntities`, `agentMemoryUnitEntities`,
  `agentMemoryEntityCooccurrences`, `agentMemoryLinks`,
  `agentMemoryDirectives`, `agentMemoryReflections`, or
  `agentSessionHistories` as appropriate.
- Runtime-managed banks are identified structurally through
  `agent_session_t.bank_id` and excluded before default count and pagination.
  A session-ID equality fallback exists only for pre-binding interactive rows.
- Interactive sessions bind their durable `agent_session_t` row after either
  memory store creates the bank. A conflicting binding fails closed.
  Workflow-job sessions are intentionally bankless.
- Session history is bank-scoped, projection-aware, and read-only in the
  Portal. Lists omit message bodies; detail reads are bounded and redact
  credential-like fields.
- Unit/entity associations are hard links without active/version fields.
  Entity co-occurrence is a derived, read-only diagnostic.
- Bank deactivation is rejected while active children or active/closing bound
  interactive sessions exist.
- Embeddings are never returned to the browser.

### Development qualification

Run the source-only contract gate from the workspace root with:

```bash
./implementation/light-portal/scripts/run-hindsight-memory-phase-6-gate.sh --source-only
```

The full local gate installs `light-portal` artifacts first, then tests
`genai-query`, `genai-command`, `portal-view`, `light-agent`, and this book:

```bash
./implementation/light-portal/scripts/run-hindsight-memory-phase-6-gate.sh
```

Pass `--postgres-url jdbc:postgresql://...` to execute the isolated-schema
command-projection-query lifecycle test. After deploying the development
services, set `HINDSIGHT_SMOKE_PORTAL_URL`, `HINDSIGHT_SMOKE_HOST_ID`, and
either `HINDSIGHT_SMOKE_BEARER_TOKEN` or `HINDSIGHT_SMOKE_COOKIE`, explicitly
authorize the disposable lifecycle with `HINDSIGHT_SMOKE_ALLOW_WRITE=true`,
and add `--live`. The live gate creates a uniquely named bank, waits for the
query projection, updates it, verifies isolated lookup, and deactivates it.

## Historical Design Notes

The sections below record the design path that produced the implemented
contract. Where they differ from the Current Portal Contract above, the current
contract is authoritative.

## Recommended Design

Use events for durable memory state, and treat pure caches as rebuildable
projection state.

Recommended ownership:

| Table | Ownership |
| --- | --- |
| `agent_memory_bank_t` | Event-backed aggregate |
| `agent_memory_doc_t` | Event-backed aggregate |
| `agent_memory_unit_t` | Event-backed aggregate |
| `agent_memory_entity_t` | Event-backed aggregate |
| `agent_memory_unit_entity_t` | Event-backed association |
| `agent_memory_link_t` | Event-backed association |
| `agent_memory_directive_t` | Event-backed aggregate |
| `agent_memory_reflection_t` | Event-backed aggregate |
| `agent_session_history_t` | Event-backed aggregate or explicit operational table |
| `agent_memory_entity_cooccur_t` | Derived projection cache by default |

`agent_memory_entity_cooccur_t` should stay projection-owned unless exact
co-occurrence counts are considered business state. It can be rebuilt from
memory units and unit-entity links during replay.

`agent_session_history_t` needs an explicit decision. It contains conversation
content and may be high volume. The recommended first phase is to make it
event-backed for correctness, but keep snapshot export opt-in because it can
contain sensitive user text.

## Event Model

Add explicit event constants and aggregate constants for the Hindsight schema.
Use aggregate ids that include enough context to avoid cross-bank collisions.

Suggested aggregate ids:

```text
AgentMemoryBank:        hostId|bankId
AgentMemoryDoc:         hostId|bankId|docId
AgentMemoryUnit:        hostId|bankId|unitId
AgentMemoryEntity:      hostId|bankId|entityId
AgentMemoryUnitEntity:  hostId|bankId|unitId|entityId
AgentMemoryLink:        hostId|bankId|fromUnitId|toUnitId|linkType
AgentMemoryDirective:   hostId|bankId|directiveId
AgentMemoryReflection:  hostId|bankId|reflectionId
AgentSessionHistory:    hostId|bankId|sessionId
```

Suggested events:

```text
AgentMemoryBankCreatedEvent
AgentMemoryBankUpdatedEvent
AgentMemoryBankDeletedEvent

AgentMemoryDocCreatedEvent
AgentMemoryDocUpdatedEvent
AgentMemoryDocDeletedEvent

AgentMemoryUnitRetainedEvent
AgentMemoryUnitUpdatedEvent
AgentMemoryUnitDeletedEvent

AgentMemoryEntityCreatedEvent
AgentMemoryEntityUpdatedEvent
AgentMemoryEntityDeletedEvent

AgentMemoryUnitEntityLinkedEvent
AgentMemoryUnitEntityUnlinkedEvent

AgentMemoryLinkCreatedEvent
AgentMemoryLinkUpdatedEvent
AgentMemoryLinkDeletedEvent

AgentMemoryDirectiveCreatedEvent
AgentMemoryDirectiveUpdatedEvent
AgentMemoryDirectiveDeletedEvent

AgentMemoryReflectionCreatedEvent
AgentMemoryReflectionUpdatedEvent
AgentMemoryReflectionDeletedEvent

AgentSessionHistoryCreatedEvent
AgentSessionHistoryAppendedEvent
AgentSessionHistoryCompactedEvent
AgentSessionHistoryDeletedEvent
```

Do not reuse the current `AgentMemoryCreatedEvent` name for
`agent_memory_unit_t`. That name already maps to legacy `agent_memory_t` and
would create ambiguity. Either deprecate the legacy event family or keep it
separate with a clear `LegacyAgentMemory` name in documentation and tests.

For session history, avoid `Upserted` as the long-term event name. The
underlying table may use `INSERT ... ON CONFLICT DO UPDATE`, but the event log
should express intent. Use `AgentSessionHistoryCreatedEvent` to start a
session, `AgentSessionHistoryAppendedEvent` to add one or more messages, and
`AgentSessionHistoryCompactedEvent` only when the retained JSON history is
summarized or truncated.

## db-provider Refactor

Add a dedicated Hindsight persistence component, for example:

```text
HindsightMemoryPersistence
HindsightMemoryPersistenceImpl
```

Responsibilities:

- replay Hindsight memory events into the current tables
- preserve `aggregate_version` ordering on every mutable table
- handle `JSONB`, `vector(384)`, and `UUID[]` fields explicitly
- maintain foreign-key order during replay
- rebuild or incrementally update derived `agent_memory_entity_cooccur_t`

Update:

```text
PortalConstants
EventTypeUtil
PortalDbProvider.handleEvent
PortalDbProviderImpl
GlobalSnapshotPersistenceImpl table-to-event overrides
GlobalSnapshotPersistenceImpl skip lists
importer/src/snapshot/table_rules.rs
```

The replay order must satisfy foreign keys:

```text
agent_memory_bank_t
agent_memory_doc_t
agent_memory_unit_t
agent_memory_entity_t
agent_memory_unit_entity_t
agent_memory_link_t
agent_memory_directive_t
agent_memory_reflection_t
agent_session_history_t
```

If `agent_memory_entity_cooccur_t` remains derived, rebuild it after replay or
update it from `AgentMemoryUnitEntityLinkedEvent`.

## light-agent Refactor

Introduce a memory persistence abstraction:

```text
MemoryStore
  DirectPgMemoryStore
  PortalCommandMemoryStore
```

`DirectPgMemoryStore` preserves the current local behavior during migration. It
should be marked as a local/runtime compatibility mode and should not be
considered portable event state.

`PortalCommandMemoryStore` should be the enterprise/default target once the
command path is stable. It sends memory commands through the portal command API
using the agent's service token. This gives memory writes the same validation,
event persistence, replay, and audit behavior as the rest of the portal.

Configuration:

```yaml
memory:
  writeMode: portal-command # portal-command | direct-pg
  retainSessionHistory: true
  exportableMemory: false
```

Initial implementation uses environment variables in `light-agent`:

```text
LIGHT_AGENT_MEMORY_WRITE_MODE=portal-command # portal-command | direct-pg
LIGHT_AGENT_PORTAL_COMMAND_URL=https://...   # optional; defaults from portal config
```

`exportableMemory` should default to `false` until privacy and environment
promotion rules are finalized.

`DirectPgMemoryStore` should be phased out after `PortalCommandMemoryStore` is
stable. Keeping two permanent write paths would reintroduce schema drift and
make local development behave differently from production.

### Read-Your-Writes

The agent currently reads directly from PostgreSQL after direct writes. Moving
writes behind command/event processing creates a read-your-writes requirement.
For Phase 1, the command endpoint should apply the projection synchronously
before returning. This keeps `light-agent` simple and avoids session-local
buffer race conditions.

Other options can be evaluated later if latency requires them:

- agent keeps a small session-local memory buffer until replay catches up
- agent reads through a query endpoint that can merge persisted memory with the
  session-local buffer

## Snapshot Policy

After the event-backed path is implemented:

1. Remove event-backed Hindsight tables from `CONVERSION_SKIP_TABLES`.
2. Keep export opt-in for memory tables because they may contain private user
   content.
3. Keep `agent_memory_entity_cooccur_t` skipped if it remains derived.
4. Add explicit table-to-event overrides for each event-backed Hindsight table.
5. Keep Java `GlobalSnapshotPersistenceImpl` and Rust importer skip lists in
   sync.

Suggested export behavior:

```text
default snapshot export: skip memory content
entityTypes=agent_memory: include event-backed memory tables
entityTypes=agent_session_history: include session history only when explicitly requested
```

Production session history export should be blocked by default even when the
entity type is requested. Allow production export only with an explicit
administrative override and a masking/scrubbing step. Lower environments may
allow opt-in export for debugging, but the export response should record that
memory/session content was included.

## Migration Plan

### Phase 1: Align db-provider With Current Schema

- Add `HindsightMemoryPersistenceImpl`.
- Add constants and event dispatch for the current Hindsight schema.
- Deprecate or rename legacy `AgentMemory` and old `AgentSessionHistory`
  methods that do not match the current tables.
- Add db-provider tests for replaying bank, unit, session history, and one
  association table.

### Phase 2: Add Command APIs

- Add command schemas for Hindsight memory operations.
- Validate `hostId`, `bankId`, and optional `agentDefId` ownership.
- Generate events through the normal command path.
- Add authorization checks so an agent can only write memory for its host and
  allowed bank.

### Phase 3: Refactor light-agent

- Introduce `MemoryStore`.
- Move direct SQL writes behind `DirectPgMemoryStore`.
- Add `PortalCommandMemoryStore`.
- Default local development to direct mode if needed, but document it as
  non-portable.
- Deprecate direct mode after the command path is stable and make
  `PortalCommandMemoryStore` the only supported production write path.
- Validate service-token `host`, `sid`, and `env` before writing through
  command APIs.

### Phase 4: Snapshot And Import

- Add table-to-event overrides and conversion tests.
- Remove event-backed tables from conversion skip lists.
- Keep export of memory content opt-in.
- Update Rust importer table rules and dependency graph.
- Add replay-order tests for the FK chain.

### Phase 5: Backfill Existing Rows

- Build a one-time backfill tool that reads existing direct-write rows and
  emits synthetic Hindsight events in dependency order.
- Preserve `aggregate_version` where possible.
- Mark backfilled events with metadata such as:

```json
{
  "source": "agent-memory-backfill",
  "backfilled": true
}
```

Do not remove skip rules for production exports until backfill has been run or
the deployment has no legacy direct-write rows.

## Testing

Add focused tests:

- `GlobalSnapshotPersistenceImplTest`: memory tables remain skipped before
  event support; event-backed tables are included after the event-backed path
  is enabled.
- db-provider replay tests for each Hindsight event family.
- `EventTypeUtil` aggregate-id tests.
- Rust importer table-rule parity tests.
- light-agent `MemoryStore` tests using a mock command client.
- end-to-end test: `light-agent` retain memory -> command event -> replay ->
  recall reads the memory.

## Resolved Decisions

- `agent_session_history_t` is exportable only as an explicit opt-in. Production
  export is blocked unless an administrative override and data masking/scrubbing
  step are provided.
- `agent_memory_entity_cooccur_t` remains derived. Store the underlying facts
  as events and rebuild or update co-occurrence counts as projection state.
- Direct PostgreSQL writes are a migration bridge only. They should be removed
  after the command-backed memory path is stable.
- Memory vectors should not be stored in events. Events store source text,
  metadata, and embedding model metadata when needed. Projection rebuilds should
  generate vectors, preferably through the embedding task pipeline, so the
  platform can re-embed after model upgrades.
