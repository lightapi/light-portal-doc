# LLM Gateway Configuration Topology

## Decision

Light Portal is the authoring control plane for LLM providers, deployments,
aliases, pricing, and policy. The standard Portal configuration system is the
only delivery channel to `light-gateway`.

For each selected gateway instance, Portal compiles the active GenAI records
into typed `llm-router.*` instance properties. The user creates and promotes a
normal immutable config snapshot. Config server exposes that snapshot as
`values.yml`, and the gateway consumes it only during startup or an explicit
module reload.

The former LLM-specific filesystem projection, continuous polling worker,
sequence/checkpoint protocol, and per-replica publication acknowledgement are
not part of this architecture.

## Source of Truth

```text
GenAI control-plane records
          |
          | deterministic compilation and instance publication
          v
Typed llm-router.* instance properties
          |
          | normal snapshot creation and promotion
          v
Immutable config snapshot / values.yml
          |
          +---- startup -------------------------+
          |                                      |
          +---- selected llm-router reload ------+
                                                 v
                                      compiled immutable LLM runtime
```

The config snapshot is the runtime authority. Control-plane tables remain the
authoring authority, but changing them alone cannot alter a running gateway.
Publishing properties alone also cannot alter a running gateway: the intended
snapshot must be promoted and then consumed by startup or an explicit reload.

## Gateway Instances and Replicas

An LLM gateway instance is a Portal instance with its own properties and
current config snapshot. A host and environment may have a normal production
instance plus separate test or canary instances. Applying one immutable
configuration revision to multiple instances supports canary qualification and
exact promotion without regenerating mutable control-plane state.

Replicas of one instance share the same current snapshot. Replica identity is
useful for runtime health, audit, and diagnostics, but it is not a separate
configuration partition and does not require an LLM publication ACK protocol.

## Startup

At startup:

1. `startup.yml` identifies config server and the target instance context.
2. The runtime downloads the current immutable `values.yml` snapshot.
3. The config loader resolves `llm-router.yml` from that values document.
4. `LlmCompiler` validates and compiles the complete provider, deployment,
   alias, pricing, policy-derived, and runtime-material graph.
5. The gateway atomically publishes one immutable LLM runtime snapshot.

If the enabled LLM configuration is invalid, the gateway starts with LLM
routing unavailable and reports the configuration error. It does not assemble a
second candidate from local projection files.

## Explicit Module Reload

The control plane uses the existing module reload operation. It may request one
or more modules. The runtime downloads the current `values.yml` once for that
operation, creates a fresh reload context, and invokes only the requested
reloaders.

When `llm-router` is selected, `LlmRouterReloader` compiles a candidate from the
fresh context. The candidate replaces the active LLM runtime only after the
entire graph validates. A failed compile leaves the previous runtime active.
Requests already in flight continue using the immutable snapshot they captured.

Reloading an unrelated module cannot change LLM routing.

## Configuration Contract

Portal-owned typed properties include:

| Property | Meaning |
| --- | --- |
| `llm-router.enabled` | Enables the module when valid topology is present. |
| `llm-router.developmentFixtures` | Explicit development-only validation mode. |
| `llm-router.providers` | Provider endpoints, auth references, headers, network profiles, and quota ownership. |
| `llm-router.deployments` | Physical model IDs, capabilities, runtime capacity, prices, and provider references. |
| `llm-router.aliases` | Public/internal aliases, ordered routes, limits, audit, PII, and required capabilities. |
| `llm-router.openaiExtensionAllowlist` | Explicit request-extension policy. |
| `llm-router.runtimeMaterial` | Non-secret credential mappings, trust-bundle mappings, evidence keys, and reasoning-seal references. |

Maps and lists must remain typed YAML nodes in `values.yml`; they must not be
double-encoded as quoted JSON. Publication must be deterministic, bounded, and
must reject dangling or cross-host references.

## Secret Boundary

Portal, instance properties, config snapshots, and `values.yml` contain only
credential references. Raw provider keys and reasoning-seal key bytes are
injected into the gateway environment or another locally supported secret
materialization mechanism.

`runtimeMaterial.credentialEnvironment` may map an opaque `credential://`
reference to an allowed environment-variable name. Direct `env:NAME`
references are also supported. Trust bundles use approved references plus local
paths and digests. The compiler fails closed if required material cannot be
resolved and never logs resolved values.

## Publication Workflow

1. Select the logical environment and target LLM gateway instance.
2. Generate a read-only preview from active control-plane records.
3. Verify exact model IDs, route order, capabilities, pricing, and credential
   references; verify no secret value appears.
4. Publish the canonical typed property set to that instance.
5. Create and promote a config snapshot through the normal Config workflow.
6. Restart the gateway, or request an explicit reload containing
   `light-pingora/llm-router`.
7. Confirm startup/module-reload success, then test provider behavior through
   the gateway.

Publication and snapshot loading prove configuration consistency and
application. They do not prove provider reachability, credential validity,
quota availability, or model quality.

## Canary and Rollback

For canary promotion, apply the same immutable property revision and digest to
the production instance; do not regenerate from mutable records after the
canary test. Create/promote the production instance snapshot and perform its
normal restart or reload.

Rollback applies an earlier immutable property revision to the affected
instance, creates/promotes a new snapshot, and restarts or reloads. Historical
revisions and snapshots are never mutated.

## Operational Guarantees

- One config-server snapshot supplies every selected module in a reload.
- Configuration changes only at startup or explicit reload.
- Only requested modules reload.
- LLM publication has no independent file poller or ACK state machine.
- Invalid LLM reloads retain the last-known-good runtime.
- In-flight requests remain pinned to one immutable compiled generation.
- Secrets remain outside Portal and config-server artifacts.
- Local, dev, and install environments use the same exported event baseline and
  standard snapshot workflow.
