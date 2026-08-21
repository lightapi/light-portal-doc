# Global And Tenant Knowledge Bases For Shared Agent Retrieval

## Status

Proposed design for discussion.

## Decision Summary

Add Knowledge Bases as a Light Portal resource with two ownership scopes:

- knowledge_base_t.host_id IS NULL represents a platform-owned global
  Knowledge Base that is discoverable and bindable by every tenant;
- knowledge_base_t.host_id = the trusted host represents a Knowledge Base
  owned and administered by that tenant.

Do not add a common flag. Global scope comes only from the nullable host_id
defined by
[Global And Tenant Entity Scope](global-tenant-entity-scope.md).

A global Knowledge Base is not automatically queried by every Agent. Each
tenant uses an explicit host-local Agent binding to enable it. This separates
platform ownership and global visibility from tenant enablement and avoids
silently changing every Agent's context.

Keep the product and administration experience in Light Portal, but run
indexing, ingestion, and retrieval in one independently deployable
`light-knowledge` service under `light-fabric/apps`. Build its API on the
`light-axum` framework and ship one long-running container by default. Inside
that process, supervise the retrieval API, Config Server configuration loader,
lightweight job scheduler, and on-demand build tasks as separate lifecycle
components. Retain the build engine as reusable library and
CLI/Kubernetes-Job functionality for exceptional heavy or offline work, but do
not require an idle worker deployment in the normal topology.

Keep authoritative Knowledge Base administration in the Config Server
PostgreSQL database. Light Portal projects committed control-plane events,
compiles a least-privilege Knowledge audience document, and publishes it as an
immutable Config Server snapshot. `light-knowledge` loads and validates that
snapshot at startup and on explicit refresh, then atomically materializes its
content-minimized published control replicas in the Knowledge database; it does
not consume Portal events or query Portal projection tables. All high-volume
Knowledge data-plane state
resides in a logically separate `knowledge` database. A deployment may place
both logical databases in one PostgreSQL instance for a small installation or
use separate instances for stronger isolation, but Light Knowledge still uses
the Config Server API rather than a Config Server database connection.

Every retrieval request pins one immutable applied configuration snapshot, then
reads its version-matched published control replicas for Knowledge Base state,
source state, Agent bindings, retrieval-profile selection, and strategy
qualification together with the active generation, ACL revisions, and
candidates from one transactionally consistent Knowledge-database snapshot.
Security-removing control-plane actions do not report effective completion until
the required Light Knowledge instances acknowledge the new Config Server
snapshot. An expired or otherwise invalid applied policy fails closed.

Use a generally available PostgreSQL release with pgvector as the initial
metadata, lexical-search, vector, authorization, graph-projection, and job-state
database. PostgreSQL 19 SQL/PGQ is a future qualification target after general
availability; it exposes relational tables as read-only property graphs and is
not a native graph-storage engine. Store original binary documents in object
storage. Do not introduce a separate vector database, graph database, or Turso
backend for the first release. Turso remains a possible later embedded or
local-first storage profile only after it passes the same authorization,
transaction, concurrency, recovery, vector-recall, and operational gates.

Treat embedding models as replaceable dependencies. Persist normalized document
versions and immutable chunk artifacts independently from embedding vectors and
generation-specific search projections. A model upgrade builds an isolated
candidate vector space from those reusable artifacts, catches up concurrent
source changes, passes retrieval-quality and authorization gates, and changes
the active generation only through an atomic promotion. Retain the predecessor
generation for a bounded rollback window; never mix incompatible vectors in one
similarity index or rewrite a promoted generation in place.

Treat routine source additions, edits, deletions, and permission changes as
incremental operations. A logical index generation may reuse an immutable base
segment plus ordered immutable delta segments instead of copying or rebuilding
the complete physical index. Each validated update publishes a new generation
manifest atomically; periodic compaction replaces accumulated deltas with a new
base only when measured size, latency, or dead-record thresholds require it.

Implement hybrid RAG first:

1. filter by trusted consumer tenant, effective Knowledge Base visibility,
   active Agent binding, source state, and document authorization;
2. generate lexical and vector candidates;
3. fuse the candidate lists;
4. optionally rerank the small fused set after a canonical rerank operation is
   separately designed and qualified;
5. return bounded passages with stable citations.

Keep the retrieval contract framework-independent. External RAG projects and
papers can inform evaluation hypotheses, but the Portal resource model,
authorization boundary, canonical data, APIs, and lifecycle remain owned by
Light Portal. Do not expose or copy another framework's workspace, schema, or
query contract into tenant-facing APIs.

Do not implement GraphRAG in the first release. Add it only as an optional
derived index and retrieval strategy when a measured evaluation set shows
that relationship-heavy or corpus-wide questions are not served adequately by
hybrid RAG. A graph index never becomes the source of truth or an authorization
boundary.

If a graph-assisted strategy is qualified later, prefer a bounded relational
path planner over returning every neighbor or complete community by default.
The planner operates only on authorized evidence contributions, prunes noisy or
low-value traversal, and preserves useful relationship ordering as optional
evidence structure. Canonical chunks and citations remain the returned evidence;
a path score or generated graph description never becomes factual authority.

Keep Knowledge Bases separate from Hindsight Agent Memory. Hindsight stores
session and Agent experience; a Knowledge Base stores governed source material.
They may reuse common embedding, authorization, audit, and job-processing
primitives, but they must not share aggregate identities, lifecycle rules, or
Portal workspaces.

Make the embedding-space registry, deployment-conformance rules, and protected
gateway workload-lane machinery shared platform components. Knowledge Base,
Hindsight, and tool-description embedding remain separate consumers with their
own declared spaces, policies, quotas, and lifecycle; they must not implement
three drifting copies of the compatibility contract.

## Context

The current [Agent Memory Event Refactor](../agent-memory-event-refactor.md)
implements a bank-first Hindsight workspace and the following runtime-oriented
data:

- documents, memory units, entities, co-occurrences, links, directives, and
  reflections;
- session history associated with interactive Agent execution;
- a direct PostgreSQL runtime path and an event-backed Portal administration
  path;
- a fixed-dimension vector index for memory units.

That schema is useful evidence that PostgreSQL and pgvector already fit the
platform, but it is not a Knowledge Base implementation:

- a Hindsight bank can be bound to one Agent or user, while one Knowledge Base
  must be reusable by many Agents;
- current memory document records do not model connector cursors, external
  versions, source permissions, parse artifacts, or index generations;
- current memory recall is vector-oriented and does not provide the lexical
  fusion, citation, source synchronization, or principal-level ACL contract
  required for enterprise documents;
- Confluence and SharePoint content has an external lifecycle and an
  authorization model that must remain visible after ingestion;
- source documents can contain instructions that are untrusted from the
  Agent's perspective.

The workflow schema already has a data-store concept for RAG. Knowledge Bases
should become the concrete Light Portal resource referenced by that concept
rather than creating workflow-local copies of documents.

## Goals

- Let each tenant create and administer multiple Knowledge Bases.
- Let platform administrators create global Knowledge Bases that every tenant
  can discover and bind without copying their documents.
- Let a Knowledge Base be bound to zero or more Agents and workflows.
- Ingest uploaded files, Confluence content, and SharePoint content
  incrementally.
- Enforce tenant, Agent-binding, source, and end-user authorization before any
  content is returned.
- Provide useful hybrid retrieval with citations and deterministic version
  evidence.
- Keep ingestion failures and source staleness visible and recoverable.
- Support asynchronous parsing, chunking, embedding, ACL refresh, and
  reindexing.
- Support planned embedding-model migrations with cost estimation, resumable
  backfill, source-delta catch-up, isolated evaluation, atomic promotion, and
  bounded rollback without interrupting retrieval from the active generation.
- Give Portal administrators a retrieval playground and quality evidence
  before enabling a Knowledge Base for production Agents.
- Preserve a path to additional retrieval engines and GraphRAG without making
  them first-release dependencies.
- Let retrieval strategies evolve behind one authorization, evidence,
  citation, and audit contract without adopting an external framework's public
  API.
- Apply routine source changes by rebuilding only artifacts whose versioned
  inputs or contracts changed, while keeping deletion, permission, metadata,
  citation, and retrieval behavior transactionally consistent.

## Non-Goals

- A Knowledge Base is not conversational memory or session history.
- It is not a general file-authoring or content-management system.
- The first release does not generate answers. It retrieves evidence; the
  Agent or workflow owns answer generation. A future qualified reranker may
  score candidates without becoming an answer-generation path.
- Answer-faithfulness and no-answer evaluation use a fixed, version-pinned
  external answer model in the evaluation harness. That model is outside the
  knowledge service and its identity is recorded with the evaluation result.
- The first release does not provide GraphRAG, autonomous ontology generation,
  or a separate graph database.
- The design does not require, embed, fork, or reproduce an external RAG
  framework. External implementations are comparative references only.
- It does not copy provider credentials or long-lived source tokens into Portal
  tables or browser responses.
- It does not turn every document, chunk, embedding, or sync progress update
  into a Portal business event.
- It does not let a tenant publish a tenant-owned Knowledge Base globally by
  setting a common flag. A global Knowledge Base is a separate platform-owned
  scope with host_id IS NULL.
- Global visibility does not mean anonymous access, automatic Agent enablement,
  or permission to mutate platform-owned sources.
- Phase 1a does not perform OCR, image understanding, audio/video transcription,
  or spreadsheet-specific semantic extraction. Unsupported or scanned-only
  content is reported explicitly rather than silently indexed as empty text.

## Terminology

| Term | Meaning |
| --- | --- |
| Knowledge Base | Logical corpus, retrieval policy, and active index generation with either global or tenant ownership. |
| Global Knowledge Base | Platform-owned Knowledge Base whose host_id is null and which is visible and bindable by every tenant. |
| Tenant Knowledge Base | Knowledge Base whose non-null host_id identifies its owning tenant. |
| Consumer host | Tenant whose Agent is using a tenant or global Knowledge Base. It can differ from the owner scope of a global Knowledge Base. |
| Effective catalog | Global Knowledge Bases combined with Knowledge Bases owned by the trusted consumer host. |
| Projection replay | Reapplication of authoritative administrative history to rebuild projections in the same environment, with external effects suppressed. |
| Logical environment publication | Creation of equivalent desired state in another environment or ownership scope through new target commands and target-local identities. |
| Physical restore | Recovery of the same environment from compatible Portal-history, Knowledge PostgreSQL, and versioned object-store checkpoints while preserving identities. |
| Portability manifest | Versioned publication package containing a canonical desired-state payload plus a signed export envelope; it is not an event stream or physical backup. |
| Source | One configured input such as a Confluence space, SharePoint site or library, or upload collection. |
| Source object | Provider object identified by a stable external identifier, such as a Confluence page or SharePoint drive item. |
| Document | Normalized, versioned representation of one source object. |
| Chunk | Immutable, citation-addressable passage derived from one document version and chunker contract. A chunk is reusable across index generations when its document version, parser output, chunker contract, and normalized text are unchanged. |
| Passage anchor | Stable structural identity for a passage across document versions when the connector or parser can prove continuity. It is separate from the immutable chunk ID used for exact historical evidence. |
| Embedding space contract | Immutable identity for one mathematically compatible document-vector space: space ID, revision, dimension, normalization, distance metric, and document input-transform version. Equal dimensions alone do not imply compatibility. |
| Embedding profile | Approved reference from a Knowledge Base owner scope to one model-authority host, internal embedding Alias, and immutable embedding-space contract. |
| Model-authority host | Platform or tenant host that owns the LLM control-plane Alias used by the knowledge service. It is distinct from the nullable owner scope of a Knowledge Base or embedding profile. |
| Index generation | Immutable logical manifest of document versions, chunks, ACLs, embedding space, and ordered physical index segments promoted together for retrieval. |
| Index segment | Immutable BASE or DELTA lexical/vector projection. A BASE represents a complete logical snapshot; a DELTA contains additions, replacements, tombstones, metadata changes, or ACL changes relative to earlier segments. |
| Embedding migration | Operational workflow that builds and evaluates a candidate generation under a target embedding profile while the current generation continues serving. |
| Canonical content watermark | Monotonic knowledge-service boundary identifying the exact document-version, chunk, ACL, and tombstone state that a candidate generation has incorporated. It is distinct from an opaque connector cursor. |
| Agent binding | Explicit host-local many-to-many authorization and configuration relationship between a tenant Agent and a visible Knowledge Base. |
| Source ACL | Provider permission information normalized into subjects that the platform can compare with trusted caller identity. |
| ACL revision | Immutable, monotonically ordered authorization snapshot for one stable document. It changes independently from content versions and is referenced explicitly by every index segment that exposes the document. |
| Retrieval profile | Candidate sizes, fusion, result limit, and token budget used by a binding or Knowledge Base. A rerank policy is added only after a canonical rerank operation exists. |
| Lexical contract | Versioned identity for lexical input construction, language selection, tokenizer/parser, dictionaries, stemming, stopwords, identifier and phrase normalization, ranking function, and optional trigram or BM25 implementation. |
| Embedding workload lane | Independently admitted gateway ingress and memory pool for either latency-sensitive KB queries or asynchronous KB indexing. An Alias alone is not a lane because global admission occurs before Alias parsing. |
| Retrieval strategy | Server-owned implementation selected by an authorized retrieval profile, such as HYBRID or GRAPH_ASSISTED. |
| Derived index | Rebuildable lexical, vector, or graph projection created from canonical document versions, chunks, ACLs, and provenance. |
| Evidence contribution | Link from a derived entity, relation, or summary to the exact chunk and document version that contributed information. |
| Relational evidence path | Request-scoped ordered sequence of authorized entities and typed relations used to discover, group, and rank canonical chunk evidence. It is a retrieval artifact, not canonical Knowledge Base state. |
| Evidence group | Optional additive response structure that records why and in what order existing result chunks belong together, without adding uncited text or granting access to new evidence. |

Phase tags on invariants mean the first delivery phase in which the invariant is
binding: P0 is contract qualification, P1a is the documentation pilot, P1b is
incremental and multi-KB retrieval, P2 is enterprise ACLs, P3 is production
migration and scale, and P4 is optional graph-assisted retrieval. A later-phase
tag does not weaken an earlier authorization invariant.

## Required Invariants

1. **[P1a]** A Knowledge Base has exactly one immutable owner scope:
    host_id IS NULL for platform-global ownership or a non-null host_id for
    tenant ownership.
2. **[P1a]** There is no common flag. Scope, ownership, visibility, and tenant enablement
    are represented separately.
3. **[P1a]** Only an authorized platform administrator can create, update, deactivate,
    delete, synchronize, or reindex a global Knowledge Base and its sources.
4. **[P1a]** A tenant administrator can create and manage Knowledge Bases owned by the
    trusted tenant, and can bind or unbind visible global Knowledge Bases, but
    cannot mutate their global definitions or content.
5. **[P1a]** Consumer host identity is derived from trusted authentication and routing
    context. A request body cannot select a different tenant.
6. **[P1a]** Effective catalog queries return rows where host_id equals the trusted
    consumer host or host_id IS NULL. By-ID reads repeat the same visibility
    predicate.
7. **[P1a]** An Agent can retrieve from a tenant or global Knowledge Base only through an
    active binding owned by the Agent's host and valid for the same environment.
8. **[P1a]** A caller-supplied Knowledge Base list can only narrow the bound set; it can
    never grant access or convert global visibility into runtime enablement.
9. **[P1a]** Document authorization is evaluated before content is returned. A
    post-retrieval UI filter is not an authorization control.
10. **[P2]** When source ACL mapping is incomplete, ambiguous, stale beyond
    policy, or unsupported, source-ACL mode fails closed.
11. **[P1a]** Source content is untrusted data. Retrieved text does not override system,
    developer, policy, or tool-authorization instructions.
12. **[P1a]** Original documents, normalized text, chunks, and embeddings have explicit
    versions. A retrieval result identifies the promoted index generation and
    document version used.
13. **[P1a]** A failed or partial synchronization never replaces the last valid promoted
    generation.
14. **[P1a]** Embedding vectors and connector secrets are never returned to the browser
    or ordinary Agent clients.
15. **[P1a]** Deactivation, deletion, retention, and legal-hold behavior apply to both
    metadata and object-store content.
16. **[P1a]** All retrieval results have a stable citation containing at least the
    Knowledge Base, source, document, content version, and source URI or
    equivalent locator.
17. **[P1a]** Operational ingestion records are rebuildable from source and control-plane
    configuration. They are not treated as Portal-authored business state. A
    Portal event replay rebuilds Portal authoring projections only; a separate
    validated publication creates the immutable Config Server Knowledge
    snapshot. Neither operation proves that target-environment documents,
    chunks, embeddings, indexes, or object-store artifacts exist. A logical
    publication into another environment creates new target commands and
    resource identities, while only an exact disaster-recovery restore preserves
    the original identities and effective generation.
18. **[P1a]** Every retrieval audit distinguishes the nullable owner host of the
    Knowledge Base from the non-null consumer host whose Agent issued the
    query.
19. **[P1a]** A retrieval strategy can rank or expand only the document versions already
    authorized for the request. It cannot widen tenant, binding, source, or
    principal scope.
20. **[P4]** Every derived entity, relation, description, or summary retains complete
    evidence contributions. If safe authorized reconstruction is impossible,
    the artifact is excluded from retrieval.
21. **[P1a]** Runtime callers cannot select an arbitrary engine, workspace, graph
    partition, or index namespace. The service resolves the active strategy and
    generation from trusted bindings and profiles.
22. **[P1a]** Every promoted index generation is bound to one immutable embedding-space
    ID and revision. Dimension equality, a shared provider protocol, or a
    common public Alias name is not proof of vector-space compatibility.
23. **[P1a]** Every embedding deployment eligible for an indexing or query Alias must
    declare the same complete embedding-space contract. Gateway publication
    rejects a mixed-space Alias, including incompatible fallback and canary
    routes.
24. **[P1a]** Indexing and query embedding requests send the expected space ID and
    revision. A mismatch fails before provider dispatch; it never silently
    follows an Alias update or replacement.
25. **[P3]** A change to model weights, dimension, normalization, distance metric, or
    document input transform creates a new embedding-space revision and a new
    candidate index generation. A query-transform-only change creates a new
    embedding-profile revision and evaluation; it may reuse document vectors
    only under the equivalence gate defined below. Existing promoted
    generations remain queryable only through their recorded space and profile
    revision.
26. **[P1a]** A global Knowledge Base uses a platform-owned workload identity and an
    Alias owned by a designated platform model-authority host. Consumer tenants
    never select the embedding Alias or embed its queries directly.
27. **[P1a]** The active index generation is resolved exactly once at retrieval start.
    Lexical, vector, graph, citation, and audit queries all use that pinned ID,
    even if promotion occurs while the request is running.
28. **[P1a]** Global Knowledge Base retrieval is metered and admitted per consumer host.
    One tenant cannot exhaust another tenant's query concurrency or cost
    allocation through the shared platform embedding authority.
29. **[P1a]** Normalized document versions and immutable chunk artifacts are canonical
    intermediate state. They are not owned by one vector space. An
    embedding-only migration reuses them and does not refetch, reparse, or
    rechunk content whose relevant contracts and hashes are unchanged.
30. **[P1a]** Index-generation membership is separate from chunk identity and embedding
    identity. A generation-specific lexical or ANN projection is rebuildable
    from canonical document versions, chunks, ACL revisions, and immutable
    embedding artifacts.
31. **[P1a]** The promoted generation is authoritative for the runtime embedding profile.
    Selecting a target profile for a migration never mutates the profile or
    vector space of the promoted generation. Runtime retrieval does not read a
    desired or candidate profile from mutable Knowledge Base settings.
32. **[P1a]** A candidate generation records a starting canonical content watermark,
    backfills that snapshot, consumes every subsequent content, ACL, and
    tombstone delta, and passes a final reconciliation fence at a recorded
    promotion watermark. A partial or stale candidate cannot be promoted.
33. **[P3]** Old-space and new-space vectors remain in separate physical ANN indexes.
    Evaluation compares ranked documents, citations, and task metrics; it never
    treats raw similarity scores from different spaces as comparable or merges
    those scores into one ranking.
34. **[P3]** The first release exposes candidate generations only through authorized,
    budgeted evaluation paths. It does not randomly route ordinary Agent
    requests between generations. Any future shadow or cohort rollout requires
    explicit privacy policy, stable cohort assignment, separate accounting, and
    complete per-request generation pinning.
35. **[P3]** Promotion retains the predecessor generation for a bounded rollback window.
    Rollback is an atomic pointer transition and is allowed only while the
    predecessor has remained current through dual-applied deltas or has passed a
    fresh reconciliation gate. Rollback retention never outranks authorization
    removal or an approved erasure: a revoked or erased predecessor immediately
    loses rollback eligibility. A valid legal hold may retain inaccessible bytes
    when law or policy requires it, but can never keep them retrievable.
36. **[P3]** Fine-tuning, provider-side weight changes, or a supposedly equivalent model
    replacement are embedding-space changes unless compatibility is positively
    proven. Open weights alone do not make existing vectors reusable. Only the
    query-transform-only equivalence case described above may avoid document
    re-embedding.
37. **[P1b]** A routine source update creates an immutable DELTA segment and a new logical
    generation manifest that reuses unchanged segments. It does not require a
    complete physical vector-index rebuild merely because the generation ID
    changes.
38. **[P1b]** Every generation's ordered segment manifest has deterministic latest-wins
    semantics for stable documents, document versions, and passage anchors. A
    document-scoped supersede operation suppresses every older chunk for that
    document, including passages that disappeared and therefore have no new
    anchor match. Tombstones and ACL revocations suppress older segment records
    before content is returned; an older base hit cannot bypass a newer deny or
    replacement delta.
39. **[P1b]** All segments in one generation use compatible parser, chunker,
    metadata, citation-anchor, ACL-normalization, lexical, embedding-space, and
    distance contracts.
    An incompatible contract change builds a new BASE candidate rather than
    adding an ambiguous delta.
40. **[P1a]** Each normalized document, chunk, embedding, and derived projection records
    the digest of the exact inputs and versioned contracts that produced it.
    Invalidation walks those dependencies and rebuilds only affected descendants.
41. **[P1b]** Embedding reuse is keyed by the digest of the exact transformed embedding
    input plus space ID/revision and document-transform version. Reuse is limited
    to an approved Knowledge Base or owner-policy scope; it never crosses tenant
    boundaries or tenant/global scope by default.
42. **[P1b]** A stable passage anchor never replaces immutable evidence identity. Runtime
    results and audit retain document-version ID and chunk ID, while the passage
    anchor supports current-section resolution and relationship continuity.
43. **[P1b]** Deletions and ACL revocations have scheduling priority over content
    additions, ordinary modifications, reconciliation repair, and bulk
    backfill. A model migration cannot delay a known authorization removal.
44. **[P1b]** Every BASE and DELTA segment publishes count and digest evidence for
    documents, versions, chunks, embeddings, metadata, ACL state, and tombstones.
    Promotion and scheduled anti-entropy checks compare the manifest with
    canonical state and the physical projections.
45. **[P4]** Graph seed retrieval, subgraph construction, path planning, description
    construction, and evidence grouping operate only on the request's authorized
    evidence-contribution set. Post-traversal filtering is not sufficient.
46. **[P4]** A path retrieval score is a versioned ranking signal derived from query and
    graph structure. It is not factual confidence, authorization evidence, or a
    substitute for complete node, relation, and chunk provenance.
47. **[P4]** Every member of a relational evidence path resolves to canonical chunks
    already eligible for the request. An optional evidence group may order or
    group those chunks but cannot introduce generated claims as evidence.
48. **[P4]** Relational paths are request-derived rather than durable graph truth. Any
    cache is bounded and keyed by generation, authorization boundary, planner
    version, retrieval profile, and normalized query-signal digest; it cannot be
    reused across an incompatible tenant, principal, or policy boundary.
49. **[P4]** Graph traversal has server-owned limits for seeds, seed pairs, fan-out,
    hops, visited nodes and edges, paths, tokens, wall time, and memory. Empty,
    disconnected, pruned, or timed-out traversal safely falls back to authorized
    hybrid evidence and never widens retrieval.
50. **[P1a]** Runtime authorization pins one validated immutable Config Server
    Knowledge snapshot and resolves operational ACL and generation state from one
    transactionally consistent knowledge-service database snapshot. A
    cross-database join, mutable fallback read, or expired policy snapshot cannot
    authorize a request.
51. **[P2]** ACL state has an immutable identity and sequence independent of a
    document content version. An ACL-only change publishes a new ACL revision,
    and every segment membership references the exact revision it enforces.
52. **[P1b]** Multi-Knowledge-Base retrieval ranks within each Knowledge Base and
    embedding space before cross-KB fusion. It never compares raw lexical,
    vector, reranker, or graph scores across incompatible profiles or spaces.
53. **[P1a]** A binding-selected retrieval profile can only narrow a Knowledge
    Base's active qualified-strategy set and server-owned budgets. It cannot
    enable GRAPH_ASSISTED or any other strategy the Knowledge Base has not
    qualified.
54. **[P1a]** Lexical projections are bound to one immutable lexical contract.
    Segments with different tokenization, dictionaries, stemming, stopwords,
    identifier handling, language rules, or ranking implementation are not
    silently fused as one compatible lexical index.
55. **[P2]** ACL correctness is bounded by discovery as well as application.
    Every MIRROR_SOURCE_ACL source has a maximum reconciliation interval, a
    maximum ACL age, and a measured revocation-visibility SLO; exceeding any of
    them removes the affected source from eligibility until reconciliation.
56. **[P1a]** Initial crawl, resynchronization, reindex, and migration all have
    explicit tenant and Knowledge Base ceilings for discovered objects, chunks,
    source bytes, stored bytes, embedding tokens and spend, wall time, and
    concurrent work. Reaching a ceiling pauses or fails boundedly and never
    changes the active generation.
57. **[P1a]** A source trust tier and approval policy are retrieval metadata, not
    authorization or instruction priority. Global content cannot be promoted
    without its configured change-review gate, and every citation exposes the
    source trust tier so Agent policy can treat global evidence appropriately.

## Bounded Context And Topology

Use Light Portal as the control plane and a knowledge service as the data
plane:

~~~text
                          Light Portal control plane
                    ┌─────────────────────────────────┐
Portal administrator│ Knowledge Bases, Sources,       │
───────────────────>│ Agent Bindings, Policies, Jobs  │
                    └──────────────┬──────────────────┘
                                   v
                    Config Server PostgreSQL database
                    authoritative commands and events
                                   │
                                   v
                    immutable Knowledge configuration
                    served by the Config Server API
                                   │ load/refresh
                                   v
             ┌─────────────────────────────────────────────┐
             │ one long-running light-knowledge container  │
             │                                             │
             │ config -> published replicas -> enforcement │
Controller ─>│ bounded control handler      │              │
             │                              v              │
Confluence ─>│ connector ─┐       durable job queue        │
SharePoint ─>│ connector ─┼─> on-demand build tasks        │
Uploads ────>│ connector ─┘                 │              │
             │                              v              │
             │ retrieval API <──── knowledge database      │
             │                       PostgreSQL + pgvector │
             └──────────┬────────────────────┬─────────────┘
                        │                    └─ object storage
                        v
               Agents, workflows, MCP
~~~

Implement the knowledge data plane in the `light-fabric` workspace. The
`apps/light-knowledge` application is the stateless API artifact and uses
`light-axum` for its HTTP runtime, middleware, configuration integration,
security integration, health endpoints, and REST and MCP transports. Keep the
Portal command/query services as the control-plane boundary; do not move their
administrative actions into `light-knowledge`.

The default deployment contains only `light-knowledge`. Its internal components
remain explicit rather than being folded into HTTP handlers:

- the REST and MCP retrieval API;
- one typed Config Server loader with staged replica materialization, atomic
  apply, and last-known-good handling;
- one lightweight job supervisor that waits without polling aggressively,
  performs recovery and scheduled reconciliation, and starts bounded job tasks;
- on-demand connector, parsing, chunking, ACL, embedding, compaction, migration,
  and maintenance tasks; and
- a bounded controller command handler for runtime operations.

Domain, authorization, storage, projection, and ingestion logic belongs in
shared `light-fabric/crates/knowledge-*` crates. The service binary composes
those libraries; it does not duplicate the former worker implementation inside
HTTP handlers. The job engine remains callable from a CLI or an optional
Kubernetes Job for large Confluence, SharePoint, migration, restore, or
backfill work. That escape hatch is execution on demand, not a required
always-running second service.

The single process keeps a read-only Config Server client and distinct Knowledge
API and job database pools and roles for accidental-misuse containment, query
attribution, and auditing. It has no control-plane event-store or Portal
projection credential. A narrowly scoped client may acknowledge configuration
application through the Config Server API and may call approved Portal command
APIs; it does not gain general Config Server write access. This does not
preserve process-level credential isolation: a complete process compromise can
reach every credential held by the container. Production deployments that
require that stronger boundary must select the optional external job-execution
mode and prove contract parity with the embedded engine.

Indexing is admitted behind bounded semaphores and separate database and gateway
lanes so it cannot consume the final capacity reserved for retrieval. CPU-heavy
or blocking work uses bounded blocking pools or child processes whose lifetime
is owned by the job task. A job panic, connector failure, or exhausted build
budget fails that job without terminating the HTTP server. Container-level OOM,
disk exhaustion, and image/tooling exposure remain shared risks and are covered
by the capacity and isolation gates below.

### Configuration and bootstrap

Do not deploy a `light-knowledge-bootstrap` container. `light-runtime` loads
non-secret configuration and approved files from Config Server into its merged
runtime configuration before binding the server. `light-knowledge` consumes
that merged configuration rather than reopening a separately mounted
`knowledge.yml` behind the runtime's back.

Only the minimum information needed to reach Config Server remains local or
embedded: its URI, client authentication, TLS trust, service identity, and
environment. The merged configuration identifies the Knowledge data-plane
database; its credentials remain deployment secrets. The service validates the
connection and expected database identity before readiness and refuses a
configuration that points a Knowledge role at the control-plane schema. It has
no Config Server PostgreSQL credential. Delegation secrets, query-cache
keys, connector credentials, and the distinct `kb-index` and `kb-query`
workload credentials also come from deployment secret references. Direct
environment values are permitted for local development, but production prefers
`_FILE`, orchestrator-secret, or secret-provider references because plain
environment values are visible through common container inspection paths.

Configuration reload is explicit. Safe limits and feature switches may reload
through a registered runtime module. Database endpoints, credential rotations,
embedding-space identity, object-store roots, and other construction-time
settings require a coordinated component rebuild or process restart; a generic
`reload_modules` acknowledgement must not claim they changed in place.

### Configuration publication and controller commands

Portal commands and their committed CloudEvents remain the durable source of
administrative intent inside the control plane. Portal projections compile that
state into a least-privilege Knowledge audience document, create an immutable
configuration snapshot, and activate it through Config Server. Light Knowledge
loads only the authenticated Config Server artifact, validates its target,
schema, publication identity, digests, signature, validity window, and
compatibility generation, stages the complete control-replica inventory and
tombstones, then atomically applies the snapshot and replica set or retains the
last known good set according to policy. It never reads the Portal event stream.

The controller command stream is an optional low-latency operational path, not
a replacement for committed Portal intent or Config Server publication. A
Portal UI mutation commits its command/event and publishes the resulting
snapshot first; the controller may then tell `light-knowledge` to refresh to the
named snapshot. Direct controller or administration tools may expose status,
reload, retry, wake, and job creation operations. Any tool that creates work
returns a durable job ID, pins the applied snapshot ID, uses an idempotency key
and trusted host/environment scope, and never keeps the control stream open for
the duration of a build. If controller delivery is lost, an explicit refresh or
restart obtains the current immutable snapshot from Config Server; operational
jobs remain durable in the Knowledge database.

### Embedded job execution

There is no permanently active builder task consuming resources. A lightweight
supervisor owns queue notification, startup recovery, expired-lease handling,
scheduled maintenance, promotion acknowledgement, and a periodic fallback scan.
The database emits a notification when work becomes eligible; notification is
only a wake-up hint, and the durable `knowledge_job_t` row remains authoritative.

Each claimed job runs in a bounded supervised task and exits when it reaches a
terminal, paused, or retryable state. Claims retain lease tokens,
`FOR UPDATE SKIP LOCKED`, bounded renewal, idempotent effects, and terminal
compare-and-set updates so several `light-knowledge` replicas can safely share
the queue. Singleton scheduling work uses a durable consumer lease or database
advisory leadership with takeover; it is not inferred from a container name.

An external CLI or Kubernetes Job invokes the same job engine and claims one
explicit durable job. It cannot bypass authorization, budgets, leases,
generation validation, promotion, acknowledgement, audit, or purge contracts.
It reads the pinned configuration identity and work state from the Knowledge
job contract, accesses only the Knowledge database and approved object/provider
dependencies, and has no Portal event-store or projection credential.

### Database boundary and physical isolation

The control plane and data plane are separate logical databases even when a
small deployment colocates them physically:

| Mode | Deployment | Isolation |
| --- | --- | --- |
| Compatibility | Config Server and Knowledge schemas share one PostgreSQL database. | Lowest operational cost; no resource or failure isolation. |
| Separate database | `configserver` and `knowledge` are different databases in one PostgreSQL cluster. | Separate credentials, namespaces, logical backup and connection budgets; shared CPU, memory, I/O, WAL and failure domain. |
| Separate instance | `configserver` and `knowledge` use different PostgreSQL instances or managed clusters. | Strongest resource, maintenance, failure-domain and restore isolation. |

Code and migrations target the logical boundary, not the compatibility mode.
There are no cross-database foreign keys, joins, writes, or distributed
transactions. Control-plane UUIDs stored in `knowledge` are external identities
validated against the immutable Config Server snapshot pinned when work is
admitted. Local foreign keys may reference snapshot-materialized published
control-replica roots or Knowledge-owned operational roots, never a remote
relation. Backup and restore validate the applied Config Server
publication/snapshot identity, replica manifest digest, Knowledge checkpoint,
and object manifest as one compatibility set.

Compatibility mode adopts the same delivery semantics as isolated mode: Light
Knowledge loads policy through the Config Server API and accesses only its
Knowledge operational database role. Physical colocation never authorizes a
direct read of `event_store_t` or a Portal authoring/projection table.

Published control replicas carry the content-minimized Knowledge Base, source,
profile, qualification, policy, and Agent-binding fields required by local
constraints and queries. The snapshot loader is their sole writer. Operational
roots carry the external identities and immutable policy/profile digests under
which their jobs, generations, and artifacts were created. Neither category is
a Portal administrative write model. Predecessor database functions and
triggers that read authoritative control-plane tables are changed to validate
only local replica/operational invariants and caller-supplied expected
identity/digest values. In particular,
`validate_knowledge_index_generation_profile()` validates the generation's
pinned embedding-profile identity and digest, and
`promote_knowledge_base_generation()` receives the expected environment and
policy identity from the validated applied snapshot while keeping pointer
compare-and-set, history, outbox, and acknowledgement evidence in one Knowledge
transaction. Fresh-schema gates reject every data-plane routine that resolves a
Config Server table.

`cascade_relationship_policy_t` is also boundary-owned metadata. Policies for
foreign keys that move with Knowledge data are installed and validated in the
Knowledge database; Config Server retains only policies for constraints that
remain there. Migration removes or relocates obsolete registry rows in the same
release that moves their constraints, and both fresh and upgraded Config Server
schema gates must pass `validate_cascade_relationship_policies()`.

Portal's event store remains authoritative for administrative history inside
the control plane, but Light Knowledge never reads it. Portal publishes the
Knowledge audience projection as an immutable Config Server artifact carrying
Knowledge Base, source, binding, profile, strategy, publication, validity, and
compatibility data. Each Light Knowledge instance validates and atomically
applies the artifact, reports its snapshot/publication/digest evidence, and
retains the last known good snapshot according to the signed validity policy.
The Knowledge PostgreSQL database does not contain a Portal-event inbox, cursor,
heartbeat, or event-built runtime authorization projection. It does contain the
published control replicas required by retrieval and operational joins, keyed
to the active snapshot and source control versions.

The retrieval API pins the currently applied immutable configuration snapshot,
serializes quota admission in a short read-committed transaction that locks the
consumer quota row, and then reads version-matched published control replicas,
the active generation pointer, source ACL revisions, and candidate rows in one
separate transaction at a repeatable snapshot. It authorizes from the pinned
configuration/replica set plus operational evidence; it never uses a Portal-
database join or mutable policy fallback. Each admitted job and query audit
records the snapshot/publication and policy digests it used.

An authorization-removing action such as unbind, source deactivation, Knowledge
Base deactivation, or strategy revocation is `PENDING` until every required
Light Knowledge instance acknowledges applying the new configuration snapshot.
The initial SLO is five seconds from snapshot activation to effective deny. If
the applied snapshot expires, fails signature/digest validation, or falls
outside the accepted compatibility generation, new retrieval fails closed for
the affected scope. Portal shows desired versus applied snapshot identity and
the measured revocation lag.

Configuration and promotion acknowledgements are accepted only from an
allowlisted Knowledge workload principal. During topology rollback
compatibility, the acknowledgement contract may admit both the existing
`light-knowledge-worker` principal and the consolidated `light-knowledge`
principal. The consolidated principal must pass Config Server acknowledgement
and five-second deny tests before cutover; the worker principal is removed only
after the rollback window closes. Local, development, installer, and
production-like configuration use the same identity migration contract rather
than environment-specific literal names.

Portal never reads or writes Knowledge operational tables while accepting a
promotion acknowledgement. Light Knowledge signs the exact promotion evidence;
Portal verifies it and appends an idempotent control-plane event, then returns
the committed event receipt. Light Knowledge inserts the acknowledgement and
moves its promotion outbox row to `ACKNOWLEDGED` in one Knowledge-local
transaction. Work-producing Portal commands use a Portal-local transactional
delivery outbox and private idempotent Light Knowledge command endpoint after
the Portal event commit. The detailed migration and lost-response gates are in
[Portal Operational Access Boundary For Light Knowledge](../light-knowledge/portal-operational-query-boundary.md).

## Ownership And Event Model

Use the existing Portal command, event store, and projection model for
low-volume durable configuration:

- Knowledge Base identity, display metadata, state, and policy;
- Source configuration without secret material;
- Agent-to-Knowledge-Base bindings;
- requested lifecycle actions such as synchronize, reindex, compact, embedding
  migration, generation promotion or rollback, deactivate, retire, and purge
  approval.

Suggested configuration events are:

~~~text
KnowledgeBaseCreatedEvent
KnowledgeBaseUpdatedEvent
KnowledgeBaseDeactivatedEvent
KnowledgeBaseDeletedEvent

KnowledgeSourceCreatedEvent
KnowledgeSourceUpdatedEvent
KnowledgeSourceDeactivatedEvent
KnowledgeSourceDeletedEvent
KnowledgeSourceSyncRequestedEvent
KnowledgeSourceConnectivityTestRequestedEvent

AgentKnowledgeBaseBoundEvent
AgentKnowledgeBaseBindingUpdatedEvent
AgentKnowledgeBaseUnboundEvent

KnowledgeBaseReindexRequestedEvent
KnowledgeBaseCompactionRequestedEvent
KnowledgeBaseEmbeddingMigrationRequestedEvent
KnowledgeBaseEmbeddingMigrationPauseRequestedEvent
KnowledgeBaseEmbeddingMigrationResumeRequestedEvent
KnowledgeBaseEmbeddingMigrationCancelRequestedEvent
KnowledgeBaseIndexGenerationPromotionRequestedEvent
KnowledgeBaseIndexGenerationRollbackRequestedEvent
KnowledgeBaseIndexGenerationRetirementRequestedEvent
KnowledgeBasePurgeRequestedEvent

KnowledgeBasePortabilityManifestIssuedEvent

KnowledgeBaseImportStartedEvent
KnowledgeBaseImportDependenciesBoundEvent
KnowledgeBaseImportBuildApprovedEvent
KnowledgeBaseImportAbandonedEvent

KnowledgeBaseRetrievalStrategyQualifiedEvent
KnowledgeBaseRetrievalStrategyRevokedEvent
KnowledgeBaseIndexGenerationPromotedEvent
KnowledgeBaseIndexGenerationRolledBackEvent
~~~

Do not create one event for each document, chunk, embedding, permission row, or
sync progress transition. Those are high-volume operational projections owned
by the knowledge service. A control-plane request may create an operational
job, and job status is then queried from the operational read model.

Cross-environment publication uses two separate aggregates, one on each side.
Neither is part of the Knowledge Base aggregate, because both must outlive the
Knowledge Base rows they describe.

`KnowledgeBasePortabilityManifestIssuedEvent` belongs to a source-side
manifest-export aggregate identified by source owner scope, source environment,
and `publication_id`. The `KnowledgeBaseImport*` events belong to a target-side
publication aggregate identified by target owner scope, target environment, and
`publication_id`, never the target knowledgeBaseId, because the publication
identity must survive target deletion:

~~~text
Global export:  environment|publicationId  (manifest-export aggregate)
Tenant export:  hostId|environment|publicationId
Global import:  environment|publicationId  (publication aggregate)
Tenant import:  hostId|environment|publicationId
~~~

The two aggregates share a `publication_id` but are distinct streams in
different environments and are never merged, correlated into one lifecycle, or
used to authorize each other. A target may import a manifest whose source
environment has no reachable history, and a source may issue a manifest that is
never imported.

Export appends exactly one `KnowledgeBasePortabilityManifestIssuedEvent` after
successful signing and before the artifact is released. It records only the
`publication_id`, `payload_digest`, source Knowledge Base UUID and version,
manifest-format version, exporter reference, issuance time, signing-key ID,
signature digest, and delivery classification. It never records payload
content, signature bytes, display names, source URIs, credentials, or artifact
contents. KMS audit logs remain authoritative for cryptographic key use; this
event records the administrative issuance decision, not the key operation.
Export is synchronous in the first release. If it later becomes asynchronous,
split issuance into distinct requested and completed events rather than
redefining this one.

`KnowledgeBaseImportStartedEvent` records the manifest digest and the generated
target identities, so the ordinary target `KnowledgeBaseCreatedEvent` and
`KnowledgeSourceCreatedEvent` carry no import-specific fields. Abandonment is
recorded on the publication aggregate, not on the imported Knowledge Base.

The event-backed configuration must remain usable if the knowledge service is
temporarily unavailable. Conversely, the retrieval API must continue serving
the last promoted generation while a new synchronization or reindex is
running, provided its applied Config Server snapshot remains valid. A last-known-
good snapshot cannot be used beyond its signed validity policy to create an
unbounded authorization-revocation window.

### Cross-environment publication, replay, and restore

Projection replay, logical publication, and physical restore are different
operations and must not share an ambiguous "import events" control:

| Operation | Purpose | Identity and data behavior |
| --- | --- | --- |
| Portal projection replay | Rebuild Portal control-plane projections for the same environment from authoritative administrative history, then publish a new immutable Knowledge configuration snapshot. | Preserves aggregate identities and versions, suppresses external effects, and does not recreate operational Knowledge data or write a Knowledge authorization projection. |
| Logical environment publication | Create an equivalent Knowledge Base definition in another environment or ownership scope. | Submits new target-environment commands, creates new Knowledge Base/source identities and target-local dependency mappings, and builds a new generation from source or approved canonical source artifacts. |
| Physical restore | Recover the same environment and administrative history after loss. | Preserves identities only when Portal history, the Knowledge PostgreSQL checkpoint, and the matching versioned object-store checkpoint are restored at compatible watermarks. |

A raw chronological event stream is not a portable Knowledge Base package.
Historical synchronize, reindex, migration, promotion, rollback, retirement,
delete, and purge requests must not execute merely because a Portal projection
is being rebuilt or events are being inspected in another environment. Portal
projection application and external-effect dispatch therefore use explicit live
versus replay/import modes. A replay updates only Portal control-plane
projections; it does not call Light Knowledge, fetch sources, call an embedding
provider, change an active generation pointer, or issue a runtime
acknowledgement. Any resulting Knowledge configuration is delivered only by an
explicit validated Config Server publication.

Logical publication uses a versioned portability manifest derived from accepted
current desired state, not by rewriting immutable source events. Its two layers
have different canonicalization rules:

- `desired_state_payload` is deny-unknown, canonically serialized, and
  content-addressed. It contains its payload schema version, source environment,
  source Knowledge Base identity and version, source lineage, portable Knowledge
  Base/source metadata, immutable repository revision or provider version where
  available, bounded include/exclude policy, trust and approval policy,
  schedules, ingestion/retrieval policy, required processing-contract digests,
  required embedding-space and workload-lane characteristics, and named target
  binding slots. Target requirements do not assume that a source-environment
  Alias, profile UUID, provider, endpoint, credential, or Agent exists in the
  target.
- `publication_envelope` is not part of the payload digest. It contains the
  manifest-format version, explicit `publication_id`, digest algorithm,
  `payload_digest`, export time, exporter identity, signing-key identity, and
  signature. The signature covers the canonical envelope fields other than the
  signature, including `payload_digest`; the digest is computed only from
  canonical `desired_state_payload` bytes and therefore never includes itself.

`publication_id` is a UUIDv7 generated by the source environment's export
command, never supplied by a caller and never derived from the payload. Each
export attempt mints a new one, and the signature binds it to that exporter and
digest. A caller-chosen or reused identifier is rejected, because the identity
below is permanent in the target and a squatted value would otherwise burn it
for an unrelated publication.

Two exports of unchanged desired state have the same `payload_digest` even when
their export time, exporter, signature, or `publication_id` differs. Reusing a
`publication_id` means retrying the same intended target publication; selecting
a new `publication_id` explicitly requests a separate publication attempt.

The portability manifest never contains secret values, bearer tokens, raw
connector credentials, vectors, query-audit text, job progress, source
environment pointer state, or promotion/rollback acknowledgements. Active Agent
bindings are excluded by default because Agents and consumer hosts are
environment-local; an authorized target administrator may map selected bindings
explicitly after their Agent definitions and policies are validated.

The target command processor re-authorizes the importing actor, derives the
target environment and permitted owner scope from trusted context, verifies the
envelope and payload digest, generates new resource UUIDs, records the
source-to-target identity map, and emits ordinary target creation events. A
TENANT target derives its host from the authenticated target context. A GLOBAL
target requires the explicit platform Knowledge Base administration capability;
neither an authorized tenant importer nor a tenant-authored manifest can grant
or translate itself into GLOBAL scope. A GLOBAL target also inherits the global
source trust, approval, and change-review gate before target-local promotion.

The idempotency identity is target owner, target environment, and
`publication_id`, permanently bound to one `payload_digest`. The same
`publication_id` and digest always returns the same import and target identities
and may resume it only while its state is explicitly retryable. The same
`publication_id` with another digest is rejected. Abandonment is terminal: an
abandoned import cannot resume, and abandoning, deleting, retiring, or purging
its target never releases the publication identity. A new attempt requires a
new `publication_id`; a new ID with the same payload is an explicit separate
publication and remains subject to ordinary name, scope, quota, and
authorization rules. A retained import tombstone preserves this guarantee after
target deletion.

That tombstone is content-minimized and retained indefinitely by design. It
holds only the publication identity, `payload_digest`, terminal state and
reason code, timestamps, the authorizing actor reference, the generated target
identities that must never be reissued, and bare source lineage identifiers:
source environment plus source Knowledge Base UUID and version. It holds no
manifest payload, display names, source URIs, policy or schedule detail,
credential or secret reference, document content, or personal data, so
indefinite retention is compatible with the erasure and retention rules for
every other artifact. Purge and erasure workflows may remove the imported
Knowledge Base and its content but never the tombstone.

Abandonment requires the same target-scope administration capability as the
import that created the publication: an authorized tenant administrator for a
TENANT target, and the platform Knowledge Base administration capability for a
GLOBAL target. It is irreversible, so it is authorized and audited as an
administrative action rather than as an ordinary cleanup.

Import creates the Knowledge Base in `DRAFT` with no active generation pointer
and no effective promotion state. Source credentials, secret references,
model-authority host, Alias, embedding profile, budgets, feature flags, and any
selected Agent bindings must be rebound and validated in the target before one
explicit reconciliation/build request is admitted.

The target worker then obtains the pinned source revision and runs the normal
idempotent pipeline. If that revision is unavailable, changed, outside policy,
or incompatible with the target processing contracts, publication fails closed
without promoting partial data. An approved publication may reference canonical
original or normalized source artifacts in a separately encrypted and
authorized object bundle; those artifacts remain outside Portal events and use
the same hashes, retention, malware/type, ownership, and object-checkpoint rules
as ordinary ingestion.

A source-environment `KnowledgeBaseIndexGenerationPromotedEvent` is lineage and
audit evidence only in a logical publication. It cannot establish target
effective state because the referenced generation, vectors, ACL revisions,
citations, object versions, and embedding deployment have not been proven in the
target. The target publishes its own promotion acknowledgement only after its
complete generation passes authorization, quality, citation, capacity, and
embedding-space gates.

Physical restore is the only portability mode that preserves resource UUIDs,
aggregate versions, active pointer, and historical acknowledgement state. It
uses the backup contract below rather than logical publication, rejects partial
Portal/database/object-store combinations, and keeps retrieval disabled until
the restored Config Server snapshot identity, generation manifest, object
versions, embedding-space availability, and environment identity are mutually
consistent.

For Phase 1a, a clean target fixture means fresh isolated Portal and Knowledge
schemas, an isolated object-store namespace, and the deterministic fake
embedding provider. It is an integration/CI fixture, not a requirement for a
second deployed environment. Phase 3 production qualification adds an exercise
against a separately deployed clean target environment before operator-driven
cross-environment publication is enabled.

## Global And Tenant Scope

Knowledge Bases intentionally support both scopes in one root table:

| knowledge_base_t.host_id | Ownership | Portal visibility | Runtime use |
| --- | --- | --- | --- |
| null | Platform-global | Every authenticated tenant can discover it. | A tenant Agent needs an active host-local binding. |
| trusted host ID | Tenant-owned | Only that tenant can discover it. | An Agent in the same tenant needs an active host-local binding. |

The effective catalog for a trusted consumer host is logically:

~~~sql
SELECT *
FROM knowledge_base_t
WHERE host_id = :trusted_host_id
  AND environment = :trusted_environment
  AND status <> 'DELETED'
UNION ALL
SELECT *
FROM knowledge_base_t
WHERE host_id IS NULL
  AND environment = :trusted_environment
  AND status <> 'DELETED';
~~~

Equivalent OR predicates are valid when query plans and indexes remain
predictable. By-ID reads must apply the same visibility rule; a globally unique
UUID alone is not authorization.

The first release does not apply name shadowing. If a tenant Knowledge Base and
a global Knowledge Base have the same display name, the effective catalog
returns both with a visible Global or Tenant badge and their authoritative
UUIDs. This avoids a tenant row silently replacing platform content.

Create commands accept a semantic scope such as GLOBAL or TENANT, not an
arbitrary host_id:

- for TENANT, the command handler derives host_id from the authenticated Portal
  context;
- for GLOBAL, the handler requires a platform-admin capability and persists
  host_id as null;
- an update cannot change scope; moving content between scopes requires an
  explicit clone or publication workflow with a new Knowledge Base identity.

Suggested event aggregate identities follow the same convention:

~~~text
Global Knowledge Base:  knowledgeBaseId
Tenant Knowledge Base:  hostId|knowledgeBaseId
~~~

Knowledge Base, source, document, and chunk UUIDs are globally unique. Child
resources inherit owner scope from knowledge_base_t through knowledge_base_id
instead of using a caller-supplied host value. A denormalized owner_host_id may
be maintained for partition pruning, but it is derived and validated by the
knowledge service.

agent_knowledge_base_t remains host-scoped even when it references a global
Knowledge Base. Its host_id is the consuming tenant, not the owner of the
global row. Binding validation requires:

~~~text
binding.host_id = agent.host_id
and binding.environment = agent.environment
and (
  knowledge_base.host_id = binding.host_id
  or knowledge_base.host_id is null
)
~~~

This permits one global Knowledge Base to have independent bindings from many
tenants without copying its sources, documents, chunks, or embeddings.

## Data Model

### Control-plane tables

These authoritative event-backed tables reside in the Config Server database.
Use globally unique resource IDs and explicit nullable owner scope:

| Table | Purpose | Important fields |
| --- | --- | --- |
| knowledge_base_t | Global or tenant lifecycle root. | host_id nullable, knowledge_base_id, name, description, environment, status, desired_embedding_profile_id, version |
| knowledge_source_t | Connector configuration inheriting owner scope from the Knowledge Base. ACL mode is deliberately per source so one KB may combine curated uploads with provider-mirrored content. | knowledge_base_id, source_id, source_type, display_name, config_json, secret_reference, status, acl_mode, source_trust_tier, approval_policy, schedule, ACL reconciliation/freshness policy, ingestion_policy_id, version |
| agent_knowledge_base_t | Host-local many-to-many Agent binding to a visible Knowledge Base. | host_id non-null, agent_id, knowledge_base_id, environment, retrieval_profile_id, priority, active |
| knowledge_retrieval_profile_t | Global or tenant-owned bounded retrieval settings. | host_id nullable, profile_id, strategy, candidate limits, fusion method, top_k, token_budget, optional qualified graph-planner contract and hard bounds, version |
| knowledge_base_strategy_qualification_t | Active KB-level strategy eligibility and evidence. | knowledge_base_id, strategy, status, compatible profile constraints, qualification evidence ID, qualified_at, expires_at, version |
| knowledge_ingestion_policy_t | Global or tenant-owned hard crawl and indexing ceilings. | host_id nullable, policy_id, max documents/chunks/source bytes/stored bytes/embedding tokens/spend/wall time/concurrency, version |
| knowledge_embedding_profile_t | Approved immutable embedding-space and query-policy reference. | host_id nullable, profile_id, profile_revision, alias_owner_host_id non-null, public_alias_id, expected_space_id, expected_space_revision, dimension, normalization, distance_metric, document_input_transform_version, query_input_transform_version, active |
| knowledge_base_manifest_export_t | Standalone source-side projection of the manifest-export aggregate. It records one audited issuance of a portability manifest. | manifest_export_id, host_id nullable, environment, publication_id, payload_digest, source knowledge_base_id and version, manifest_format_version, exporter reference, issued_at, signing_key_id, signature_digest, delivery_classification |
| knowledge_base_import_t | Standalone projection of the publication aggregate. It records one target-scope publication attempt, its permanent identity binding, and its terminal tombstone. It is not a child of the imported Knowledge Base. | knowledge_base_import_id, host_id nullable, environment, publication_id, payload_digest, manifest_format_version, exporter identity, signing-key identity, source environment and source knowledge_base_id/version lineage, state, terminal reason code, authorizing actor, target_knowledge_base_id nullable, timestamps, version |
| knowledge_base_import_identity_map_t | Source-to-target identity lineage for one import. | knowledge_base_import_id, source_resource_type, source_resource_id, generated target resource ID |

Important rules:

- knowledge_base_id, source_id, and profile IDs are globally unique UUIDs.
- Tables with nullable owner host IDs use their globally unique resource UUID as
  the primary key, for example `PRIMARY KEY (knowledge_base_id)` and `PRIMARY
  KEY (profile_id)`. A nullable `host_id` never participates in a primary key;
  ownership uniqueness is enforced with partial indexes.
- knowledge_base_t.host_id is null for a global row and non-null for a
  tenant-owned row. There is no common flag.
- Use partial semantic unique indexes such as UNIQUE (environment, name) WHERE
  host_id IS NULL and UNIQUE (host_id, environment, name) WHERE host_id IS NOT
  NULL.
- Scope is immutable after creation.
- knowledge_base_manifest_export_t and knowledge_base_import_t follow the
  nullable-owner convention above with a UUIDv7 surrogate key: `PRIMARY KEY
  (manifest_export_id)` and `PRIMARY KEY (knowledge_base_import_id)`. Scoped
  uniqueness is enforced by partial indexes on both tables, UNIQUE
  (environment, publication_id) WHERE host_id IS NULL and UNIQUE (host_id,
  environment, publication_id) WHERE host_id IS NOT NULL. `publication_id`
  alone is never a primary key, because the same manifest may legitimately be
  imported by different tenants or into different environments; uniqueness is
  per owner scope and environment, matching the aggregate identity.
- These surrogate keys are projection storage identities only. The event
  aggregate identity remains source or target owner scope, environment, and
  `publication_id`, and no external contract, manifest, or API response
  identifies a publication by its surrogate key.
- knowledge_base_import_identity_map_t is keyed through its parent import with
  `PRIMARY KEY (knowledge_base_import_id, source_resource_type,
  source_resource_id)`. It does not repeat host_id, environment, or
  publication_id, which it inherits from knowledge_base_import_t.
- knowledge_base_manifest_export_t stores the source scope in its
  `host_id`/`environment`, unlike the target scope stored on the import tables.
  It is append-only and content-minimized, and unlike the import tombstone it is
  not retained indefinitely: it follows an explicit declared retention rule
  alongside other control-plane administrative audit records, and expiry deletes
  the whole row rather than degrading it.
- knowledge_base_manifest_export_t, knowledge_base_import_t, and
  knowledge_base_import_identity_map_t have no foreign key to knowledge_base_t.
  `target_knowledge_base_id` is a nullable recorded value that is set when the
  target is created and retained after the target is deleted or purged. Deleting
  a Knowledge Base must never cascade to, release, or rewrite a publication
  identity or an issuance record.
- An import row is never physically deleted. It transitions to its terminal
  tombstone state, and the content-minimization rule above bounds what it
  keeps: the terminal transition clears every portable-policy and exporter
  detail beyond that field set, and the identity map retains the generated
  target identities plus bare source resource IDs.
- Child source configuration inherits scope from the Knowledge Base. A tenant
  administrator cannot mutate a source owned by a global Knowledge Base.
- agent_knowledge_base_t is explicit. Do not add a single knowledge_base_id
  column to the Agent definition because both sides are many-to-many.
- The binding's non-null host_id always identifies the consuming tenant. It may
  reference a Knowledge Base with the same host_id or a null host_id.
- Bindings are environment-aware so a development Agent cannot silently use a
  production corpus.
- `priority` is an integer budget weight from 1 through 100, default 50. It
  allocates bounded per-KB candidate and token budget only after every selected
  KB receives its qualified minimum. It is not an authorization precedence or
  a raw-score boost; equal weights use stable Knowledge Base UUID order as a
  tie-break.
- HYBRID is qualified by the Phase 1a release gate. Any other strategy requires
  an active knowledge_base_strategy_qualification_t row. A binding profile is
  rejected if its strategy is absent, expired, or incompatible with that set;
  tenant bindings cannot qualify a global Knowledge Base.
- Graph-planner parameters are server-owned qualified profile settings. Runtime
  clients may narrow result and token limits but cannot select a planner,
  increase traversal bounds, or supply decay, pruning, edge-weight, or fallback
  behavior.
- A global Knowledge Base uses platform-owned connector secret references.
  Tenant users can see redacted source health but cannot resolve or replace
  those credentials.
- A global Knowledge Base can use only a global embedding profile. A tenant
  Knowledge Base can use a visible global profile or a profile owned by the
  same tenant.
- The profile's nullable host_id is its Knowledge Base ownership scope;
  alias_owner_host_id is always non-null and identifies the LLM model authority
  that owns public_alias_id. Do not overload either field with the other
  meaning.
- A global embedding profile resolves through a designated platform
  model-authority host and a platform-owned internal Alias. The knowledge
  service uses its workload credential for both ingestion and query embedding.
- Portal creates an embedding profile only from the LLM control-plane and
  conformance read model. `/v1/models` is an OpenAI discovery surface and is
  not sufficient qualification evidence because it intentionally omits space,
  operation, dimension, and revision details.
- An Alias replacement or retirement never rewrites an active embedding
  profile. A new space or revision requires a new profile and candidate index
  generation.
- `knowledge_base_t.desired_embedding_profile_id` is configuration for the first
  generation or a future migration. Runtime retrieval derives its profile only
  from the request-pinned promoted generation. Changing the desired profile
  therefore cannot move live queries into an unbuilt space.
- Parser, chunker, and lexical contract digests belong to the artifacts they create, not
  the shared embedding profile. A generation records the compatible contract
  set that it composes. Changing a contract invalidates its affected descendants
  and requires a candidate generation; it requires a complete BASE only when
  the new artifacts cannot be composed compatibly with retained segments. It
  does not by itself redefine the vector space.
- `query_input_transform_version` is profile policy rather than part of the
  immutable document-vector identity. A query-transform-only change creates a
  new profile revision, evaluation, and generation pointer. It may reuse the
  existing embedding artifacts and compatible segment set only when space
  ID/revision and document transform are unchanged and an equivalence gate
  proves the new query transform meets the release-quality floor.
- Connector authentication uses secret_reference following the existing
  external-secret pattern. config_json contains non-secret provider selectors
  only.
- The active index generation changes only through an atomic promotion.
- Knowledge Base, source, Agent binding, profile, and strategy policy is supplied
  by the validated immutable Knowledge audience snapshot from Config Server and
  materialized as content-minimized published control replicas. It is not
  projected from Portal events into the Knowledge database.
- Control-plane foreign keys to `host_t`, `agent_definition_t`, LLM Alias, and
  other Portal tables remain in Config Server. The Knowledge database does not
  reproduce remote constraints that require unrelated Portal relations. It
  stores globally unique external IDs, the permitted local replica constraints,
  and the configuration snapshot/profile digests pinned by operational work.
- Data-plane foreign keys reference published control-replica roots or
  Knowledge-owned operational roots such as jobs, documents, generations,
  segments, and pointers. They never reference a Config Server table through a
  foreign data wrapper or application-managed cross-database check on the
  retrieval path.

### Operational tables

The knowledge service owns operational records:

| Table | Purpose |
| --- | --- |
| knowledge_sync_run_t | One scheduled or requested synchronization, cursor inputs, counts, status, and error summary. |
| knowledge_source_cursor_t | Opaque provider delta token, cursor, watermark, and last full reconciliation time. |
| knowledge_document_t | Stable source-object identity and current lifecycle state. |
| knowledge_document_version_t | Immutable normalized content version, content hash, source version, parser contract digest, metadata-schema version, timestamps, and object-store references. |
| knowledge_document_acl_t | Immutable normalized ACL revision for a stable document. Rows include acl_revision_id, monotonic acl_sequence, document_id, allow/deny subject or provider-effective decision, observed/fresh-until timestamps, ACL-normalization contract digest, completeness state, and source permission evidence; content version is not its identity. |
| knowledge_document_relationship_t | Versioned connector-proven containment, attachment, amendment, or reference relationship with source evidence and explicit lifecycle/cascade policy. |
| knowledge_passage_anchor_t | Stable provider or structural passage identity, continuity evidence, current document-version mapping, and lifecycle state. |
| knowledge_chunk_t | Immutable reusable passage artifact with document version, passage anchor when available, parser-output identity, chunker contract digest, offsets, section path, text, token count, lexical input, lexical-contract input digest, metadata-schema version, and content hash. |
| knowledge_embedding_artifact_t | Security-scoped immutable vector keyed by exact transformed-input digest, space ID/revision, dimension, and document-transform version. It may be referenced by multiple eligible chunks under the same approved reuse policy. |
| knowledge_chunk_embedding_t | Auditable association from a chunk to an embedding artifact with creating profile/revision, request evidence, and reuse decision. A later query-only profile revision may reuse the artifact only through the defined equivalence gate. |
| knowledge_index_segment_t | Immutable BASE or DELTA segment with watermark range, compatible parser/chunker/metadata/citation/ACL/lexical/embedding contract digests, physical projection locator, vector projection precision, state, document/chunk/vector/ACL/tombstone counts, and manifest digests. |
| knowledge_segment_document_t | Document-scoped BASE membership or DELTA operation. It activates one content version and exact acl_revision_id, supersedes every older version/chunk, publishes an ACL-only revision, or tombstones the document independent of passage-anchor continuity. |
| knowledge_segment_chunk_t | BASE membership or DELTA operation for a canonical chunk/document version/passage anchor and resolved acl_revision_id; operation is upsert, replace, tombstone, or metadata-only. A document-level ACL-only delta does not duplicate one operation per chunk. |
| knowledge_segment_vector_t | Rebuildable segment-specific ANN row referencing a chunk embedding; a physical backend may materialize vector bytes in a segment-owned partition. |
| knowledge_generation_segment_t | Ordered generation manifest linking one logical generation to compatible BASE and DELTA segments with deterministic precedence. |
| knowledge_index_generation_t | Building, catching-up, validating, ready, promoted, failed, superseded, or purged logical generation; embedding profile/revision, space ID/revision, compatible parser/chunker/metadata/citation-anchor/ACL-normalization/lexical contract-set digest and member identities, query-transform version, canonical watermarks, ordered-segment manifest digest, available strategy projections and their graph/extractor/prompt contracts, and aggregate evidence. |
| knowledge_index_pointer_t | Atomically selected active generation for one Knowledge Base and environment. The active embedding profile is derived from that generation. |
| knowledge_index_pointer_history_t | Immutable promotion or rollback transition with previous and selected generations, authorization, evaluation evidence, reason, release notes, and rollback deadline. |
| knowledge_embedding_migration_t | Planned target profile, source/candidate generations, estimates, state, snapshot and catch-up watermarks, progress, evaluation evidence, promotion, rollback, and error summary. |
| knowledge_query_audit_t | Bounded retrieval evidence including strategy/planner versions, segment manifest, graph path/group aggregates, fallback, and exact result identities without embedding values or full document duplication. |
| knowledge_ingestion_error_t | Per-object retryable or terminal failure with redacted diagnostic details. |

The Knowledge DDL also contains content-minimized published control replicas for
Knowledge Bases, sources, profiles, qualifications, policies, and Agent
bindings. The Config Server snapshot loader is their only writer; their local
schema, constraints, writer, definition digest, and version gate are recorded in
the three-category ownership manifest. Operational rows that depend on control-
plane policy record the applied configuration snapshot ID, publication ID, and
required policy/profile digests. Derived lexical, vector, segment, and optional
graph projections remain Knowledge-owned operational artifacts.

Optional strategies may add derived operational tables for extracted entities,
aliases, relationships, summaries, and evidence contributions. Those tables
must include knowledge_base_id and index_generation_id or an immutable segment
referenced by that generation, and every generated artifact must link to its
contributing chunk and document-version records. A strategy may use compatible
BASE/DELTA projections only when replacement, deletion, and contribution
invalidation semantics are proven; otherwise it rebuilds a complete candidate
projection. Derived records never become independent Portal aggregates.

Suggested optional graph-projection tables are:

| Table | Purpose |
| --- | --- |
| knowledge_entity_t | Generation-scoped canonical entity, type, aliases, retrieval text, and origin classification. |
| knowledge_entity_contribution_t | Entity evidence from one chunk and document version, including structural or extractor contract, version, and diagnostic confidence. |
| knowledge_relation_t | Generation-scoped directed typed edge between two canonical entities, including explicit, structural, or extracted origin. |
| knowledge_relation_contribution_t | Relation evidence from one or more exact chunks and document versions, including source relation, extractor contract, and lifecycle state. |
| knowledge_graph_summary_t | Optional theme or community retrieval text for one uniform visibility boundary. |
| knowledge_graph_summary_contribution_t | Complete source contribution set for one generated summary. |

Do not keep a merged entity, relation, or summary description as the only
representation. UNIFORM_SCOPE may materialize one generation-scoped merged
description because every contribution has the same visibility. A future
MIRROR_SOURCE_ACL implementation must construct or cache descriptions by a
proven visibility partition; it cannot reuse text synthesized from a broader
contribution set.

Do not materialize all possible entity-to-entity paths as canonical rows. A path
is derived for one pinned generation, authorized contribution set, query, and
retrieval profile. Query audit records the planner version, bounds, aggregate
seed/path/pruning counts, optional evidence-group mapping, and contribution
digest without storing an uncited path narrative as source truth. If an
implementation later caches paths, reference accounting and invalidation follow
the same generation and authorization-boundary rules as other derived caches.

Every operational table includes knowledge_base_id and inherits its owner scope
from knowledge_base_t. Tables may include a nullable owner_host_id for physical
partitioning and query pruning, but the worker derives it from the Knowledge
Base root and prevents it from drifting. Runtime query-audit rows additionally
store a non-null consumer_host_id because a global Knowledge Base owner scope
does not identify the tenant that used it.

Document identity and version identity must be separate. A source page keeps a
stable document_id while edits create immutable document-version rows. An
immutable chunk belongs to one document version and parser/chunker contract. A
passage_anchor_id may connect corresponding chunks across versions only when
provider or structural continuity is proven. Ordered knowledge_index_segment_t
and knowledge_generation_segment_t records supply logical generation
membership. Every MODIFY first adds a knowledge_segment_document_t supersede
operation for the stable document and then adds the new version's chunks. The
supersede operation makes chunks that disappeared from the new version
ineligible even when there is no corresponding passage anchor. Provider deletion
creates a document tombstone DELTA operation; it does not silently leave old
chunks active.

An embedding-only migration reads knowledge_chunk_t directly. It creates a new
knowledge_embedding_artifact_t for each distinct eligible transformed input in
the target scope and associates every eligible chunk through
knowledge_chunk_embedding_t. It then builds an isolated BASE
knowledge_index_segment_t and knowledge_segment_vector_t projection. It does not
rerun connector fetch, parsing, or chunking unless an artifact is missing,
corrupt, outside retention, or bound to a changed parser/chunker contract. A
physical pgvector layout may copy vector bytes into a segment-owned partition
for ANN pruning; that copy is a rebuildable search projection, not a second
embedding-provider call.

Persistent embedding reuse starts conservatively within one Knowledge Base.
Broadening reuse to several tenant-owned Knowledge Bases requires identical
owner host, encryption, residency, retention, legal-hold, transform, and data-use
policy. Global and tenant scopes never share artifacts. Reference accounting
prevents one chunk deletion from removing an artifact still used by another,
while purge evidence proves that no prohibited reference or physical copy
survives when the last eligible reference is removed.

Document-level ACLs are preferred. ACL revisions belong to the stable
document_id and advance independently of immutable content versions. An
ACL_ONLY change writes a new acl_revision_id and acl_sequence without mutating
the prior revision or creating a content version; the next segment references
that revision exactly. Chunks inherit the document authorization unless a
connector can prove that a smaller section has a distinct ACL. Avoid duplicating
the same permission set on every chunk.

Document relationships do not imply deletion cascade. Only a connector-proven
relationship type with an explicit lifecycle policy—for example an attachment
owned exclusively by one parent—may generate dependent tombstones. A reference,
link, shared file, or graph-extracted semantic relationship never authorizes
cascade deletion. Every dependent action is visible in the DELTA manifest and
remains subject to retention, legal hold, and authorization validation.

### Object storage

Store large original binaries and optional normalized parse artifacts in an
S3-compatible object store. Store object keys, content hashes, encryption
metadata, and retention state in PostgreSQL.

Use a path or metadata layout that begins with an explicit global or tenant
owner scope, followed by Knowledge Base, source, document, and immutable
content version. Object-store policies must prevent a tenant-facing client from
constructing a key for another tenant or directly accessing a global object.
Downloads are served through an authorized service or short-lived signed URL
after the same effective-catalog, Agent-binding, and document ACL checks.

PostgreSQL and object storage do not provide one atomic transaction. Uploads
therefore use a staged object key and checksum: write the object, commit its
pending reference and expected object version in PostgreSQL, then mark it
committed through an idempotent finalization job. A scheduled orphan collector
deletes unreferenced staged objects only after a grace period and proves that no
active, candidate, rollback, backup, retention, or legal-hold manifest refers to
them. It also reports missing referenced objects; it never converts a missing
object into an empty document.

Backups use object versioning plus a PostgreSQL checkpoint manifest containing
every required object key, version, and digest. A restore is accepted only when
that manifest can be resolved completely and its generation/segment digests
match the restored database. A PostgreSQL snapshot without its matching object
checkpoint is not a consistent Knowledge Base backup.

## Database Decision

### Initial choice: PostgreSQL plus pgvector

PostgreSQL is the recommended first database because the platform already
operates it and the Knowledge Base needs more than nearest-neighbor search:

- owner-scope-aware relational constraints and transactions;
- Agent binding and source-ACL joins;
- full-text lexical search;
- JSON metadata and provider cursor state;
- asynchronous job claiming and retry state;
- HNSW vector indexes through pgvector;
- atomic generation promotion and consistent audit evidence.

Production starts on a generally available PostgreSQL release. PostgreSQL 19
may enter compatibility CI while it is beta, but it cannot become the production
baseline until PostgreSQL 19 is generally available and the exact pgvector,
backup/restore, driver, migration, extension, replication, and workload image
combination passes the full qualification matrix. An upgrade is a database
release change with rollback evidence, not a prerequisite for the database
split.

PostgreSQL 19 SQL/PGQ declares a property graph over ordinary relational vertex
and edge tables and queries it through `GRAPH_TABLE`. The graph is a read-only
logical view using PostgreSQL's normal planning and execution infrastructure;
it is not a separate native graph storage engine. This is useful for the later
bounded graph-assisted strategy because canonical entity, relation, ACL,
generation, and provenance rows remain relational and transactional. SQL/PGQ
does not by itself qualify traversal latency, memory bounds, ACL filtering, path
semantics, or graph-derived text.

Use an HNSW index for a sufficiently large BASE or DELTA vector segment and a
PostgreSQL full-text index over normalized chunk text and selected title or
heading fields. Prefer an exact scan for a small recent DELTA until measurement
justifies a separate HNSW build. Give `(knowledge_base_id, index_segment_id)` a
physical partition boundary—for example list/subpartitioning or a segment-owned
vector table—so both values are resolved before ANN traversal. A logical
generation manifest references one compatible BASE plus bounded ordered DELTAs;
it does not copy unchanged vector rows merely to obtain a new generation ID.

Core PostgreSQL full-text ranking is not assumed to provide BM25 or robust exact
identifier matching. The initial lexical candidate path combines an explicitly
named text-search configuration with an identifier-preserving field and
`pg_trgm` candidates for punctuation-heavy tokens and phrases such as
`light-portal.knowledge.base`. Language selection, parser, dictionaries,
stemming, stopwords, field weights, phrase behavior, trigram thresholds, and
ranking/fusion formula form one immutable lexical contract. A BM25 extension
may replace or supplement this path only after extension operations, upgrade
behavior, recall, latency, and license are qualified and recorded as a new
lexical contract.

A candidate segment or manifest is never attached to the active pointer before
it passes promotion gates. Detach and later purge unreferenced segments under
retention policy and the rollback deadline. Do not depend on a single cross-KB,
cross-space HNSW graph plus a post-filter, and do not let DELTA count grow without
a measured compaction policy.

Document ACL eligibility remains an exact predicate. With HNSW, selective ACL
predicates are applied after approximate index traversal, so a fixed candidate
count can under-fill results and damage recall. On pgvector 0.8 or later, enable
bounded iterative scans and escalate `hnsw.ef_search`, `hnsw.max_scan_tuples`,
and scan memory only within the retrieval profile's latency and memory limits.
For a sufficiently small authorized subset, prefer an exact scan over that
subset. Generate lexical and vector candidates independently and fuse them with
reciprocal-rank fusion. First-release HYBRID does not rerank.

Qualification compares filtered ANN results with exact authorized nearest
neighbors at 100%, 25%, 5%, and 1% authorized-corpus fractions. The initial
release floor is Recall@10 >= 0.90 at every stratum, with no authorization
leakage. The initial end-to-end service ceiling, including authorization, query
embedding, database search, and fusion but excluding Agent answer generation,
is p95 <= 1,000 ms for one KB and p95 <= 1,500 ms for up to four KBs at the
declared reference concurrency and corpus envelope. Warm-cache and cold-cache
results are reported separately. Phase 0 may tighten these proposed ceilings;
relaxing them requires an explicit design decision rather than an unnamed
"separately measured" target. MIRROR_SOURCE_ACL cannot graduate from Phase 2
until the measured corpus meets every recall and latency floor at its
representative selectivity.

Segmented retrieval qualification additionally compares the BASE-plus-DELTA
result with an exact evaluation over the generation's resolved logical corpus.
Candidate budgets account for stale base hits suppressed by replacement,
tombstone, and ACL deltas; fixed per-segment top-k values are not assumed to
preserve recall. Compaction must reproduce the same eligible corpus and meet the
same retrieval-quality floor before its new BASE manifest is promoted.

The current Hindsight vector dimension must not become an accidental Knowledge
Base contract. The first release approves one immutable embedding-space
contract per profile and records its ID and revision on every generation and
chunk embedding. Two 1,024-dimensional models may occupy unrelated vector
spaces. Dimension is therefore one checked property, not the identity. A model,
weight, dimension, normalization, distance-metric, or document-transform change
creates a new embedding-space revision, profile, and generation rather than
updating an active vector index in place. A query-transform-only revision may
reuse the document vectors only under the explicit equivalence gate above.

Model replacement therefore requires re-embedding every eligible chunk, not
merely chunks changed since the last source synchronization. Because normalized
documents and chunks are canonical reusable artifacts, that work starts at the
embedding stage rather than the connector or parser stage. Capacity planning
must include concurrent old/new vector storage, candidate HNSW build overhead,
provider tokens and cost, delta catch-up, and the retained rollback generation.

### Capacity envelope and build isolation

Phase 0 produces a capacity sheet for each launch tier with expected documents,
average and p95 chunks per document, vector count, embedding dimension, vector
projection precision, normalized-text bytes, metadata/index bytes, source growth,
and query/ingestion concurrency. Raw full-precision vector payload is
approximately `chunk_count * dimension * 4` bytes: ten million 1,024-dimensional
vectors are about 40.96 GB before row, HNSW, WAL, backup, dead-tuple, and build
workspace overhead. Measured HNSW size and build peak replace estimates in the
release gate.

The canonical embedding artifact retains the precision required for audit and
qualified rescoring. A segment projection may use `vector`, `halfvec`, or binary
quantization with higher-precision rescoring. Projection precision is not part
of mathematical embedding-space identity, but it is an immutable segment
property and must pass the same exact-neighbor recall floor before promotion.

Steady-state projected disk must remain below 60% of provisioned capacity and a
candidate build plus rollback predecessor below 80%. A build is rejected or
paused before crossing either ceiling. Re-evaluate partitioning or a separate
vector engine when the HNSW working set exceeds 70% of serving-node memory, the
declared one-year growth envelope exceeds those disk ceilings, or tuned
PostgreSQL misses a recall/latency/ingestion SLO in two qualification runs.

Bulk HNSW creation, compaction, or migration cannot run as unbounded maintenance
on the database instance serving the protected query lane. Production uses a
dedicated candidate-build instance or an equivalently isolated build pool whose
I/O, `maintenance_work_mem`, WAL, and parallel-worker caps have been load-tested
against query p95. A candidate is copied or replayed to the serving topology and
validated there before pointer promotion. The small Phase 1a pilot may share an
instance only while the same caps and a concurrent-load gate prove it stays
within the declared query ceiling.

Partitioning should be driven by measured data volume. The logical keys and
queries must make nullable owner scope and Knowledge Base pruning possible from
the start. PostgreSQL row-level security can be added as defense in depth, but
its policies must explicitly distinguish platform-global rows from
tenant-owned rows. It does not replace effective-catalog predicates, binding
validation, or trusted service identity.

### When to consider a separate vector engine

Do not add a second vector database only because the feature is called RAG.
Evaluate one when production measurements show that PostgreSQL cannot meet an
agreed recall, latency, ingestion, replication, or isolation objective after
normal indexing, partitioning, and query tuning.

The knowledge service owns a retrieval interface so the physical engine can be
replaced later without changing Agent contracts. Metadata, tenant ownership,
bindings, and audit should remain authoritative in PostgreSQL even if vector
candidate generation moves elsewhere.

### Turso qualification boundary

Turso is not an initial alternative to PostgreSQL for the shared
`light-knowledge` service. Distinguish production-proven libSQL/Turso Cloud
vector indexing from the newer Rust Turso Database engine: their vector-index,
concurrency, synchronization, SQL-compatibility, and operational contracts are
not interchangeable. Neither product is assumed to provide PostgreSQL 19
SQL/PGQ or a native property-graph contract merely because an ANN vector index
uses a graph internally.

Turso may be evaluated later for a single-user embedded, offline/local-first,
edge-cache, or database-per-tenant profile. Such a profile must not weaken the
authoritative Config Server event model or runtime authorization. Before it is
supported, a code-grounded spike must replace or account for PostgreSQL-specific
`JSONB`, arrays, `TSVECTOR`, GIN/`pg_trgm`, PL/pgSQL functions and triggers,
deferrable constraints, `LISTEN`/`NOTIFY`, advisory leadership, and
`FOR UPDATE SKIP LOCKED`; then pass identical schema, ACL non-disclosure,
generation promotion, crash recovery, concurrent writer, exact/ANN recall,
backup/restore, and operational gates. Keep the Rust storage boundary narrow,
but do not build an unqualified lowest-common-denominator SQL abstraction in
Phase 1a.

### No graph database in the first release

No first-release requirement needs a graph database. If GraphRAG is later
justified, begin with relational entity, relation, community, and provenance
tables in PostgreSQL. Introduce a graph database only when measured traversal
patterns and operational scale make the relational representation the
bottleneck.

Canonical documents, ACLs, chunks, versions, citations, and generation state
remain in the Light Portal knowledge schema even if an optional vector or graph
engine is introduced. Engine-specific namespaces are internal mappings from
knowledge_base_id and index_generation_id; they are never caller-controlled
tenant identifiers.

## Ingestion Pipeline

Each source object moves through two idempotent stages separated by durable
canonical artifacts:

Phase 1a implements the source/change-planning stages but always builds one
complete BASE candidate from their output. The routine DELTA generation stage,
passage-anchor continuity, and artifact reuse shown below become active in Phase
1b only.

~~~text
source stage:
  discover
  -> fetch metadata and permissions
  -> fetch changed content
  -> malware/type/size validation
  -> normalize and parse
  -> identify structure and language
  -> chunk with stable anchors
  -> persist immutable document versions, ACL revisions, and chunk artifacts

change-planning stage:
  compare source identity/version/content hash and artifact contract digests
  -> classify ADD | MODIFY | DELETE | ACL_ONLY | METADATA_ONLY
  -> invalidate only affected descendants

routine generation stage:
  build an immutable DELTA segment from changed artifacts
  -> validate the new BASE-plus-DELTA logical manifest
  -> atomically promote the manifest

incompatible-contract or model-migration stage:
  build an isolated complete BASE candidate
  -> catch up content, ACL, and tombstone deltas
  -> validate and atomically promote
~~~

The source-operation idempotency identity is based on source_id, stable external
object ID, operation kind, and provider version or content hash. Artifact
identity additionally includes the relevant parser, metadata, chunker,
lexical, citation-anchor, ACL-normalization, document-transform, and embedding-space
contract digests. Replaying a cursor page, webhook, or job must not create
duplicate document versions, artifacts, or DELTA operations.

An immutable chunk ID identifies exact evidence and therefore includes document
version, parser-output identity, chunker contract, offsets or section path, and
normalized text hash. It changes whenever that evidence changes. A separate
passage anchor remains stable across versions only when a provider anchor or
versioned structural-matching algorithm proves continuity. Citations retain both
identities plus source offsets or provider anchors where available.

### Chunking contract

The documentation pilot starts with structure-first chunks targeting 450 tokens,
a hard maximum of 800 tokens, and up to 64 tokens of overlap only when a natural
heading, paragraph, list, table, or code boundary cannot provide continuity.
These values are a versioned baseline to evaluate, not mutable worker defaults.
The chunker contract records target/max size, overlap, tokenizer identity,
boundary precedence, language handling, heading-prefix construction, and
normalization rules.

Heading hierarchy is prepended as labeled context to lexical and embedding
inputs while the returned passage preserves the exact source offsets. Code
fences and tables remain whole when they fit the hard maximum. Oversized code is
split on line/block boundaries; oversized tables are split by row while
repeating the header as derived context. A chunk never combines different
document versions or ACL revisions.

An optional small-to-big expansion may return the containing section around a
ranked child chunk only when the section belongs to the same document version
and ACL revision, fits the response budget, and repeats authorization. Ranking
and audit retain the child chunk as the evidence hit and identify added parent
context separately. Phase 1a returns child chunks only; context expansion must
qualify in Phase 1b before enablement.

### Ingestion budgets

Before discovery, every initial crawl and later synchronization reserves a
bounded run budget from knowledge_ingestion_policy_t. Connectors stop paginating
before exceeding object, source-byte, wall-time, or provider-call ceilings;
workers stop parse/chunk/embed work before exceeding stored-byte, chunk,
embedding-token, spend, or concurrency ceilings. A run that reaches a ceiling
becomes `PAUSED_BUDGET` or `FAILED_BUDGET`, reports the exact bounded counters,
and leaves the active generation unchanged. An authorized administrator must
approve a new estimate or narrower source scope before resume. Initial sync is
never exempt from these controls.

Derived projections maintain reverse provenance from each artifact to every
input artifact and contributing chunk. An edit, deletion, ACL change, metadata
schema change, parser change, or chunker change invalidates only descendants
whose recorded input or contract digest no longer matches. The worker either
reuses an exact compatible artifact, reconstructs the artifact from remaining
eligible contributions, or removes it; it never leaves a description or
relationship synthesized from stale source material.

Before promotion, validate at least:

- every active document version has a parse outcome;
- every searchable chunk has the expected embedding profile;
- every document, chunk, filter field, citation anchor, and ACL record conforms
  to the generation's declared metadata, lexical, and normalization contracts;
- ACL synchronization completed under source-ACL mode;
- deleted or deactivated documents have no active-generation chunks;
- vector dimensions and embedding-space ID/revision are uniform and match the
  approved profile;
- every eligible indexing and query fallback route has the same declared
  embedding-space contract;
- candidate membership, embeddings, ACL state, and tombstones have reached the
  recorded promotion watermark, with no undrained migration deltas;
- ordered segment precedence resolves to one current document state/version and
  passage anchor, document supersession leaves no older orphan chunk eligible,
  and segment counts/digests match the generation manifest;
- sampled citations resolve to the expected source object;
- aggregate source, document, chunk, and error counts are internally
  consistent.

The last valid generation remains active when validation fails. Portal shows
the failed candidate and error counts without exposing secret or document
content in logs.

### Embedding execution and workload isolation

The knowledge service, not an Agent or consumer tenant, calls
`POST /v1/embeddings`. It resolves the approved profile and sends the profile's
expected space ID and revision on every indexing and query request. The gateway
returns the actual space ID, revision, and accepted configuration generation in
non-provider-sensitive response headers only for a request that supplied the
expected-space contract or used an Alias that requires it. Ordinary SDK calls
do not receive the replica-global configuration generation. The service rejects
a missing or mismatched response before storing a vector or running similarity
search.

For a Knowledge Base Alias, every eligible deployment declares exactly the
single supported dimension in the space contract. The gateway injects that
dimension when the OpenAI request omits `dimensions` and rejects any different
value. Merely listing the contract dimension among several provider dimensions
is insufficient.

Use two internal workload Aliases and two independently admitted gateway
workload lanes:

- `kb-index` is asynchronous and throughput-oriented;
- `kb-query` is latency-oriented and has protected capacity.

The Alias names are `kb-index` and `kb-query`; the distinct workload-lane
identifiers remain `kb_index` and `kb_query`. Alias names and lane identifiers
are separate contracts and must not be substituted for one another.

The immutable space registry and gateway conformance/admission implementation
are shared platform services used by Knowledge Base, Hindsight, and
tool-description embedding. Each consumer registers its own operation, space,
data-use policy, lane, and quota. Reuse means common enforcement code and
telemetry, not shared vectors, accidental equal dimensions, or one consumer
borrowing another consumer's reserved capacity.

The Aliases may have different budgets and retry policies, but Alias permits
alone do not isolate the lanes: the shipped gateway's ingress and embedding
memory semaphores are acquired before Alias parsing. The implementation must
therefore provide distinct query and index ingress plus memory pools selected
before body capture. The preferred production mechanism is a dedicated
internal listener or gateway deployment for each lane, protected by network
policy and workload identity; a path or untrusted header alone is not an
authorization boundary. The index lane cannot borrow query-reserved ingress,
memory, provider-account, or deployment capacity.

Within the indexing lane, use bounded fair scheduling with reserved worker and
database capacity in this order:

1. known ACL revocations and document/source tombstones;
2. ordinary incremental additions and modifications needed to meet freshness
   SLOs;
3. reconciliation and anti-entropy repair; and
4. bulk reindex, compaction, and embedding-model migration backfill.

Lower-priority work cannot consume the final reserved slots for a higher-priority
class. A revocation or tombstone that requires no embedding bypasses embedding
capacity entirely but still passes the same manifest validation and atomic
publication path.

Both lanes must reference the same embedding-space ID and revision. Admission
metrics and saturation tests are reported separately. The knowledge service
also applies per-consumer-host concurrency, rate, and cost quotas before using
the shared global-KB query lane; the platform Alias ledger is a backstop, not
the tenant accounting mechanism. Query audit and chargeback retain the consumer
host even though the provider call uses a platform workload credential.

The gateway's capability-ceiling reservation remains the safe default. Before
large ingestion runs, qualify a model-specific tokenizer or conservative input
estimator for the selected space. Start with measured batches of roughly 32 to
128 chunks, not the provider maximum. When a batch has an item-specific
failure, bisect it until the bad chunk is isolated; preserve input order and an
input-hash idempotency key throughout retries.

Continuous updates use latency-bounded micro-batches with both a maximum item
count and maximum wait time; migration and compaction use separately measured
throughput batches. No fixed external-provider batch or concurrency number is a
platform default. Qualification and current provider limits determine both.

## Incremental Corpus Updates And Compaction

Routine source synchronization must be proportional to the change, not the
corpus size. A new logical generation provides an immutable audit and rollback
boundary, but it does not imply a new physical copy of every unchanged lexical
row, vector, or HNSW node.

### Change classification and dependency-scoped work

The worker determines work from trusted source identity/version evidence,
content hashes, normalized metadata, permissions, and recorded artifact
contract digests:

| Change | Required work |
| --- | --- |
| ADD | Create one document version, parse and chunk the new content, reuse or create exact-input embeddings, and add lexical/vector records in a DELTA segment. |
| MODIFY | Create a new immutable document version, add a document-scoped supersede operation before its chunks, preserve passage anchors only where continuity is proven, and rebuild changed descendants. The supersede kills disappeared passages without requiring an anchor match. |
| DELETE | Add an immediate document tombstone and remove every version/chunk from eligibility without parsing or embedding; physical purge follows the precedence rules for erasure, retention, and legal hold. |
| ACL_ONLY | Create a new immutable ACL revision and add an exact authorization delta referencing its acl_revision_id without parsing, chunking, embedding, or mutating the content version. A revocation is freshness-critical and fails closed until published. |
| METADATA_ONLY | Rebuild filter, citation, or lexical artifacts whose metadata inputs changed. Re-embed only when the qualified document input transform actually includes the changed metadata. |

A parser, chunker, metadata-schema, lexical, citation-anchor, or ACL-normalization change
invalidates only artifacts produced by the affected contract when mixed
contracts remain semantically valid. If compatibility cannot be proven, build a
complete BASE candidate. For example, a PDF-parser upgrade need not reparse
Markdown documents merely because both source types share a Knowledge Base.

### Immutable BASE-plus-DELTA manifests

A routine promotion creates a new generation manifest by referencing one
compatible BASE and one or more ordered DELTAs:

~~~text
generation G42
  BASE B7        complete corpus at watermark W100
  DELTA D108     additions and replacements through W108
  DELTA D109     ACL changes and tombstones through W109
~~~

DELTA records use deterministic operation IDs and latest-wins precedence first
by stable document identity and then by passage anchor/chunk. A document
supersede operation declares that every chunk for document D from earlier
segments is dead unless the same or a later segment activates it for the new
document version. This catches removed passages for which no replacement anchor
exists. A replacement never deletes or mutates the prior segment during
construction. The new manifest becomes visible only after validation and one
atomic knowledge_index_pointer_t transition. Failure leaves the previous
manifest and all in-flight requests unchanged.

One generation cannot compose segments from different embedding spaces,
distance metrics, or incompatible parser/chunker/metadata/ACL/lexical contracts. A
model migration creates a new BASE in the target space and may then catch up
with target-space DELTAs before promotion; it never attaches a target-space
DELTA to the old-space BASE.

### Segmented retrieval

Retrieval resolves and pins the logical generation once, then:

1. loads its ordered segment manifest and exact document-supersede, replacement,
   tombstone, and ACL-revision overlay;
2. runs lexical and vector candidate generation against the BASE and eligible
   DELTAs, using exact vector scans for small DELTAs and qualified ANN indexes
   for larger segments;
3. rejects superseded, deleted, deactivated, or unauthorized evidence before it
   can be returned, even when an older BASE produced the candidate;
4. merges vector candidates only because every segment has the same exact
   embedding-space contract, merges lexical candidates only under the same
   lexical contract, then performs the normal lexical/vector fusion;
5. resolves each surviving passage anchor to the exact document version and
   chunk selected by the pinned manifest; and
6. records segment IDs and manifest digest in retrieval audit without returning
   physical namespaces to the caller.

Per-segment top-k and over-fetch are bounded retrieval-profile settings, not
constants. Qualification measures recall against the exact resolved logical
corpus because tombstones, replacements, selective ACLs, or many small segments
can otherwise exhaust approximate candidate budgets.

### Compaction

Compaction is a derived-index maintenance operation. Trigger it from measured
segment count, delta-to-base ratio, tombstoned/superseded candidate rate,
retrieval fan-out latency, index size, or maintenance cost—not from every source
update or deletion.

The compactor resolves one pinned manifest at a canonical watermark, reuses
eligible chunks and embedding artifacts, and builds a complete replacement BASE
without connector fetches or embedding-provider calls when inputs and contracts
are unchanged. Before promotion it proves:

- document-version, passage-anchor, chunk, ACL, tombstone, lexical, and vector
  counts and digests equal the resolved source manifest;
- exact authorized retrieval returns the same eligible corpus;
- ANN and fused retrieval continue meeting approved recall and latency floors;
- no newer source delta was silently omitted; and
- rollback retention preserves the predecessor manifest and referenced segments.

Compaction publishes a new logical generation with reason COMPACTION through the
normal atomic pointer and audit path. Unreferenced old segments are detached and
purged only after every active, candidate, rollback, backup, retention, and
legal-hold reference has expired.

### Scoped embedding reuse and anti-entropy

Before calling the gateway, compute a security-scoped digest over the exact
post-transform embedding input, including any qualified title, section,
language, or task prefix. Reuse an embedding artifact only when this digest,
space ID/revision, dimension, normalization, and document-transform version all
match. A raw-text hash alone is insufficient. Cache hits and misses are audited
as bounded counts without exposing text or digests to tenant callers.

Every segment carries a versioned manifest of counts and digests by source and
artifact type. Promotion verifies it synchronously. A scheduled anti-entropy
job compares canonical documents, resolved generation membership, embedding
references, physical lexical/vector rows, ACL state, and tombstones. Missing,
orphaned, or inconsistent artifacts quarantine the affected candidate or create
bounded repair work; they never silently broaden retrieval.

## Embedding Model Upgrade And Re-Embedding

Embedding-model replacement is an expected Knowledge Base lifecycle operation,
not an emergency repair. A new provider model, fine-tuned weights, dimension,
normalization, distance metric, tokenizer behavior, or document input transform
creates a target embedding profile and isolated candidate generation. The
promoted generation continues serving through its recorded profile and space
until the candidate is explicitly promoted. Unlike a routine source update, the
migration constructs a complete BASE segment in the target vector space.

### Preflight and migration state

Before starting provider work, the knowledge service calculates a bounded
estimate from canonical chunk token counts and the qualified target profile:

- eligible document and chunk counts, total estimated input tokens, and objects
  excluded by retention or error state;
- provider cost range, qualified batch size, rate limits, available index-lane
  capacity, and estimated duration;
- temporary vector, HNSW-build, WAL, backup, and predecessor-retention storage;
- changed parser, chunker, or document-transform contracts that would prevent
  chunk reuse and expand the work to earlier pipeline stages; and
- source freshness, unresolved ACL state, legal holds, and other conditions that
  would block eventual promotion.

Estimates are planning evidence rather than billing guarantees. Starting a
migration requires an authorized target profile, an approved budget ceiling,
available temporary capacity, and an explicit decision about the rollback
window. A global Knowledge Base additionally requires platform authorization;
consumer tenants cannot initiate or alter its migration.

Use an operational migration state machine equivalent to:

~~~text
PLANNED -> BACKFILLING -> CATCHING_UP -> VALIDATING -> READY
READY -> PROMOTED -> SOAKING -> COMPLETED
SOAKING -> ROLLED_BACK
BACKFILLING | CATCHING_UP -> PAUSED -> prior resumable state
PLANNED | BACKFILLING | CATCHING_UP | VALIDATING | READY -> FAILED | CANCELED
~~~

Pause and resume preserve content watermarks, per-chunk idempotency, retry
state, and budget evidence. Cancel removes only unpromoted derived projections
and provider work; it never deletes canonical documents/chunks or changes the
active pointer.

### Snapshot, backfill, and catch-up

At migration start, record a canonical content watermark from the knowledge
service's own committed document-version, chunk, ACL, and tombstone log. An
opaque SharePoint or Confluence connector cursor is source evidence but is not a
cross-source promotion boundary.

The migration then:

1. creates the candidate generation, target-space BASE segment/partition, and
   idempotent work manifest without changing Knowledge Base runtime
   configuration;
2. reads reusable knowledge_chunk_t artifacts at the starting watermark and
   creates or reuses exact-input target-space embedding artifacts in resumable
   batches, associates them with every eligible chunk, and materializes the BASE
   vector projection;
3. keeps ordinary synchronization and the old-space active generation running;
4. records every later document, chunk, ACL, and tombstone change in an ordered,
   idempotent candidate-delta stream;
5. applies those changes as compatible target-space DELTA segments in the
   candidate manifest, including replacements, removals, metadata, and
   permission changes; and
6. uses a short promotion fence to establish a final canonical watermark, drain
   all deltas through it, reconcile aggregate counts and source state, and then
   release ordinary synchronization.

Backfill can be incremental at the system level, but a partially populated
target space is never treated as compatible with the old space and never serves
ordinary Agent traffic. The old and new ANN partitions do not share an HNSW
graph or generation manifest. New source updates may be embedded in both spaces
during catch-up, but each provider request declares and verifies its own exact
space contract.

### Evaluation and promotion

Evaluation compares complete retrieval outcomes rather than vector values or raw
similarity scores. At minimum, compare active and candidate generations on the
same authorized query set using Recall@k, nDCG or MRR, citation precision,
no-answer behavior, filtered-ANN recall, latency, and cost. A candidate must also
pass source-count, ACL, deletion, citation, expected-space, and drift gates at
its final watermark.

Start with curated offline evaluation in the Quality workspace. An optional
shadow evaluation may duplicate a production query only when tenant and data
policy permit that processing, uses an evaluation budget and isolated capacity,
does not expose candidate results to the caller, and does not retain raw query
text beyond the approved policy. The first release does not randomly send a
percentage of ordinary Agent requests to the candidate. A future live cohort
rollout requires stable binding-level assignment and explicit product and
privacy design; per-request random selection is prohibited.

The Portal evaluation command may address an authorized candidate generation,
but POST /v1/knowledge/retrieve cannot. Promotion is one transaction that:

1. verifies the candidate is still READY at the approved final watermark and
   that its evaluation evidence has not expired;
2. appends immutable pointer-transition and authorization evidence;
3. atomically changes knowledge_index_pointer_t to the candidate;
4. derives the runtime embedding profile from the new active generation without
   writing an event-sourced control-plane projection;
5. marks the predecessor superseded but retained through the rollback deadline;
   and
6. publishes an idempotent promotion acknowledgement through the knowledge
   service outbox. The Portal command processor appends
   KnowledgeBaseIndexGenerationPromotedEvent and may align desired configuration
   in its own event stream.

Every in-flight request continues using the generation it pinned at request
start. New requests see the new generation only after the committed pointer
transition. A global promotion requires release notes because it changes shared
retrieval for every active tenant binding in that environment.

### Rollback and retirement

During the bounded soak period, keep the predecessor's query Alias, embedding
profile, referenced BASE/DELTA segments, citations, and configuration evidence
available. To remain rollback-eligible after new source changes, the predecessor
must receive the same post-promotion content, ACL, and tombstone deltas under its
own space, or pass a complete reconciliation to the rollback watermark before
pointer restoration. Portal shows the extra embedding and storage cost of
maintaining this protection.

Rollback uses the same authorization and atomic pointer machinery as promotion.
It never rewrites vectors or repoints an embedding profile. If the predecessor
is stale, incomplete, outside its deadline, or depends on a retired Alias, an
emergency rollback is rejected until reconciliation or a new candidate rebuild
restores a valid generation.

After the soak window closes, retire the previous query/index Aliases when no
other generation uses them, invalidate profile-scoped query caches, detach the
superseded segment set, and purge it only after retention, backup,
legal-hold, audit, and explicit purge gates pass. Canonical source objects,
document versions, and reusable chunks follow their own retention policies and
are not deleted merely because one embedding space is retired.

Authorization removal is different from ordinary retirement. A permission
revocation, source/KB deactivation, or approved erasure immediately removes the
affected predecessor from rollback eligibility and suppresses it in every
serving generation. Rollback retention and ordinary retention cannot postpone
that suppression or an approved physical erasure. A valid legal hold may keep
inaccessible evidence in a sealed retention class, but rollback can never make
it searchable again.

## Connector Framework

Implement providers behind a connector interface rather than embedding
provider-specific behavior in Portal handlers.

A connector needs operations equivalent to:

~~~text
validateConfiguration()
testConnection()
discoverChanges(cursor)
fetchObject(externalId, version)
fetchPermissions(externalId)
resolveCitation(externalId, version, anchor)
refreshAuthorizationSubjects(subjects)
~~~

The normalized connector output includes:

- stable external object ID and parent hierarchy;
- display title, canonical URI, media type, language, and source timestamps;
- provider version, ETag, or content hash;
- normalized content or an object-store artifact;
- permission subjects and inheritance evidence;
- deletion or tombstone state;
- the next cursor or delta token.

Connector code treats cursors and delta links as opaque. It persists the value
only after the corresponding page has been processed successfully.

### Git and Markdown repository source

Add `GIT_REPOSITORY` (or the narrower `MARKDOWN_REPOSITORY`) as a first-class
source type for maintained documentation. Its non-secret configuration contains
the repository URL, branch or immutable tag, included path patterns, and
excluded path patterns; authentication remains an external secret reference.
Each successful synchronization records the last indexed commit.

Use the commit SHA plus Git blob SHA as source-version evidence. Citations add
repository, commit, path, and heading anchor to the common citation contract.
The parser preserves Markdown heading hierarchy, code fences, tables, and
links so chunks remain useful and citation anchors remain stable.

The first global pilot should be a uniform-scope `Light Platform
Documentation` Knowledge Base containing at least:

- `light-portal-doc/src/**/*.md`;
- `light-fabric/docs/src/**/*.md`.

This corpus is suitable for hybrid lexical-plus-vector retrieval and does not
require GraphRAG for the first release.

### Global sources

Sources under a global Knowledge Base are configured and synchronized by
platform administrators and workers using platform-owned secret references.
Tenant administrators can inspect redacted source metadata, freshness, and
quality evidence, but cannot change the connector scope, schedule, credential,
ACL mode, document lifecycle, or index generation.

Only content deliberately approved for cross-tenant use belongs in a global
Knowledge Base. A tenant-specific Confluence space or SharePoint library must
not become global merely because its connector can be reached by a platform
credential.

Every source has a trust tier such as CURATED_PLATFORM, TRUSTED_OWNER, or
EXTERNAL_UNTRUSTED, but all retrieved text remains untrusted instructions. A
global source also has a change-review policy. New sources, connector-scope or
credential changes, and content outside an approved signed/allowlisted release
policy remain in a candidate generation until an authorized platform review
approves them. The review records source version or commit, diff/count evidence,
reviewer, reason, and policy version. Trust tier is returned with citations so
the Agent can prefer curated evidence without treating it as authorization.

### SharePoint

Use Microsoft Graph drive and site APIs. Prefer incremental synchronization
through delta tokens, supplemented by a periodic full reconciliation and
provider notifications where practical.

Configuration should select approved sites, libraries, folders, file types,
and size limits. Use least-privilege application access, such as selected-site
permissions where it satisfies the deployment, and store credentials in the
external secret system.

Permission changes are content changes from the retrieval perspective. A
SharePoint item must not remain searchable under an old ACL merely because the
file bytes did not change.

For MIRROR_SOURCE_ACL, request the documented hierarchical-sharing and
sharing-change delta behavior where the tenant and application permissions
support it, then fetch the complete effective permission detail for changed
hierarchies. Delta annotations are discovery hints, not the sole correctness
path: inheritance changes, missed notifications, resync responses, scope
changes, and connector bugs are covered by a full permission reconciliation.
If the permission scan requires a broader Microsoft Graph permission than the
deployment approves, the source cannot qualify for MIRROR_SOURCE_ACL; it does
not silently fall back to a partial scan.

Sharing-link scopes require explicit handling. Anonymous links never grant
Knowledge Base retrieval because possession of a link is not represented in the
trusted Agent principal. An organization link maps only to a proven Microsoft
tenant/consumer-host organization subject. A users link maps only its resolved
recipients. Unknown, expired, password-only, or unresolvable link semantics fail
closed for that document.

### Confluence

Use the Confluence REST API with cursor pagination. Scope each source to
approved spaces and optional content filters. Incremental discovery can use
provider timestamps or CQL, but a periodic reconciliation remains necessary
for deletions, moves, permission changes, and missed updates.

Preserve the canonical page URL, page ID, version, space, ancestor path, title,
headings, and permission evidence for citations and administration.

Confluence content timestamps and CQL are not a permission-change feed. A
MIRROR_SOURCE_ACL source therefore performs a complete bounded restriction and
effective-access reconciliation on its configured interval. Page/content
restrictions alone do not prove view access: the connector must also account for
space permission, product access, inherited restrictions, users/groups, guests
or external collaborators, and the provider's operation semantics. It stores
the provider-effective decision and evidence rather than flattening these layers
into an unordered principal list. Any unsupported precedence or unresolved
layer denies the document.

### Uploads

Uploads use the same pipeline as remote connectors. Portal accepts the file and
metadata, stores the binary in object storage, and enqueues ingestion. It does
not parse or embed the file in the browser or the Portal request thread.

Define an allowlist of media types and bounded file sizes. Scan files before
parsing and reject encrypted or unsupported content with a visible,
non-sensitive reason.

## Authorization Model

Support two explicit source ACL modes. Mode belongs to knowledge_source_t, not
knowledge_base_t, because a single Knowledge Base may combine a curated upload
collection with a SharePoint source that mirrors provider permissions:

| Mode | Behavior |
| --- | --- |
| UNIFORM_SCOPE | Every caller allowed by consumer-tenant policy and an active Agent binding may retrieve all active documents from that source. |
| MIRROR_SOURCE_ACL | A caller must also match the current immutable ACL revision for each document from that source. |

UNIFORM_SCOPE is suitable only for a source whose complete contents are
approved for every authorized consumer of the bound Agent. It must not be used
as an implicit fallback when source permissions cannot be read.

MIRROR_SOURCE_ACL normalizes provider identities into platform subject types
such as user, group, organization role, or an explicitly approved everyone
subject. The service compares those records with trusted principal claims and
resolved group membership. A provider-effective deny wins over an allow whenever
the provider semantics define that precedence. Provider IDs and claim mappings
for a tenant-owned Knowledge Base are host-scoped.

For a source in a global Knowledge Base, MIRROR_SOURCE_ACL is permitted only when the
platform can map every source subject into a platform-wide identity or into an
unambiguous subject for the current consumer host. If a provider group from a
global source cannot be resolved safely for a tenant, retrieval fails closed
for that document. Curated cross-tenant corpora will commonly use
UNIFORM_SCOPE after the platform has approved the entire corpus for all
authorized tenant consumers. Mixing source modes does not create a least-common
denominator: retrieval evaluates the policy of the source that owns each
document before cross-source fusion.

Every MIRROR_SOURCE_ACL source records `acl_reconciliation_interval`,
`acl_max_age`, and `revocation_visibility_slo`. The initial Phase 2 ceiling for
all three is fifteen minutes; configuration may shorten it but cannot lengthen
it without a new qualification. Provider notifications or delta annotations may
reduce observed lag but never replace the sweep. If a sweep cannot complete
within the ceiling, the source must be narrowed or sharded, or remains
ineligible for mirrored retrieval. Once acl_max_age is crossed, the complete
affected source is excluded until a successful reconciliation publishes fresh
immutable ACL revisions.

Global catalog visibility is not document authorization. It permits a tenant
administrator to discover the Knowledge Base and create a host-local binding;
it does not let arbitrary users retrieve content without the Agent, tenant
policy, source state, and document ACL checks.

The runtime authorization sequence is:

1. authenticate the calling workload and obtain host, environment, principal,
   Agent actor, and delegated user evidence;
2. resolve active Knowledge Base bindings whose binding host matches the
   Agent's trusted consumer host;
3. join each binding to a Knowledge Base owned by that host or to a global
   Knowledge Base with host_id IS NULL;
4. intersect the visible bound set with an optional caller-requested Knowledge
   Base list;
5. enforce environment, Knowledge Base, source state, source approval, and the
   validity of the pinned Config Server Knowledge snapshot;
6. build the eligible document set from consumer-tenant policy, each source's
   ACL mode, and the exact current document ACL revision;
7. run lexical and vector candidate generation within that eligible set;
8. apply any future qualified reranker only to this eligible set, then return
   only eligible chunks.

Optional graph-assisted retrieval follows the same ordering. It first computes
the eligible document-version set, then limits graph expansion and description
construction to evidence contributions from that set. Filtering citations only
after graph traversal is insufficient because a node or summary may already
contain information synthesized from an unauthorized document.

The initial graph-assisted pilot is therefore restricted to Knowledge Bases
whose every included source uses UNIFORM_SCOPE, so the complete promoted
generation has one visibility boundary.
MIRROR_SOURCE_ACL is not eligible until automated tests prove that additions,
edits, deletions, permission removals, and shared entities cannot leak excluded
contributions. A global Knowledge Base remains subject to the same rule; global
catalog visibility does not make a mixed-permission graph safe.

The delegated-token boundary used by Agent runtime should be extended rather
than replaced. Retrieval audit records should include consumer_host_id, the
nullable Knowledge Base owner_host_id, Agent actor, caller subject, session or
workflow correlation, policy digest, data-boundary digest, Knowledge Base IDs,
and active index generations.

## Retrieval Design

### Strategy boundary

The knowledge service owns a small internal retrieval interface equivalent to:

~~~text
retrieve(
  authorizedKnowledgeBases,
  authorizedDocumentVersions,
  query,
  retrievalProfile,
  narrowingFilters,
  budget
) -> ranked evidence
~~~

HYBRID is the required production strategy. GRAPH_ASSISTED is an optional
strategy that may be enabled only when both the Knowledge Base has an active
strategy-qualification record and the binding-selected retrieval profile names
that strategy within the qualified constraints. The profile may reduce budgets
or select HYBRID; it cannot expand the KB's qualified set. Binding creation or
update rejects an ineligible strategy instead of waiting for runtime fallback.
Additional implementations can be evaluated behind this boundary, but all
strategies receive an already authorized corpus and return the same stable
chunk-level evidence and citation contract.

The strategy may derive separate query signals for precise entities or rare
identifiers and for broader themes or relationships. These signals can select
different candidate sources before rank fusion. This is a useful general
retrieval principle, not a requirement to reproduce another project's keyword
format, graph schema, prompts, or algorithm.

Graph descriptions and summaries can help locate evidence, but final results
remain bounded canonical chunks. Generated graph text is diagnostic retrieval
context unless it has complete contribution provenance; it is not presented as
an authoritative source citation.

### Optional authorized path planner

GRAPH_ASSISTED may use a path-pruned planner to reduce redundant graph context
while retaining the relationship between evidence items. This is one internal
planner under the existing strategy, not a caller-selectable PathRAG mode. For a
pinned generation and retrieval profile, it:

1. retains the ordinary lexical and vector chunk candidates and retrieves a
   bounded set of entity or relationship seeds from precise and thematic query
   signals;
2. constructs an eligible subgraph only from entity and relation contributions
   whose exact document versions and chunks are authorized for the request;
3. considers a bounded set of seed pairs, propagates a decaying graph signal,
   and stops expansion when the configured contribution, fan-out, hop, visited
   node/edge, memory, or wall-time bounds are reached;
4. ranks surviving paths with a versioned pathRetrievalScore, retaining
   disconnected seeds when no supported path exists instead of forcing a
   narrative connection;
5. resolves every node and relation in each path back to its complete canonical
   chunk contributions, removes repeated passage text while preserving path
   membership and order, and excludes any path with incomplete provenance;
6. fuses the resulting chunk candidates with ordinary hybrid candidates, then
   applies diversity, per-document, byte, and token limits; and
7. returns the same ranked chunk evidence plus optional additive evidence groups
   that an Agent may use to preserve relationship order under its own prompt and
   model policy.

The retrieval profile owns maximum seeds, seed pairs, paths, hops, fan-out,
visited nodes and edges, graph tokens, graph latency, and memory. Decay,
pruning, edge-origin weights, and activation thresholds are versioned planner
settings qualified per corpus; research-paper values are not defaults. A
high-degree hub, edge direction, or structural path length can be useful ranking
evidence but is not proof that a relation is important or true.

The planner may activate only when the server-owned strategy detects sufficient
multi-entity or relationship evidence and the graph budget is available. A
single-fact query, weak or ambiguous seeds, a disconnected authorized graph, or
planner failure continues through HYBRID. This fallback is recorded and uses the
same already-authorized corpus.

### Default hybrid pipeline

The first release uses:

1. Resolve and pin the active logical generation, ordered segment-manifest
   digest, and embedding-profile revision once for the complete request.
2. Query normalization and optional language detection.
3. Query embedding by the knowledge service with the active generation's exact
   expected space ID and revision. A mismatch fails before vector search.
4. Resolve the generation's latest-wins document-supersede, replacement,
   tombstone, metadata, and ACL-revision overlay.
5. PostgreSQL lexical candidate generation across eligible BASE/DELTA segments.
6. pgvector or exact candidate generation across the same compatible segments,
   with per-segment budgets and suppression of stale base hits.
7. Merge segment-local candidates, then apply reciprocal-rank fusion to the
   lexical and vector lists.
8. Diversity and per-document limits.
9. Token-budget truncation that preserves complete citation metadata.

The query string for Phase 1 must be self-contained. The Agent owns
conversation-aware rewriting of turns such as "how do I promote it?" before it
calls retrieval and records the rewritten query in its own execution evidence.
The service does not silently read conversation history. A future optional
rewrite stage must be server-owned, versioned, evaluated for semantic drift and
prompt injection, included in audit, and run before per-space query embedding.

Lexical search handles identifiers, names, exact phrases, and rare terms that
semantic search can miss. Vector search handles paraphrases and conceptual
similarity. A reranker is deferred until the LLM gateway has a canonical
`rerank` operation, pricing, usage, latency, and determinism contract; do not
model first-release reranking as an ordinary `generate` Alias.

Use a bounded, short-lived query-embedding cache keyed by consumer policy
boundary, space ID, space revision, query-transform version, normalization
version, and normalized-query hash. The cache never stores raw query text in
its key, logs, or metrics; a persistent key uses a rotated keyed digest rather
than a bare hash. Cache entries are bounded by bytes and count, expire by TTL,
are invalidated on profile retirement, and contain no provider metadata. The
consumer-policy component prevents cache timing or data-policy behavior from
becoming a cross-tenant side channel.

Retrieval policy defines hard upper bounds for candidate counts, top_k,
returned bytes, chunks per document, and total tokens. Client parameters may
only narrow those limits.

### Multi-Knowledge-Base retrieval and fusion

Phase 1a limits one runtime request to one Knowledge Base. Phase 1b supports up
to four selected, authorized bindings by default; a server-owned profile may set
a lower cap. For more than one KB, retrieval:

1. resolves each binding, qualified strategy, source policy, active generation,
   and ordered segment manifest independently in the same authorization snapshot;
2. groups query embedding work by exact space ID/revision and query-transform
   version, computing one query vector per compatible group and never reusing it
   across a different consumer-policy boundary;
3. gives each KB a qualified minimum lexical, vector, and token budget, then
   allocates remaining bounded budget by binding priority without starving any
   selected KB;
4. produces a fully authorized lexical/vector/optional-graph rank within each KB;
5. rank-normalizes each KB list and applies a second reciprocal-rank fusion over
   per-KB ranks. Raw similarity, FTS, reranker, graph, or component scores are
   never compared across KBs or spaces; and
6. applies global diversity, byte, result, and token limits while retaining all
   citations when duplicate text from different KBs is collapsed for context.

The request audit records distinct embedding spaces, per-KB budgets, candidate
counts, local ranks, fusion contribution, and fan-out timing. Binding priority
affects work allocation and deterministic tie-breaks only; it never converts a
low-ranked result into a raw cross-space score or grants access.

The response returns evidence, not an answer. Optional evidence groups describe
relationships among chunks already present in results; they do not contain a
generated answer or uncited graph narrative. This keeps citation and
authorization behavior independently testable and lets Agents decide how to use
the evidence and structure under their own prompt and model policy.

### Citation contract

Every result includes:

- knowledge_base_id, source_id, document_id, document_version_id, chunk_id, and
  passage_anchor_id when continuity is available;
- title, canonical source URI, section path, and optional page or anchor;
- source ACL mode, source trust tier, and approved source version or review ID;
- bounded text passage;
- content version and active index generation;
- combined rank and optional component scores;
- retrieval methods that contributed to the rank, such as lexical, vector, or
  graph expansion; add `reranker` only after that operation is qualified;
- timestamps needed to show source freshness.

When present, each evidence group has a strategy-independent group ID and type,
an ordered list of result chunk IDs, and optional typed relations between those
members. A RELATIONAL_PATH group may also include a diagnostic
pathRetrievalScore and planner version. Every referenced chunk must already
appear in results, every relation must resolve to authorized contribution
records, and clients may ignore the complete additive field. The response never
includes graph database identifiers, internal namespaces, raw entity
embeddings, propagation state, or an unsupported generated edge description.

chunk_id and document_version_id are the immutable evidence identity.
passage_anchor_id is a stable navigation and continuity aid, not permission to
substitute a newer document version into an audited historical result. Resolving
an anchor to current content repeats the complete Knowledge Base, binding,
source-state, document-ACL, and generation checks.

Rank scores are diagnostic, strategy/profile-scoped, and not a calibrated
similarity, authorization, or answer-confidence guarantee. The Portal may show
them in the retrieval playground, but normal Agents should consume ranked
passages, citations, and the top-level retrieval disposition. A client must not
apply a universal numeric threshold to an RRF score.

## API Contracts

### Portal control-plane actions

Keep the existing Light Portal action-based command and query style. The first
implementation can use service lightapi.net/genai, version 0.1.0, with a
Knowledge Base action family.

Suggested command actions are:

~~~text
createKnowledgeBase
updateKnowledgeBase
deactivateKnowledgeBase
deleteKnowledgeBase

createKnowledgeSource
updateKnowledgeSource
deactivateKnowledgeSource
deleteKnowledgeSource
testKnowledgeSource
requestKnowledgeSourceSync
requestKnowledgeSourceAclReconciliation
receiveKnowledgeSourceProviderNotification (workload only)

bindAgentKnowledgeBase
updateAgentKnowledgeBaseBinding
unbindAgentKnowledgeBase

requestKnowledgeBaseReindex
requestKnowledgeBaseCompaction
requestKnowledgeBaseEmbeddingMigration
pauseKnowledgeBaseEmbeddingMigration
resumeKnowledgeBaseEmbeddingMigration
cancelKnowledgeBaseEmbeddingMigration
promoteKnowledgeBaseIndexGeneration
rollbackKnowledgeBaseIndexGeneration
retireKnowledgeBaseIndexGeneration
requestKnowledgeBaseBackupCheckpoint
verifyKnowledgeBasePhysicalRestore
requestKnowledgeBasePurge
testKnowledgeRetrieval

exportKnowledgeBasePortabilityManifest
importKnowledgeBasePortabilityManifest
bindImportedKnowledgeDependencies
approveKnowledgeBaseImportBuild
abandonKnowledgeBaseImport

acknowledgeKnowledgeProjection
acknowledgeKnowledgeBaseIndexGenerationPromotion
acknowledgeKnowledgeBaseIndexGenerationRollback
~~~

Suggested query actions are:

~~~text
getKnowledgeBases
getFreshKnowledgeBase
getKnowledgeSources
getFreshKnowledgeSource
getKnowledgeSyncRuns
getFreshKnowledgeSyncRun
getKnowledgeDocuments
getFreshKnowledgeDocument
getKnowledgeIndexGenerations
getKnowledgeIndexSegments
getFreshKnowledgeIndexSegment
estimateKnowledgeBaseEmbeddingMigration
getKnowledgeBaseEmbeddingMigrations
getFreshKnowledgeBaseEmbeddingMigration
getKnowledgeMigrationEvaluations
getKnowledgeGenerationRetention
getKnowledgeBackupCheckpoints
getKnowledgePurgeEvidence
getAgentKnowledgeBaseBindings
getKnowledgeBaseImport
getKnowledgeBaseImportLineage
~~~

`exportKnowledgeBasePortabilityManifest` creates the canonical desired-state
payload and signed publication envelope, then appends exactly one
`KnowledgeBasePortabilityManifestIssuedEvent` before releasing the artifact. A
signing or append failure releases nothing.
`importKnowledgeBasePortabilityManifest`
verifies them and establishes the target `DRAFT` plus identity lineage.
`bindImportedKnowledgeDependencies` records authorized target-local mappings;
`approveKnowledgeBaseImportBuild` admits the single target-local reconciliation
only after every required mapping and policy gate passes; and
`abandonKnowledgeBaseImport` makes an incomplete import terminal without
releasing its publication identity. The two import queries expose minimized
status and source-to-target lineage without returning secrets or source content.
The three `acknowledge*` actions are workload-authenticated internal actions,
not administrator or browser operations. They make projection progress and
knowledge-service pointer outcomes durable in Portal history through an
idempotent reverse acknowledgement path.

estimateKnowledgeBaseEmbeddingMigration accepts a visible qualified target
profile and returns chunk/token counts, cost and duration ranges, temporary
storage, changed-contract consequences, and blocking conditions. It does not
change desired or active state. requestKnowledgeBaseEmbeddingMigration captures
that estimate version, budget ceiling, rollback window, expected current active
generation, and target profile. It returns an operational migration ID and
candidate generation ID rather than holding the command open.

Promotion and rollback commands require the caller's expected active-generation
ID and Knowledge Base version for optimistic concurrency. Promotion additionally
requires the READY candidate, final watermark, unexpired evaluation-evidence ID,
and release notes. Rollback requires a retained rollback-eligible predecessor
and records why the candidate was rejected. Neither command accepts host_id,
Alias, provider, space identity, or arbitrary vector-index namespace from the
browser.

Pause, resume, and cancel commands are idempotent and require the expected
migration version. Cancellation is rejected after promotion. Retirement is
allowed only for a superseded generation that is not active, is no longer
rollback-eligible, is not referenced by another active migration, and has no
retention or legal-hold blocker; physical deletion remains an asynchronous purge
operation.

requestKnowledgeBaseCompaction is an authorized derived-index maintenance
request. It accepts expected active-generation and Knowledge Base versions plus
an optional bounded reason, but never a caller-selected physical namespace. The
knowledge service chooses the eligible manifest and compaction watermark,
returns a job/candidate generation ID, and uses the normal validation, atomic
promotion, rollback retention, and purge path. Automatic compaction uses the
same contract and records the measured trigger.

testKnowledgeRetrieval may select an active/candidate generation pair only in
the separately authorized Portal evaluation contract. The knowledge service
resolves both profiles and spaces from those generation records. This diagnostic
selection is never copied into the ordinary runtime retrieval API.

Portal authorization initially follows portal.r and portal.w conventions.
Fine-grained actions can later distinguish source credential administration,
binding, retrieval testing, and purge approval. Global creation and mutation
also require an explicit platform Knowledge Base administration capability;
ordinary portal.w in a tenant context is insufficient.

Manifest export is a separately audited data-egress capability. Import into a
GLOBAL target and approval of its build require the platform Knowledge Base
administration capability and the global source change-review gate, regardless
of the source manifest's owner scope or approvals.
`abandonKnowledgeBaseImport` requires that same target-scope administration
capability because it is irreversible and permanently retires the publication
identity.

`testKnowledgeRetrieval` is a command because it consumes embedding capacity,
budget, and audit storage even though it returns diagnostic results. It is
separately authorized, rate-limited per user and consumer host, charged to an
evaluation budget, and scheduled so playground traffic cannot consume the
protected production query lane.

createKnowledgeBase accepts scope but never accepts an authoritative host_id:

~~~json
{
  "scope": "GLOBAL",
  "name": "Light Platform Documentation",
  "environment": "prod"
}
~~~

The command handler derives a tenant host for TENANT or persists null for an
authorized GLOBAL request. updateKnowledgeBase does not accept scope changes.
createKnowledgeSource or updateKnowledgeSource carries aclMode because that
choice belongs to the source, plus its trust tier, approval policy, ACL
freshness policy, reconciliation interval, and ingestion policy.

Commands return accepted configuration state or a job identifier. They do not
hold a request open for a crawl or reindex. getKnowledgeBases returns the
effective catalog for the trusted host and labels each row GLOBAL or TENANT.
Global rows are read-only unless the caller has platform administration
authority. Query responses are visibility-scoped, paginated, and
content-minimized. Document list responses omit full text; detail access is
separately authorized and bounded.

### Runtime retrieval API

Expose a stable service-owned contract:

~~~http
POST /v1/knowledge/retrieve
Authorization: Bearer <delegated workload token>
Content-Type: application/json
~~~

Example request:

~~~json
{
  "knowledgeBaseIds": ["5b6f8d30-7d57-4d36-910a-8e4094b522e5"],
  "query": "How is a production API promoted?",
  "topK": 8,
  "filters": {
    "sourceIds": ["c2aecb62-b451-4e79-a725-367893ac8c1a"],
    "languages": ["en"]
  }
}
~~~

The body deliberately has no host_id, owner scope, principal ID, claim set, or
arbitrary ACL expression. knowledgeBaseIds, sourceIds, languages, and topK only
narrow the server-authorized result. The service resolves the consumer host
from the token and derives the Knowledge Base owner scope from storage.

The query must be the self-contained retrieval query defined above. The service
also honors the trusted request deadline propagated by the gateway, clamps it to
the retrieval-profile maximum, passes the remaining budget to embedding and
database stages, and cancels outstanding fan-out when the deadline expires.

The runtime request also does not accept an engine name, graph workspace, or
index namespace. The active Agent binding and retrieval profile select a
qualified server-owned strategy. An authorized Portal evaluation endpoint may
compare candidate profiles, but that diagnostic capability does not widen the
production runtime contract.

The runtime request also never accepts an embedding Alias, model, space ID, or
provider. The knowledge service resolves those values from the promoted index
generation and embedding profile, then calls the gateway with its platform or
tenant workload credential. Tenant Agents do not call `/v1/embeddings` as part
of Knowledge Base retrieval.

Example response:

~~~json
{
  "queryId": "8d0eef7d-97d1-4676-aeb5-b24d1e2eb09b",
  "status": "COMPLETE",
  "retrievalDisposition": {
    "status": "EVIDENCE_FOUND",
    "policyVersion": "kb-evidence-gate-v1"
  },
  "results": [
    {
      "knowledgeBaseId": "5b6f8d30-7d57-4d36-910a-8e4094b522e5",
      "knowledgeBaseScope": "GLOBAL",
      "sourceId": "c2aecb62-b451-4e79-a725-367893ac8c1a",
      "documentId": "7a47556a-e97e-4f16-b418-d3bcb7c9ca4b",
      "documentVersionId": "18f9af71-5689-4b34-a9bd-c9346b89ecfb",
      "chunkId": "7d281955-0f99-40d5-83c7-62df079e73dd",
      "passageAnchorId": "49cc592d-2c9d-4a03-b22e-51d2d441a63b",
      "title": "Production Promotion",
      "uri": "https://example.atlassian.net/wiki/spaces/OPS/pages/1234",
      "section": "Approval and rollout",
      "text": "A bounded passage returned by retrieval.",
      "contentVersion": "42",
      "indexGenerationId": "56a9e721-35c6-4f06-b6a4-c5db08e6a0de",
      "sourceAclMode": "MIRROR_SOURCE_ACL",
      "sourceTrustTier": "TRUSTED_OWNER",
      "rank": 1,
      "rankScore": 0.0328,
      "retrievalMethods": ["lexical", "vector"]
    }
  ],
  "warnings": []
}
~~~

The example omits the optional top-level evidenceGroups field. When supplied,
it contains only groupId, type, ordered member chunkIds already present in
results, provenance-backed relation types between those members, plannerVersion,
and diagnostic pathRetrievalScore. It is an additive common response feature,
not a different graph endpoint, and clients that do not assemble structured
context can ignore it. The runtime request cannot require a particular planner,
set propagation parameters, or request an evidence group that the authorized
retrieval result did not produce.

retrievalDisposition is `EVIDENCE_FOUND`, `NO_QUALIFIED_EVIDENCE`, or
`UNKNOWN`. It is produced by a versioned retrieval-profile gate evaluated on
authorized rank, coverage, and citation signals; it is not answer-model
confidence. `NO_QUALIFIED_EVIDENCE` is the service's no-answer signal and may
still include bounded diagnostic warnings. `rankScore` is explicitly an
uncalibrated within-request fusion value and must not be treated as similarity
or compared across profiles, KBs, or requests.

For multi-KB retrieval, EVIDENCE_FOUND requires at least one returned fused
result, NO_QUALIFIED_EVIDENCE requires every selected KB to complete its gate
with no qualifying evidence, and UNKNOWN is used when permitted partial failure
prevents that conclusion.

### Retrieval errors, warnings, and partial results

The stable warning codes initially include:

| Code | Meaning |
| --- | --- |
| KB_SKIPPED_ACL_STALE | An otherwise authorized KB/source was excluded because its ACL revision exceeded the freshness ceiling. |
| KB_SKIPPED_GENERATION_UNAVAILABLE | An authorized KB had no usable promoted generation. |
| SOURCE_PARTIAL_INGESTION | Results use the last valid generation while a source has bounded ingestion failures. |
| DEADLINE_BUDGET_REDUCED | Optional work was skipped to honor the propagated deadline. |
| GRAPH_FALLBACK_HYBRID | Qualified graph planning failed or exhausted its bounds and authorized hybrid results were used. |

Warnings contain code, affected knowledgeBaseId/sourceId when disclosure is
authorized, retryability, and a redacted correlation ID; they never contain
document text, hidden resource names, principal lists, or provider errors.

Each binding's server-owned retrieval profile chooses `FAIL_REQUEST` or
`RETURN_PARTIAL` for operational failure across several already authorized KBs;
the strictest selected profile wins for the aggregate request. A caller may
narrow `RETURN_PARTIAL` to strict failure but cannot opt into partial behavior
that the binding disallows. Under `RETURN_PARTIAL`, an ACL-stale or unavailable
KB contributes no candidates, the response status is `PARTIAL`, and a warning
identifies the skipped authorized KB. Invalid or expired configuration,
authentication failure, an unbound requested ID, or inability to prove owner
scope always fails the complete request; partial results never bypass a trust
decision.

HTTP mapping is stable: 400 malformed or over-limit input, 401 authentication,
403 visible-but-unbound or operation-forbidden selection, 404 unknown,
not-visible, scoped document, or citation absence, 409 incompatible/effective
configuration state, 422 valid but
unsupported filter or query contract, 429 quota, 503 stale authorization
projection or unavailable required dependency, and 504 propagated deadline.
Complete, empty, and permitted partial retrieval use 200 with the explicit body
status. Every error uses a stable code, retryable flag, and correlation ID.

The initial frozen error-code mapping is:

| Code | HTTP | Retryable |
| --- | ---: | --- |
| KNOWLEDGE_INVALID_REQUEST | 400 | No |
| KNOWLEDGE_AUTHENTICATION_REQUIRED | 401 | No |
| KNOWLEDGE_FORBIDDEN | 403 | No |
| KNOWLEDGE_NOT_FOUND | 404 | No |
| KNOWLEDGE_STATE_CONFLICT | 409 | No |
| KNOWLEDGE_UNSUPPORTED_CONTRACT | 422 | No |
| KNOWLEDGE_QUOTA_EXCEEDED | 429 | Yes |
| KNOWLEDGE_CONFIGURATION_STALE | 503 | Yes |
| KNOWLEDGE_DEPENDENCY_UNAVAILABLE | 503 | Yes |
| KNOWLEDGE_DEADLINE_EXCEEDED | 504 | Yes |

Also expose an authorized document-resolution endpoint for a user following a
citation:

~~~http
GET /v1/knowledge/documents/{documentId}/versions/{versionId}
~~~

This endpoint returns bounded normalized content or redirects to the canonical
provider URI. It repeats the current authorization check and does not assume
that possession of a citation grants access.

When a result contains passageAnchorId, an authorized client may also resolve
that stable anchor against the currently pinned or current active generation:

~~~http
GET /v1/knowledge/documents/{documentId}/passages/{passageAnchorId}
~~~

The response identifies the exact resolved documentVersionId and chunkId. A
missing, ambiguous, deleted, moved-without-continuity, or unauthorized anchor is
not guessed from heading text; the endpoint returns a scoped not-found or
conflict result. Historical audit continues to use the exact version endpoint.

### MCP surface

Expose a small MCP adapter from the `light-knowledge` API application alongside
the REST routes through `light-axum`:

~~~text
knowledge.search
knowledge.get_document
~~~

knowledge.search accepts a query and narrowing filters. knowledge.get_document
resolves one authorized citation. Do not expose connector administration,
embedding values, arbitrary SQL or vector search, cross-tenant identifiers, or
provider credentials as MCP tools.

The REST and MCP transports must remain thin adapters over the same shared
authorization and retrieval application layer so they cannot drift. Do not run
MCP as a separate service or give it a distinct authorization path.

## Agent And Workflow Integration

An Agent may be bound to several Knowledge Bases, and a Knowledge Base may be
bound to several Agents. A binding can select a retrieval profile and priority
without copying the corpus.

A tenant binding to a global Knowledge Base references the global UUID
directly. It does not create a tenant copy of the corpus, connector, ACL,
chunks, or embeddings. Binding state and tenant-specific retrieval settings
remain owned by the consumer host.

At runtime:

- Hindsight recall supplies session and experience context.
- Knowledge retrieval supplies governed source evidence.
- The Agent composes both under an explicit context-token budget.
- Each category is labeled so the model can distinguish memory from source
  evidence.
- Source evidence retains citations through answer generation.

The Agent should not query every bound Knowledge Base blindly for every turn.
It can use a simple policy or routing description to choose relevant bindings,
but the retrieval service still authorizes the selected set.

Workflow data-store references should resolve to a versioned Knowledge Base
binding or identifier. Workflow definitions store references, not connector
credentials or copied chunks. Executions record the active generation used so
that a result can be investigated later.

## Portal Management Experience

Add a separate top-level GenAI workspace:

~~~text
/app/genai/KnowledgeBases
/app/genai/KnowledgeBases/:knowledgeBaseId
~~~

Do not add Knowledge Bases as a tab in the Hindsight Memory Bank workspace.
The navigation may use similar bank-first workspace patterns, but the concepts,
permissions, and lifecycle are different.

### Knowledge Base list

Provide My Knowledge Bases and Global Catalog filters over the same effective
catalog query. Every row has a prominent Global or Tenant badge. Global rows
are read-only for tenant administrators but offer Bind to Agent and Open
actions.

Show:

- name, description, environment, owner scope, and state;
- source ACL-mode summary, including any MIRROR_SOURCE_ACL freshness failure;
- source trust/change-review state and ingestion-quota utilization;
- number and health of sources;
- last successful sync and current staleness;
- active index generation and document or chunk counts;
- active embedding profile plus candidate migration state, progress, and
  promotion/rollback warnings when present;
- active BASE/DELTA segment count, delta-to-base ratio, last compaction, and a
  warning only when measured compaction thresholds or consistency checks fail;
- bound Agent count for the current tenant; only platform administrators can
  see cross-tenant binding totals for a global Knowledge Base;
- warning and failed-object counts.

For a tenant-owned row, the primary actions are open, synchronize, deactivate,
and delete. For a global row, tenant administrators can open, bind, and unbind;
only platform administrators can synchronize, deactivate, or delete. Delete is
gated by active bindings, retention, legal hold, and purge policy.

### Knowledge Base detail

Use these tabs:

| Tab | Purpose |
| --- | --- |
| Overview | State, freshness, active generation, counts, policy, and recent warnings. |
| Sources | Configure uploads, Confluence, and SharePoint sources; test connections; request sync. |
| Documents | Search document metadata, inspect versions, ACL status, parse state, and citations. |
| Sync Runs | Progress, cursor type, ADD/MODIFY/DELETE/ACL_ONLY/METADATA_ONLY counts, artifact reuse, retries, rate limiting, and redacted errors. |
| Index Generations | Active and candidate logical generations, ordered BASE/DELTA manifests, segment counts/digests, artifact and embedding reuse, compaction evidence, embedding migrations, watermarks, promotion evidence, rollback deadline, and retention state. |
| Agent Bindings | Bind or unbind Agents and choose retrieval profile and priority. |
| Access Policy | Per-source ACL mode, immutable ACL revision/freshness, claim mappings, revocation SLO, applied configuration snapshot and acknowledgement lag, trust/change-review policy, and fail-closed diagnostics. |
| Retrieval Playground | Run as the current authorized principal, inspect ranks and citations, and compare profiles. |
| Quality | Curated questions, expected documents, citation and retrieval metrics, strategy comparisons, latency, cost, and release gates. |
| Settings | Name, description, environment, retention, desired embedding profile for a first generation or future migration, deactivation, and purge. Runtime profile is read-only and derived from the active generation. |

For a global Knowledge Base:

- Sources, Documents, Sync Runs, Access Policy, Quality, and Settings are
  read-only for tenant administrators;
- Agent Bindings lists and changes only bindings owned by the current tenant;
- Retrieval Playground requires an Agent binding from the current tenant and
  runs with the current authorized principal;
- platform administrators receive the mutation controls and an aggregate view
  of consuming tenants without exposing one tenant's Agent details to another.

### Incremental update and compaction visibility

Index Generations expands a logical generation into its ordered BASE/DELTA
manifest without exposing physical database names or storage credentials. For
each segment, show kind, state, watermark range, compatible contract versions,
document/chunk/vector/ACL/tombstone counts, reuse ratios, bounded digest status,
build duration, and whether another active, candidate, or rollback generation
still references it.

Sync Runs explains why work was or was not performed. An unchanged source object
shows the matching provider version/content hash. A changed object shows its
classification and the invalidated pipeline stages. Embedding reuse reports
counts and cost avoided without displaying reusable text, raw input digests, or
cross-document identities.

Portal recommends compaction only when measured segment count, delta ratio,
suppressed-candidate rate, retrieval fan-out latency, or storage/maintenance
cost crosses policy. An authorized owner administrator may request compaction,
but cannot choose namespaces, force incompatible segments together, skip
validation, or purge referenced predecessors. Global compaction controls remain
platform-only; tenant consumers receive redacted read-only health.

Quality shows a lightweight impacted-query validation result for routine DELTA
promotion and the broader curated evaluation required for a new BASE,
incompatible contract, or embedding migration. Structural, authorization,
tombstone, citation, and manifest consistency gates always run regardless of
query-evaluation tier.

### Embedding upgrade workflow

From Index Generations or Settings, an authorized administrator can start a
guided embedding upgrade:

1. select a qualified target profile visible to the Knowledge Base owner scope;
2. review whether the change reuses existing chunks or also requires parsing or
   rechunking;
3. review document/chunk/token counts, cost and time ranges, temporary storage,
   provider capacity, candidate freshness, and rollback-window cost;
4. submit an explicit budget ceiling and rollback window;
5. monitor backfill, retries, failed chunks, delta lag, source/ACL watermark,
   index build, and validation without exposing text or vectors;
6. compare active and candidate retrieval metrics and citations in Quality;
7. promote only after every gate passes and release notes are supplied; and
8. monitor the soak period, roll back while eligible, or allow retirement and
   purge after the deadline.

The UI states plainly that a different or fine-tuned embedding model normally
requires every eligible chunk to be embedded again. Reusable chunks avoid
connector, parsing, and chunking work; they do not make different vector spaces
compatible. It also shows that old/new vector storage and, during the rollback
window, dual embedding of changed chunks are temporary migration costs.

Candidate evaluation is visually distinct from live retrieval. The Portal does
not offer a percentage-traffic slider in the first release. If shadow evaluation
is enabled by policy, the UI displays its query-handling, retention, budget, and
capacity consequences and never exposes shadow results to ordinary callers.

For a global Knowledge Base, tenant administrators see the active profile,
candidate status, release notes, planned promotion time, and rollback outcome as
read-only information. Only platform administrators can choose the target,
start, pause, cancel, promote, roll back, retire, or purge the shared generation.

### Source wizard

The source wizard is available to the owner tenant for a tenant Knowledge Base
and to platform administrators for a global Knowledge Base. It should:

1. select Git/Markdown repository, upload, Confluence, or SharePoint;
2. select or create an external credential reference;
3. test provider connectivity without exposing secret values;
4. browse and select allowed spaces, sites, libraries, or folders;
5. choose file, content, size, and language filters;
6. choose UNIFORM_SCOPE or MIRROR_SOURCE_ACL with a clear consequence;
7. choose a source trust tier, global change-review policy when applicable, and
   ACL reconciliation/freshness ceiling;
8. choose a schedule and ingestion policy;
9. review estimated documents, bytes, chunks, embedding tokens/spend, duration,
   and hard ceilings before saving;
10. enqueue the first bounded synchronization.

Portal never displays connector tokens or embedding values. Error messages are
redacted before persistence and display.

### Retrieval playground

The playground calls the same runtime retrieval path used by Agents. It shows:

- the effective principal and Agent binding used for the test;
- the active generation and source freshness;
- returned text, citation, and source authorization evidence;
- lexical, vector, and fused positions when diagnostic permission is present;
- the selected retrieval strategy and any graph expansion, with optional ordered
  evidence groups, path retrieval score, relation origins, and contributing
  canonical chunks rather than opaque graph claims;
- graph seed, pair, visited-node/edge, retained-path, pruned-path, token, timeout,
  and fallback counts when diagnostic permission is present;
- total latency and stage timings;
- warnings for stale ACLs or partial sources; add reranker health only when the
  canonical operation exists.

Add an "Explain exclusion" diagnostic that traces, without exposing hidden
content, the effective catalog, binding, KB/source state, source approval, ACL
revision/freshness, principal/group match, document supersession, generation,
candidate, and budget decision for a known authorized document reference. It
records the actor, reason, policy/contract versions, and correlation ID.

An administrator may not impersonate another user merely by entering a user
ID. Before MIRROR_SOURCE_ACL is operationally supported, Portal must add an
explicit audited authorization-simulation capability. It resolves a target
subject and current claims server-side, requires a fine-grained capability,
reason or ticket, short expiry, and complete actor/target audit, and limits a
tenant administrator to that tenant. Simulation uses the same authorization
implementation but cannot mint a delegated token, call tools, or expose content
that the simulator is not separately permitted to inspect.

## GraphRAG Decision

GraphRAG is not required to create a useful shared Knowledge Base. Its indexing
pipeline normally adds entity and relationship extraction, deduplication,
community detection, and summary generation. Those steps add model cost,
latency, evaluation complexity, and new provenance questions.

The entity and co-occurrence tables in Hindsight are not by themselves
GraphRAG. They describe relationships in Agent memory and do not provide a
source-governed document graph, community summaries, or a GraphRAG query
planner.

External graph-RAG papers and implementations are research inputs, not product
dependencies. We can independently adopt generally useful ideas such as
separating precise and thematic query signals, combining graph expansion with
raw chunk retrieval, pruning redundant graph context with relational paths,
preserving useful evidence structure, and rebuilding derived descriptions from
reverse provenance. We do not adopt another project's server, workspace model,
schema, API, prompts, fixed parameters, or tenant boundary as the Light Portal
contract.

### Deterministic structure before extracted relationships

The Light Platform Documentation pilot should begin with relationships that can
be reproduced directly from Git and Markdown structure:

- repository contains document and document contains heading;
- a Markdown link or explicit cross-reference points to another document or
  heading;
- a document or section documents an API operation, configuration key, service,
  component, implementation plan, or design decision when the source contains a
  deterministic identifier;
- repository path, commit, heading anchor, and link target provide exact
  contribution provenance.

Each entity and relation records its origin as explicit, structural, or
extracted plus the creating contract version. Semantic similarity can discover
query seeds but is not persisted as a factual relation. LLM-extracted entities
and relationships may be added later as lower-trust derived artifacts with
complete contributing chunks, extractor/prompt identity, diagnostic confidence,
and incremental invalidation. A generated description never outranks explicit
source structure merely because it is fluent.

An optional Light Portal graph-assisted strategy should:

1. ingest deterministic structural entities and typed relationships, then add
   qualified extracted entities, aliases, and relationships from immutable
   chunks where they provide measured value;
2. retain each chunk-level contribution instead of storing only one merged
   description;
3. index entity and relationship identifiers and descriptions for bounded seed
   discovery;
4. combine precise entity candidates, broader relationship candidates, and
   ordinary lexical and vector chunk candidates;
5. construct traversal state only from the request's authorized contribution
   set;
6. use a bounded path-pruned planner when it reduces redundant neighborhoods or
   community context, while retaining disconnected evidence when a supported
   path does not exist;
7. map every selected path back to canonical chunks, deduplicate repeated text
   without discarding path membership, and identify graph expansion only as a
   ranking method;
8. optionally return provenance-backed evidence groups so an Agent can preserve
   relationship order without adopting a Light-owned answer prompt; and
9. rebuild or remove affected artifacts after document, content, relationship,
   parser, extractor, or permission changes.

Consider a GraphRAG pilot only when all of the following are true:

- the hybrid RAG baseline is deployed and measured;
- a representative evaluation set contains relationship-heavy or corpus-wide
  questions that hybrid retrieval misses;
- the expected accuracy gain justifies extraction and reindexing cost;
- every entity, relation, and summary can retain document and chunk
  provenance;
- source deletions and ACL changes can remove or suppress derived graph data;
- every pilot source uses UNIFORM_SCOPE, or every MIRROR_SOURCE_ACL source has
  passed the graph-specific non-disclosure tests;
- the tenant explicitly enables the feature and accepts its cost and data-use
  policy.

The first pilot should be an optional per-Knowledge-Base index strategy behind
the same retrieval API. Use relational tables for entities, aliases,
relationships, communities, summaries, and provenance first. A client must not
need a different API merely because the server selects a graph-assisted
retrieval plan. Relational paths are normally computed at query time over the
pinned generation rather than precomputed as an all-pairs path index. No graph
database is required unless measured traversal scale makes PostgreSQL or a
bounded in-memory adjacency projection the bottleneck.

Compare strategies using the same normalized documents, chunks, embedding
profile, authorization inputs, answer model, and question set. The evaluation
must include exact facts, rare identifiers, cross-document relationships,
corpus-wide themes, time or version-sensitive questions, and questions with no
supported answer. Measure retrieval recall and ranking, citation precision,
answer faithfulness, forbidden-document rate, latency, indexing cost, and
incremental add, edit, delete, and ACL-change behavior. Pairwise LLM preference
can supplement these measurements but cannot replace them.

The answer model used for faithfulness and no-answer scoring is an external
evaluation-harness dependency, not a knowledge-service operation. Its provider,
model/version, prompt digest, decoding settings, and data-use policy are pinned
for the complete comparison; changing any of them starts a new evaluation
series rather than silently moving the baseline.

Within GRAPH_ASSISTED, compare path-pruned retrieval with bounded immediate
neighborhood and community-summary baselines. Measure unique canonical chunks,
duplicate passage tokens, path overlap, supported evidence per token, marginal
gain after each added path, graph-planner latency, and fallback rate. Corrupt the
evaluation graph with missing, stale, incorrectly directed, unsupported, and
permission-revoked edges plus erroneous entity merges and splits. The planner
must degrade to supported chunk evidence instead of fabricating a connection.
Prompt-order experiments belong to the Agent evaluation layer and must be
repeated for each qualified answer-model family; the Knowledge Base service does
not standardize the paper's prompt ordering heuristic.

## Security And Data Governance

- Treat every source document as potentially malicious prompt content.
- Treat extracted entity/relation descriptions and evidence-group ordering as
  derived untrusted content. A typed path or high path retrieval score cannot
  authorize tools, elevate a source claim, or override Agent policy.
- Clearly delimit retrieved passages and instruct Agents that evidence cannot
  authorize tools, reveal secrets, or change policy.
- Treat a platform-global source as a cross-tenant content supply chain. Enforce
  its configured approval/change-review gate before promotion, include source
  trust tier and approved source version in citations, and permit Agent policy
  to exclude lower-trust tiers. Delimiting text alone is not the prompt-injection
  control.
- Apply file-type allowlists, malware scanning, decompression limits, parser
  timeouts, and content-size limits before indexing.
- Encrypt provider secrets externally, objects at rest, database connections,
  and service traffic.
- Use explicit global or tenant object paths and scope-specific encryption keys
  when required by policy.
- Treat the portability manifest and any canonical source-artifact bundle as
  controlled egress. Separately authorize export, record it as a durable
  `KnowledgeBasePortabilityManifestIssuedEvent` with a content-minimized
  export-audit projection rather than log lines alone, write artifacts only to
  an approved encrypted destination, apply explicit retention/expiry and
  deletion rules, and require stronger content-export authorization plus
  independent object ACLs for the separately encrypted source bundle. Keep KMS
  audit authoritative for key use and Portal history authoritative for the
  administrative issuance.
- Redact tokens, document bodies, query text, and personal identifiers from
  ordinary logs.
- Never log embedding input text, vectors, workload credentials, or provider
  response bodies. Qualification evidence stores hashes, bounds, request IDs,
  space identity, and aggregate measurements only.
- Define retention separately for originals, normalized content, chunks, query
  audit, and failed-job artifacts.
- Make purge asynchronous, auditable, idempotent, and visible until all
  database, object-store, cache, and derived-index records are gone.
- Require explicit policy for sending document content to an external
  embedding or reranking provider.
- Preserve source classification and sensitivity labels where the connector
  supplies them, and allow policy to exclude unsupported classifications.

## Developer Test Strategy

Release qualification is not the developer feedback loop. CI uses a
deterministic fake embedding provider with declared space ID
`test-kb-deterministic-v1`, revision 1, fixed dimension, normalization, and
distance contract. It derives finite repeatable vectors from a versioned test
algorithm and deliberately supports mismatch, throttling, malformed vector, and
timeout modes. No CI assertion depends on a live external model or raw
similarity from a different fake-space revision.

Seeded corpora cover tenant/global scope, identical names, stable document
edits, removed passages without replacement anchors, ACL-only revisions,
lexical identifiers/punctuation, several KBs in different spaces, source trust
tiers, object-store orphans, and no-answer queries. Fast tests include:

- pure contract tests for chunking, lexical normalization, ACL normalization,
  provider precedence, document supersession, per-KB budgeting, local rank and
  cross-KB RRF, warning/error mapping, and deadline propagation;
- PostgreSQL/pgvector integration tests for effective-catalog and binding joins,
  one-snapshot authorization, exact versus ANN retrieval, BASE resolution,
  lexical/trigram candidates, atomic pointer changes, and stale-projection
  failure;
- connector fixtures for replayed/out-of-order pages, SharePoint inheritance and
  link scopes, Confluence restriction/space/product layers, incomplete sweeps,
  ACL staleness, and first-crawl quota exhaustion;
- portability fixtures proving stable payload digests across changed envelope
  metadata, signature and deny-unknown verification, same-ID/same-digest retry,
  same-ID/different-digest rejection, terminal abandonment without ID reuse,
  new-ID publication, the same manifest imported into two distinct target
  scopes yielding two independent imports while each scope stays idempotent,
  GLOBAL capability/change-review enforcement, generated
  target identities, target dependency rebinding, exactly one issuance event
  per released artifact with no signature bytes or payload content and no
  artifact released when signing or the append fails, and a tombstone that
  survives target deletion and purge with its identity binding and content
  minimization intact; and
- crash/retry tests around object staging, database commit, segment publication,
  outbox acknowledgement, orphan collection, and consistent restore manifests.

The [clean target
fixture](#cross-environment-publication-replay-and-restore) is defined with the
publication modes above. It rebuilds with the deterministic fake provider and
asserts both the replay-suppressed-effect counter and dispatcher spy: expected
replay effects are counted as suppressed and no connector, embedding, indexing,
pointer, acknowledgement, delete, or purge call escapes replay mode.

The authorization matrix crosses owner scope, consumer host, environment,
bound/unbound/inactive binding, active/inactive KB/source, UNIFORM/MIRROR source,
user/group/organization/link subject, allow/deny/unresolved mapping, fresh/stale
ACL revision, Config Server snapshot validity, and complete/partial multi-KB
policy. Every deny case asserts both zero returned content and content-free
logs/errors. A small deterministic suite runs on each change; the larger
qualification and load gates run before phase promotion.

## Reliability And Observability

At minimum, expose metrics and diagnostics for:

- synchronization lag and last successful reconciliation by source;
- ACL discovery age, reconciliation duration/coverage, revocation-visibility lag,
  stale-source fail-closed count, and unsupported provider-permission states;
- Config Server snapshot/publication identity, refresh and acknowledgement lag,
  digest or signature rejection, last-known-good use, five-second
  revocation-SLO violations, and expired-policy request failures;
- discovered, unchanged, updated, deleted, parsed, embedded, skipped, and
  failed object counts;
- ADD, MODIFY, DELETE, ACL_ONLY, and METADATA_ONLY classifications; invalidated
  parser/chunker/metadata/lexical/ACL/embedding stages; exact artifact-reuse and
  security-scoped embedding-reuse counts;
- provider throttling and retry-after behavior;
- ingestion-policy reservations and object/chunk/byte/token/spend/time ceiling
  utilization, pauses, and rejected resumes;
- queue depth, attempt count, terminal failures, and dead-letter age;
- active and candidate generation state;
- active BASE/DELTA segment count, delta-to-base ratio, per-segment candidate
  fan-out and latency, replacement/tombstone suppression rate, manifest digest
  failures, compaction reason/progress, and unreferenced-segment retention age;
- embedding-migration state, snapshot/final watermarks, reusable-chunk coverage,
  chunks and tokens completed/remaining, retry and bisection counts, effective
  throughput, budget consumed/remaining, estimated completion range, delta lag,
  temporary storage, and rollback deadline;
- active-versus-candidate quality deltas, shadow-evaluation volume when enabled,
  promotion-gate failures, rollback eligibility, and predecessor catch-up lag;
- retrieval request count, latency by stage, empty-result rate, and errors;
- lexical, vector, and fused contribution, plus reranker contribution only when
  that future operation is enabled;
- retrieval strategy, graph-expansion contribution, and strategy fallback;
- graph seed/pair counts, visited nodes/edges, fan-out and hop distributions,
  retained/pruned paths, path-planner latency/timeouts, evidence-group count,
  unique contributing chunks, duplicate-token ratio, path overlap, supported
  evidence per token, and fallback reason;
- ACL-denied candidate count and stale-ACL failures;
- embedding token or cost usage, plus reranking usage only when that future
  operation is enabled;
- embedding workload (`index` or `query`), space ID/revision, expected-space
  rejection count, route-drift quarantine count, single-query latency, and
  batch throughput without input text or vector values;
- per-consumer-host global-KB quota usage, throttling, fair-queue delay, and
  evaluation-budget consumption without query text;
- citation-resolution failures;
- candidate HNSW build CPU/I/O/WAL/memory/parallelism, serving-query p95 impact,
  and capacity-envelope headroom;
- staged-object age, orphan collection, missing referenced objects, checkpoint
  manifest completeness, and restore validation failures;
- scheduled anti-entropy lag and canonical/manifest/lexical/vector/ACL/tombstone
  mismatch or repair counts;
- owner scope, consumer tenant, Knowledge Base, Agent, generation, and query
  correlation identifiers.

Retrieval readiness covers the query database, required runtime dependencies,
and a valid applied Config Server snapshot. Whether a particular Knowledge
Base has a usable promoted generation is a scoped request result, not a reason
to remove every retrieval replica from service. Configuration validation
failure or an expired applied snapshot fails readiness and retrieval closed. A
connector or individual job
failure is reported through component health, metrics, and job state without
taking healthy retrieval for unrelated sources offline.

Job claiming uses bounded leases, attempts, backoff, and idempotency. Multiple
embedded or explicitly requested external executors may run concurrently, but
only one promotion may advance a Knowledge Base from a specific prior active
generation. The supervisor is considered healthy only while it can observe and
reconcile the durable queue; it need not have an active build task.

## Lifecycle

Knowledge Base lifecycle states should include:

~~~text
DRAFT -> ACTIVE -> DEPRECATED -> INACTIVE -> DELETING -> DELETED
~~~

Index generations should include:

~~~text
BUILDING -> CATCHING_UP -> VALIDATING -> READY -> PROMOTED
                                 \-> FAILED
PROMOTED -> SUPERSEDED -> PURGED
SUPERSEDED -> PROMOTED  (rollback only while eligible)
~~~

Index segments should include:

~~~text
BUILDING -> VALIDATING -> READY -> REFERENCED
                    \-> FAILED
REFERENCED -> UNREFERENCED -> PURGED
~~~

Segment state never determines runtime visibility by itself. Only an active,
request-pinned generation manifest makes a READY/REFERENCED segment queryable,
and reference accounting includes active, candidate, rollback, backup, and
retention manifests.

A DRAFT Knowledge Base can ingest and use the retrieval playground but cannot
serve ordinary Agent bindings. Activation requires a valid generation and
policy. Deactivation immediately removes it from new runtime retrieval while
retaining content according to policy.

For a tenant-owned Knowledge Base, the owner tenant controls this lifecycle.
For a global Knowledge Base, only a platform administrator can advance it.
Deprecating a global Knowledge Base blocks new bindings, identifies an optional
replacement Knowledge Base, and gives existing consumer tenants a visible
migration deadline. Before deactivation, Portal shows the number of affected
tenant bindings. Deletion is rejected while bindings remain unless an explicit
platform emergency policy authorizes forced removal.

Tenant administrators can unbind their Agents from a global Knowledge Base at
any time. They cannot deactivate the global root for other tenants.

Source deletion or deactivation immediately installs a deny/tombstone fence and
removes eligibility without waiting for parsing, embedding, compaction, or a
model-migration backfill. Phase 1a follows with a replacement full BASE; Phase
1b publishes the fence in a highest-priority tombstone DELTA. Physical purge
follows the erasure/retention/legal-hold precedence above. A later recreated
source receives a new source identity unless an explicit restore operation
proves continuity.

Routine document, metadata, and permission changes create a compatible DELTA
and new logical generation manifest. Parser, chunker, metadata, or ACL contract
changes may rebuild only affected artifacts when compatibility is proven;
otherwise they create a complete BASE candidate. Compaction changes physical
layout but not the resolved logical corpus.

Embedding-space changes always create a complete candidate BASE, a new embedding
profile, and a separate physical vector index. Parser, chunker, metadata, or
ACL-normalization contract changes also create a candidate generation but may
use scoped replacement DELTAs when the compatibility and resolved-corpus gates
pass. No contract change rewrites the promoted generation in place. The
[embedding upgrade workflow](#embedding-model-upgrade-and-re-embedding)
separates reusable canonical chunks from generation membership, backfills an
isolated target index, catches up through a final content watermark, and keeps
the active pointer on the predecessor until promotion. An Alias replacement
cannot silently move the existing generation to the replacement space.
Promoting a generation for a global Knowledge Base changes the shared corpus
for every active tenant binding in that environment. Promotion therefore
requires platform authorization, evaluation evidence, an audit record, and
visible release notes. Bindings follow the active generation between requests,
but every request pins the resolved generation for its complete lexical,
vector, citation, and audit lifecycle.

## Delivery Plan

The source implementation through the one-container R6 cutover is complete.
The following sequence remains the rollout and rollback-evidence procedure;
predecessor identity/configuration retirement occurs only after its qualified
rollback window.

Before adding further Knowledge phases, consolidate the runtime topology without
changing persisted domain, event, job, generation, retrieval, or authorization
contracts:

- extract job execution from the standalone worker binary into reusable library
  components and retire its Portal-event projection path;
- embed those components in `light-knowledge` behind mutually exclusive
  `external` and `embedded` execution modes;
- use the `light-runtime` merged Config Server path for Knowledge configuration
  and deployment secrets instead of a local bootstrap container;
- publish and validate the Knowledge Config Server audience snapshot, remove the
  event-consumer credential and cursor/inbox state, then cut over job claiming
  after all old claims drain or expire;
- keep the old worker image deployable for one rollback window while proving
  embedded/external parity, then remove it from the default release and
  Compose/Kubernetes topology; and
- retain one-shot CLI/Kubernetes-Job execution for approved heavy work.

### Phase 0: contract and evaluation baseline

- Approve terminology, global and tenant trust boundaries, per-source ACL modes,
  strategy qualification, warning/error taxonomy, and API schemas.
- Build a representative tenant-isolation, global-sharing, and retrieval
  evaluation corpus.
- Define and publish the immutable embedding-space contract and choose the
  initial qualified profile through the LLM control-plane read model.
- Require same-space fallback/canary routing and expected-space request and
  response headers before any durable vector is written.
- Establish the platform model-authority host plus separately admitted
  indexing/query gateway lanes, Aliases, and provider capacity with protected
  query resources.
- Define the reference capacity/concurrency envelope, enforce the proposed p95
  ceilings, and validate Recall@10 >= 0.90 at the 100%, 25%, 5%, and 1%
  authorization strata against exact authorized-neighbor baselines.
- Define question categories and deterministic Recall@k, nDCG or MRR, citation
  precision, answer-faithfulness, no-answer, and authorization measurements.
- Freeze full-BASE generation, document-supersede, tombstone, metadata, chunker,
  lexical, citation, ACL, and contract-digest semantics needed by Phase 1a.
- Publish capacity/storage math, initial ingestion ceilings, object-store backup
  checkpoint, shared embedding-registry ownership, and candidate-build isolation
  criteria.
- Threat-model connector credentials, source ACLs, prompt injection, and
  document download.
- Freeze the cross-environment portability manifest schema, the canonical
  payload and signed-envelope boundary, the export-generated publication ID and
  payload-digest idempotency identity, the source-side manifest-export and
  target-side publication aggregates with their event families and standalone
  export-audit and ledger/tombstone projections, new-identity mapping, target
  dependency binding, replay side-effect suppression, logical publication
  lineage, and the exact physical-restore marker. Raw event replay must not
  execute historical jobs or import effective generation state.

### Phase 1a: documentation pilot with full BASE generations

- Add event-backed global and tenant Knowledge Base, Source, retrieval profile,
  and host-local Agent binding configuration in Portal, compile the Knowledge
  audience snapshot, and publish it through Config Server with runtime
  acknowledgement.
- Implement nullable owner scope, partial uniqueness, effective-catalog reads,
  immutable scope, platform-only global mutation, strategy qualification, and
  one-KB runtime retrieval.
- Add the minimum PostgreSQL operational tables, consistent object storage, the
  deterministic fake embedding provider, and CI authorization matrix.
- Implement bounded Git/Markdown repository ingestion, parsing, chunking,
  embedding, lexical search, vector search, fusion, citations, and generation
  promotion.
- Build exactly one immutable BASE per candidate generation and perform a full
  rebuild when the pilot source changes. Do not implement DELTA segments,
  compaction, passage anchors, context expansion, cross-generation embedding
  reuse, upload ingestion, or multi-KB fusion in Phase 1a.
- Implement the minimal Portal list/detail, Git source status, Agent binding,
  retrieval playground, Quality view, source trust/review, and quota evidence.
- Expose the retrieval REST contract. Reject more than one selected KB with the
  stable over-limit error until Phase 1b.
- Build the global `Light Platform Documentation` pilot and evaluate hybrid
  retrieval, lexical identifiers, no-answer behavior, capacity, and full-rebuild
  cost before authorizing incremental scope.
- Publish the pilot's portability manifest into the clean target fixture with
  new identities, rebind its target dependencies, rebuild one
  complete BASE, and prove that no source-environment job, pointer, binding, or
  promotion acknowledgement became target effective state through replay.

### Phase 1b: incremental, upload, and multi-KB retrieval

- Add upload ingestion for qualified text-bearing media types and the object
  staging/orphan-collection lifecycle.
- Add content/permission change classification, dependency-scoped invalidation,
  document-level supersede records, routine DELTA promotion, stable passage
  anchors, exact-input embedding reuse within one Knowledge Base, and
  BASE-plus-DELTA retrieval.
- Add per-segment lexical/vector budgets, compaction, anti-entropy, optional
  small-to-big context expansion, and deterministic cross-KB rank fusion with
  one query embedding per distinct compatible space.
- Add the remaining Portal operational tabs, warning/partial-result diagnostics,
  exclusion explanation, and the MCP adapter.
- Promote Phase 1b only when pilot measurements show that full rebuild cost,
  freshness, or corpus growth justifies the added state machinery and every
  incremental qualification test passes.

### Phase 2: enterprise connectors and ACLs

- Add SharePoint delta synchronization and permission normalization.
- Add Confluence cursor synchronization, reconciliation, and permissions.
- Add provider notifications where useful, with reconciliation as the
  correctness path.
- Preserve connector-proven containment/reference relationships and qualify
  explicit cascade policies without using semantic graph edges for lifecycle.
- Qualify MIRROR_SOURCE_ACL, immutable ACL revisions, SharePoint link scopes,
  Confluence effective-access layers, group mapping, fifteen-minute ACL
  discovery/refresh ceilings, stale-source fail-closed behavior, and audited
  authorization simulation/exclusion explanation.

### Phase 3: production quality and operations

- Add curated query evaluations, operational dashboards, rate limiting, cost
  controls, backup and restore, and purge evidence. Add reranker profiles only
  after the gateway's canonical rerank contract is implemented and qualified.
- Add operator automation, status, audit, and recovery controls for logical
  environment publication and exact physical restore while retaining their
  distinct identity and side-effect semantics.
- Before enabling that automation, publish into a separately deployed clean
  target environment and verify authorization, artifact egress/retention,
  dependency rebinding, abandonment, target-local build/promotion, and replay
  suppression with the same contracts used by the Phase 1a fixture.
- Implement the embedding-migration preflight, resumable backfill, ordered delta
  catch-up, final promotion fence, candidate evaluation, atomic promotion,
  bounded soak, rollback eligibility, Alias retirement, and segment-set
  purge workflow.
- Add freshness-priority scheduling, per-segment manifests, scheduled
  anti-entropy, measured compaction, embedding-reference purge evidence, and
  segmented exact-versus-ANN recall qualification.
- Qualify large-corpus partitioning and horizontal worker scale.
- Record generation evidence in Agent and workflow execution audit.

### KB Embedding Qualification Gate

Durable indexing is blocked until the separate KB embedding-stability
checkpoint passes. Qualification evidence must:

- embed a fixed multi-probe corpus through every eligible fallback deployment
  and bind the result to the declared space ID and revision;
- detect silent model/provider drift with a versioned multi-probe fingerprint;
- prove expected-space mismatches fail before provider dispatch;
- prove the dimension is injected and pinned for every required-space Alias;
- verify index and query requests across gateway replicas, publication
  changes, route expiry, quarantine, and fallback without crossing spaces;
- measure single-query p95 latency separately from batch throughput and prove
  indexing cannot starve protected query capacity;
- build a candidate HNSW under declared maintenance/WAL/I/O/parallel-worker caps
  while the reference query load remains within the single-KB p95 ceiling;
- prove one consumer host cannot exhaust another host's global-KB query budget
  or concurrency;
- verify batch index/order, finite values, dimensions, retry-after handling,
  bounded backoff, request-ID capture, and input-hash idempotency; and
- prove input text, vectors, secrets, and physical provider details do not
  appear in logs, errors, metrics, or stored qualification evidence.

Before routine incremental indexing is promoted, an end-to-end update
qualification additionally must:

- exercise ADD, MODIFY, DELETE, ACL_ONLY, and METADATA_ONLY changes separately
  and in one reordered/replayed connector page;
- prove unchanged parser, chunker, and embedding artifacts are reused while
  changed contract descendants are rebuilt exactly once;
- crash workers before and after segment validation and pointer publication,
  proving there is neither a partial visible manifest nor a duplicate DELTA
  operation;
- compare segmented lexical/vector/fused retrieval with an exact evaluation over
  the resolved logical corpus at representative segment counts, tombstone rates,
  and ACL selectivity;
- prove a newer tombstone, replacement, or ACL revocation always suppresses an
  older BASE hit and is scheduled ahead of concurrent migration work;
- edit a document so one old passage disappears without a replacement anchor
  and prove the document-level supersede record removes that BASE hit;
- validate stable passage-anchor continuity and rejection of ambiguous or
  unproven matches while exact historical chunk citations remain resolvable;
- prove embedding reuse uses exact transformed-input and space identity, cannot
  cross disallowed tenant/global or policy scopes, and still produces complete
  purge evidence; and
- compact a multi-DELTA manifest into a replacement BASE, demonstrate logical
  and retrieval equivalence, atomically promote it, and retain/purge predecessor
  segments according to references and policy.

Before multi-KB retrieval is enabled, qualification also selects four bound KBs
across at least two incompatible spaces and proves per-space embedding grouping,
per-KB minimum/priority budgets, local-rank-only RRF, partial/strict failure,
deadline cancellation, deterministic tie-breaks, and the p95 ceiling without
raw cross-space score comparison.

Before the first production model upgrade, an end-to-end Knowledge Base
migration qualification additionally must:

- switch a representative corpus to a different space while source
  synchronization, edits, deletions, and ACL changes continue;
- prove unchanged chunks are reused without connector fetch, parse, or chunker
  execution while every eligible chunk receives a target-space embedding;
- interrupt and resume workers at several backfill and catch-up boundaries
  without duplicate vectors, skipped deltas, or budget-accounting drift;
- enforce the accepted cost ceiling and leave the active generation unchanged
  when the migration pauses, fails, exceeds policy, or is canceled;
- prove candidate quality is evaluated without cross-space score comparison and
  without candidate selection through the runtime API;
- promote while queries and synchronization are concurrent and prove each query
  observes exactly one pinned generation; and
- apply post-promotion content and permission deltas, roll back within the soak
  window, and prove the restored generation is current and authorized before the
  predecessor is later retired and purged.

The existing OpenAI-compatible `/v1/embeddings` body remains unchanged. This
gate adds Light-specific request and response headers and control-plane
invariants for durable vector consumers; ordinary OpenAI SDK calls may omit the
expected-space headers, but such calls are not qualified to write or query a
Knowledge Base index.

### Phase 4: optional GraphRAG pilot

- Select the global Light Platform Documentation corpus or another global or
  tenant corpus whose included sources all use UNIFORM_SCOPE and which has
  relationship-heavy and corpus-wide questions.
  Add a MIRROR_SOURCE_ACL corpus only after the uniform pilot passes.
- Build deterministic repository, document, heading, link, API-operation,
  configuration-key, service, and design-reference relationships before adding
  LLM-extracted graph artifacts.
- Add provenance-preserving graph extraction, bounded authorized path retrieval,
  and optional structured evidence groups behind the existing API.
- Compare HYBRID and GRAPH_ASSISTED using identical source versions, chunks,
  embeddings, authorization inputs, budgets, and answer models.
- Within GRAPH_ASSISTED, compare path pruning with bounded immediate-neighborhood
  and community-summary baselines; do not expose those planners as runtime API
  choices.
- Compare quality, citation accuracy, faithfulness, unique evidence per token,
  redundancy, latency, indexing and query cost, update behavior, and ACL
  correctness with the hybrid baseline.
- Exercise incremental add, edit, delete, and permission-removal scenarios and
  prove that no stale graph contribution remains retrievable.
- Exercise missing, stale, unsupported, incorrectly directed, and
  permission-revoked edges, entity merge/split errors, high-degree hubs,
  disconnected seeds, graph-budget exhaustion, and planner timeout.
- Promote GraphRAG only for tenants and Knowledge Bases where the evidence
  supports it.

## Acceptance Criteria

Each criterion is tagged with the earliest delivery gate that must enforce it.
Phase 1a is complete when every P1a criterion passes; later phases add their own
criteria without postponing the core trust boundary:

- **[P1a]** The default deployment has exactly one long-running Knowledge
  container. No bootstrap, Portal-event consumer, projector, or idle builder
  container is required for startup, configuration convergence, ingestion,
  maintenance, or retrieval.
- **[P1a]** `light-knowledge` starts from Config Server merged configuration plus
  deployment-secret references. A Config Server outage follows the declared
  last-known-good/startup policy, while a missing required secret fails startup
  without logging its value.
- **[P1a]** The typed Config Server loader conditionally fetches the authenticated
  Knowledge audience snapshot, validates its target, schema, digests, signature,
  validity, and compatibility, stages and atomically applies the complete
  published control-replica set, acknowledges the result, and converges after
  refresh loss or process restart without reading Portal events.
- **[P1a]** Controller delivery loss cannot lose administrative intent. A direct
  controller work request is idempotent, returns a durable job ID, and pins an
  already published Config Server snapshot or is limited to a non-authoritative
  runtime operation.
- **[P1a]** With no eligible job, no build task remains active and the supervisor
  performs no sub-second polling. On notification or fallback reconciliation it
  claims at most the configured concurrency, and every job task exits after a
  terminal, paused, or retryable transition.
- **[P1a]** Concurrent indexing at the maximum admitted embedded capacity keeps
  single-KB retrieval p95 at or below 1,000 ms and cannot consume query-reserved
  database, gateway, memory, or blocking-thread capacity.
- **[P1a]** Shutdown stops new controller commands, configuration refreshes, and
  job claims;
  drains or safely releases active work within the shared deadline; preserves
  recoverable leases and idempotency; and closes all API and job
  database pools without force-killing the container.
- **[P1a]** The optional CLI/Kubernetes-Job path runs the same engine and produces
  byte- and row-equivalent job, artifact, generation, acknowledgement, audit,
  and failure results as embedded execution for the same frozen input.
- **[P1a]** Every retrieval request pins one validated immutable Config Server
  Knowledge snapshot and uses one transactionally consistent Knowledge-database
  snapshot for its version-matched published control replicas plus operational
  ACL, generation, and candidate state. An
  unacknowledged deny remains visibly PENDING, snapshot-activation-to-effective
  deny meets five seconds, and invalid or expired policy returns no content.
- **[P1a]** Authoritative Knowledge administration and events remain in the
  Config Server database; Portal publishes their Knowledge audience projection
  as an immutable Config Server snapshot. High-volume operational and derived
  search state resides behind the logical `knowledge` database boundary.
  Colocated and isolated deployments produce equivalent jobs, generations,
  retrieval results, and audit without cross-database joins, foreign keys,
  foreign data wrappers, or distributed transactions.
- **[P1a]** A crash before or after applying a Config Server snapshot leaves
  either the complete prior snapshot or the complete candidate active, causes no
  duplicate operational side effect, and produces an idempotent acknowledgement.
- **[P1a]** Compatibility mode uses the same Config Server API and Knowledge-only
  database role as isolated mode even when the databases are physically
  colocated; Light Knowledge has no Portal event-store or projection credential.
- **[P1a]** Portal has no SQL read or write path to Knowledge operational state.
  Work commands use the Portal transactional delivery outbox and private
  idempotent Knowledge command API; promotion acknowledgements use signed
  assertions and Knowledge-local acknowledgement/outbox completion. Lost
  responses, duplicates, and either-side restarts leave a bounded backlog and
  converge to `ACKNOWLEDGED` without duplicate effects.
- **[P1a]** Every data-plane foreign key, trigger, function, and cascade-policy
  registry row resolves only Knowledge-local tables after the split.
  `validate_knowledge_index_generation_profile()` and
  `promote_knowledge_base_generation()` preserve their validation and atomic
  promotion contracts through pinned snapshot/profile digests and local
  operational roots, and fresh/upgraded Config Server cascade-policy validation
  remains clean.
- **[P1a]** Config Server acknowledgement authorization admits the consolidated
  `light-knowledge` workload principal before cutover, admits both old and new
  principals during the rollback window, and removes the worker principal only
  when rollback support is retired. Development and installer configuration-
  application and deny smoke tests exercise the real configured principal
  rather than a local shared ID.
- **[P1a]** Production uses a generally available PostgreSQL plus qualified
  pgvector build. PostgreSQL 19 remains non-production until GA and the complete
  compatibility/rollback matrix passes; Turso is not an initial supported
  backend.
- **[P1a]** The documentation pilot builds one complete BASE, accepts one KB per
  request, and rejects unimplemented DELTA, passage-anchor, reuse, upload,
  context-expansion, MCP, and multi-KB behavior rather than simulating it.
- **[P1a]** Punctuation-heavy identifiers and exact phrases pass the lexical
  quality set under a recorded lexical contract; a lexical contract change
  cannot silently compose incompatible projections.
- **[P1a]** The initial crawl respects document/chunk/byte/token/spend/time
  ceilings and leaves the active generation unchanged on budget exhaustion.
- **[P1a]** A global source cannot promote outside its approved change-review
  policy, and every citation exposes its trust tier and approved source version.
- **[P1a]** Responses expose a versioned retrieval disposition and uncalibrated
  rankScore, plus stable warnings/errors; clients are not required to infer
  no-answer from a universal numeric threshold.
- **[P1a]** Object staging, orphan collection, checkpoint backup, and restore
  validation prove PostgreSQL and object-store consistency.
- **[P1a]** Publishing the documentation pilot into the clean target fixture
  creates new target identities and ordinary target creation events, imports no
  secret or active binding, starts with no active generation, and becomes
  retrievable only after a target-local rebuild and promotion passes every
  applicable gate.
- **[P1a]** Projection replay and portability import execute no historical sync,
  reindex, migration, promotion, rollback, delete, or purge side effect. The
  replay-suppressed-effect counter and dispatcher spy provide fixture evidence;
  a source promotion acknowledgement cannot establish target effective state.
- **[P1b]** Multi-KB retrieval computes one query embedding per compatible
  space/transform group, ranks within each KB, applies cross-KB RRF only to
  local ranks, and obeys qualified per-KB/fan-out budgets.
- **[P2]** Every ACL-only change creates an independent immutable ACL revision,
  and every segment/document eligibility decision names the exact revision.
- **[P2]** SharePoint/Confluence MIRROR_SOURCE_ACL discovery and full
  reconciliation meet the fifteen-minute ceiling; stale, partial, unresolvable
  link/restriction, or incomplete effective-access state excludes the source.
- **[P3]** Revocation or approved erasure immediately invalidates rollback for
  affected evidence; rollback retention never restores it to retrieval.

- **[P1a]** Tenant A cannot list, bind, retrieve, resolve a citation from, or infer the
  existence of Tenant B's Knowledge Bases.
- **[P1a]** Tenant A and Tenant B can both list the same active global Knowledge Base
  without receiving copies with tenant host IDs.
- **[P1a]** A tenant administrator can bind a global Knowledge Base to Agents in that
  tenant but cannot mutate its sources, credentials, content, policy,
  generation, or lifecycle.
- **[P1a]** A tenant Agent cannot retrieve from a visible global Knowledge Base until an
  active binding exists for that Agent and consumer host.
- **[P1a]** By-ID reads reject Tenant B's tenant-owned Knowledge Base but accept a visible
  global Knowledge Base subject to normal operation authorization.
- **[P1a]** Global retrieval audit records contain the non-null consumer host and a null
  owner host without exposing one tenant's binding details to another.
- **[P1a]** An unbound Agent receives no results even if it knows a Knowledge Base UUID.
- **[P1a]** Request filters cannot widen trusted tenant, Agent, source, or principal
  scope.
- **[P1a]** Changing the retrieval strategy does not change the public retrieval,
  citation, authorization, or audit contract.
- **[P1a]** Runtime clients cannot select a graph workspace, engine namespace, or
  unqualified retrieval strategy.
- **[P2]** MIRROR_SOURCE_ACL returns no content when a mapping or permission refresh is
  incomplete beyond policy.
- **[P1a]** Synchronizing the same provider cursor page twice is idempotent.
- **[P1b]** A routine ADD, MODIFY, DELETE, ACL_ONLY, or METADATA_ONLY update publishes a
  bounded DELTA and new immutable logical manifest without copying every
  unchanged vector or rebuilding the complete BASE.
- **[P1b]** ACL_ONLY and DELETE changes require no embedding, take priority over bulk
  indexing, and suppress older BASE/DELTA hits in the next promoted manifest.
- **[P1b]** Artifact dependency and contract digests cause only changed descendants to be
  rebuilt; exact compatible artifacts are reused and incompatible contracts
  cannot be composed in one generation.
- **[P1a]** A document edit creates a new immutable version and citations identify the
  version returned.
- **[P1b]** A passage anchor resolves across versions only with proven continuity, while
  every result and audit retains the exact document-version and chunk identity.
- **[P1a]** A source deletion disappears from the replacement generation without
  corrupting the last valid generation.
- **[P2]** A permission removal disappears from eligibility within its
  revocation-visibility SLO without corrupting the last valid content version.
- **[P4]** An optional graph-derived entity, relationship, description, or summary is
  rebuilt or removed when any contributing document is edited, deleted, or
  loses authorization.
- **[P1b]** Deleting a parent cascades only through a connector-proven lifecycle relation
  and explicit source policy; a hyperlink, semantic similarity edge, or
  graph-extracted relationship never authorizes cascade deletion.
- **[P4]** A graph-assisted result resolves to authorized canonical chunks; an opaque
  generated graph description is never the sole citation.
- **[P4]** When graph-assisted path retrieval is enabled, every seed, visited node,
  relation, path member, and evidence-group member is derived from the
  request-pinned generation and authorized contribution set before traversal.
- **[P4]** A pathRetrievalScore is exposed only as diagnostic ranking evidence. It never
  appears as factual confidence, permission evidence, or a replacement for exact
  chunk and relation-contribution citations.
- **[P4]** Every evidence-group member already appears as an authorized result chunk,
  every typed relation has complete contribution provenance, and clients may
  ignore the optional structure without changing the underlying evidence.
- **[P4]** Seed, pair, fan-out, hop, visited-node/edge, path, token, latency, and memory
  limits are enforced. Disconnected evidence, pruning exhaustion, timeout, or
  planner failure produces bounded authorized hybrid results or a scoped error,
  never an invented path or a wider corpus.
- **[P4]** Missing, stale, unsupported, incorrectly directed, or permission-revoked graph
  edges and erroneous entity merges/splits cannot leave an unauthorized or
  uncited claim retrievable.
- **[P4]** A relational-path cache, if implemented, cannot cross generation,
  authorization, tenant, principal, policy, planner-version, retrieval-profile,
  or normalized query-signal boundaries and participates in normal purge
  evidence.
- **[P1a]** A failed candidate generation leaves retrieval on the previous promoted
  generation and displays the failure in Portal.
- **[P1a]** An embedding Alias with missing or mixed space contracts cannot publish, and
  an expected-space mismatch cannot reach a provider.
- **[P1a]** Every stored vector records the exact creating profile/revision and space
  ID/revision, while every promoted generation records the exact query profile
  and vector space it selected.
- **[P3]** An embedding-only migration reuses unchanged canonical chunks and does not
  refetch source content, rerun parsing, or rerun chunking; a changed parser or
  chunker contract invalidates that reuse explicitly.
- **[P3]** Old-space and new-space vectors never occupy the same ANN index, and
  evaluation never compares or merges their raw similarity scores.
- **[P3]** A model migration records a starting content watermark, applies every later
  content, ACL, and tombstone delta, and cannot become READY or PROMOTED until a
  final reconciliation proves it current at the promotion watermark.
- **[P3]** Selecting a desired target profile cannot affect live retrieval. The active
  generation remains authoritative until one atomic pointer transition changes
  the generation and its derived runtime profile together.
- **[P3]** A failed, paused, canceled, or incomplete migration leaves the previous
  generation serving without changing its profile, segment set, or
  citations.
- **[P3]** Candidate retrieval is available only to authorized evaluation commands in
  the first release. Ordinary Agent requests cannot choose a candidate or be
  randomly routed between active and candidate generations.
- **[P3]** Promotion retains a rollback-eligible predecessor through the configured
  deadline. Rollback is atomic and succeeds only when that predecessor has
  received all required deltas or passed a fresh reconciliation gate.
- **[P3]** Portal shows migration scope, token/cost/time and temporary-storage estimates,
  progress and delta lag, quality evidence, promotion authorization, rollback
  deadline, and retirement state without exposing document text or vectors.
- **[P1a]** Index and query workload Aliases use the same space while ingestion load
  cannot starve protected live-query capacity.
- **[P1a]** One consumer tenant's global-KB retrieval volume cannot exhaust another
  tenant's query budget or concurrency.
- **[P1a]** Filtered ANN meets Recall@10 >= 0.90 against exact authorized
  neighbors at the 100%, 25%, 5%, and 1% strata and meets the declared p95
  ceiling.
- **[P1a]** All retrieval stages use one request-pinned index generation even when a
  promotion occurs concurrently.
- **[P1b]** Every retrieval stage also uses that generation's one ordered segment-manifest
  digest; a newer replacement, tombstone, metadata, or ACL delta cannot be
  omitted for an older BASE candidate.
- **[P1b]** Segmented ANN/fusion meets the approved recall floor against the exact resolved
  logical corpus at representative segment counts and tombstone rates.
- **[P1b]** Compaction produces a logically and retrieval-equivalent BASE before atomic
  promotion, and a failed compaction leaves the prior manifest active.
- **[P1b]** Exact-input embedding reuse cannot cross a disallowed tenant, global, data-use,
  encryption, residency, retention, or legal-hold boundary, and last-reference
  deletion produces complete physical purge evidence.
- **[P3]** A model, dimension, normalization, distance, or document-transform change
  creates a new space/profile candidate index instead of mutating a promoted
  generation. A query-transform-only revision reuses document vectors only
  after the explicit equivalence gate passes.
- **[P2]** SharePoint and Confluence throttling is retried according to provider
  guidance without busy looping.
- **[P1a]** Every retrieval result has a resolvable, authorized citation.
- **[P1a]** Retrieval and Portal APIs never expose embedding values or connector
  credentials.
- **[P1a]** Hindsight memory and Knowledge Base retrieval can both participate in one
  Agent turn without sharing lifecycle or authorization state.
- **[P1a]** Purge evidence covers PostgreSQL, object storage, caches, and every
  applicable derived index/artifact. P1b adds DELTA, embedding-reference, and
  passage-anchor evidence; P4 adds graph projections.

## Open Implementation Decisions

The architecture above does not depend on these choices, but implementation
planning must settle them:

- the approved object-store implementation and encryption-key model;
- initial parsers and media-type limits, plus the post-Phase-1a roadmap and
  authorization/citation contract for OCR, images, scans, and spreadsheets;
- the initial qualified embedding-space contract, platform model-authority
  host, and separately admitted LLM gateway indexing/query lanes and Aliases;
- the physical identity and deduplication rules for canonical chunks, segment
  operations, immutable embedding artifacts, chunk/artifact references, and
  materialized ANN rows;
- canonical serialization and digest algorithms for parser, chunker, metadata,
  lexical, citation-anchor, ACL-normalization, transform, and projection
  contracts plus the dependency-invalidation planner;
- whether evaluation retains or adjusts the Phase 1a 450-token target,
  800-token maximum, 64-token overlap, heading prefix, code/table behavior, and
  later small-to-big context policy;
- passage-anchor creation and continuity algorithms, provider-anchor precedence,
  ambiguity behavior, and anchor retention across moves and renames;
- embedding-artifact reuse scope, reference accounting, keyed-digest and
  encryption strategy, side-channel controls, and last-reference purge proof;
- BASE/DELTA segment size/count limits, exact-versus-HNSW crossover,
  per-segment candidate budgets, compaction triggers, and compaction resource
  isolation;
- segment vector projection choice (`vector`, `halfvec`, or binary-quantized
  candidate search with higher-precision rescoring), measured HNSW overhead,
  and dedicated build-instance/import mechanism;
- lexical language configurations, identifier field, trigram thresholds,
  field weights, ranking formula, and whether an operationally qualified BM25
  extension adds enough value to replace or supplement core FTS;
- metadata-schema evolution, required-field validation, backfill policy, and
  compatibility rules for composing old/new segment metadata;
- connector-proven document relationship types and the narrow lifecycle rules
  that permit cascade tombstones without treating semantic graph relations as
  ownership;
- the canonical content-log implementation, ordering guarantees, promotion
  fence, and reconciliation algorithm used while source synchronization remains
  active during a long embedding migration;
- embedding-migration estimate tolerances, budget-overrun behavior,
  pause/resume scheduling, and how provider price revisions affect an accepted
  estimate;
- the rollback soak duration, whether predecessor deltas are always dual
  embedded or reconciled only on demand, and the extra-capacity policy for
  global Knowledge Bases;
- the privacy, tenant-consent, sampling, retention, and capacity policy for any
  optional shadow evaluation; the first release has no live random-traffic
  canary;
- the physical KB/segment partition lifecycle, iterative-scan bounds, exact
  search crossover, and ACL-selectivity recall thresholds beyond the initial
  all-strata Recall@10 floor;
- per-consumer-host global-KB quota defaults, chargeback policy, and fair
  scheduling algorithm;
- ingestion-policy defaults by tenant/KB/source tier, reservation granularity,
  budget-increase approval, and restart behavior after PAUSED_BUDGET;
- object-store versioning implementation, staged-object grace period,
  checkpoint-manifest format, and restore/orphan scan frequency;
- portability manifest canonical serialization, signing algorithm and key
  rotation, logical publication tooling, optional canonical source bundle
  format, dependency-binding workflow, import-tombstone reporting horizon,
  export-audit retention horizon and its relationship to platform audit
  retention, and the operator surface that keeps Portal projection replay, logical
  publication, and physical restore unambiguous;
- query-embedding cache size, TTL, keyed-digest rotation, and policy-boundary
  rules;
- the exact SharePoint/Confluence sweep sharding needed to meet the fifteen-minute
  ACL ceiling, group-membership resolution/cache policy, link/restriction edge
  cases, and stricter thresholds for particular source classifications;
- per-binding strict/partial operational-failure policy defaults, evidence-gate
  calibration, and stable warning-code extension process;
- the platform capability and approval workflow for global creation,
  source change review, generation promotion, deprecation, and emergency removal;
- ownership and rollout of the shared embedding-space registry/conformance/lane
  component across Knowledge Base, Hindsight, and tool-description consumers;
- deployment reference concurrency and tighter SLOs beyond the proposed launch
  ceilings, plus the measurements that trigger partitioning or a separate
  vector engine;
- the qualification threshold and cost policy for enabling GRAPH_ASSISTED;
- the deterministic entity/relation taxonomy for Git and Markdown, origin and
  trust weighting for explicit, structural, and extracted relations, and
  handling for high-degree index pages and ambiguous identifiers;
- path-planner activation, seed and pair selection, decay/pruning/scoring
  version, fan-out/hop/visited/path/token/latency/memory limits, and safe fallback
  policy;
- the strategy-independent evidenceGroups schema, relation-type exposure,
  deduplication that preserves path membership, Agent consumption contract, and
  whether the first graph pilot returns it outside Portal diagnostics;
- whether query-derived relational paths need a cache and, if so, its
  generation/authorization/query key, TTL, reference accounting, invalidation,
  and purge policy;
- whether and how MIRROR_SOURCE_ACL can safely qualify for graph-assisted
  retrieval without partitioning the graph by visibility boundary;
- query-audit retention and whether raw query text is stored, hashed, or
  omitted by policy.

## References

Current Light Portal design and implementation references:

- [Agent Memory Event Refactor](../agent-memory-event-refactor.md)
- [Tool Description Embedding Population](../tool-description-embedding.md)
- [Portal Event](../portal-event.md)
- [Light Portal Fine-Grained Authorization](../light-portal-fga.md)
- [Global And Tenant Entity Scope](global-tenant-entity-scope.md)
- [LLM Gateway Topology Per Host And Environment](llm-gateway-topology.md)

External implementation references:

- [pgvector filtering and iterative scans](https://github.com/pgvector/pgvector#filtering)
- [pgvector half-precision and binary quantization](https://github.com/pgvector/pgvector#half-precision-vectors)
- [PostgreSQL text-search configuration](https://www.postgresql.org/docs/current/textsearch-configuration.html)
- [Microsoft Graph driveItem delta](https://learn.microsoft.com/en-us/graph/api/driveitem-delta?view=graph-rest-1.0)
- [Microsoft Graph sharing-link scopes](https://learn.microsoft.com/en-us/graph/api/driveitem-createlink?view=graph-rest-1.0)
- [Microsoft Graph permissions reference](https://learn.microsoft.com/en-us/graph/permissions-reference)
- [Confluence REST API v2](https://developer.atlassian.com/cloud/confluence/rest/v2/intro/)
- [Confluence content restrictions](https://developer.atlassian.com/cloud/confluence/rest/v1/api-group-content-restrictions/)
- [Confluence Query Language](https://developer.atlassian.com/cloud/confluence/advanced-searching-using-cql/)
- [Incremental RAG update patterns](https://particula.tech/blog/update-rag-knowledge-without-rebuilding),
  consulted as practitioner input for change classification, delta indexing,
  artifact reuse, and validation; its example timing, batch, and concurrency
  numbers are not Light Platform SLOs or defaults
- [Microsoft GraphRAG methods](https://microsoft.github.io/graphrag/index/methods/)
- [Microsoft GraphRAG query overview](https://microsoft.github.io/graphrag/query/overview/)
- [LightRAG paper](https://arxiv.org/html/2410.05779v3) and
  [reference implementation](https://github.com/HKUDS/LightRAG), consulted as
  comparative research rather than a runtime dependency or product contract
- [PathRAG paper](https://arxiv.org/html/2502.14902v2), consulted for bounded
  relational-path retrieval, redundancy reduction, structure-preserving evidence,
  and graph-sparsity evaluation; its algorithm, prompt order, parameters, and
  reported quality or token results are research hypotheses rather than Light
  Platform defaults or SLOs
