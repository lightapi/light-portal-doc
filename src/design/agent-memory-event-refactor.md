# Agent Memory Event Refactor

## Problem

`GlobalSnapshotPersistenceImpl` currently skips these Hindsight memory tables
for both snapshot export and snapshot-to-event conversion:

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

The skip is intentional for the current implementation. These tables are not
currently populated from portal events as the source of truth. They are runtime
state written directly by `light-agent` or memory client code, so exporting them
as portable portal domain state or converting them into generic created events
would be unsafe.

The current implementation also has a schema drift risk:

- `light-agent` writes directly to the current Hindsight tables:
  `agent_memory_bank_t`, `agent_session_history_t`, and
  `agent_memory_unit_t`.
- `light-fabric/crates/hindsight-client` writes directly to
  `agent_memory_unit_t`.
- `light-portal` Java db-provider has event replay methods for
  `AgentSessionHistory` and `AgentMemory`, but those methods do not cover the
  current Hindsight table family. `AgentMemory` writes `agent_memory_t`, and
  `AgentSessionHistory` expects the older `session_history_id`, `process_id`,
  `role`, and `content` shape rather than the current
  `(host_id, bank_id, session_id, messages)` schema.
- The Rust importer also skips the same `agent_memory_*` and
  `agent_session_history_t` tables, so the Java and Rust conversion paths are
  aligned around the current non-event-backed behavior.

## Goal

Refactor the agent memory persistence path so that memory state has a clear
owner:

```text
command/event path -> event_store_t -> db-provider replay -> Hindsight tables
```

Once that contract is in place, snapshot export and conversion can safely
include the event-backed memory state where appropriate.

## Non-Goals

- Do not promote existing direct-write memory rows into snapshots before a
  backfill/migration event strategy exists.
- Do not convert derived caches into authoritative state unless a product
  decision requires exact cache promotion.
- Do not require every chat token or partial model response to become an event.
- Do not remove the current direct PostgreSQL path until `light-agent` has a
  stable command-backed memory store and operational validation.

## Current State

### Snapshot Export And Conversion

`GlobalSnapshotPersistenceImpl` excludes the memory tables from export and
conversion. This prevents two bad outcomes:

- exporting user/session memory into another environment without an explicit
  promotion contract
- converting rows into events that no replay handler can faithfully apply

The Rust importer has the same conversion skip list. Any future change must
update both Java and Rust paths.

### light-agent

`light-agent` currently owns some memory writes directly:

```text
ensure_session_memory_bank
  INSERT INTO agent_memory_bank_t

session history persistence
  INSERT INTO agent_session_history_t ... ON CONFLICT DO UPDATE

hindsight retain
  INSERT INTO agent_memory_unit_t
```

This is operationally simple and gives the agent read-your-writes behavior, but
it bypasses portal command validation, event persistence, replay, and snapshot
conversion.

### Java db-provider

The Java db-provider already has event handler plumbing for many GenAI tables.
For memory, however, the existing methods are not aligned with the Hindsight
schema:

```text
AgentMemoryCreatedEvent -> agent_memory_t
AgentSessionHistoryCreatedEvent -> old session-history row shape
```

There are no current event handlers for:

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
```

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
