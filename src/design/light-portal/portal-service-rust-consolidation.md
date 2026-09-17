# Portal Service Consolidation Into Rust

## Status

Proposed on 2026-09-16. Not yet implemented.

## Decision

Replace the Java `light-hybrid-4j` portal services with two Rust services built
from a single repository:

- `portal-command` replaces `hybrid-command` and every `*-command` repository.
- `portal-query` replaces `hybrid-query`, every `*-query` repository, and the
  outbox projection consumer.

Both services use a shared Rust port of `light-portal/db-provider`,
`command-common`, and `common-util`.

The migration is incremental. The external contract stays the same: the
`/portal/command` and `/portal/query` endpoints, the hybrid
`host/service/action/version` envelope, CloudEvent payloads, database schema,
and error codes. Services move one domain at a time. The gateway routes each
migrated service to Rust and everything else to Java. A parity harness is
required before each domain cuts over.

Reducing memory use is a side benefit, not a reason for this decision.

## Context

### Current Layout

Each portal domain is split into two Maven repositories that build jars. When
deploying, those jars are copied into the `hybrid-command` or `hybrid-query`
service folder and loaded from the classpath. Handlers register with
`@ServiceHandler(id="lightapi.net/<service>/<action>/<version>")` and validate
input against each repository's `spec.yaml`.

Measured on 2026-09-16 (main source only, tests excluded):

| Component | Repositories | Java lines | Service handlers |
|-----------|--------------|------------|------------------|
| `*-command` | 29 | ~30k | 464 |
| `*-query` | 29 | ~27k | 454 |
| `hybrid-command`, `hybrid-query` | 2 | <1k | n/a |
| `light-portal/db-provider` | 1 | ~108k | n/a |
| `light-portal/common-util` | 1 | ~7k | n/a |
| `light-portal/command-common` | 1 | ~1k | n/a |
| **Total** | **~60** | **~173k** | **918** |

`db-provider` also has ~29k lines of tests. The largest domains by handler
count are `genai`, `config`, `user`, `workflow`, `oauth`, and `instance`.
Several repositories (`blog`, `news`, `page`, `form`, `template`, `document`,
`error`) are placeholders with fewer than 100 lines.

For comparison, `light-fabric` is one Cargo workspace with ~323k lines of Rust.
It already contains `light-gateway`, `light-workflow`, `light-knowledge`,
`config-loader`, `portal-registry`, and several `sqlx` Postgres stores.

### Request And Event Flow Today

```text
Portal UI
   |
   | POST /portal/command  {host, service, action, version, data}
   v
light-gateway (Rust)  -- parses the hybrid envelope (is_portal_hybrid_path)
   |
   v
hybrid-command (Java)
   | AbstractCommandHandler: trusted scope, owner checks, idempotency,
   | aggregate version, CloudEvent build
   | PortalDbProvider: event_store_t + outbox_message_t in one transaction
   v
PostgreSQL
   |
   | LISTEN event_channel / gapless c_offset polling
   v
hybrid-query (Java) DbEventConsumerStartupHook
   | projection writers in db-provider
   v
projection tables  <-- read by hybrid-query handlers via /portal/query
```

`hybrid-command` also calls `hybrid-query` through `HybridQueryClient` for some
flows, such as event replay.

### Problems

1. **Two languages.** Contracts shared by both runtimes (CloudEvent shapes,
   config loading, token handling, error codes, entity scope rules) are
   implemented twice and can drift apart. Every security patch and dependency
   update must be done in both toolchains.
2. **Too many repositories.** A single feature usually touches `db-provider`,
   a `*-command` repository, a `*-query` repository, and sometimes
   `light-portal-event`. These must be released in dependency order. Portal code
   is now written mostly by AI agents, and agents work best when they can see
   the whole change, run every affected test, and make one atomic commit. Many
   repositories prevent all three.
3. **Memory.** `hybrid-command` and `hybrid-query` together use about 500 MB,
   roughly ten times a comparable Rust service. This is real but not decisive.

## Options Considered

### A. Keep Java And Hybrid As-Is

- Pros: already tested in production; no migration risk; jars can be deployed
  independently.
- Cons: the two-language cost never goes away and grows with each shared
  contract; the multi-repository workflow stays; any AI-driven change keeps
  spanning repositories.

### B. Merge Java Repositories Into One Maven Monorepo

Keep `light-hybrid-4j`, but move every `*-command`, `*-query`, and
`light-portal` module into one multi-module repository.

- Pros: fixes problem 2 in days with almost no behavior risk; the build and
  deployment stay the same.
- Cons: does not fix problem 1 or 3; the Java side keeps growing in parallel
  with Rust.

### C. Rewrite In Rust With Two Services (Chosen)

- Pros: one language and toolchain; shares crates with `light-fabric`
  (`config-loader`, `portal-registry`, security, stores); one atomic commit per
  feature; the compiler and `sqlx` query checks catch many AI mistakes before
  runtime; lower memory and faster startup.
- Cons: behavior drift is the main risk, not code volume; loses runtime jar
  drop-in (services are compiled in and optionally gated by Cargo features);
  a large workspace compiles slowly; both runtimes must be operated during the
  migration.

Option B is an optional first step for C. See [Phase 0](#phase-0-optional-java-monorepo).

## Target Architecture

### Repository Placement

Recommended: add the portal to `light-fabric`.

```text
light-fabric/
  apps/
    portal-command/        # HTTP server, handler registry, startup
    portal-query/          # HTTP server, handler registry, outbox consumer
  crates/
    portal-hybrid/         # envelope, handler trait, registry, schema validation
    portal-command-core/   # port of AbstractCommandHandler and command-common
    portal-db/             # port of PortalDbProvider (split by persistence area)
    portal-projection/     # outbox consumer and projection writers
    portal-domain-<name>/  # per-domain command and query handlers + spec.yaml
```

Reasons: the gateway, config loader, registry client, and existing Postgres
stores already live in `light-fabric`, and a single workspace gives agents the
whole contract surface in one place.

Alternative: a separate `portal-service` Cargo workspace that depends on
published `light-fabric` crates. Choose this only if the portal needs a release
cadence separate from the gateway and agents. It brings back cross-repository
changes whenever a shared crate changes.

### Handler Model

```rust
#[async_trait]
pub trait HybridHandler: Send + Sync {
    /// "lightapi.net/<service>/<action>/<version>"
    fn id(&self) -> &'static str;
    async fn handle(&self, ctx: &RequestContext, data: JsonValue)
        -> Result<JsonValue, PortalStatus>;
}
```

- Handlers register in a static registry. Each domain crate exports a
  `register(&mut Registry)` function, and the apps call it for every enabled
  domain.
- Each domain crate keeps its `spec.yaml` unchanged. Validation runs before the
  handler, as in `light-hybrid-4j`.
- `RequestContext` carries the authenticated claims, the trusted host, and the
  idempotency key. Trusted-scope and owner checks come from
  `portal-command-core`, not from each handler.
- Errors keep the existing `ERRxxxxx` codes and status message templates from
  `app-status.yml`.

### Database Layer

- Use `sqlx` with Postgres, matching the rest of `light-fabric`.
- Split `PortalDbProviderImpl` (~240k characters) and the large
  `*PersistenceImpl` classes by persistence area. Each area becomes a module
  inside `portal-db`, or its own crate if compile time requires it.
- Command writes keep one transaction covering the aggregate version check,
  `event_store_t`, and `outbox_message_t`. The optimistic concurrency semantics
  described in existing designs stay exactly the same.
- CloudEvent serialization must produce the same JSON as Java, field for field,
  including aggregate type and ID derivation. `getCloudEventAggregateId` rules
  for Knowledge types must be kept.

### Projection Consumer

The outbox consumer reads with gapless `c_offset` ordering, so Java and Rust
consumers cannot share it event type by event type. It moves as **one unit**:

1. Port every projection writer while Java remains the live consumer.
2. Verify offline by replaying the full event stream through the Rust consumer
   into a scratch database and diffing every projection table against the
   Java-built database.
3. Cut over by stopping the Java consumer at offset N and starting the Rust
   consumer from N+1.

Until that cutover, Rust query handlers read projections written by Java. This
works because the schema is shared.

### Gateway Routing

`light-gateway` already parses the hybrid envelope for `/portal/query` and
`/portal/command`. Add a per-service upstream table:

```yaml
portalHybridRouting:
  command:
    default: hybrid-command
    services:
      tag: portal-command
      category: portal-command
  query:
    default: hybrid-query
    services:
      tag: portal-query
```

Routing is by `service` only; a domain moves all of its actions at once. The
table is removed when the migration finishes.

## Migration Plan

### Phase 0: Optional Java Monorepo

See [Portal Java Monorepo](./portal-java-monorepo.md) for the detailed plan.

If Phases 2 and 3 are expected to take more than about two months, merge the
Java repositories into one Maven multi-module repository first (Option B). This
fixes the multi-repository pain for the length of the migration and gives the
parity harness one Java build to run against.

### Phase 1: Foundation

- `portal-hybrid`, `portal-command-core`, handler registry, schema validation,
  status codes, config loading, JWT and trusted-scope context.
- The core parts of `portal-db`: event append, outbox, idempotency ledger,
  entity creation scope contract.
- Gateway per-service routing.
- Parity harness (below).
- Exit criteria: one trivial domain (such as `tag`) passes parity and is routed
  to Rust in a development environment.

### Phase 2: Command And Query Domains

Migrate domains from small and low-risk to large and security-sensitive:

1. `tag`, `category`, `schema`, `schedule`, `ref`, `position`, `role`, `group`,
   `attribute`, `rule`, `product`
2. `host`, `deployment`, `maproot`, `service`, `instance`
3. `workflow`, `config`, `genai`
4. `oauth`, `user`

The placeholder domains (`blog`, `news`, `page`, `form`, `template`,
`document`, `error`) are planned features. Create their domain crates when
their features are built, in Rust if the migration has started by then.

For each domain:

1. Port the command handlers, query handlers, and `db-provider` persistence
   methods together.
2. Pass the parity harness.
3. Route the domain to Rust in development, then test, then production.
4. Delete the Java repositories for that domain once production has run on
   Rust for one release cycle.

### Phase 3: Projection Consumer Cutover

Follow the [Projection Consumer](#projection-consumer) procedure after every
projection writer is ported. This can run in parallel with Phase 2 group 3 or 4.

### Phase 4: Retirement

Remove `hybrid-command`, `hybrid-query`, `light-portal`, the per-service
gateway routing table, and the Java build from CI and deployment manifests.

## Parity Harness

The parity harness is the safety mechanism that makes an AI-written port
acceptable. A domain may not cut over without passing it.

- **Recorded scenarios.** Request sequences per domain covering success, every
  validation failure, owner and admin-override paths, cross-host denial,
  idempotent retry, and version conflict. Seed them from the existing
  `db-provider` tests and `light-portal-test`.
- **Dual execution.** Run each scenario against Java and Rust, each on a fresh
  database built from the same snapshot bootstrap.
- **Comparison.** Compare HTTP status and normalized response body; appended
  `event_store_t` and `outbox_message_t` rows (ignoring generated IDs and
  timestamps); and the resulting projection rows.
- **Stream replay.** For the projection consumer, replay a production-shaped
  event stream and diff all projection tables.
- Differences fail CI. An intentional difference must be written down in the
  scenario with a reason.

## Risks

| Risk | Mitigation |
|------|------------|
| Behavior drift in authorization, scope, or error codes | Parity harness; migrate `oauth` and `user` last |
| CloudEvent payload mismatch breaks replay or snapshots | Byte-level event comparison in the harness; snapshot bootstrap round-trip test |
| Split-brain projection writes | Consumer moves as one unit at a recorded offset |
| Slow compile times in `light-fabric` | Per-domain crates; Cargo features to build only selected domains during development |
| Long period operating both runtimes | Phase 0 monorepo; strict domain ordering; delete Java code per domain promptly |
| Loss of independent jar deployment | Accepted; jars are already deployed together in practice |
| External users depend on the Java jars on Maven Central | Announce an end-of-life date per domain; publish a final Java release; see Open Questions |

## Open Questions

1. Confirm repository placement: `light-fabric` (recommended) or a separate
   `portal-service` workspace.
2. Decide whether Phase 0 is worth doing, based on the expected migration time.
3. Decide whether `portal-command` and `portal-query` should also be able to run
   as one combined binary for small deployments.
4. Some users depend on the Java portal jars on Maven Central. Decide how long
   the Java artifacts receive fixes after their domain moves to Rust, and how
   those users are told.
