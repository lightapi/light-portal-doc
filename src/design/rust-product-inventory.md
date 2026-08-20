# Rust Product And Portal Service Inventory

## Status

Code- and deployment-grounded inventory as of 2026-08-19.

This inventory answers three separate questions:

1. which externally useful Rust products and runtime services exist;
2. which customer or operator feature families each product exposes; and
3. whether each feature is production-ready in the current repository and
   deployment evidence.

It also includes the Java Light Portal command/query services hosted by
`hybrid-command` and `hybrid-query`. Those services are not Rust products, but
they are the control plane that configures and manages the Rust products and
therefore belong in the operational inventory.

## Readiness Vocabulary

| Status | Meaning |
|---|---|
| **Production-ready** | Implemented, enabled in a supported production profile, and backed by current release/deployment qualification with no known blocker in the reviewed scope. |
| **Conditional** | Implemented and useful, but production use still depends on a deployment-specific gate, stable release artifact, security configuration, or qualification evidence. Treat this as **not yet proven production-ready** for a new deployment. |
| **Development** | Implemented locally or in component/integration gates, but the product documentation or deployment still calls out missing runtime, scale, recovery, security, or promotion evidence. |
| **Partial** | Only part of the advertised contract is implemented, or the current implementation contains a scaffold/stub path. |
| **Proposed** | Design exists, but it is not an available product feature. |

The status is intentionally conservative. A passing unit test or a service in
`all-in-lt` proves implementation or local integration; it does not by itself
prove production readiness. Image tags ending in `-dev`, `SNAPSHOT`, or
`latest`, default-off production switches, placeholder health checks, and an
explicitly pending live gate prevent a **Production-ready** classification.

## Product Boundary

The following are counted as products or independently deployable product
services:

| Product or service | Source | Primary purpose | Overall readiness |
|---|---|---|---|
| Light API | `light-fabric/frameworks/light-axum`, `light-example-rs` | Build small Rust REST or MCP services on the common Light runtime. | **Conditional**: framework and examples exist; there is no single Light API production binary or current product-level qualification record. |
| Light Gateway | `light-fabric/apps/light-gateway`, `light-pingora` | API microgateway, BFF, MCP gateway, WebSocket gateway, and shared policy enforcement point. | **Conditional** for the core proxy/BFF surface; advanced profiles have the more restrictive statuses below. |
| LLM Gateway profile | Same `light-gateway` binary with the LLM handler/profile | Governed OpenAI-compatible inference across provider deployments. | **Development**: extensive implementation exists, but production enablement is explicitly blocked by live performance, SDK/provider, canary, and rollback evidence. |
| Light Agent | `light-fabric/apps/light-agent` | Durable, policy-governed interactive enterprise, coding, and personal-agent runtime. | **Development**: the durable engine is substantial, but the architecture remains under staged qualification and the local stack uses a dev image. |
| Light Workflow | `light-fabric/apps/light-workflow` | Durable workflow orchestration, human tasks, API/MCP calls, agent calls, retries, cancellation, and compensation. | **Development**: implemented paths are broad; live workflow-MCP, remote runner, recovery, and production rollout qualification remain incomplete. |
| Light Knowledge | `light-fabric/apps/light-knowledge` | Governed Knowledge Base ingestion, indexing, retrieval, citations, uploads, and MCP retrieval. | **Development**: Phase 1a/1b code and local gates exist; production operations and external qualification remain pending. |
| Light Deployer | `light-fabric/apps/light-deployer` | Cluster-local rendering, policy checking, and Kubernetes deployment execution. | **Partial**: the Phase 1 slice is implemented, with controller integration, config references, rollback integration, and richer deployment engines still missing. |
| Controller RS | `controller-rs` | Runtime registration/discovery and MCP-based operational control of services and execution runners. | **Development**: JSON/WebSocket V1 is the active milestone; authorization, persistence/worker, backpressure, and deployment qualification are not fully closed. |
| Config Server | `portal-service/apps/config-server` | Authenticated delivery of generated service configuration, certificates, and files. | **Conditional**: the Rust API and Java-parity work exist, but the local Compose health check is a placeholder and production deployment evidence is not recorded here. |
| Light OAuth | `portal-service/apps/light-oauth` | OAuth/OIDC authorization server, JWT/JWKS issuer, authorization-code and token exchange service. | **Conditional**: the core server and parity tests exist; production key custody, TLS, HA, and deployed-flow qualification are environment-specific and not proven by `all-in-lt`. |
| Portal Service | `portal-service/apps/portal-service` | Rust reference/schema service, memory recall endpoint, and emerging MCP facade. | **Partial**: reference/schema APIs are implemented; MCP tool execution is explicitly a stub and memory has a narrow surface. |
| Rust Event Importer | `importer` | Import CloudEvents and convert Portal database snapshots into replayable events. | **Conditional**: both CLI modes are implemented; production use requires database backup, dry-run/report review, schema compatibility, and an operator-controlled import window. |

`llm-gateway` is listed separately because it is separately deployed in
`all-in-lt`, but it is a profile of the Light Gateway binary rather than an
independent source product.

## Feature Inventory

### Light API

| Feature | What it provides | Readiness |
|---|---|---|
| Axum application framework | Common startup, configuration, server binding, lifecycle, tracing, and handler composition for Rust APIs. | **Conditional**: implemented and reused, but qualification belongs to each product built on it. |
| REST API services | Typed Axum routes and JSON APIs; demonstrated by customer-profile and offer-decision examples. | **Development** as a product template; the example services are not production products. |
| MCP server services | Streamable HTTP/MCP service construction; demonstrated by the insurance-claim MCP example. | **Development** as a template; example-server qualification is not product qualification. |
| Config Server bootstrap and controller registration | Download runtime config and register the running instance with the control plane. | **Conditional** on production TLS, identity, and controller/config-server availability. |
| Graceful shutdown and observability | Shared signal handling, request draining, structured logging, health/readiness patterns. | **Conditional**: implementation exists; the cross-product design says deployment qualification is pending. |

### Light Gateway

| Feature | What it provides | Readiness |
|---|---|---|
| HTTP/HTTPS reverse proxy | Pingora-based ingress, upstream forwarding, URI routing, TLS, headers, and connection handling. | **Conditional**: this is the core product path, but readiness still depends on the exact release image, certificates, and deployment profile. |
| Handler chains | Ordered correlation, security, access control, rate limit, header, CORS, metrics, proxy, static, MCP, and other handlers. | **Conditional**; invalid or incomplete production chains must fail startup. |
| Service discovery | Static targets, direct registry lookup, controller-backed discovery, and service-aware routing. | **Conditional** on the selected discovery backend and outage/failover qualification. |
| JWT/API policy and fine-grained authorization | Authentication plus request access control and response row/field filtering using endpoint identities. | **Conditional**; production safety depends on current Portal projections, exact endpoint identities, and fail-closed policy configuration. |
| Endpoint identity | Method-qualified identities such as `/v1/models@get` for policy, metrics, and audit. | **Development**: accepted and represented in current code/design, but the design record is not itself release qualification. |
| Static SPA/BFF | Static Portal/sign-in assets, cookie sessions, CSRF, downstream token injection, and logout. | **Conditional** on secure cookies, public TLS, OAuth redirect configuration, and live browser qualification. |
| Stateless social OAuth | Authorization-code callbacks and refresh for Google, Facebook, GitHub, and generic providers. | **Conditional**: initial Rust implementation is complete; provider-specific production qualification is still required. |
| Microsoft MSAL login/exchange | Azure token validation, optional Light OAuth exchange, cookies, CSRF, refresh, and downstream token selection. | **Conditional** on tenant/provider configuration and live login/refresh testing. |
| WebSocket routing | Upstream WebSocket proxying, session limits, idle/size controls, and production controls. | **Conditional**: implemented, with route-specific soak and operational qualification required. |
| MCP legacy stateful routing | `initialize`, `tools/list`, `tools/call`, frontend session state, direct HTTP tools, service discovery, and backend MCP forwarding. | **Conditional**: implemented single-process session mapping; HA/session-placement constraints must be respected. |
| MCP 2026-07-28 sessionless/stateless profiles | Modern dual-profile MCP routing and lifecycle validation. | **Development**: code and gates exist, but client/backend compatibility and deployment qualification remain profile-specific. |
| MCP tool authorization and filtering | Request access control, list filtering, response filtering, and tool metadata enforcement. | **Conditional** on complete policy projections and exact caller claims. |
| Workflow-backed MCP tools | Expose a published workflow as one governed MCP tool with synchronous/asynchronous execution, cancellation, compensation, and optional skill binding. | **Development**: phases are implemented in component gates, but runtime promotion is disabled and live qualification is incomplete. |
| Module registry and reload | Report active modules and masked config, then reload supported modules without restart. | **Partial**: Phase 4 is implemented for gateway modules; additional reloaders remain planned. |
| Cache control plane | List, inspect, and clear named service caches through controller tools. | **Proposed** as a generic product feature; controller forwarding exists but the cross-product cache contract is not complete. |
| HMAC webhook authentication | Raw-body HMAC verification, initially for GitHub webhooks, composable with JWT/API key. | **Proposed**; implementation has not started. |
| Kubernetes Gateway API product | Kubernetes-native GatewayClass/Gateway/HTTPRoute control plane. | **Proposed** as a separate future `light-k8s-gateway`; it is not a current Light Gateway feature. |

### LLM Gateway Profile

| Feature | What it provides | Readiness |
|---|---|---|
| OpenAI-compatible model APIs | `GET /v1/models`, model detail, Chat Completions, Responses, and Embeddings. | **Development**: core APIs are implemented; live production qualification is pending. |
| Buffered and SSE streaming inference | Bounded request/response handling, early SSE, usage frames, cancellation, and deadlines. | **Development** pending declared performance and live SDK/provider evidence. |
| Provider-neutral routing | Governed public aliases mapped to OpenAI, Anthropic, Gemini, NVIDIA, Bedrock, Ollama/local, and other configured deployments. | **Development**; every physical deployment requires a current conformance result and secret/trust configuration. |
| Routing reliability | Eligibility, priorities, retry/fallback, passive circuits, deadlines, admission, and overload behavior. | **Development** pending live failure/canary/rollback exercises. |
| Runtime snapshot publication | Monotonic Portal projection, immutable compiled runtime, multi-replica convergence, acknowledgement, and rollback. | **Development**; operational publication approval and exact deployment evidence are outstanding. |
| Token and cost governance | Usage normalization, budgets, rate metadata, accounting, and replay-aware circuit state. | **Development** pending external qualification against real providers and production policy. |
| Durable audit | Bounded async or local-durable WAL/sink, ownership lock, replay, reclamation, and privacy-aware records. | **Development**; durability and performance evidence are required for the selected profile. |
| Request-scoped PII tokenization | Authenticated placeholders and exact fragmented-stream recovery with independent promotion lanes. | **Development**; all functional, security, durability, and PERF-4 lanes must pass. |
| Session/host-scoped reversible PII | Durable vault-backed token mappings beyond one request. | **Not available** until the durable-vault lane is implemented and qualified. |

### Light Agent

| Feature | What it provides | Readiness |
|---|---|---|
| Authenticated WebSocket chat | Interactive sessions, streaming turns, model/tool loop, cancellation, and reconnect behavior. | **Development** pending complete live multi-user and failure-injection qualification. |
| Durable sessions, turns, actions, and event projections | PostgreSQL state machine, idempotent admission, terminal reconciliation, and projection rebuild. | **Development**: implemented in current code, but still part of a staged rollout. |
| Immutable agent policy snapshots | Fail-closed admission against published definition, policy, catalog, model, profile, and boundary digests. | **Development** pending production publication and revocation exercises. |
| Fair scheduling and quotas | Host-scoped advisory locking, cross-replica fair dispatch, pool concurrency, token/cost reservation, and trusted settlement. | **Development** pending scale and failover evidence. |
| Enterprise business-agent profile | Remote model providers plus typed API/MCP tools through Light Gateway. | **Development**; safe broad production use still depends on gateway delegation and policy qualification. |
| Coding-agent profile | Immutable repository bundles, bounded workspaces, approved tools, Pi/Codex-style runner dispatch, and patch limits. | **Development**; sandbox/runner production baseline is not closed. |
| Personal-assistant/edge profile | Typed edge actions, effect classification, approval, runner identity, and schema revalidation. | **Development**; channel and edge-runner rollout is not production-qualified. |
| Tool discovery and execution | Portal effective catalog, gateway `tools/list` intersection, exact `tools/call`, and short-lived delegated tokens. | **Development** pending live catalog/revocation and mixed-failure exercises. |
| Human approval | Durable approval request, approval/rejection, fresh attempts, and policy revalidation. | **Development** pending complete operator/UI and recovery qualification. |
| Memory and Knowledge integration | Hindsight/Portal memory, Knowledge Base bindings, retrieval, and upload-only delegation. | **Development**; Knowledge and memory production lanes remain separately gated. |
| Skill packages | Immutable package publication, revocation, retention, and diagnostics. | **Development**; safe materialization/execution qualification remains required. |
| Broad gateway-token compatibility | Legacy forwarding of a broad caller bearer token. | **Not production-ready**; it is a default-off local compatibility mode. |

### Light Workflow

| Feature | What it provides | Readiness |
|---|---|---|
| Durable orchestration | Event-driven workflow start, process/task persistence, idempotency, leases, and restart recovery. | **Development** pending deployed recovery and scale qualification. |
| Core task model | `set`, `assert`, `switch`, `ask`, HTTP/OpenAPI/JSON-RPC/MCP calls, agent calls, export, and transitions. | **Development**: broad implementation and tests exist; production compatibility is limited to the explicitly supported Open Workflow subset. |
| Human tasks | Assignment, wait, answer, deadline, approval, rejection, and expiry behavior. | **Development** pending full Portal UI/operator and failure-path qualification. |
| Synchronous and asynchronous invocation API | Start, status, wait, result, cancellation, and credential refresh for long-running work. | **Development**; live gateway/workflow deployment qualification remains incomplete. |
| User plus gateway authorization | Original user JWT in `Authorization`, gateway service JWT in `X-Scope-Token`, environment and caller-service validation. | **Development**; gateway, workflow, and database migration must ship together. |
| Retries, effects, cancellation, and compensation | Deadline-aware retries, effect fencing, uncertain outcome reconciliation, cancellation, and compensation flow. | **Development** pending live side-effect and crash/recovery evidence. |
| Fork/join parallelism | Bounded workflow forks with service-wide maximum parallelism. | **Development** pending concurrency and capacity qualification. |
| Native agent task | Load Portal agent/skill/tool state, call a model directly, validate bounded structured output, and continue the workflow. | **Development**; it is the recommended boundary but not a substitute for interactive Light Agent. |
| Workflow-backed MCP execution | Execute published workflows invoked as gateway MCP tools. | **Development**; runtime promotion remains disabled until numeric live gates pass. |
| Runner scheduling and result reconciliation | Reserve remote runners, fence attempts, reconcile results, and enforce effective policy. | **Development/Partial**; code exists, while the tenant-side runner architecture is still documented as proposed. |
| Sandboxed execution backends | MicroVM, container, Kubernetes Job, dedicated VM, host-integrated, or fixed-action execution selected by policy. | **Proposed/Partial**; the production sandbox backend baseline is not complete. |
| Artifact publication and retention | Tenant-scoped staged artifacts, digest verification, promotion evidence, cleanup, and provenance. | **Development** pending external object-store and production recovery qualification. |
| Rule test API | Execute the supported rule/expression profile for Portal authoring and validation. | **Development**; useful locally, not evidence that arbitrary CEL/Open Workflow behavior is supported. |

### Light Knowledge

| Feature | What it provides | Readiness |
|---|---|---|
| Knowledge Base control-plane projection | Consume Portal events and project KBs, sources, bindings, profiles, generations, and authorization into the Knowledge database. | **Development**; projection freshness and security-removal acknowledgements require deployed qualification. |
| Git/Markdown ingestion | Approved repository source, normalized documents, bounded chunking, full BASE generations, embeddings, and atomic promotion. | **Development**: Phase 1a/local implementation exists; production object store and model qualification remain pending. |
| Hybrid retrieval | Authorization filter, lexical/vector candidates, fusion, bounded passages, citations, and query embedding cache. | **Development** pending production recall, latency, concurrency, and protected-lane evidence. |
| Exact-version citations | Resolve immutable document versions and citation anchors returned by retrieval. | **Development**; exact-version support exists, with broader passage-anchor behavior belonging to later qualification. |
| Upload ingestion | Upload-only delegated authorization, staged objects, validation, orphan cleanup, and indexed publication. | **Development**: Phase 1b implementation is locally complete, not production-promoted. |
| Incremental/delta generations | BASE plus ordered DELTA segments, reuse, catch-up, and compaction. | **Development** behind Phase 1b switches and external crash/restart qualification. |
| Multi-KB retrieval | Select multiple authorized KBs and fuse results without crossing tenant or policy boundaries. | **Development** behind Phase 1b promotion gates. |
| REST and MCP retrieval | `/v1/knowledge/retrieve`, upload APIs, MCP `initialize`, `tools/list`, and `tools/call`. | **Development** pending live REST/MCP parity and auth-failure matrices. |
| Readiness, metrics, jobs, and leases | Health/readiness, metrics, embedded worker/projector, job leases, retry, and heartbeat behavior. | **Development** pending operational SLO and recovery evidence. |
| Embedding model migration | Candidate generation, backfill/catch-up, evaluation, atomic promotion, rollback, and retirement. | **Development**; an end-to-end production model-upgrade exercise is still required. |
| Enterprise SharePoint/Confluence ACL connectors | Source-specific ACL ingestion and authorization projection. | **Proposed** for Phase 2. |
| Graph-assisted retrieval | Optional bounded relational-path evidence with hybrid fallback. | **Development pilot/default-off**; not a production baseline. |

### Light Deployer

| Feature | What it provides | Readiness |
|---|---|---|
| Deployment render/validate | Parse YAML structurally, substitute placeholders, redact secrets, and produce a safe diff. | **Development**; typed placeholders and Config Server `valuesRef` are not complete. |
| Git template fetch | Fetch public/private HTTPS repositories and select a ref/path. | **Development**; HTTPS token auth exists, SSH and stronger repository trust handling are deferred. |
| Kubernetes server-side apply | Dry-run, apply, delete, status, and basic rollout handling with `kube-rs`. | **Development** pending production cluster/RBAC/recovery qualification. |
| Pruning and blast-radius policy | Calculate stale resources and enforce pruning safety rules. | **Development** pending broader resource and rollout exercises. |
| SSE deployment events | Request-scoped progress events. | **Development**; durable/resumable delivery is not established. |
| Controller-mediated execution | Route Portal deployment commands through the controller to the cluster-local deployer. | **Partial**; direct HTTP/MCP-style mode was implemented first and controller integration remains a stated gap. |
| Rollback from Portal snapshots | Restore a prior generated deployment/config state. | **Partial**; represented in the model but Portal snapshot integration remains. |
| Helm/Kustomize | Render and deploy Helm charts or Kustomize overlays. | **Not implemented**. |

### Controller RS

| Feature | What it provides | Readiness |
|---|---|---|
| Runtime registration and discovery | Track live instances, service identities, endpoints, health, and subscriptions over authenticated WebSockets. | **Development** pending HA/distributed-state and production deployment qualification. |
| Unified external MCP control socket | MCP initialize, list/call, caller context, correlation, limits, and Portal notifications on `/ctrl/mcp`. | **Development**; JSON/WebSocket V1 is the active milestone. |
| Runtime inspection | Server info, list/get instances, runtime capabilities, checks, and module information. | **Development** with fail-closed capability intersection; production authorization and compatibility must be qualified. |
| Logging control | Get/set loggers and filters, read logs, start/renew/stop caller-owned live log streams. | **Development** pending live Portal/client soak and disconnect recovery evidence. |
| Cache and module forwarding | List/get/clear caches and reload supported runtime modules. | **Partial** because participating runtimes do not all implement the generic contracts. |
| Shutdown and chaos operations | Feature-switched shutdown, chaos configuration, and chaos execution. | **Development/default-off**; not production-enabled without explicit policy and switches. |
| Admission/backpressure | Connection, per-subject, request-rate, queue, in-flight, message-size, and JSON-depth limits. | **Development** pending deployment load/abuse qualification. |
| JWT and scope policy | JWKS validation, exact scopes, expiry, read/write separation, and mutation-specific switches. | **Development**; the repository README still calls out richer key management and external policy gaps. |
| Audit and persistence | Event/outbox/runtime-instance persistence scaffolding and bounded audit values. | **Partial**; downstream outbox/projection completion remains a known gap. |
| Runner enrollment, leases, and fencing | Register execution runners and mediate workflow/agent attempts with capabilities and isolation metadata. | **Development**; the end-to-end runner product boundary is not production-qualified. |
| WebTransport/rkyv | Alternative browser/runtime transport and binary codec. | **Proposed/blocked**; WebSocket plus JSON remains the active baseline. |

### Rust Config Server

| Feature | What it provides | Readiness |
|---|---|---|
| `/config-server/configs` | Resolve product/version/instance properties and generate runtime configuration. | **Conditional** on schema parity, trusted host/instance identity, and exact product mappings. |
| `/config-server/certs` | Return authorized certificate material for the requesting runtime. | **Conditional** on production certificate custody, rotation, and caller authorization. |
| `/config-server/files` | Return authorized instance files and metadata. | **Conditional** on host/service binding and production storage policy. |
| JWT SID/host enforcement | Bind service identity and trusted claims to the requested host and instance. | **Conditional**; Rust and Java parity must remain covered for every route. |
| Snapshot output parity | Produce the same deterministic `values.yml`/snapshot semantics as the Java Config Server. | **Development/Conditional**: parity work and comparison tests exist; all product codecs and live rollback paths must remain qualified. |
| Embedded defaults and graceful shutdown | Bootstrap from embedded configuration and drain HTTPS/database resources on termination. | **Conditional**; cross-product deployment qualification remains pending. |

### Rust Light OAuth

| Feature | What it provides | Readiness |
|---|---|---|
| JWKS endpoint | Provider-scoped signing-key publication. | **Conditional** on secure production signing-key storage, rotation, and HA. |
| Authorization code endpoint | Create/validate authorization codes and tenant/auth-host session state. | **Conditional** on complete browser, redirect, replay, and tenant-boundary testing. |
| Token endpoint | Authorization-code, refresh, client, and supported exchange flows with scoped JWT issuance. | **Conditional** on exact enabled grants and live security qualification. |
| OIDC discovery | Root and provider-scoped `openid-configuration` documents. | **Development/Conditional**; code is present, while ecosystem consumer qualification is still required. |
| External JWT exchange | Optional Microsoft/CCAC verification and internal token exchange. | **Conditional** on issuer/audience/JWKS and failure-path configuration. |
| Refresh-token rotation grace | Rotation and bounded replay/grace handling. | **Conditional** on concurrency/replay tests and production database policy. |
| TLS and graceful shutdown | Rustls HTTPS listener and bounded database/server drain. | **Conditional** on production certificates and orchestrator qualification. |

### Rust Portal Service

| Feature | What it provides | Readiness |
|---|---|---|
| Reference data API | Host/global, language, and relation-aware reference lookup with cache. | **Conditional** pending production authorization, cache invalidation, and parity qualification. |
| Schema registry read API | Retrieve a schema by alias/version, optionally as an envelope, with metadata headers. | **Conditional** pending complete auth, cache, and Java/API compatibility qualification. |
| Memory recall API | Vector-based recall from one authenticated host and memory bank. | **Partial/Development**; the public route is narrow and does not establish the full governed Agent Memory product. |
| MCP initialize and tools list | Legacy SSE/messages MCP scaffold and Portal skill listing. | **Partial**; session handling is described in code as not real yet. |
| MCP tool execution | Route skill tools and memory operations. | **Not production-ready**: `memory_recall` returns placeholder text and other tools return “not implemented yet.” |
| Config bootstrap/controller registration | Load local/remote config, register, expose runtime control, and shut down gracefully. | **Conditional** on production identity/TLS and controller availability. |

### Rust Event Importer

| Feature | What it provides | Readiness |
|---|---|---|
| CloudEvent import | Validate and insert ordered Portal events with aggregate-version, nonce, offset, and transaction rules. | **Conditional**: suitable for controlled operations, not unattended production mutation. |
| Replacement and enrichment | Rewrite approved values and add import metadata without changing unrelated event semantics. | **Conditional**; generated output and target state must be reviewed. |
| Dry run, fail-fast, batching, and summary | Preflight events, choose failure behavior, control transaction batches, and emit machine-readable results. | **Conditional** and recommended before every production import. |
| Snapshot conversion | Convert supported Portal snapshot tables into ordered CloudEvents with host/admin rewrite and table-specific rules. | **Conditional**; schema/table coverage must match the snapshot version. |
| Idempotency/conflict detection | Detect duplicate identifiers, aggregate conflicts, and database collisions. | **Conditional**; a database backup and explicit operator recovery plan remain required. |

## Portal Java Application Inventory

### Hybrid Hosts

| Service | What it is for | Readiness |
|---|---|---|
| `hybrid-command` | Runs all Light Portal write-side Java command modules in one `light-hybrid-4j` process. It validates commands, applies aggregate rules, appends CloudEvents/outbox records, and performs command-side operational work. | **Conditional** for the reviewed local artifact: Compose uses a stable host image, but the mounted modules are `2.3.8-SNAPSHOT`; current production release and live rollout evidence must be supplied separately. |
| `hybrid-query` | Runs all Light Portal read-side Java query modules in one process. It serves read models, event projections, filters, admin/query APIs, and selected background tasks. | **Conditional** for the reviewed local artifact: mounted modules are `2.3.8-SNAPSHOT`, hostname verification is disabled by a JVM development flag, and the current production release is not proven here. |

The two hybrid containers are deployment hosts, not replacements for the
individual domain services below. Each JAR remains an independently named
service/module with its own API contract and repository.

### Command And Query Domain Services

All 29 command/query pairs below are present as mounted JARs in
`portal-config-loc/all-in-lt`. Their baseline status is **Conditional** rather
than **Production-ready** because this inventory sees `2.3.8-SNAPSHOT`
artifacts in a local stack. A domain marked “advanced paths gated” has a usable
core but also contains newer functions whose own documents require additional
promotion evidence.

| Domain | Command service | Query service | What it manages | Current readiness |
|---|---|---|---|---|
| Attribute | `attribute-command` | `attribute-query` | Reusable attribute definitions and values used to extend Portal entities. | **Conditional** core CRUD/projection. |
| Blog | `blog-command` | `blog-query` | Portal blog content and publication metadata. | **Conditional** core CRUD/projection. |
| Category | `category-command` | `category-query` | Hierarchical catalog/content categorization. | **Conditional** core CRUD/projection. |
| Client | `client-command` | `client-query` | OAuth clients, client credentials, scopes, and client/host relationships. | **Conditional**; secret regeneration and tenant/security paths require live qualification. |
| Config | `config-command` | `config-query` | Config properties, product-version mappings, instance configs, snapshots, clone, commit, rollback, and Gateway publication inputs. | **Conditional; advanced paths gated** for snapshot rollback, instance clone, and publication workflows. |
| Deployment | `deployment-command` | `deployment-query` | Deployment definitions, environments, targets, requests, and status/read models. | **Conditional; advanced paths gated** because Rust deployer and production approval/rollback are not complete. |
| Document | `document-command` | `document-query` | General Portal documents/content records. | **Conditional** core CRUD/projection. |
| Error | `error-command` | `error-query` | Error/status-code catalog definitions and localized metadata. | **Conditional** core CRUD/projection. |
| Form | `form-command` | `form-query` | Schema-driven form definitions and Portal form metadata. | **Conditional** core CRUD/projection. |
| GenAI | `genai-command` | `genai-query` | Providers, models, deployments, aliases, agents, skills, tools, Knowledge Bases, grants, embedding spaces, and AI publication state. | **Development/Conditional by subfeature**; LLM, Agent, Knowledge, and workflow-tool promotion gates remain separate. |
| Group | `group-command` | `group-query` | User groups and group-based access-control relationships. | **Conditional** core CRUD/projection. |
| Host | `host-command` | `host-query` | Tenants/organizations, host lifecycle, ownership, and host settings. | **Conditional**; tenant-boundary changes require security regression coverage. |
| Instance | `instance-command` | `instance-query` | Runtime instances, instance APIs/apps/files, cloning, and runtime configuration. | **Conditional; advanced paths gated** for clone, config snapshots, and live runtime operations. |
| Map Root | `maproot-command` | `maproot-query` | Root mappings used to organize and resolve configurable map/reference structures. | **Conditional** core CRUD/projection. |
| News | `news-command` | `news-query` | Portal news/announcement content. | **Conditional** core CRUD/projection. |
| OAuth | `oauth-command` | `oauth-query` | OAuth providers, keys, authorization metadata, and related Portal administration. | **Conditional**; end-to-end issuer/key/tenant flows require live security qualification. |
| Page | `page-command` | `page-query` | Portal page definitions and page content/configuration. | **Conditional** core CRUD/projection. |
| Position | `position-command` | `position-query` | Organization/job positions and position-based relationships. | **Conditional** core CRUD/projection. |
| Product | `product-command` | `product-query` | Products, versions, releases, and product-version configuration associations. | **Conditional**; Rust release/config mapping automation is not fully operationalized. |
| Reference | `ref-command` | `ref-query` | Reference tables, localized data, relationships, and lookup models. | **Conditional**; Rust Portal Service cache invalidation/control-plane parity is not complete. |
| Role | `role-command` | `role-query` | Roles, permissions, scopes, and role assignments. | **Conditional** core CRUD/projection with security-sensitive regression requirements. |
| Rule | `rule-command` | `rule-query` | Rule definitions, versions, YAML/CEL metadata, and rule lookup/test inputs. | **Conditional** for supported rule subsets; arbitrary CEL/YAML behavior is not implied. |
| Schedule | `schedule-command` | `schedule-query` | Scheduled jobs/triggers and scheduler-facing read models. | **Conditional**; distributed scheduling behavior needs deployment-specific qualification. |
| Schema | `schema-command` | `schema-query` | JSON Schema registry records, aliases, versions, and publication/read APIs. | **Conditional**; registry/runtime consumer parity must be maintained. |
| Service | `service-command` | `service-query` | Services, endpoints, APIs, paths, callable tools, and Gateway publication metadata. | **Conditional; advanced paths gated** for endpoint identity, tool publication, and live Gateway apply/rollback. |
| Tag | `tag-command` | `tag-query` | Reusable tags and tagged-entity relationships. | **Conditional** core CRUD/projection. |
| Template | `template-command` | `template-query` | Reusable content/config/deployment templates. | **Conditional** core CRUD/projection. |
| User | `user-command` | `user-query` | Users, memberships, sessions, notifications, private messages, and user/host access. | **Conditional; security-sensitive** for host binding, claims, notification access, and privacy paths. |
| Workflow | `workflow-command` | `workflow-query` | Workflow definitions/versions, publication, editor/read models, invocation-facing metadata, and workflow-tool grants. | **Development/Conditional by subfeature**; publication is implemented, while workflow-backed MCP production promotion is incomplete. |

### Alternate Java Runtime Services In `docker-compose-java.yml`

These are Java alternatives for core runtime positions in the stack. They are
not additional Rust products, but an operator choosing the Java profile runs
them alongside the Portal hybrids.

| Compose service | Java implementation | Purpose |
|---|---|---|
| `controller` | `light-controller` | Runtime registry and operational control plane. |
| `light-oauth` | `oauth-kafka` | OAuth/JWT authorization server and Kafka-backed OAuth processing. |
| `config-server` | Java Config Server | Runtime configuration, certificates, and files. |
| `portal-service` | `light-reference` | Reference/schema service used by applications. |
| `light-gateway` | Java Light Gateway | Portal ingress/BFF/API/MCP gateway alternative. |

## Deployment Coverage In `all-in-lt`

| Deployment item | Inventory treatment |
|---|---|
| PostgreSQL/TimescaleDB and `knowledge-schema-migration` | Infrastructure and one-shot migration helper, not products. |
| `controller`, `light-oauth`, `config-server`, `portal-service`, `light-workflow`, `light-gateway`, `llm-gateway`, `light-agent`, `light-knowledge` | Rust product services described above. |
| `hybrid-command`, `hybrid-query` and their 58 mounted JARs | Java Light Portal control-plane services described above. |
| `demo-customer-profile-api`, `demo-offer-decision-api`, `demo-insurance-claim-mcp-server` | Rust examples/qualification fixtures, not supported product SKUs. |
| `light-knowledge-worker` | A build/worker component in source; the current normal Compose topology embeds/supervises Knowledge work in `light-knowledge` rather than declaring a separate long-running service. |

## Source Components That Are Not Separate Products

The following should remain visible to engineering without inflating the
product count:

- `light-axum` and `light-pingora` are frameworks;
- `light-runtime`, `portal-registry`, `model-provider`, `workflow-core`,
  execution-backend crates, Knowledge crates, and security/config crates are
  shared libraries;
- `light-k8s-gateway` is proposed and does not yet belong in the current
  product count.

Every additional Rust executable currently present under `light-fabric/apps`
is classified below so that a component cannot be confused with an omitted
product:

| Executable | Classification and purpose | Readiness as an independent product |
|---|---|---|
| `light-workflow-runner` | Tenant-side fenced executor for workflow tasks and agent actions near private systems or sandboxes. | **Not an independent production product**; runner architecture and end-to-end qualification remain in development. |
| `light-agent-worker` | Worker-side agent execution component sharing the runner/execution contracts. | **Not an independent production product**; component of Light Agent execution. |
| `light-agent-channel` | Separate channel-gateway boundary for personal-assistant messages and proactive triggers. | **Not an independent production product**; personal profile rollout remains in development. |
| `light-knowledge-worker` | Knowledge ingestion/build worker that can be reused for heavy or offline work. | **Not a default standalone product**; the normal Compose topology embeds Knowledge work in `light-knowledge`. |
| `light-github-action-provider` | Fixed-action/provider integration for bounded GitHub operations. | **Component/development integration**, not a general product. |
| `light-pi-rpc-adapter` | Adapter between the Light runner protocol and the Pi coding-agent RPC boundary. | **Component/development integration**, not a general product. |
| `provider-qualification-runner` | Captures model-provider conformance evidence used by LLM Gateway promotion. | **Qualification tool**, not a serving product. |
| `llm-provider-mock` | Deterministic upstream provider used by tests and qualification gates. | **Test fixture**, never a production provider. |
| `llm-phase0-spikes` | Experimental LLM performance/architecture spike binary. | **Experiment**, not a supported product. |
| `light-coding-agent-fixture` | Deterministic coding-agent fixture used to exercise runner contracts. | **Test fixture**, not a production agent. |

The three binaries in `light-example-rs` are likewise examples rather than
products: `demo-customer-profile-api`, `demo-offer-decision-api`, and
`demo-insurance-claim-mcp-server`.

## Readiness Summary

No reviewed advanced Rust feature should be presented to customers as
unconditionally production-ready from this checkout alone. The core Gateway,
Config Server, Light OAuth, reference/schema API, Light API framework, and
Importer have useful implemented baselines, but all are **Conditional** because
the current inventory does not include the exact stable artifact plus deployed
security, performance, failover, canary, and rollback evidence required for a
new production claim.

The clearest non-ready areas are:

- LLM Gateway production promotion;
- workflow-backed MCP runtime promotion;
- broad multi-profile Light Agent execution;
- tenant runner and sandbox execution;
- Light Knowledge production operations and enterprise connectors;
- Controller distributed/production qualification;
- Light Deployer controller/rollback/config-reference integration; and
- Portal Service MCP execution.

Release management should turn **Conditional** into **Production-ready** only
for a named product version and deployment profile, with immutable evidence for
the exact source commit, image digest, configuration/projection digest,
database migration set, and live qualification run.
