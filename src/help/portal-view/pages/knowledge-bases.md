# Knowledge Bases

Use `/app/genai/KnowledgeBases` to configure governed retrieval from approved
content. The page separates build limits, retrieval behavior, and embedding
identity because they have different owners and lifecycles.

## Recommended setup sequence

1. Select the target environment and create or choose an ingestion policy.
2. Create or choose a retrieval profile.
3. A platform administrator publishes an eligible embedding Alias and creates
   its immutable embedding profile.
4. Create the tenant Knowledge Base and assign the embedding profile.
5. Open the Knowledge Base, add sources pinned to reviewed commits, and sync.
6. Inspect the completed run and documents, then promote a READY generation.
7. Bind an Agent and select the retrieval profile that should govern searches.
8. Test the authorized `light-knowledge` REST or MCP endpoint. The Portal
   Retrieval Playground is not released yet.

## Knowledge Bases section

This table lists the logical collections of content. **Desired state** is the
administrator's requested lifecycle state. **Effective state** is the worker
projection. **Active BASE** is the immutable generation currently visible to
retrieval; a newly built READY candidate is not searchable until promotion.

Choose **Create tenant KB**, give it a stable name and description, and select
an active embedding profile or assign one later under **Settings**. Opening the
name enters the workspace for sources, builds, bindings, and diagnostics.

## Ingestion policies section

An ingestion policy supplies hard ceilings for source processing: documents,
chunks, source and stored bytes, embedding tokens, billed cost, wall time, and
concurrency. A zero spend ceiling is valid for a genuinely free embedding
route; the gateway still rejects any request whose calculated billed cost is
greater than zero.

- A **global policy** is reusable by every tenant and is maintained by a
  platform Knowledge Base administrator.
- A **tenant policy** belongs to the selected host and is visible only there.

Use **Create policy** for a new limit set. Portal generates the UUID; sources
select policies by name. You may maintain several policies for different
corpus sizes. Deactivation is refused while a non-deleted source refers to the
policy. An inactive policy remains visible and can be edited to reactivate it.

## Retrieval profiles section

A retrieval profile defines bounded query behavior independently of how the
index was built. Agent bindings select one active profile. Global profiles are
reusable defaults; tenant profiles support tenant-specific behavior.

The fields mean:

- **Strategy:** lexical, vector, hybrid, or graph-assisted retrieval.
- **Lexical/vector candidates:** maximum candidate pools gathered before
  fusion. **Top K** limits the final results.
- **Token budget:** maximum retrieved context supplied downstream.
- **Failure policy:** fail the request, or return safe partial results when an
  optional retrieval component fails.
- **Maximum Knowledge Bases:** upper bound for multi-base retrieval, from one
  through four.
- **Lexical evidence required:** requires lexical support in the result set.
- **Segment candidate multiplier:** bounds candidate expansion across immutable
  BASE and DELTA segments.
- **Context expansion before/after:** includes bounded neighboring passages.

RRF is the fixed fusion method. Use **Create retrieval profile**, select tenant
or global ownership, and start with **Balanced hybrid** unless the use case
requires different bounds. Portal generates the UUID. Deactivation is refused
while an active Agent binding uses the profile.

## Embedding profiles section

An embedding profile freezes the vector-space identity used to build and query
an index: protected public Alias, space ID and revision, dimension,
normalization, distance metric, and input transforms. It does not duplicate
live model conformance or lifecycle status.

Only a platform administrator creates these global profiles. In **Create global
embedding profile**, select an eligible public Alias; Portal derives the Alias
owner, public Alias ID, expected space, and qualification digest. Do not invent
the digest or UUID. Assign the profile when creating a Knowledge Base or later
under **Settings**.

## Knowledge Base workspace

### Overview

Shows desired/effective state, active generation, pointer version, source
count, and document count. Use it as a quick readiness summary.

### Sources

Creates and syncs approved content inputs. For Git/Markdown:

- **Display name:** a short operator-facing label.
- **Approved repository URI:** an HTTPS clone URI, for example
  `https://github.com/networknt/light-fabric.git`.
- **Immutable commit:** the full 40- or 64-character commit SHA. Branches and
  tags move, so they are not reproducible source identities.
- **Ingestion policy:** an active global or tenant policy selected by name.

A mixed source-and-documentation repository is allowed. The connector applies
the configured Markdown include/exclude policy, ignores other file types and
symlinks, does not execute hooks, and rejects submodules. The default Portal
form includes `**/*.md` and an empty exclude list. Click **Sync** after creating
or updating a source. The worker resolves all active source and policy records
from the database and builds one complete BASE for the Knowledge Base.

### Documents

Lists immutable document versions written by successful builds. An empty-state
message before the first completed build is expected.

### Sync Runs

Tracks accepted, running, succeeded, failed, paused-budget, and cancelled runs.
The page polls while a run is non-terminal. For a failure, use the displayed
error code and message rather than clicking Sync repeatedly; fix the underlying
configuration and submit a new sync.

### Index Generations

Shows immutable generations and operational evidence. A successful build
creates a READY candidate. Review it, then choose **Promote for retrieval** to
atomically update the active pointer. Rebuild, compaction, embedding migration,
rollback, and retention controls also appear here when applicable.

### Incremental

Displays upload, classified-change, stable-passage-anchor, compaction, and
anti-entropy diagnostics. These records explain how later DELTA work relates
to the BASE without exposing source text.

### Agent Bindings

Connects an Agent to this Knowledge Base. Enter the Agent UUID, choose an active
retrieval profile by name, and decide whether missing Knowledge evidence must
fail the turn. The service validates tenant ownership and profile activity; a
foreign or inactive profile cannot be bound.

### Access Policy

Shows source trust, ACL reconciliation, freshness, transition, and connector
evidence. Use **Simulate access** with a normalized USER, GROUP, or ORGANIZATION
subject before relying on mirrored source permissions. Retrieval fails closed
when permission evidence is stale, incomplete, ambiguous, or unresolved.

### Retrieval Playground

The Portal retrieval-test workflow is currently not released, so the question
field is intentionally disabled. Test the promoted generation through the
authorized `light-knowledge` REST `/v1/knowledge/retrieve` endpoint or MCP
`knowledge.search` tool and review its audit evidence.

### Quality

Collects generation and production evidence used to judge promotion,
migration, rollback, backup, anti-entropy, and purge behavior. Provider latency
and retrieval-quality qualification remain explicit operational gates.

### Settings

Assigns the desired immutable embedding profile and manages Knowledge Base
lifecycle. Changing embedding space requires a governed migration rather than
silently rebuilding into an incompatible vector space. Physical purge is not
released; deactivation remains available.

## Authentication and errors

Knowledge queries require `portal.r`; mutations require `portal.w`. The Portal
does not use `portal.knowledge.r` or `portal.knowledge.w`. JWT security runs
before handlers, so a valid token without the action scope produces a
structured `AUTH_TOKEN_SCOPE_MISMATCH` response that the UI displays.

For **Knowledge Base operation failed**, inspect the returned code and the
gateway/service logs. Common causes are a missing access-control route, an old
GenAI command/query deployment that lacks a new handler, an unapplied database
patch, an unavailable service, or an object outside the selected tenant.
