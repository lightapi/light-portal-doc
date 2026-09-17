# Product Upgrade and Rollback

For sidecars and centralized gateways, clone a version-specific instance when
scheduling an upgrade. Retain the previous instance, configuration, and pipeline
for rollback and continued editing. Publishing a product release alone changes
no deployments; upgrade fleets in batches.

This is an operator-controlled policy. The
[runtime contract](../design/product-upgrade-runtime-contract.md) records current
limitations, including Java DCL snapshot consistency, provenance, and compatibility.

## Emergency rollback checklist

Use the prequalified rollback mode. For a healthy old blue/green cohort, verify
it and switch traffic without restarting it or changing its files. A remote-only
rollback needing a restart depends on Config Server availability; see
[rollback availability](#rollback-availability).

1. **Record:** retrieve the [previous release record](#release-record-location-and-template),
   artifact, snapshot/bundle, pipeline inputs, and migration recovery constraints.
2. **Reservation:** take control of the [existing release reservation](#release-controls)
   with its owner; prevent competing deployments and configuration changes.
3. **Hold:** block new traffic to unhealthy workloads and hold incompatible
   reloads/restarts. For a same-identity restart, stop the incompatible cohort
   before changing its snapshot. See [rollback coordination](#rollback-procedure).
4. **Directory, for this pipeline-controlled start:** [remote mode](#configuration-loading-modes)
   needs a pre-created writable directory without `values.yml`; local mode needs
   the recorded export. Preserve bootstrap material and exclude candidate files.
5. **Activate or install:** [activate the saved snapshot or install the qualified
   local bundle](#rollback-procedure), then start the old artifact with its old pipeline.
6. **Startup checks:** reject fallback and any download/write failure, verify the
   file inventory and runtime health, and keep the [DCL logger at INFO](#java-dcl-startup-and-configuration-evidence).
7. **Traffic:** admit traffic only to verified old-version workloads; for
   [blue/green](#centralized-gateway-bluegreen-example), switch to the healthy old pool.
8. **Evidence:** record results and verification limits, obtain [rollback approval](#release-controls),
   then end the freeze/reservation. Defer retirement until the group is stable.

## Configuration loading modes

A Java DCL runtime loads its configuration at startup in one of two modes. The
release record names the mode qualified for each release.

| Mode | How configuration arrives | Startup dependency |
| --- | --- | --- |
| **Remote mode** (normal) | `light-config-server-uri` is set. `DefaultConfigLoader` calls Config Server `/configs`, `/certs`, and `/files` for `host + serviceId + envTag`, receives the **current** snapshot for that identity, and writes `values.yml`, certificates, and files into the config directory. | Config Server must be available. |
| **Local-export mode** (contingency) | `light-config-server-uri` is absent from every property/environment source. The pipeline installs a previously exported, approved bundle (`values.yml`, certificates, files) into the config directory, and the runtime starts from those local files. | None on Config Server; the bundle must be retained and checksummed. |

In remote mode, a pipeline-controlled start must use a writable directory with
**no `values.yml`**. Otherwise a failed download can fall back to an existing
file, possibly the candidate's, and the start still looks successful. See
[startup checks](#java-dcl-startup-and-configuration-evidence).

Local-export mode is a rollback contingency, not a replacement for remote mode.
Qualify it before the upgrade when a restart-based rollback must survive a Config
Server outage; see [rollback availability](#rollback-availability).

## Configuration identity decision

Keep the Config Server lookup identity:

```text
host + serviceId + envTag
```

Activate the approved snapshot for that identity; `configPhase` selects its
phase. Keep `product_version_id` in the instance and its unique index to retain
version-specific authoring state. Instance UI flags do not select the served
snapshot or identify the running binary.

Qualify binary/configuration compatibility before activation: the Portal server
ignores legacy `productVersion` parameters, and Java DCL has no active version
guard. See the [identity and compatibility decision](../design/product-upgrade-runtime-contract.md#decision-selection-and-compatibility-are-different).

## Preserve the complete deployable release

Record the instance/product version, runtime identity, snapshot, deployment
binding, pipeline, artifact, inputs, and verification evidence using the template
below. Pin pipeline source/scripts/templates and binary/image checksums: pipeline
IDs and moving image tags alone cannot reproduce a release. Preserve access to
the required credentials through secret-manager references.

Retain both the editable instance and deployment recipe. Snapshot activation
selects configuration; redeployment installs the old binary. Shared settings,
external-state migrations, and editable graphs require their own recovery plan.

### Release record location and template

The owning service/platform team designates a deployment configuration repository
and publishes its URL/on-call owner in the service catalog or change register.
Store records at `release-records/<host-id>/<deployment-group>/<release-id>.yml`,
using a stable, path-safe group name. Link commit permalinks from the change
ticket, pipeline run, and snapshot description. Retain input revisions and
attempt history, accessible to on-call staff even when Portal is unavailable.

This template is an operational convention, not an automatic Portal export.
Use one record per deployment binding, with fleet records linking members.
Keep secrets and configuration bundles in restricted artifact storage.

```yaml
releaseId: "gateway-2.3.9-attempt-1"
recordRepository: "<canonical team deployment configuration repository URL>"
recordOwner: "<owning service/platform team and on-call contact>"
deploymentGroup: "production-gateway"
runtimeIdentity:
  hostId: "<host UUID>"
  host: "<host name>"
  serviceId: "light-gateway"
  envTag: "prod"
instanceId: "<instance UUID>"
productVersionId: "<product-version UUID>"
productVersion: "2.3.9"
deploymentInstanceId: "<deployment binding UUID>"
artifact: "<immutable image digest or binary URI plus checksum>"
pipeline:
  id: "<pipeline UUID>"
  sourceRevision: "<immutable pipeline/scripts/templates revision>"
  inputsRef: "<restricted input artifact URI plus checksum>"
  credentialRef: "<secret-manager reference, never a credential>"
configuration:
  mode: "current-snapshot" # or qualified local-export deployment
  modeQualificationRef: "<successful pre-upgrade test of this release/mode>"
  rollbackAvailabilityRef: "<tested local-export contingency or approved Config Server dependency>"
  snapshotId: "<approved snapshot UUID>"
  configPhase: "R"
  responseDigest: null # capture the raw /configs response digest when served
  bundleRef: "<restricted values/certs/files artifact plus inventory/checksums>"
  authoringBaselineRef: "<reviewed graph revision/export/diff reference>"
rollbackRecord: "<previous release record commit permalink>"
coordination:
  reservationRef: "<exclusive pipeline lock/run or serialized change ticket>"
  changeFreeze: "clone through observation completion"
  observation: "24h production, including a representative traffic cycle"
  rollbackCriteriaRef: "<approved health, traffic and compatibility thresholds>"
  operator: "<deployment owner/on-call role>"
  approver: "<service/release owner>"
evidence:
  pipelineRun: null
  runtimeVersionRef: null
  fetchAndFileVerificationRef: null
  runtimeReportedSnapshotId: null # unavailable in unmodified Java DCL
  assurance: "pending; distinguish external evidence from runtime attestation"
  completionApprovalRef: null
  retirementApprovalRef: null
```

The response digest covers `/configs` YAML, not a complete certificate/file
bundle. Keep separate export/file checksums; a non-current candidate's exported
output is not itself a `/configs` response. DCL reserializes values before
writing `values.yml`, so its local file hash need not equal the response digest.

## Retain at most two available instances

Apply one limit per **logical deployment group**: at most two available Portal
instances and one upgrade in progress across all its versions, runtime
identities, and replicas. Record the group's member identities in the release
plan. Normally a group has one `(host_id, service_id, env_tag)`; blue/green adds
two cohort identities to the same group, not two separate retention budgets.
For sidecars, the group normally represents one API's sidecar deployment and
all its replicas, not each Pod and not the entire fleet. Keep:

1. The currently deployed, verified instance.
2. Either the previous working instance or the next upgrade candidate.

The words **current release**, **rollback release**, **candidate**, and
**retired** describe operational roles in this guide; they are not new database
status values.

A strict two-instance policy uses the following transitions:

| Stage | Available instance | Available instance | Retired instance |
| --- | --- | --- | --- |
| 2.3.8 is running and verified | 2.3.8 current | 2.3.7 rollback | Older releases |
| Begin the 2.3.9 upgrade | 2.3.8 current | 2.3.9 candidate | 2.3.7 |
| 2.3.9 succeeds and passes the observation period | 2.3.9 current | 2.3.8 rollback | 2.3.7 |
| 2.3.9 fails | 2.3.8 current | Optionally restore 2.3.7 | Failed 2.3.9 |

Before creating 2.3.9, retire 2.3.7 only after 2.3.8 is verified stable and the
operator accepts that 2.3.7 will require restoration if needed again. Do not
retire an older release just because a higher version exists. If retaining
immediate access to both existing releases during preparation is required, the
policy must explicitly allow a temporary third candidate.

The limit bounds the normal UI working set, not database storage. Soft-deleted
instances, events, snapshots, and deployment history still occupy storage and
need a separate retention/recovery policy. Do not hard-delete old instances as
routine cleanup: snapshot foreign keys include `ON DELETE CASCADE`.

## Release controls

Record these operator-managed controls before starting:

- Reserve the deployment group with an exclusive pipeline lock covering all
  cohorts and manual operations. Without a shared lock, designate a release
  manager to serialize runs in one change register. Record the owner/active run,
  investigate abandoned runs before takeover, and release the reservation only
  after completion or verified rollback. A ticket alone provides no lock.
- Freeze API onboarding and configuration changes from the source baseline
  through observation completion. This has an onboarding cost for shared
  gateways. Blue/green shortens cutover downtime; ending the freeze early also
  requires an approved dual-update policy. For that policy or an emergency
  exception, apply equivalent supported changes to both retained instances,
  requalify snapshots/rollback records, and restart observation. Complete both
  records before declaring onboarding complete. If the rollback version cannot
  support equivalent behavior, maintain the freeze or pause the upgrade.
- Use a default observation period of 24 hours in production, including a
  representative traffic cycle, and 30 minutes in staging. The service owner may
  approve a different period in the release record before rollout.
- Define readiness deadlines and error-rate/latency thresholds and intervals.
  Roll back on missed deadlines, failed required route/authentication/authorization
  checks, incompatible configuration, or sustained threshold breaches. Require
  fetch/file evidence for promotion. Use the qualified migration recovery plan
  when external-state changes make binary rollback unsafe.
- The deployment operator executes the change and may invoke the preapproved
  rollback criteria without waiting for another approval. The service/release
  owner approves completion and retirement after reviewing evidence. Record
  these approvals explicitly; passing a pipeline job is not approval.

## Upgrade procedure

### 1. Qualify the target release

Register the target product version, its configuration/property mappings,
configuration profiles, schemas/defaults, and supported deployment pipelines.
Record property additions, removals, renamed keys, changed types/defaults, and
any deployment or external-state migration requirements.

Check that the old pipeline and binary can still run. If the new release makes
an irreversible external-state change, an old instance and snapshot alone are
not sufficient recovery; qualify that release's migration/recovery procedure.

Record and test the previous release's rollback loading mode now. Local-export
mode is eligible only after that old artifact, pipeline, bootstrap, and complete
exported bundle have passed a deployment test together. Do not first switch to
local-export mode during an emergency because Config Server is unavailable.

#### Rollback availability

If only remote mode was qualified and Config Server is unavailable, rollback
requiring an old-binary restart is blocked. A healthy running blue/green cohort
can still receive traffic; this protection ends if it also needs a restart.
For critical centralized gateways, qualify a local-export contingency before
the upgrade, or record Config Server availability as an explicitly accepted
rollback dependency. Link the test or dependency approval in the release record.

### 2. Prepare the source and retention slot

Identify the deployed instance, rollback snapshot, and pipeline inputs. Compare
its editable graph with the deployed snapshot: cloning copies the projected
authoring graph. Resolve or explicitly include pending changes before cloning.

Acquire the release reservation and begin the change freeze. Reconcile any
changes since the recorded baseline before cloning. Keep the freeze through
observation unless the approved dual-update policy is in place, so the rollback
instance does not lose newly onboarded APIs.

If two instances are already available, apply the retention rule before creating
another. Never retire the current release or a release with running workloads,
an unfinished deployment, or a required immediate rollback role.

### 3. Clone the version-specific candidate

Use **Instance Admin → Clone** and the [Clone an Instance](../help/portal-view/pages/instance-clone.md)
workflow. For a same-identity rollout, retain the production service ID and
environment tag; for a separate-cohort rollout, select the approved cohort
identity. Explicitly select the target product version. Select `Environment`
independently from `Env Tag`; they are different inputs.

Review APIs, apps, properties, and optional files/deployments (excluded by
default). Verify credentials separately: OAuth clients/tokens, deployment runs,
and runtime instances are outside clone scope. A same-identity clone may reuse
valid Config Server authorization; separate cohort identities need credentials
authorized for their host/service/env context.

**Leave “Create current snapshot” unchecked (`createSnapshot=false`).** Enabling
it would replace the served snapshot for a shared identity before review/deploy.

Plan and execute once, then wait for `PROJECTED`. Reuse the original request
identity when checking a timed-out request. Treat `FAILED_DLQ` as a recovery
case; do not blindly submit a fresh clone request.

### 4. Review configuration and select the target pipeline

Validate the candidate against the target release:

| Change | Required review |
| --- | --- |
| New optional property | Confirm its target default and whether an override is needed. |
| New required property | Supply a valid value if no usable default exists. |
| Changed default | Compare effective values and retained explicit overrides. |
| Renamed property or changed type/meaning | Apply the release migration and validate the resulting value. |
| Deprecated property | Retain it only while supported by the target release. |
| Removed property | Omit it from the candidate output while preserving the older instance/history. |

Preserve catalog properties used by older releases. Review mappings, profiles,
approved extensions, inherited overrides, and required defaults in the actual
generated output. Editor visibility alone cannot establish release support.
If excluding an unsupported inherited value would affect other instances'
shared settings, stop and resolve the generation gap. See
[applicability/defaults follow-ups](../design/product-upgrade-runtime-contract.md#proposed-follow-up-work).

Explicitly bind every candidate deployment to a pipeline supported by the target
version/environment; cloned deployments retain their original pipeline IDs.

### 5. Create and verify a candidate snapshot

After configuration/deployment projections catch up, create a snapshot with
`current=false` and pass the graph-readiness/revision check.

Iterating on the candidate does not create instances. Edit the same cloned
candidate and create another non-current snapshot for each review or test round:
twelve configuration fixes produce one candidate instance and twelve snapshots.
Delete unneeded candidate snapshots with the snapshot delete command, but keep
every snapshot that was deployed, approved, or referenced by a release record,
and keep the rollback snapshot.

Use [snapshot output and comparison](../design/portal-view/config-snapshot-output-comparison.md)
to review the candidate against the retained rollback snapshot. Check both
values and their sources, required configuration, selected files/certificates,
API routes, and the deployment inputs. Record the candidate snapshot ID and
checksums of the approved exports. Freeze its release inputs or repeat
validation if they change.

Check actual snapshot output where environment and product-version values
compete; editor precedence currently differs. Preserve referenced catalog names
and metadata through retention to keep output reproducible. See the
[implementation limits](../design/product-upgrade-runtime-contract.md#implementation-status).

### 6. Deploy, activate, and observe

Test the target artifact using the approved exported configuration, or use an
isolated test deployment with its own authorized identity. Do not activate a
candidate on the production identity merely to download it for a test.

`/configs` always selects current, ignoring `snapshotId`. Ancillary endpoint
pinning alone does not enable a pinned deployment. See the
[snapshot-selection contract](../design/product-upgrade-runtime-contract.md#f5-define-explicit-values-snapshot-selection).

Choose a rollout procedure that respects this limitation:

- If old and new binaries can consume the same configuration during overlap,
  validate that compatibility and coordinate activation with deployment.
- If they require different configurations, use a maintenance window that
  drains/stops the old release before activation/startup, or use the
  [separate-cohort procedure](#centralized-gateway-bluegreen-example).
  Hold automatic restarts and all manual/controller-triggered configuration
  reloads on old processes during the transition. Snapshot activation affects
  subsequent reloads as well as new starts; it is not itself a reload broadcast.
  Transparent per-deployment snapshot selection under one identity requires
  code changes.

Run the selected target pipeline with the approved artifact and inputs. Activate
the candidate snapshot at the point required by the chosen rollout procedure,
then follow the [DCL startup checks](#java-dcl-startup-and-configuration-evidence).
Verify the running product version, readiness, and representative API traffic.
A submitted job, successful clone, or UI flag alone does not establish success.

Keep the previous instance available throughout the observation period. Mark
the release transition complete only after runtime verification. Do not start
the next upgrade for the deployment group while this transition is unresolved.

## Java DCL startup and configuration evidence

These gates apply to **rollout/rollback starts and retries controlled by the
release pipeline**. The pipeline enforces the no-cache preparation and rejects
fallback for those attempts; do not install a permanent init step that deletes
`values.yml` on every boot. After release verification, steady-state liveness
restarts, evictions, and scale-out follow the normal runtime fallback policy.
Retain release-scoped storage; changing that ongoing policy belongs to F7.
Custom loaders and Rust runtimes need their own qualified procedure.

Keep `com.networknt.server.DefaultConfigLoader` at **INFO or more restrictive**,
even when parent loggers use DEBUG. Use INFO for source verification; DEBUG/TRACE
can expose values and base64 certificates/files. Restrict access to error logs,
which can contain response bodies. See the
[implementation table](../design/product-upgrade-runtime-contract.md#implementation-status)
for the code paths behind these gates.

1. **Prepare the controlled start.** In remote mode, pre-create a writable
   release directory with approved bootstrap templates/trust material and
   **no `values.yml`**. For prequalified local-export mode, install the recorded
   complete bundle, including values, and disable remote loading. Qualify any
   bootstrap that requires seeded values before adopting the remote-mode gate.
   When reusing a volume, stop the process, archive it securely, and reconcile
   loader-owned files against the approved inventory. Preserve independent
   credentials/bootstrap files. Repeat preparation for a pipeline retry after
   partial startup; exclude the candidate's values/files from an old release.
2. **Hold activation and reloads.** Keep the selected snapshot fixed across
   `/configs`, `/certs`, `/files`, and retries. Use a controlled restart for
   cert/file changes; DCL reload refreshes values only.
3. **Reject failed remote starts.** Require
   `Server startup config source: config server`, successful downloads, and
   successful writes. Any fallback/source-cache message, empty/unusable values,
   or download/write error fails the release attempt: stop/quarantine it and
   admit no traffic. The shared `Failed to load configs from config server with status`
   message also covers cert/file calls. A values-source success message alone
   is insufficient; verify all three downloads and the resulting inventory.
4. **Verify and record.** Check the running version, health, representative
   traffic, effective values, and complete file inventory. While activation is
   held, compare an authorized server fetch with local YAML semantically and
   verify file checksums. Correlate deployment/server-side request evidence where
   available. Java DCL provides no runtime-reported snapshot ID/digest: leave
   that manifest field unset and label the evidence external. If runtime
   attestation is required, hold the rollout pending instrumentation. See
   [evidence limits](../design/product-upgrade-runtime-contract.md#limits-of-current-dcl-evidence).

## Centralized gateway blue/green example

Config Server selects configuration only by `host + serviceId + envTag`, and
`/configs` always serves that identity's current snapshot. Two deployments that
share an identity therefore always receive the same configuration:

- **Compatible releases:** if old and new binaries can consume the same
  configuration, separate identities are unnecessary. A rolling update or an
  existing blue/green traffic switch under one identity works as is.
- **Incompatible releases:** if the new release needs different configuration,
  activating its snapshot on a shared identity also changes what the old cohort
  receives on its next restart, eviction, or reload, so the rollback target no
  longer has its old configuration. Give each cohort its own identity.

For incompatible releases, use two runtime identities behind one stable public
gateway address. Both use the same tenant host and `serviceId=light-gateway`;
blue uses `envTag=prod-blue`, green uses `envTag=prod-green`. The cohorts alternate:

| Stage | Blue (`prod-blue`) | Green (`prod-green`) | Public traffic before canary |
| --- | --- | --- | --- |
| Prepare 2.3.9 | 2.3.8 current | 2.3.9 candidate | Blue 100% |
| 2.3.9 passes observation | 2.3.8 rollback | 2.3.9 current | Green 100% |
| Prepare 2.3.10 | 2.3.10 candidate; 2.3.8 retired first | 2.3.9 current | Green 100% |

The strict two-instance limit leaves 2.3.9 without a warm rollback during
2.3.10 preparation. Recovering retired 2.3.8 can require rebuilding its pools,
routing, and credentials as well as restoring Portal state. Accept that recovery
time explicitly, or approve a temporary third instance and retain its warm
infrastructure through preparation.

Both instances can select the production `Environment`; `Env Tag` is the
separate snapshot/authorization identity, not that environment selector.

1. Preserve the blue instance, approved snapshot, pipeline, and deployment.
   Clone green with the target product version and `prod-green`, with automatic
   current-snapshot creation disabled. Use the shared reservation and
   [deployment-group retention rule](#retain-at-most-two-available-instances).
2. Bind green's pipeline/bootstrap to `prod-green` and credentials authorized
   for that host/service/env context. Review env-tag-dependent discovery,
   controller registration, routing, and policies. Provision separate upstream
   pools so the traffic switch can distinguish blue and green replicas.
3. Approve and activate green's snapshot only on `prod-green`; leave blue's
   current snapshot unchanged. Start green using its own config volume and run
   the startup checks. Route test/canary traffic through the load balancer, then
   increase its share against the recorded health/traffic criteria. Snapshot
   activation is not the traffic switch.
4. During observation keep blue ready with its own pipeline/configuration.
   Roll back by directing traffic to healthy blue replicas, redeploying blue
   with the saved inputs if needed. Never point a blue binary at `prod-green`.
5. After completion keep blue as the retained rollback release. At a later
   authorized retirement, remove it from routing/discovery, drain/stop its
   workloads, disable redeploy/reload triggers, and clear its current snapshot
   selection before soft retirement. Retire unused cohort credentials only
   when no retained recovery procedure or other deployment needs them. Do not
   rename the surviving instance's identity to collapse the cohorts.
6. For 2.3.10, obtain retirement approval for blue 2.3.8 and complete step 5's
   cleanup first. Clone the verified green 2.3.9 authoring instance into a **new**
   2.3.10 instance targeting `prod-blue`, with `createSnapshot=false`. This is an
   explicit cross-env-tag clone; keep the intended production `Environment` and
   review copied environment-dependent values, files, authorization, and pipeline
   bindings. Do not switch the old 2.3.8 instance's version. Its retired row
   remains in history alongside the new active 2.3.10 row in `prod-blue`, but
   only green 2.3.9 and blue 2.3.10 count as available. Activate blue's approved
   new snapshot and repeat the checks/canary; green remains the rollback target.
   If that exact target version already exists retired, restore/reconcile it
   using the retry procedure instead of creating another row.

### Kubernetes Service-selector variant

On Kubernetes, perform blue/green at the Service level, the same way it is done
for other workloads. The "load balancer" and "upstream pools" above map to:

- Two Deployments, for example `light-gateway-blue` and `light-gateway-green`,
  each labeled with its color (`color: blue` / `color: green`).
- One stable Service whose `selector` chooses the live color. The cutover, canary
  completion, and rollback are all a change to that selector.

For incompatible releases, the only Portal-specific addition is that each
Deployment carries its own configuration identity: set `envTag` to `prod-blue`
or `prod-green` in that Deployment's bootstrap/environment, bind it to its own
Portal instance and snapshot, and give it credentials authorized for that env
tag, as well as its own config volume. If both Deployments share one env tag, a
selector switch still moves traffic correctly, but snapshot activation changes
what the old color loads on any Pod restart or reload. For compatible releases,
Service-level blue/green with a single env tag needs none of this.

A weighted canary needs a mechanism beyond a plain selector switch, such as a
gateway or service-mesh traffic split, or a temporary Service selecting both
colors by a shared label.

Different `serviceId` values can also separate cohorts, but require equivalent
authorization, discovery, and routing review. Reusing a cohort/version already
in history follows the retry/restoration procedure below.

## Rollback procedure

1. Select the retained previous instance, approved snapshot, binary/image, and
   pipeline revision from the release record.
2. Coordinate traffic and process shutdown/startup so each binary receives
   compatible configuration. Retain the release reservation; hold incompatible
   processes' reloads and automatic restarts. Prepare the previous release's
   configuration directory using the DCL checks above.
3. Use the loading mode recorded and qualified for the previous release:

   - **Current-snapshot mode:** activate the saved previous snapshot for the
     old runtime identity, then redeploy the old artifact using its saved
     pipeline and inputs. Keep activation fixed until all startup downloads
     finish. With separate cohorts, blue may already have the correct snapshot;
     verify it and switch traffic only after confirming blue is healthy.
   - **Local-export mode:** have the pipeline install the previously approved
     values, certs, and files using the old release's tested local-only bootstrap.
     Ensure `light-config-server-uri` is absent from every property/environment
     source. Use this mode only when its pre-upgrade qualification is recorded;
     otherwise follow the [availability dependency](#rollback-availability).

   Consume the saved snapshot/export. Regenerating from current authoring tables
   creates different inputs, and `/configs?snapshotId=...` is ignored today.
4. Complete the DCL fetch/file checks for remote mode, or verify installed bundle
   checksums for local mode. Record the actual runtime version, readiness, API
   traffic, and the configuration evidence/limitations. Do not claim that
   unmodified Java DCL reported a snapshot ID or digest.
5. Retain the failed candidate for diagnosis or soft-retire it when safe. If the
   two-instance policy requires restoring an older release, retire the failed
   candidate first and use the supported lifecycle restoration procedure.
   Obtain approval of the verified rollback outcome, end the change freeze,
   and release the reservation only after the deployment group is stable.

Redeploy the retained old instance rather than changing the candidate's version.
Resume onboarding there after rollback; create new snapshots for new edits and
preserve the original rollback snapshot. Reconcile APIs added only to the newer
instance and review shared catalog/inheritance changes.

## Retry a failed product-version upgrade

This section covers a release attempt that was declared failed, rolled back, and
retired. Fixing configuration during an unfinished attempt is not a retry: edit
the same candidate and create another snapshot, as described in
[step 5](#5-create-and-verify-a-candidate-snapshot). Each retry reuses the same
instance row, so repeated attempts add snapshots and release records, not
instances.

After a failed 2.3.9 upgrade is retired, its row still reserves
`(host_id, service_id, env_tag, product_version_id)`. Clone checks include retired
rows. A fresh clone of 2.3.8 into that same 2.3.9 identity will be rejected, even
with a new instance UUID.

1. First finish or repair the original clone/deployment attempt, including any
   `FAILED_DLQ` projection, and establish a stable running release. A command
   retry and a new release attempt are different operations.
2. Acquire the same release reservation and apply the two-instance retention
   rule. For example, retire a restored 2.3.7 rollback instance before restoring
   2.3.9, keeping verified 2.3.8 available throughout.
3. Restore the existing 2.3.9 instance and required cascaded children through
   the lifecycle workflow. Confirm projection completion and inspect the
   restored graph, files, and deployment bindings; restoration is not a re-clone.
4. Reconcile the restored candidate with the latest approved 2.3.8 baseline,
   including APIs onboarded since the first attempt. Review a three-way diff
   where possible: original source baseline, current source, and failed
   candidate. Use normal editing commands to apply the selected changes and
   the 2.3.9 migration again. Clone does not provide a merge-into-existing-target
   operation. If the original baseline is unavailable, perform a full comparison
   and configuration review before proceeding.
5. Create a new non-current snapshot and a new attempt-specific release record
   referencing the same candidate instance ID. Preserve the first attempt's
   snapshot/evidence. Repeat validation, deployment, and observation; do not
   reuse approval from the failed attempt.

Do not hard-delete the retired row or silently replace it with a new clone to
bypass uniqueness. Portal is event-sourced: a direct database delete bypasses the
event store, leaving projections and events inconsistent, and snapshot foreign
keys cascade the delete to that attempt's snapshots. Clean up with lifecycle
commands instead: soft retirement/restoration for instances and the snapshot
delete command for unneeded candidate snapshots.

## Safe retirement and recovery

Use Portal lifecycle commands/events for soft retirement; owned graph rows are
cascaded, snapshots/history retained, and the instance hidden from normal lists.
First clear selected current snapshots and confirm there are no running
deployments or required rollback obligations. Operators enforce these gates;
soft retirement alone leaves selected snapshots servable. See the
[implementation table](../design/product-upgrade-runtime-contract.md#implementation-status).

Preserve shared product versions, pipelines, artifacts, and access needed by
other instances or the recovery plan. Qualify restoration of the instance,
cascaded children, and deployment infrastructure before relying on archives.
Retired rows still reserve their version identity: use the
[restore/retry procedure](#retry-a-failed-product-version-upgrade).

## Fleet operation

### Sidecar version overlap

A Kubernetes Deployment normally uses `RollingUpdate`, so old and new Pods can
overlap under the same Config Server identity. `Recreate` stops the old revision
before creating the new revision during a Deployment upgrade; it does not give
the same guarantee for manual Pod deletions or other controllers. See the
[Kubernetes Deployment strategy contract](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/#strategy).

Choose and record one policy for each API's sidecar deployment group:

- **Compatible rolling update:** qualify the served values, certs, and files
  for both old and new binaries, including old-Pod restarts/reloads and rollback
  while any new Pods remain. Use that approved common configuration throughout
  the overlap; do not rely on old Pods retaining a cache. Keep activation fixed
  through each complete DCL download sequence.
- **Incompatible versions:** use a qualified `Recreate` rollout or a maintenance
  restart, accepting the API/application Pod outage. The pipeline must ensure
  old consumers are stopped, activate the target snapshot, then permit new
  startup. `Recreate` alone does not schedule the external snapshot activation:
  use a tested startup gate or an explicit scale-down/wait/activate/start
  sequence. Hold autoscaler/GitOps reconciliation and other deployment/reload
  triggers during that sequence. Coordinate every workload sharing the identity,
  not just one Deployment, and use the same ordering for rollback.

If neither policy is acceptable, stop and design isolated identities or a
qualified pinned/local-export deployment before rolling out. Per-Pod blue/green
env tags are not the default fleet strategy. Batch by independent deployment
groups; batching does not solve incompatible overlap within a group.

### Batch coordination

For sidecar fleets, automate the reviewed workflow around existing commands:
select eligible instances, reserve one upgrade per deployment group, clone in
bounded batches, validate, deploy in cohorts, and record each result. Preserve the
request identity across retries and distinguish accepted commands from fully
projected and runtime-verified outcomes.

Apply the shared deployment-group retention rule after its own transition
checks; a successful fleet subset must not cause retirement for a failed or unfinished
instance. The current UI is not a fleet upgrade orchestrator, and a batch
implementation is additional work.

Related reading: [Instance Clone design](../design/instance-clone.md),
[Configuration Snapshots](../design/config-snapshot.md),
[Config Server operations](./docker-compose/services/config-server.md), and
[Policy-Driven Cascade Delete](../design/cascade-soft-delete.md).
For source evidence and proposed code work, see
[Product Upgrade Runtime Contract](../design/product-upgrade-runtime-contract.md).
