# LLM Gateway Topology Per Host And Environment

## Status

Proposed design for discussion.

## Decision Summary

Use exactly one **logical LLM gateway configuration** for each Light Portal
`(host, environment)` pair. Run that logical gateway as multiple stateless
replicas for availability and capacity.

Allow many MCP, Agent, API, or other AI-oriented microgateways in the same host
and environment, but do not give those microgateways direct LLM provider access.
They must invoke the logical LLM gateway through an authenticated internal
contract.

Do not add multiple independently configured LLM gateway targets to the initial
control-plane schema. Revisit that decision only when a concrete regulatory,
network-isolation, ownership, or independent-change-boundary requirement cannot
be represented by Aliases, Policy Bindings, Routes, Deployments, quotas, and
normal replica scaling.

This decision means **one configuration authority**, not one process, pod,
machine, region, or availability zone.

## Context

The LLM control plane already separates the major concerns:

- Models describe the shared model catalog.
- Registrations approve models for a host and environment.
- Provider Accounts and Deployments describe quota ownership and callable
  provider endpoints.
- Credentials reference external secrets.
- Public Aliases provide stable model names.
- Routes connect Aliases to eligible Deployments.
- Pricing records effective rates.
- Policies describe governance intent.
- Bindings assign Policies to Agents, Clients, Principals, or Product Profiles.
- Publications create immutable gateway projection roots.

This structure can expose different models and policies to different subjects
without requiring a different LLM gateway configuration for every Agent, team,
product, or MCP server.

The current implementation also already assumes one publication stream per
host and environment:

- `llm_projection_resource_t` keys resources and sequence numbers by
  `host_id + environment`.
- `llm_gateway_publication_t` keys publication versions and manifest digests by
  `host_id + environment`.
- the latest-publication query accepts only Host Id and Environment.
- candidate validation selects the active Alias surface for the environment.
- the publication command has no gateway target identifier.
- runtime `gatewayInstance` identifies a replica acknowledgement; it does not
  select a different model or policy configuration.

Relevant current sources are:

```text
portal-db/postgres/ddl.sql
light-portal/db-provider/.../LlmModelPersistenceImpl.java
genai-command/src/main/resources/spec.yaml
light-fabric/crates/llm-gateway/src/config.rs
light-fabric/crates/llm-gateway/src/projection.rs
```

## Terminology

| Term | Meaning |
| --- | --- |
| Host | Portal tenant boundary represented by `host_id`. |
| Environment | Deployment stage such as `dev`, `test`, or `prod`. |
| Logical LLM gateway | The single model-access and policy-enforcement authority for one host and environment. |
| LLM gateway replica | One process or pod serving the same immutable LLM projection as its peers. |
| AI microgateway | A gateway close to an MCP server, Agent, workflow, API, or execution domain. It handles that domain's routing and security but has no direct provider credential or LLM model access. |
| Publication | One immutable desired-state root containing supported LLM Deployments, Routes, Policies, and Pricing. |
| Gateway instance | Operational identity of an individual replica, used for acknowledgements, audit, and diagnostics. It is not a configuration partition. |

## Goals

- Provide one unambiguous model-governance authority per host and environment.
- Scale request capacity and availability with replicas.
- Keep provider credentials and model egress out of microgateways.
- Support different models, budgets, data rules, and capabilities for different
  Agents and subjects through control-plane resources.
- Preserve immutable, versioned publication and rollback semantics.
- Make authorization decisions resistant to caller-controlled gateway choice.
- Keep operational ownership, delivery status, and incident response clear.
- Leave an explicit migration path if multiple isolated LLM gateway realms are
  later justified.

## Non-Goals

- This design does not limit the number of gateway processes or pods.
- It does not require all subjects to use the same model or Policy.
- It does not prohibit regionally distributed replicas.
- It does not make every MCP or Agent request pass through one physical host.
- It does not define provider-specific policy-object vocabulary.
- It does not treat an application microgateway as an LLM provider proxy.

## Required Invariants

1. There is one desired LLM publication sequence for each `(host, environment)`.
2. Every LLM gateway replica for that pair applies the same immutable
   publication root, subject to bounded rollout convergence.
3. `gatewayInstance` identifies a replica but never changes the authorized
   model, Alias, Route, Policy, or Credential set.
4. Only the logical LLM gateway resolves provider credential references and
   opens provider inference connections.
5. AI microgateways cannot read LLM projection roots, resolve provider secrets,
   or call approved model providers directly.
6. A caller selects an authorized Public Alias, not a gateway instance or
   provider Deployment.
7. Host and environment are derived from trusted request and deployment
   context; clients cannot override them to reach another publication.
8. Policy and Alias selection is determined by trusted bindings and claims, not
   by a caller-selected route to a less restrictive gateway.
9. Every served request records the publication sequence or root digest used by
   the handling replica.
10. A failed candidate or replica acknowledgement never mutates the last valid
    published root.

## Option A: One Logical LLM Gateway Per Host And Environment

### Topology

```text
Host A / prod
│
├── MCP microgateway 1 ─┐
├── MCP microgateway 2 ─┤
├── Agent service ──────┼──> logical LLM gateway endpoint
└── Workflow service ───┘       ├── replica 1
                                ├── replica 2
                                └── replica 3
                                      │
                                      ├── Provider Deployment A
                                      ├── Provider Deployment B
                                      └── Provider Deployment C

One Portal publication root defines the models, routes, policies, and pricing
used by all three replicas.
```

### How Different Model Needs Are Represented

Different requirements remain data and policy decisions inside the one logical
configuration:

- Public Aliases expose different approved model contracts.
- Alias Routes select different Deployments, regions, priorities, and fallbacks.
- Policy Bindings assign different Policies and default Aliases to Agents or
  other subjects.
- Provider Accounts and quota groups separate capacity and billing ownership.
- Registration and Alias environment fields prevent cross-environment use.
- Credentials remain Deployment-specific.

For example, a support Agent can resolve `support-chat`, a coding Agent can
resolve `code-assistant`, and a document workflow can resolve
`document-summarizer`. They can use different providers and Policies while the
same logical LLM gateway enforces the resulting publication.

### Advantages

- **One security choke point.** Provider credentials, outbound provider access,
  PII controls, budgets, audit, and policy enforcement have one authority.
- **No gateway shopping.** A caller cannot choose a different gateway with a
  larger model set or weaker Policy.
- **Matches the current schema.** Publication versions, projection sequences,
  validation, rollback, and latest-root lookup already use Host and Environment.
- **Clear semantics.** An Alias has one meaning and one effective publication
  in the environment.
- **Simpler operations.** One dashboard, desired-state sequence, rollback line,
  conformance gate, and incident owner exist per host and environment.
- **Efficient resource sharing.** Provider clients, connection pools, model
  metadata, rate data, and compiled policy structures can be reused across
  workloads.
- **Capacity scales horizontally.** Replicas add throughput without multiplying
  configuration authorities.
- **Consistent audit.** Usage, cost, policy decision, and projection evidence
  share a common root digest and sequence.
- **Safer policy evolution.** A new publication can be validated as a complete
  environment-wide graph before it replaces the previous root.
- **Smaller Portal surface.** No target registry, target assignment matrix,
  target-specific validation, or gateway selector is required.

### Disadvantages

- **Larger logical blast radius.** A bad publication can affect every workload
  in the host and environment, even though the last valid root is retained on
  validation failure.
- **Shared change cadence.** Teams cannot independently publish unrelated
  gateway roots without coordination.
- **Shared capacity plane.** Noisy-neighbor protection must be enforced with
  subject, Alias, quota-group, and provider limits rather than separate gateway
  configurations.
- **More demanding availability design.** The logical service must be deployed
  across enough replicas, failure domains, and capacity pools.
- **Strict backward compatibility.** Every replica version participating in a
  rollout must understand the published schema and enabled features.
- **Hard isolation requires infrastructure controls.** A Policy alone is not a
  substitute for legally required network, credential, or administrative
  separation.

### Mitigations

- Deploy replicas across availability zones and, where allowed, regions.
- Apply per-subject, per-Alias, per-quota-group, and global concurrency limits.
- Use multiple provider Deployments and explicit fallback Routes.
- Validate the complete candidate before publication and retain the last valid
  root on compiler or delivery failure.
- Require a pre-production environment before production publication.
- Record per-replica acknowledgements and alert on version or root divergence.
- Use admission fairness and bounded queues so one Agent cannot exhaust the
  shared service.
- Keep request handling snapshot-based so each request observes exactly one
  immutable root even during rollout.
- Separate operational duties for Policy approval, Credential management, and
  publication approval.

## Option B: Multiple Logical LLM Gateways Per Host And Environment

Under this option, one host and environment contains multiple gateway targets
or realms, each with its own publication sequence and model/policy graph.

```text
Host A / prod
├── gateway realm regulated
│   ├── replicas
│   └── restricted models and policies
└── gateway realm general
    ├── replicas
    └── general models and policies
```

### Advantages

- **Smaller configuration blast radius.** A publication affects only one realm.
- **Independent change cadence.** Separate teams can publish and roll back
  without coordinating one environment-wide root.
- **Harder infrastructure isolation.** Realms can use different networks,
  regions, provider accounts, credentials, keys, or administrative owners.
- **Independent capacity and SLOs.** Critical and best-effort workloads do not
  have to share a compiled root or replica pool.
- **Targeted feature rollout.** A realm can adopt a new gateway version or
  projection feature before other realms.
- **Regulatory separation.** A realm can form a provable boundary when policy
  filtering inside one process is insufficient.

### Disadvantages

- **Gateway selection becomes authorization.** Every Agent, Client, Principal,
  and Product Profile needs an authoritative gateway-realm assignment. The
  caller must never choose it directly.
- **Gateway-shopping risk.** If selection is ambiguous or user-controlled, a
  caller can bypass a restrictive realm by reaching a more permissive one.
- **Alias ambiguity.** The same Alias may mean different models or Policies in
  the same environment, complicating discovery, caching, audit, and support.
- **Policy precedence becomes two-dimensional.** Effective policy depends on
  both subject bindings and gateway realm, increasing conflict and fallback
  rules.
- **Substantial schema expansion.** Publications, resources, sequences,
  rollbacks, validation, delivery evidence, commands, and queries need a target
  key.
- **More complex distribution.** Each replica must receive exactly the root for
  its assigned realm and prove that assignment during acknowledgement.
- **Duplicated configuration.** Common models, Pricing, Policies, and Routes may
  be copied or require a new shared-resource plus publication-membership model.
- **Fragmented capacity.** Idle capacity in one realm cannot automatically serve
  another, and provider quota coordination becomes harder.
- **Cross-realm fallback is dangerous.** Falling back to a model in another
  realm can violate the isolation reason for having realms.
- **Higher operational cost.** Each realm needs ownership, monitoring,
  qualification, deployment, rollback, on-call, and disaster recovery.
- **Harder incident reconstruction.** Support must identify both environment
  and realm before determining the active root and applicable Policy.

### Schema And Runtime Work Required

A safe multiple-realm design would require at least:

1. A host-scoped gateway-realm table, such as
   `llm_gateway_realm_t(host_id, environment, gateway_realm_id, realm_name, ...)`.
2. `gateway_realm_id` in publication and projection primary keys, uniqueness,
   sequence, rollback, validation, and latest-root queries.
3. An authoritative subject-to-realm assignment that is evaluated before
   routing and cannot be overridden by request input.
4. Explicit Alias ownership or availability per realm.
5. Target-scoped candidate validation that follows only the realm's Aliases,
   Routes, Deployments, Pricing, Credentials, Policies, and Bindings.
6. A separate `gatewayRealmId` deployment setting and a distinct
   `gatewayInstance` replica identity.
7. Realm-specific distribution roots and checkpoints.
8. Per-publication, per-replica acknowledgement records.
9. Rules for Alias-name uniqueness, cross-realm discovery, migration, and
   whether cross-realm fallback is forbidden.
10. Portal forms, permissions, audit views, and operational dashboards for
    realm administration.

Adding only `gateway_id` to the publication table would not be sufficient.
Selection, authorization, validation, delivery, and audit all need the same
realm boundary.

## Comparison

| Criterion | One logical gateway per host and environment | Multiple gateway realms per host and environment |
| --- | --- | --- |
| Security authority | One unambiguous enforcement point | Strong isolation possible, but selection becomes a new authorization boundary |
| Caller behavior | Caller selects an authorized Alias | Caller needs a trusted realm assignment plus an authorized Alias |
| Model and Policy variation | Expressed through Aliases, Routes, Policies, and Bindings | Expressed through those resources plus realm membership |
| Schema fit | Matches the current database | Requires cross-stack schema and contract changes |
| Horizontal scaling | Add replicas | Add replicas independently per realm |
| Publication blast radius | Entire host/environment graph | One realm |
| Operational complexity | Lower | Significantly higher |
| Resource utilization | Shared pools are efficient | Capacity and connections are fragmented |
| Independent team cadence | Requires coordination | Strong |
| Hard network or credential isolation | Requires infrastructure controls around one logical service | Natural boundary between realms |
| Alias semantics | One meaning per environment | Potentially ambiguous without realm-qualified discovery |
| Audit and cost attribution | One sequence/root namespace | Must include realm in every record and report |
| Current implementation effort | Small; improve replica delivery tracking | Large migration across DB, commands, queries, Portal, distribution, and runtime |

## Recommendation

Adopt Option A for the initial production design:

> Each host and environment owns one logical LLM gateway configuration and one
> publication sequence. The gateway is deployed with multiple replicas. All
> direct LLM model access goes through that logical service.

This is the better default because the primary variations discussed so far are
model choice, Agent choice, provider route, quota, Policy, region, and
capability. Those are already control-plane dimensions and do not require
multiple configuration authorities.

The one-gateway design also makes the security rule easy to state and audit:

```text
One host + one environment -> one authoritative LLM policy and routing graph.
```

Multiple replicas solve availability and throughput. Multiple Aliases, Routes,
Deployments, Policies, and Bindings solve workload variation. AI microgateways
solve domain-local ingress and tool routing without becoming alternate paths to
model providers.

## AI Microgateway Boundary

AI microgateways may provide:

- MCP session and tool routing;
- Agent or workflow ingress;
- API authentication and local authorization;
- protocol translation unrelated to provider inference;
- request-size, rate, and connection controls for their owned domain;
- service discovery and telemetry for MCP servers or Agents.

They must not provide:

- direct OpenAI-compatible model dispatch;
- provider-specific model clients;
- provider API keys or Credential resolution;
- access to the LLM projection distribution directory;
- a locally configured model that bypasses Public Alias authorization;
- fallback directly to a provider when the LLM gateway is unavailable.

Enforce the boundary with both application and infrastructure controls:

- only LLM gateway workloads receive provider Credential references;
- provider egress allowlists permit the LLM gateway identity, not
  microgateway identities;
- service authorization permits microgateways to call the logical LLM gateway
  but not provider endpoints;
- the central gateway derives Host and Environment from trusted identity and
  routing context;
- audit alerts detect provider-domain traffic from any unauthorized workload.

## Request Flow

```text
Caller
  -> Agent, workflow, API, or MCP microgateway
  -> authenticated internal LLM request
  -> logical LLM gateway service for host/environment
  -> authorize subject and Alias
  -> apply compiled Policy and budgets
  -> select eligible Route and Deployment
  -> resolve external Credential reference
  -> call provider
  -> record usage, cost, Policy, Alias, Deployment, and publication digest
```

The microgateway may forward an Alias requested by its application, but the
central LLM gateway remains responsible for determining whether the authenticated
subject may use that Alias. It must never trust a forwarded provider Deployment,
Policy result, price, or Credential.

## Publication And Replica Delivery

One logical configuration still needs replica-aware operations.

The existing runtime writes one acknowledgement per `gatewayInstance`, but the
Portal publication row currently has one aggregate `deliveryState` and one
`deliveryEvidence` object. Production hardening should normalize replica
delivery without introducing multiple configuration realms.

A future table can use this shape:

```text
llm_gateway_publication_ack_t
  host_id
  environment
  gateway_publication_id
  gateway_instance
  applied_sequence
  root_digest
  gateway_version
  applied_ts
  state
  evidence
```

Recommended delivery semantics:

1. Validate the complete immutable candidate.
2. Make the new projection root available to replicas.
3. Each replica validates and atomically swaps its local root.
4. Each replica writes an acknowledgement containing its instance identity,
   sequence, root digest, and gateway version.
5. Portal shows desired replicas, acknowledged replicas, divergent replicas,
   and rollout age.
6. Deployment automation determines success using an explicit quorum or
   all-required-replicas rule.
7. A failed replica retains its last valid root and is removed from readiness
   until it converges or is deliberately rolled back.

This per-replica evidence solves the operational need without allowing replicas
to have intentionally different model or Policy configurations.

## Availability And Scaling

The logical gateway must not be a physical single point of failure.

- Run at least two replicas in production and spread them across failure zones.
- Use a stable internal service identity and health-aware load balancing.
- Keep request execution stateless apart from bounded local caches and immutable
  compiled snapshots.
- Coordinate provider quotas through the published Account quota group rather
  than per-replica counters alone.
- Bound global and per-subject concurrency, streaming concurrency, queue depth,
  replay bytes, and timeouts.
- Do not route traffic to a replica that has not applied an acceptable root or
  whose required Credential material cannot be resolved.
- Preserve the prior root for bounded rollback and restart recovery.

Regional replicas may still share one logical publication. Region and residency
decisions should be expressed through supported Routes, Deployments, claims,
and compiled policy. If a legal boundary requires separate administrators,
keys, networks, and publications, that is evidence for a future realm rather
than an ordinary replica.

## Failure Modes

| Failure | Required behavior |
| --- | --- |
| Candidate validation fails | Keep the current publication; do not distribute the candidate. |
| One replica rejects the new root | Keep its last valid root, remove it from readiness if necessary, and surface divergent delivery. |
| Provider Deployment fails | Use only eligible configured fallback Routes; never bypass Policy or Credential controls. |
| Logical gateway unavailable | Fail closed or use a bounded application-specific retry; microgateways must not call providers directly. |
| Policy cannot resolve one Agent default | Reject model resolution rather than selecting an arbitrary Alias. |
| Publication and Credential rotation overlap | Reload the external secret through the approved mechanism while retaining the immutable topology root. |
| Microgateway attempts provider egress | Deny at network and identity policy and emit a security alert. |
| Replicas report different digests at one sequence | Treat as a severe consistency incident and stop routing to divergent replicas. |

## When To Revisit Multiple Gateway Realms

Do not introduce a second logical LLM gateway merely because a team wants a
different model, provider, budget, Alias, Agent default, or release preference.
Those belong in the existing control plane.

Revisit Option B only when at least one of these is demonstrated:

- a regulatory requirement mandates separate network or administrative
  boundaries inside the same host and environment;
- provider Credentials must be inaccessible to the operators or runtime of the
  other realm;
- residency rules require physically isolated egress that cannot safely be
  represented by supported routing policy;
- separate business units require independent SLOs and publication authority,
  and shared Policy governance is explicitly not acceptable;
- the shared logical service cannot meet measured scaling or failure-isolation
  requirements after horizontal scaling and quota isolation are exhausted;
- a merger, sovereign deployment, or high-assurance workload requires an
  independently audited model-access boundary.

Before approving multiple realms, require an architecture review that defines:

- the trusted subject-to-realm selector;
- why the caller cannot influence that selector;
- Alias naming and discovery rules;
- whether any cross-realm fallback is permitted;
- separate Credential, network, audit, and operational ownership;
- migration and rollback behavior;
- the additional Portal and runtime contracts.

## Future-Compatible Naming

Use **logical LLM gateway** for the current `(host, environment)` authority and
**gateway instance** for a replica. Avoid calling an instance a gateway target.

If multiple isolated configurations are later required, introduce the explicit
term **LLM gateway realm**. Do not overload `gatewayInstance`, Environment, Alias
names, or synthetic Host records to represent the realm. That keeps a future
additive migration understandable:

```text
(host_id, environment)
```

can become:

```text
(host_id, environment, gateway_realm_id)
```

with the existing data migrated into a generated `default` realm.

## Implementation Guidance

### Phase 1: Confirm The Single-Logical-Gateway Contract

- Document the one-publication-stream invariant in database and API contracts.
- Treat duplicate independently managed LLM gateways for one host/environment
  as a deployment error.
- Ensure every LLM replica has a unique, stable `gatewayInstance`.
- Ensure all replicas receive the same root and use a common readiness policy.
- Block model-provider egress and Credential distribution for microgateways.

### Phase 2: Harden Delivery And Operations

- Add normalized per-replica publication acknowledgements.
- Add Portal views for replica convergence, version compatibility, and stale
  roots.
- Add alerts for digest divergence, missing acknowledgements, unauthorized
  provider egress, and capacity saturation.
- Test replica replacement, partial rollout, rollback, Credential rotation, and
  provider failover.

### Phase 3: Prove Workload Isolation Inside One Configuration

- Verify per-subject and per-Alias admission fairness.
- Verify Policy Binding and default-Alias behavior.
- Verify quota-group sharing across replicas.
- Verify residency and classification handling supported by the publication
  compiler and gateway version.
- Demonstrate that MCP and Agent microgateways cannot bypass the central path.

### Phase 4: Optional Realm ADR

Only start this phase when the revisit criteria are met. Produce a separate ADR
and threat model before changing the current primary keys or publication API.

## Acceptance Criteria

- A host/environment has one current desired publication version and root
  digest.
- All ready replicas report that root digest and an allowed gateway version.
- Different Agents can resolve different Aliases and Policies without separate
  gateway configurations.
- Provider Credentials are available only to the logical LLM gateway workload.
- Microgateways can invoke approved Aliases but cannot call model providers.
- Removing the logical LLM gateway causes model requests to fail closed.
- A bad publication leaves the last valid root serving.
- Portal can identify every replica that has or has not applied a publication.
- Audit records identify Host, Environment, subject, Alias, Policy decision,
  Deployment, cost, publication sequence/root digest, and gateway instance.

## Open Questions

- Should production delivery require acknowledgement from every desired replica
  or a configurable quorum before Portal marks the publication delivered?
- Which service owns the authoritative desired-replica inventory used to judge
  acknowledgement completeness?
- Should a replica that is one valid root behind remain ready during a bounded
  rollout window?
- Which internal identity and claims bind a microgateway request to Host and
  Environment?
- Which network-policy mechanism will prove that microgateways cannot reach
  provider endpoints?
- Which supported policy fields provide per-subject fairness before production?
- Are regional replicas allowed to serve the same Alias when the current
  compiler cannot enforce a requested residency condition?
- What measured requirement would trigger a gateway-realm architecture review?

## Final Recommendation

Keep the current cardinality and make it explicit:

```text
one host + one environment
  = one logical LLM gateway configuration
  = one immutable publication sequence
  = many interchangeable replicas
```

Allow many AI microgateways, but keep them outside the LLM trust boundary. This
design provides the strongest default governance model, aligns with the current
database, and still supports different models and Policies through the existing
Alias, Route, Deployment, Policy, and Binding abstractions.
