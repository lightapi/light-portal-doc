# Product Upgrade Runtime Contract

This design note supports the [Product Upgrade and Rollback runbook](../operations/product-upgrade-rollback.md).
It separates implementation evidence and proposed work from operator procedures.

Source review: September 14, 2026, against the local checkouts listed below.
These are source findings, not qualification of a deployed fleet. Java runtime
observations refer specifically to light-4j's `DefaultConfigLoader` (DCL), not
every custom loader or the Rust runtime.

## Decision: selection and compatibility are different

Keep the Portal Config Server lookup identity as `host + serviceId + envTag`.
A product upgrade uses a version-specific authoring instance and an explicitly
approved snapshot. Activating that snapshot changes what the identity serves.
`productVersion` is not required as another lookup selector, and legacy
product/API parameters are tolerated but ignored by the Portal server.

This does **not** provide either product-version filtering of every generated
property or a runtime compatibility check. A 2.3.7 binary can currently load
the current 2.3.8 snapshot without a version-mismatch warning. The database
snapshot record contains `product_id` and `product_version`; the HTTP response
does not currently expose a product-version header.

An `expectedProductVersion` guard would assert compatibility with the selected
snapshot, not select a different snapshot. It should be implemented as a
separate contract. Incompatible binaries fetching different configurations from
Config Server at the same time must use separate authorized rollout identities
today. Merely adding a product-version parameter does not establish a complete
deployment, authorization, snapshot-retention, or rollback contract.

## Database identity

Keep the version in the authoring-instance unique index:

```sql
CREATE UNIQUE INDEX instance_uk
ON public.instance_t (host_id, service_id, env_tag, product_version_id);
```

`config_snapshot_t` uses `snapshot_id` as its primary key and these partial
unique indexes:

```sql
CREATE UNIQUE INDEX uq_config_snapshot_current_instance
ON public.config_snapshot_t (host_id, instance_id)
WHERE current IS TRUE;

CREATE UNIQUE INDEX uq_config_snapshot_current_logical_identity
ON public.config_snapshot_t (host_id, service_id, env_tag)
WHERE current IS TRUE;
```

Multiple version-specific instances and historical snapshots are allowed, but
only one snapshot is current per runtime identity. Removing the instance's
version key would prevent retaining both release authoring graphs under that
identity. Neither `instance_t.current` nor `instance_t.active` selects the
runtime snapshot.

## Implementation status

| Area | Verified behavior | Consequence or follow-up |
| --- | --- | --- |
| Candidate clone | `createSnapshot=true` creates a current snapshot and resets the previous current selection for the same identity. | Clone with it disabled; create a non-current candidate snapshot separately. |
| Snapshot selection | `/configs` selects current even when `snapshotId` is supplied; `/certs` and `/files` honor explicit snapshot IDs within the authorized identity. | Current-only values selection does not support per-deployment pinning. See F5. |
| DCL startup | Three separate requests; no capture of the values response's snapshot ID or pinning of ancillary calls. | Activation between calls can mix values and files from different snapshots. See F3. |
| DCL provenance | Ignores snapshot/instance/digest headers; the legacy `isHeadersMatchedJar` call is commented out. | No runtime-reported snapshot/digest evidence or active version check. See F3/F4. |
| DCL reload | `ConfigReloadHandler` calls the loader; default reload fetches values only, not certs/files. | Hold reloads during incompatible overlap; a reload is not a whole-bundle transition. See F3/F7. |
| DCL failed fetch | On connection/connect-timeout or HTTP >=300 failure, the missing-values exception is inside a directory-exists check. A missing directory can fall through without values; an existing cache can permit fallback. | For pipeline-controlled remote release starts, pre-create the directory without `values.yml` and reject fallback. Steady-state restart policy is unchanged. Fail-fast behavior must not depend on directory existence; see F7. |
| DCL ancillary errors | After values are cached, tolerated cert/file HTTP errors return an empty map. `loadFiles` checks null, so it writes nothing without a files-specific failure. The shared error still says “configs.” | Check all shared failures, not just the values source log. Distinguish an empty successful inventory from a failed fetch; see F3/F7. |
| DCL local state | File downloads do not remove obsolete files. Values write errors can be logged while the caller still reports Config Server as the source. | Source logs alone do not prove successful adoption. Use release-specific directories and inventory checks; see F7. |
| DCL sensitive logs | `loadFiles` dumps complete cert/file maps at DEBUG; `loadConfigs` dumps values at TRACE; HTTP failure messages include response bodies at ERROR. | Keep the DCL logger at INFO or more restrictive, restrict error-log access, and remove/redact payloads in F3. |
| Version applicability | Editor uses mappings/profiles; snapshot generation does not enforce their applicability. | Review actual output, including inherited overrides. See F1. |
| Inheritance/defaults | Editor prefers environment over product version; snapshot generation prefers product version over environment. Catalog defaults are not a snapshot inheritance layer. | Align resolution and define default materialization. See F2. |
| Snapshot reproducibility | Serving joins `config_t` for configuration names. | Retaining snapshot rows alone does not isolate output from incompatible catalog renames; retain catalog compatibility and verify exports. |
| Pipelines | Clone preserves the referenced pipeline ID and resets job/runtime state. Pipeline definitions and external jobs are mutable. | Select the target pipeline and retain immutable source/artifact/input references. See F6. |
| Authorization | Config Server validates host/service/env context, not an instance UUID. | Same-identity clones do not inherently need new Config Server tokens; a new rollout identity needs matching authorization. |
| Retirement | Soft delete hides inactive instances in normal listings and cascades to owned graph rows; snapshots are retained separately. Snapshot lookup does not check `instance_t.active`. | Retirement does not revoke a selected snapshot. Guard it operationally; see F6. |
| Retry | `instance_uk` and clone collision queries include retired rows. | Restore/reconcile the same target-version instance instead of cloning over it. |
| Fleet lifecycle | Individual operations exist; no complete two-release retention/reservation/orchestration workflow. | Runbook controls are manual today. See F6. |

### Limits of current DCL evidence

The startup source message distinguishes a usable values response from the
fallback path, but does not prove a local cache exists. It is not snapshot
attestation, and a write failure can still produce the Config Server source
message. The corresponding reload message has the same limitation. Absence of
an exception does not prove usable values or all files arrived. With a missing
directory, DCL can continue past failed fetches; whether the rest of the
application starts depends on its other configuration requirements.

`x-light-config-content-digest` is a digest of the server's emitted values YAML,
not a digest of all certs/files or all in-memory merged configuration. DCL parses
and reserializes values before writing, so comparing that header directly with
the local file's raw hash is not a valid verification method. The runbook uses
external fetch/inventory/behavior evidence and explicitly leaves runtime-reported
snapshot identity unknown until instrumentation exists.

### Release-start gates versus steady-state policy

The runbook's no-cache gate is preparation for rollout/rollback starts and retries
controlled by the release pipeline. It is not a permanent init-container cache
deletion policy. After verification, automatic restarts and scale-out retain
their normal fallback behavior; F7 separately owns any change to that behavior.

A remote-only rollback requiring a restart depends on Config Server availability.
Qualifying a local-export contingency before an upgrade, or explicitly accepting
that dependency, is an operational prerequisite for the release record. A running
old blue/green cohort avoids that restart only while it remains healthy.

## Proposed follow-up work

F1–F7 identify the implementation work below. Each has a GitHub issue with the
scope and acceptance criteria from this design. F4 is split into coordinated
runtime and server issues. All were assigned to `stevehu` as coordinating owner
when filed; use the linked issues for current assignment and implementation status.

| Work | Tracking issue | Coordinating owner |
| --- | --- | --- |
| F1 — snapshot applicability | [portal-db#342](https://github.com/lightapi/portal-db/issues/342) | `stevehu` |
| F2 — editor/snapshot resolution | [light-portal#809](https://github.com/lightapi/light-portal/issues/809) | `stevehu` |
| F3 — DCL pinning and safe provenance | [light-4j#2790](https://github.com/networknt/light-4j/issues/2790) | `stevehu` |
| F4 — compatibility guard | [light-4j#2792 (runtime)](https://github.com/networknt/light-4j/issues/2792), [portal-service#83 (server)](https://github.com/lightapi/portal-service/issues/83) | `stevehu` |
| F5 — explicit values snapshot selection | [portal-service#82](https://github.com/lightapi/portal-service/issues/82) | `stevehu` |
| F6 — retention and fleet orchestration | [light-portal#808](https://github.com/lightapi/light-portal/issues/808) | `stevehu` |
| F7 — DCL bundle/cache/reload policy | [light-4j#2791](https://github.com/networknt/light-4j/issues/2791) | `stevehu` |

F1/F2/F6 coordinate schema and Portal changes across `portal-db` and
`light-portal`. F3/F7 are cross-linked for DCL failure-state ownership; the two
F4 issues are cross-linked for the response-metadata and runtime guard contract.

### F1. Validate product-version applicability at snapshot creation

Define the authoritative release configuration contract across direct mappings,
profiles, inherited overrides, and approved custom/generated properties. Reject
unsupported or incomplete candidate output with actionable diagnostics; do not
silently drop extensions or delete older releases' catalog properties.

Acceptance: snapshot tests cover additions, removals, renamed/changed properties,
required values, inherited unsupported overrides, profile mappings, and approved
extensions. An old release's retained snapshot/authoring state is unchanged by
qualifying a new release.

### F2. Align editor and snapshot resolution

Choose and document one inheritance order, then use it for both preview and
snapshot creation. Explicitly decide which defaults are emitted and which are
provided by the pinned binary; do not assume that a new catalog mapping emits
its default automatically.

Acceptance: table-driven tests exercise every competing layer, null/empty
semantics, explicit overrides, and target-release defaults. The same input graph
produces the same effective preview and generated output.

### F3. Pin DCL ancillary downloads and expose safe provenance

Capture `x-light-config-snapshot-id` from the successful `/configs` response and
pass that exact `snapshotId` to `/certs` and `/files`. This uses existing server
support and does not depend on F5. Preserve the authorized host/service/env and
phase on all requests. Do not resolve current again between these calls.

Capture the host, instance, snapshot, and values-content-digest response headers
as non-secret provenance. Log/expose them through a supported runtime information
surface only with accurate state: fetched, written, and successfully adopted are
different stages. Track startup versus reload, remote versus local source, and
partial/failed bundle status. Verify the digest over the raw response before
parsing if claiming transport-content verification; do not imply it attests
in-memory values or ancillary files.

Report endpoint-specific success/failure without logging response payloads:
the present shared “configs” error and empty-map result obscure whether certs
or files failed. Remove/redact `loadFiles` DEBUG payloads, `loadConfigs` TRACE
values, and raw HTTP error bodies, including exception messages. Preserve useful
endpoint category, status, and non-secret provenance rather than secret content.

Acceptance: activate snapshot B between values and ancillary calls for A and
verify every downloaded asset still belongs to A. Exercise missing/malformed
headers, older servers, unavailable snapshots, and write failures with explicit
behavior. After a successful values fetch, make `/certs` and `/files` independently
return >=300 or fail to connect; each failure must be distinguishable from a
successful empty inventory and must not yield a complete-bundle success claim.
Test at INFO, DEBUG, and TRACE with sentinel secrets in values, binary file maps,
and error bodies; none may appear in logs or exposed provenance. Do not claim
bundle-wide reload support while reload only fetches values. Coordinate F3 and
F7 as linked light-4j DCL work items with clear failure-state ownership.

### F4. Add a product-version compatibility guard

Return `x-light-config-product-version` from the **selected snapshot's recorded
version**, not a fresh lookup of a mutable instance's version. Include recorded
product identity as needed to make the comparison unambiguous. The runtime
compares this metadata with its expected deployed product release.

Treat `expectedProductVersion` as a proposed assertion contract, not an existing
configuration option and not a second lookup selector. For ordinary packaged
products, validate the artifact's release metadata. Do not blindly compare every
application with `Server.getLight4jVersion()`: it reads the package's
`Implementation-Version`, which may identify the framework in a custom build
rather than the deployed product. Define an explicit, verifiable product/version
source for such artifacts.

Start with an explicit warning-only adoption mode if needed for compatibility;
provide a strict rejection mode for releases requiring an exact match. Define
missing metadata, legacy servers, and any declared cross-version compatibility
policy. A strict mismatch must not silently become a successful startup using
an unverified cache. Do not simply uncomment the legacy header check: it expects
the older product/API header contract, not the proposed snapshot metadata.

Acceptance: matching releases succeed, mismatches warn or fail according to the
selected policy, missing metadata is observable, custom/shaded artifact identity
is tested, and incompatible cached configurations cannot bypass strict mode.
The guard is compatibility validation, not authorization or property filtering.

### F5. Define explicit values snapshot selection

Decide the contract for `/configs?snapshotId=...`, including how deployments
choose and retain a snapshot. If implemented, authorize it against the same
host/service/env and return provenance for exactly that snapshot. Never silently
fall back to current when an explicit ID is invalid or unavailable. Until then,
document that the accepted query field is ignored; consider a separately
qualified rejection/deprecation policy to avoid implying pinning works.

Acceptance: cover historical/current selections, wrong host/service/env,
missing/retired dependencies, and consistent values/certs/files. Per-deployment
selection needs pipeline/client wiring and retention guarantees in addition to
the endpoint change. This is not required for F3's within-startup pinning.

### F6. Release retention and fleet orchestration

Implement durable release records/reservations if Portal is to own them, explicit
pipeline/artifact revision binding, target-pipeline validation, bounded clone
batches, and progress through projection and runtime verification. Apply one
two-instance limit/reservation per logical deployment group across all cohort
identities and replicas, as defined in the runbook. Retirement guards must
consider selected snapshots, running workloads, dependencies, and
rollback obligations. Retry a retired version through safe restoration and
reconciliation; do not make clone silently overwrite an archived aggregate.

Acceptance: exercise two-slot transitions, alternating blue/green env tags,
sidecar compatible-overlap and stop/activate/start policies, interrupted/retried
runs, reservation takeover, mixed fleet success/failure, safe retirement, and
restoration of a failed target whose source has since changed. No instance may be retired solely
because another fleet member succeeded. The runbook's manifest and manual lock
conventions are not a substitute for implementing these guarantees.

### F7. Qualify DCL bundle adoption and cache/reload policy

Keep broad fallback-policy changes separately scoped from the selector decision.
Define release-scoped cache ownership and file inventories, failure propagation,
and transactional adoption if a whole-bundle guarantee is required. Pinning HTTP
requests alone does not make writes atomic or remove obsolete files.

Fail fast when required remote values cannot be obtained and no policy-approved,
compatible cache exists, **whether or not the target directory exists**. Do not
infer cache presence from the directory or emit a cache-source success claim
without verifying the cache. Define explicit outcomes for unusable/empty values
and partial bundle failures. The runbook rejects fallback for pipeline-controlled
release starts, not all subsequent automatic restarts. Enforce that gate in the
release workflow rather than permanently deleting caches on each boot. Any
broader change to normal-runtime fallback policy requires compatibility approval.

Acceptance must cover:

- Absent directory, existing directory without `values.yml`, approved cache,
  and incompatible/stale cache, crossed with HTTP >=300 (including no-current
  snapshot 404), connection/connect-timeout failure, and empty/unusable values.
  No-cache failure must not silently continue in either directory state.
- A successful values fetch followed by separate cert/file failures. Failed
  empty-map responses must not be accepted as valid empty inventories or silently
  reuse stale assets. Coordinate endpoint-specific diagnostics and outcome state
  with F3; no complete-bundle success claim after a partial failure.
- Values/file write failures, partial-start retries, obsolete files on volume
  reuse, and concurrent reload. Do not remove independent local credentials or
  bootstrap files. Decide whether reload updates the whole bundle or explicitly
  requires restart for cert/file changes.
- Release-start gates versus verified-release steady-state restarts: applying
  the pipeline gate must not silently disable the existing cache fallback for
  later liveness restarts, evictions, or scale-out.

F7 is tracked in [light-4j#2791](https://github.com/networknt/light-4j/issues/2791),
coordinated with F3 in [light-4j#2790](https://github.com/networknt/light-4j/issues/2790).

## Issue disposition

The original [light-4j issue #2789](https://github.com/networknt/light-4j/issues/2789)
asks whether DCL and Config Server should support a product-version parameter.
The design answer is no required selector, but that does not mean the current
runtime already supplies compatibility checking or consistent bundle loading.

The selector decision and implementation completion are separate. Once these
documents are published and linked in the reporter response alongside the
tracking issues, #2789 can close as the decision to keep the existing selector.
F1–F7 remain tracked independently until their acceptance criteria are met.
Closing the selector question does not claim that runtime compatibility,
consistent bundle adoption, unattended upgrades, or live fleet qualification
have been delivered by this documentation change.

## Source references

Paths identify the reviewed implementation, not permanent line-number anchors.
Recheck them when the contract changes.

| Repository | Path and relevant implementation |
| --- | --- |
| `portal-db` | `postgres/schema/base.sql`: `instance_uk`, snapshot columns/indexes, `create_snapshot`, pipeline/deployment tables, cascade policy. |
| `portal-db` | `postgres/schema/cascade-runtime.generated.sql`: soft-delete/restore triggers and snapshot exclusions. |
| `light-portal` | `db-provider/src/main/java/net/lightapi/portal/db/clone/InstanceCloneExecutor.java`: optional snapshot activation and target identity collision check. |
| `light-portal` | `db-provider/src/main/java/net/lightapi/portal/db/clone/InstanceCloneQueryService.java`: plan-time target collision check includes retired rows. |
| `light-portal` | `db-provider/src/main/java/net/lightapi/portal/db/clone/InstanceCloneEventFactory.java`: copied deployment bindings retain pipeline references and reset job/runtime state. |
| `light-portal` | `db-provider/src/main/java/net/lightapi/portal/db/persistence/ConfigPersistenceImpl.java`: editor applicability/inheritance and snapshot activation. |
| `light-portal` | `db-provider/src/main/java/net/lightapi/portal/db/persistence/InstanceDeploymentPersistenceImpl.java`: deployment pipeline updates and soft deletion. |
| `config-command` | `src/main/java/net/lightapi/portal/config/command/handler/CreateConfigSnapshot.java`: projection readiness and graph revision check. |
| `portal-service` | `apps/config-server/src/main.rs`: `ConfigQuery`, `get_configs`, `get_certs`, `get_files`, `authorize_config_request`, response provenance. |
| `portal-service` | `crates/portal-core/src/lib.rs`: `get_current_config_snapshot`, `get_snapshot_entries`, explicit snapshot resolution. |
| `light-4j` | `server/src/main/java/com/networknt/server/DefaultConfigLoader.java`: `init`, `reloadConfig`, `loadConfigs`, `loadFiles`, `getServiceConfigs`, inactive `isHeadersMatchedJar`. |
| `light-4j` | `server/src/main/java/com/networknt/server/Server.java`: package metadata in `getLight4jVersion` and `getLight4jProduct`. |
| `light-4j` | `config-reload/src/main/java/com/networknt/config/reload/handler/ConfigReloadHandler.java`: loader invocation on reload. |
| `portal-view` | `src/pages/instance/InstanceClone.tsx` and `InstanceAdmin.tsx`: current-snapshot option and default active filter. |
