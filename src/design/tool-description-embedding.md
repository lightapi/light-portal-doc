# Tool Description Embedding Population

## Problem

The GenAI Tool page lets users update `tool_t.description` through the
`updateTool` form. Endpoint-backed tools are also projected into `tool_t` when
`api_endpoint_t` is populated from OpenAPI, MCP `tools/list`, or LightAPI
Description input.

The schema already has `tool_t.description_embedding VECTOR(384)`, but the
current write paths only populate the plain text description:

- `ApiServicePersistenceImpl.syncEndpointToolProjections(...)` inserts or
  updates endpoint-backed `tool_t` rows from `api_endpoint_t`.
- `GenAIPersistenceImpl.createTool(...)` inserts manually authored tools.
- `GenAIPersistenceImpl.updateTool(...)` updates the Tool page edit form.
- `genai-command` create/update tool contracts do not accept an embedding
  field, and the Portal UI should not expose raw vectors to users.

As a result, new endpoint-backed tool rows start with a null
`description_embedding`, and user edits can leave any future vector stale unless
the write path marks it for regeneration.

## Goals

- Populate `tool_t.description_embedding` for endpoint-backed and manually
  authored tools.
- Regenerate the embedding whenever the effective embedding source text changes.
- Keep Tool create/update latency independent from external embedding provider
  latency.
- Avoid trusting browser-submitted vectors.
- Preserve keyword search and normal CRUD behavior when embedding generation is
  disabled or temporarily failing.
- Keep the first implementation aligned with the existing `VECTOR(384)` schema.

## Non-Goals

- Do not require every tool to have an embedding before it can be listed,
  edited, linked to a skill, or executed through the gateway.
- Do not move MCP execution into portal-query or the controller.
- Do not store API keys or provider secrets in tool metadata.
- Do not expose raw embedding vectors in the Tool page by default.

## Recommended Design

Use asynchronous server-side embedding generation. Tool writes should save the
description immediately, mark the embedding stale or pending, and record the
embedding task in the same database transaction as the `tool_t` update. A worker
then picks up committed tasks, generates a 384-dimensional vector from a
normalized source string, and updates `tool_t.description_embedding` only if the
tool row still matches the source that was embedded.

For phase 1, this should use a transactional work table or transactional outbox
pattern. Do not call the external embedding provider inside the command
transaction, but do insert or update the work item before that transaction
commits. If a later implementation publishes tasks to Kafka or another queue,
the database transaction should still write an outbox row first, and a
dispatcher should publish after commit. This avoids a failure mode where the
tool row commits successfully but the embedding task is never queued.

This keeps command handling reliable and makes the embedding field a derived
read-model value, not user-authored command input.

```text
API version import/update
  -> api_endpoint_t rows
  -> endpoint-backed tool_t projection
  -> upsert embedding_task_t in the same transaction

Tool create/update form
  -> ToolCreatedEvent or ToolUpdatedEvent
  -> tool_t row update
  -> upsert embedding_task_t in the same transaction

embedding worker
  -> poll committed pending tasks
  -> load current tool row
  -> build source text
  -> call configured embedding provider
  -> update tool_t.description_embedding with compare-and-set guard
```

## Embedding Source Text

The vector should be generated from stable semantic fields, not audit fields or
IDs. The default source can be:

```text
name: <tool_t.name>
description: <tool_t.description>
endpoint: <tool_t.api_method> <tool_t.api_endpoint>
domain: <tool_t.routing_domain>
namespace: <tool_t.semantic_namespace>
protocol: <tool_t.source_protocol>
personas: <tool_t.target_personas>
```

For endpoint-backed tools, the projection can enrich the source with
`api_endpoint_t.endpoint_desc` and semantic keywords from
`api_endpoint_t.tool_metadata.routing.semanticKeywords` when available. The
LLM-facing description remains `tool_t.description`; enrichment only improves
semantic retrieval.

## Staleness Tracking

The current table only has the vector. To make regeneration safe and auditable,
add lightweight metadata beside it:

| Column | Purpose |
| --- | --- |
| `description_embedding_model` | Provider/model that produced the vector. |
| `description_embedding_dimension` | Expected to be `384` for the current schema. |
| `description_embedding_source_hash` | SHA-256 of the normalized source text. |
| `description_embedding_ts` | Generation timestamp. |
| `description_embedding_status` | `pending`, `ready`, `failed`, `disabled`, or `blank`. |
| `description_embedding_error` | Short last error for diagnostics. |

If the first implementation avoids schema expansion, it should at least set
`description_embedding = NULL` whenever the description or semantic routing
fields change. That prevents stale vector search, but it gives weaker
operational visibility than explicit status and source-hash columns.

The metadata can live in `tool_t` beside the vector for simple read-heavy
queries. If row width becomes a concern, move the vector and metadata to a
1:1 table such as `tool_embedding_t` or a generic `entity_embedding_t`; keep the
same source-hash and status contract either way. The work table should not be
the only durable location for ready-state metadata because completed work rows
may be retried, compacted, or purged.

## Write Path Hooks

The persistence hooks should be narrow:

1. When `syncEndpointToolProjections(...)` inserts or updates a tool row, compute
   the source hash from the projected values. If it differs from the stored hash,
   store the new `description_embedding_source_hash`, mark embedding status
   `pending`, and upsert an embedding task in the same transaction.
2. When `createTool(...)` writes a new row, store the source hash, mark the
   embedding `pending`, and upsert an embedding task in the same transaction
   unless the normalized source text is blank. For blank source text, clear the
   vector and mark the status `blank` without creating a task.
3. When `updateTool(...)` changes description, name, endpoint, routing domain,
   namespace, source protocol, target personas, endpoint description, or
   semantic keywords, store the new source hash, mark the embedding `pending`,
   and upsert an embedding task in the same transaction.
4. When a tool is deactivated, no embedding work is needed. Existing vectors can
   remain stored, but vector queries must filter `active = TRUE`.

The command contract should not add a `descriptionEmbedding` property. If a
future admin API needs a manual vector load, it should be a separate privileged
maintenance action, not part of the normal Tool form.

Embedding writes are read-model maintenance, not user-authored tool changes. The
preferred implementation should not emit a normal `ToolUpdatedEvent` and should
not advance the business aggregate version used for user edits. If the local
persistence framework requires a row-level version for every physical update,
store it separately on the embedding row or task row so embedding maintenance
does not interfere with Tool form optimistic concurrency.

## Endpoint Sync And Manual Overrides

Endpoint-backed tools need an explicit description ownership contract. Without
one, a user can improve the Tool page description and later lose the edit when
the API version is synced again from OpenAPI, MCP `tools/list`, or LightAPI
Description input.

Recommended behavior:

- `api_endpoint_t` remains the source of imported endpoint metadata.
- `tool_t.description` is the user-facing LLM description.
- When endpoint projection first creates a tool, copy the endpoint description
  into `tool_t.description`.
- When a user edits `tool_t.description` for an endpoint-backed tool, mark the
  tool description as a manual override.
- Later endpoint syncs should update generated endpoint fields and
  `api_endpoint_t.endpoint_desc`, but should not overwrite
  `tool_t.description` while the manual override is active.
- Provide a later admin action to reset the description to the imported source.

Suggested columns:

| Column | Purpose |
| --- | --- |
| `description_source` | `endpoint_sync`, `manual`, or another source label. |
| `description_manual_override` | Boolean guard used by endpoint sync. |
| `description_override_ts` | When the manual override was created. |
| `description_override_user` | Who last changed the description manually. |

If a deployment wants endpoint sync to be the absolute source of truth, the Tool
page must make that clear before allowing edits, because later syncs will
overwrite user-authored descriptions. The default portal behavior should favor
manual overrides to avoid surprising users.

## Work Queue Options

Three implementation options are viable:

| Option | Pros | Cons |
| --- | --- | --- |
| Polling backfill job | Smallest first step; scans active tools with null or stale embeddings. | Embeddings are eventually populated but not immediately after each edit. |
| Database work table | Reliable retries, status, and batching without depending on Kafka. | Adds one table and worker lifecycle. |
| Event-driven worker | Fits event-driven portal architecture and reacts immediately to tool events. | Requires one more event/consumer contract and careful replay behavior. |

Recommended phase 1 is a database work table or polling worker. It is simpler
than putting provider calls inside the command request and safer than calling an
external model from inside a database transaction.

Use a generic work table from the start so the same worker can later populate
`skill_t.description_embedding` and other platform embeddings without adding one
queue per entity type. The table can be named `embedding_task_t`.

| Column | Purpose |
| --- | --- |
| `host_id` | Tenant boundary. |
| `task_id` | Task identity for retry and diagnostics. |
| `entity_type` | `tool`, `skill`, `agent`, or another supported embedding target. |
| `entity_id` | Target row ID, such as `tool_id` or `skill_id`. |
| `source_table` | Optional source table hint, such as `tool_t`. |
| `source_hash` | Hash of the source text to embed. |
| `source_version` | Optional row version observed when queued; useful for diagnostics but not required for the final CAS guard. |
| `status` | `pending`, `running`, `ready`, `failed`. |
| `attempt_count` | Retry count. |
| `next_attempt_ts` | Backoff control. |
| `last_error` | Short diagnostic text. |
| `update_ts` | Queue row update time. |

Use a unique key such as `(host_id, entity_type, entity_id, source_hash)` so the
transactional upsert is idempotent.

The worker should claim tasks with row locking, for example
`FOR UPDATE SKIP LOCKED`, so multiple workers can run safely. The final tool
update should use the source hash as the primary compare-and-set guard:

```sql
UPDATE tool_t
SET description_embedding = ?,
    description_embedding_model = ?,
    description_embedding_dimension = 384,
    description_embedding_ts = CURRENT_TIMESTAMP,
    description_embedding_status = 'ready',
    description_embedding_error = NULL
WHERE host_id = ?
  AND tool_id = ?
  AND active = TRUE
  AND description_embedding_source_hash = ?;
```

If the row no longer matches, the worker should drop that result and let the
newer pending job win. This prevents stale vectors from overwriting a newer
description.

Avoid using `aggregate_version` as a hard CAS requirement unless it is truly
needed for local event-sourcing rules. The version may change because of fields
that are not part of the embedding source, causing spurious worker failures even
when the source hash is still valid. If `aggregate_version` must be checked, a
CAS failure should reload the row; if the stored source hash is unchanged, retry
the embedding update using the current version. If the source hash changed, drop
the stale result.

## Embedding Provider

Add a small server-side provider abstraction:

```text
EmbeddingProvider.embed(model, dimension, inputText) -> float[384]
```

Configuration should include:

| Setting | Purpose |
| --- | --- |
| `embedding.provider` | `openai-compatible`, `local-http`, or `disabled`. |
| `embedding.model` | Provider model name. |
| `embedding.dimension` | Must match `384` until the schema is migrated. |
| `embedding.batchSize` | Worker batch size. |
| `embedding.timeoutMs` | Provider call timeout. |
| `embedding.maxRetries` | Retry limit before `failed`. |

For hosted providers, configure a model that can emit 384 dimensions, such as an
OpenAI-compatible embedding endpoint with an explicit dimensions parameter. For
restricted deployments, use a local embedding service that emits the same
dimension.

## Search And Indexing

Vector search should only use ready embeddings:

```sql
WHERE host_id = ?
  AND active = TRUE
  AND description_embedding IS NOT NULL
  AND description_embedding_status = 'ready'
ORDER BY description_embedding <=> ?
```

Add a pgvector index when catalog size makes sequential vector scans too slow:

```sql
CREATE INDEX idx_tool_description_embedding
    ON tool_t USING hnsw (description_embedding vector_cosine_ops)
    WHERE active = TRUE AND description_embedding IS NOT NULL;
```

`genai-query` can continue keyword search while embeddings are being populated.
When vector ranking is enabled, combine vector distance with existing macro
filters such as host, active flag, assigned skill, routing domain, semantic
namespace, sensitivity tier, source protocol, and `semantic_weight`.

Vector nearest-neighbor search should run in `genai-query` against PostgreSQL
with pgvector, not inside the agent's local catalog cache. Database-side search
scales better because it can apply tenant, active-state, RBAC, assigned-skill,
domain, and sensitivity filters before returning a small top-K result. The agent
can still keep a lightweight local cache for fallback keyword matching and
gateway intersection, but it should not need to download every catalog vector to
rank tools.

## Backfill

Existing rows need a one-time backfill:

1. Scan active tools with a non-blank description and null or stale embedding.
2. Queue embedding work in batches per host.
3. Generate and persist vectors with retry/backoff.
4. Report counts: total tools, ready, pending, failed, disabled, blank source.

Backfill should be restartable and idempotent. It should not block portal
startup or the Tool page.

## Portal UI

The first UI change should be optional diagnostics, not vector editing:

- Do not show `description_embedding` in create/update forms.
- Optionally show read-only status columns on the Tool page:
  `Embedding Status`, `Embedding Model`, and `Embedding Updated`.
- After a user updates the description, show the saved description immediately.
  The embedding can move from `pending` to `ready` asynchronously.
- Add an admin action later for "Refresh Embedding" if operators need manual
  repair.

## Failure Behavior

- If embedding is disabled, save descriptions normally and mark status
  `disabled`.
- If provider calls fail, keep the tool active and searchable by keyword.
- Failed rows should retry with backoff and surface diagnostics.
- A stale worker result must not overwrite a newer description's embedding.
- If the source text is blank, clear the embedding and mark the status `disabled`
  or `blank`.

## Implementation Phases

### Phase 1: Safe Population

- Add embedding metadata columns to `tool_t`, or add a 1:1 embedding table, and
  add a generic `embedding_task_t` for queued work.
- Add description manual-override metadata for endpoint-backed tools.
- Add write-path hooks in endpoint projection and Tool create/update
  persistence. The hooks must upsert embedding work in the same database
  transaction as the tool row change.
- Add a polling or queue-backed embedding worker.
- Add a backfill command for existing active tools.
- Add focused tests that endpoint projection and `updateTool` mark embeddings
  pending when descriptions change.

### Phase 2: Diagnostics

- Expose read-only embedding status through `getTool` and `getFreshTool`.
- Add Tool page status columns or a diagnostics view.
- Add retry and refresh operations for failed rows.

### Phase 3: Retrieval

- Add the pgvector index.
- Add vector ranking to `genai-query` or the effective catalog path.
- Combine vector score with keyword score, macro filters, and
  `semantic_weight`.
- Keep gateway `tools/list` intersection as the runtime executability check.

## Design Decisions

- Use a transactional work table or outbox for phase 1. The provider call is
  asynchronous, but task creation must be committed atomically with the tool row
  change.
- Use source hash as the primary stale-result guard. Treat `aggregate_version`
  as diagnostic or optional unless local persistence rules require it.
- Make the task table generic with `entity_type` and `entity_id`, so skills and
  future entities can share the same worker.
- Preserve manual Tool page description edits with a manual override flag for
  endpoint-backed tools.
- Reuse the same worker for `skill_t.description_embedding` when skill semantic
  search is enabled. The task shape should already support `entity_type =
  'skill'`.
- Run vector ranking in `genai-query` with pgvector and return top-K results to
  the agent. Keep local agent ranking as a fallback or small-cache optimization,
  not the primary scalable path.
