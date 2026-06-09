# Release Workflow

## Status

Proposed design.

Light Portal should use `light-workflow` as the durable release orchestrator
for Java and Rust releases. The workflow should coordinate repository checkout,
preflight validation, build, test, package, ConfigProfile manifest handling,
artifact publishing, AI-assisted failure diagnosis, and human approval.

The workflow engine should not execute release commands directly inside the
portal service process. Command execution belongs in a sandboxed release
runner, with `light-workflow` owning state, task routing, retries, approvals,
and audit history.

## Problem

Java releases currently depend on `light-bot`, while Rust releases are handled
through separate command-line and repository-specific steps. This works, but it
keeps release knowledge outside the same workflow model used by Light Portal
for human tasks, automation tasks, and approval flows.

The release process is stateful and failure-prone:

- a release can span many repositories,
- Java and Rust products use different build and publish tools,
- a failure may require log analysis before the next action is obvious,
- publish and signing steps require stricter approval and secret handling,
- ConfigProfile manifests and generated import events must be checked before
  customers see the release as complete,
- an operator needs a durable record of what ran, what failed, what was fixed,
  and who approved publication.

The release workflow should be flexible enough to call existing command-line
tools, but controlled enough that it does not become an unrestricted shell
inside Light Portal.

## Goals

- Replace the current Java `light-bot` release path with `light-workflow` once
  parity is proven.
- Support both Java release trains and independent Rust product releases.
- Run build, test, package, and import-generation commands in sandboxed release
  runners.
- Capture command output, exit status, artifacts, and workspace changes as
  workflow task results.
- Let an AI agent analyze failed commands and propose or apply bounded fixes
  when policy allows it.
- Escalate unclear, risky, or approval-required cases to human tasks.
- Integrate ConfigProfile manifest validation and `event-importer` dry-run
  reporting into the release gate.
- Keep publish, signing, tag creation, and external customer-visible actions
  behind explicit approval.
- Preserve release auditability and reproducibility.

## Non-Goals

- Do not run arbitrary release commands in the Light Portal service process.
- Do not replace Maven, Cargo, Docker, GitHub CLI, or existing release scripts
  where they already work.
- Do not allow an AI agent to publish artifacts, sign releases, rotate secrets,
  or push final tags without human approval.
- Do not make generated tenant-specific events public. Public release metadata
  should be portable manifests, not customer import output.
- Do not remove `light-bot` until Java release parity has been demonstrated
  through several successful workflow-managed releases.

## Current State

`light-bot` is the practical Java release automation path today. It contains
working release knowledge and should remain available as a fallback during the
migration.

`light-workflow` is a good orchestration target because it already models
durable workflow instances, tasks, branching, context updates, and human task
patterns. The current executor supports control-plane task types such as
`ask`, `assert`, `call`, `set`, and `switch`.

The workflow model also defines `run.container`, `run.script`, `run.shell`, and
`run.workflow`. Those task types are the right DSL surface for release command
execution, but the runtime still needs sandbox-backed execution support before
release commands can move from scripts into `light-workflow`.

The ConfigProfile mapping work adds another release concern. Reusable profile
manifest files should live in the public `lightapi/config-profile-manifests`
repository. The release workflow should validate those manifests and use
`event-importer` to generate dry-run reports and import events for target
portal environments.

## Recommended Architecture

Use `light-workflow` as the host-side orchestrator and delegate effectful
release work to sandboxed release runners.

```text
Light Portal
  |
  | start release / approve / inspect task history
  v
light-workflow
  |
  | durable tasks, branching, retries, audit
  v
Sandboxed Release Runner
  |
  | git, mvn, cargo, docker, gh, event-importer
  v
Release Repositories and Registries
```

The main components are:

- `light-workflow`: Owns workflow instance state, task claiming, context,
  branching, retry policy, approval gates, human task creation, and audit
  metadata.
- Release runner: Executes approved commands in a sandbox or controlled worker.
  It owns checkout directories, build caches, generated files, and command
  output capture.
- AI release assistant: Consumes failed command context, classifies the
  failure, proposes fixes, and optionally creates a bounded patch when policy
  allows it.
- Human task UI: Presents failed steps, AI analysis, command logs, proposed
  actions, and approval options.
- Release integrations: GitHub, Maven repositories, Cargo crates, Docker
  registries, config-profile manifests, `event-importer`, and deployment
  verification tools.

## Execution Boundary

Host execution should be limited to orchestration and approved control-plane
calls:

- `ask`
- `assert`
- `set`
- `switch`
- context merge
- task claiming and completion
- process state persistence
- calls to approved internal APIs

Sandbox execution should be required for release effectors:

- `run.shell`
- `run.script`
- `run.container`
- repository checkout and mutation
- build, test, and package commands
- Docker build and image publishing
- Maven and Cargo publishing
- GitHub release and tag commands
- `event-importer` execution
- external MCP server processes
- AI-agent tool execution that can mutate files or repositories

For normal build, test, package, and dry-run work, use one sandbox session per
workflow instance. This lets checkout state, dependency caches, generated
artifacts, and temporary files survive across related tasks.

For publish, signing, tag creation, and tasks with release secrets, use a fresh
per-task sandbox with task-scoped secrets. These tasks should be isolated from
the broader build workspace unless policy explicitly allows artifact transfer.

## Release Lifecycle

The release workflow should follow this lifecycle.

1. Create release request.
2. Resolve release scope.
3. Run preflight checks.
4. Prepare the sandbox workspace.
5. Build and test selected Java and Rust repositories.
6. Validate ConfigProfile manifests.
7. Run `event-importer` dry-run for generated mapping events.
8. Package artifacts and images.
9. Diagnose and repair failures when policy allows.
10. Request human approval for publish.
11. Publish artifacts, tags, images, and release notes.
12. Verify published artifacts and generated portal events.
13. Close the release workflow with a durable summary.

### Release Request

The release request should be explicit enough to reproduce the run.

```json
{
  "releaseId": "2026.06.0",
  "releaseType": "java-train",
  "runtimeFamilies": ["java"],
  "repos": [
    {
      "name": "light-4j",
      "url": "https://github.com/networknt/light-4j.git",
      "ref": "master",
      "version": "2.3.5"
    }
  ],
  "configProfileManifest": {
    "repo": "https://github.com/lightapi/config-profile-manifests.git",
    "ref": "main",
    "paths": ["java/light-gateway/2.3.5.json"]
  },
  "portalTargets": [
    {
      "name": "dev",
      "hostId": "host-id-for-dev",
      "dryRunRequired": true
    }
  ],
  "publishPolicy": {
    "requireHumanApproval": true,
    "allowAiPatch": true,
    "maxRepairAttempts": 2
  }
}
```

Rust product releases use the same shape, but `releaseType` can be
`rust-products` and the repository list can contain only the selected Rust
products.

### Preflight Checks

The preflight stage should fail before any publishable side effect.

Required checks:

- requested release version is valid,
- target branches and tags do not already conflict,
- release repositories are reachable,
- release scripts and tool versions are available in the runner image,
- portal target credentials are present but not exposed in logs,
- ConfigProfile manifest files validate against the public schema,
- `event-importer` can connect to the target read model for dry-run lookup,
- no required human approval is missing.

Preflight failures should create a human task directly unless the error is a
known repairable workspace issue.

### ConfigProfile Gate

ConfigProfile mappings should be part of the release gate, not a manual
afterthought.

The workflow should:

1. Check out `lightapi/config-profile-manifests`.
2. Validate every manifest selected by the release request.
3. Run `event-importer --generate-config-profiles --dry-run` for each target
   portal environment.
4. Persist the dry-run report as a workflow artifact.
5. Block publish if the report contains missing config or property references.
6. Require human approval when `--replace` would delete profile mappings.
7. Emit or attach generated import events only after approval.

The public manifest repository should contain portable product profile
contracts. Tenant-specific generated event files, customer host IDs, and
private overrides should remain outside the public repository.

## AI Failure Loop

When a command task fails, the release workflow should create a structured
failure record and route it to the AI release assistant.

The record should include:

- workflow instance ID,
- failed task name and attempt number,
- command template and arguments,
- sanitized environment summary,
- exit code,
- stdout and stderr excerpts,
- full log artifact reference,
- repository status,
- changed files,
- relevant test reports or build artifacts,
- previous repair attempts.

The AI assistant should classify the failure before proposing a fix.

Recommended categories:

| Category | Example | Default Action |
| --- | --- | --- |
| transient infrastructure | registry timeout, GitHub API rate limit | retry with backoff |
| dependency resolution | Maven or Cargo dependency conflict | propose dependency fix |
| compile failure | Java or Rust compiler error | propose source patch |
| test failure | deterministic unit test failure | propose source or test fix |
| release metadata | version, tag, changelog, manifest error | propose metadata patch |
| permission or secret | denied publish, missing token | create human task |
| policy violation | command not approved, network blocked | create human task |
| uncertain | unclear logs or risky patch | create human task |

If policy allows repair, the AI assistant can:

- inspect the checked-out repository,
- propose a patch,
- apply a patch in the sandbox,
- rerun the failed command or a narrower verification command,
- create a branch or pull request for human review.

The AI assistant must not:

- read or print release secrets,
- bypass workflow approvals,
- publish artifacts,
- sign artifacts,
- push final tags,
- change command allowlists,
- increase its own permission scope.

Retries must be bounded. After the configured retry limit, or after any
high-risk classification, the workflow should create a human task.

## Human Task Escalation

Human tasks are the safety valve for release automation. A failed or
approval-required step should create a task with enough context for a quick
decision.

The task should show:

- release ID and release type,
- failed workflow step,
- repository and ref,
- command result summary,
- log and artifact links,
- AI classification and confidence,
- proposed patch or action,
- affected products and portal targets,
- approval history,
- available actions.

Common actions:

- retry same step,
- approve AI patch and rerun,
- reject AI patch,
- open generated pull request,
- skip non-required product,
- abort release,
- approve publish,
- request manual intervention.

## Workflow Definition Sketch

The exact DSL can evolve with `light-workflow`, but release definitions should
look like normal workflow definitions with sandbox metadata and `run.*` tasks.

```yaml
document:
  dsl: "1.0.3"
  namespace: release
  name: lightapi-release
  version: "0.1.0"
  metadata:
    lightWorkflow:
      security:
        executionProfile: release-sandbox
        sandbox:
          mode: workflow-session
          provider: cubesandbox
          template: lightapi-release-runner

do:
  - validate-config-profile-manifests:
      run:
        shell:
          command: python3
          arguments:
            - scripts/validate-manifests.py
      metadata:
        lightWorkflow:
          artifactPolicy:
            capture:
              - validation-report.json

  - build-java-products:
      run:
        shell:
          command: ./release.sh
          arguments:
            - "${ .release.version }"
      metadata:
        lightWorkflow:
          onFailure:
            call: ai-release-diagnosis

  - config-profile-dry-run:
      run:
        shell:
          command: java
          arguments:
            - "-jar"
            - "event-importer.jar"
            - "--generate-config-profiles"
            - "--manifest"
            - "${ .release.configProfileManifestPath }"
            - "--targetHostId"
            - "${ .portal.hostId }"
            - "--adminUserId"
            - "${ .release.adminUserId }"
            - "--output"
            - "./generated"
            - "--dry-run"

  - approve-release:
      ask:
        assignee: "${ .release.owner }"
        prompt: "Approve publishing release ${ .release.version }"

  - publish-release:
      run:
        shell:
          command: ./publish.sh
          arguments:
            - "${ .release.version }"
      metadata:
        lightWorkflow:
          security:
            sandbox:
              mode: per-task
              reason: release-token-isolation
            secrets:
              - github-release-token
              - maven-publish-token
```

## Command Result Contract

Each sandbox command should return a normalized task result so workflow
branching and AI diagnosis do not depend on raw console parsing.

```json
{
  "taskName": "build-java-products",
  "attempt": 1,
  "command": "./release.sh 2.3.5",
  "exitCode": 1,
  "status": "failed",
  "startedAt": "2026-06-07T18:10:00Z",
  "completedAt": "2026-06-07T18:18:30Z",
  "durationMs": 510000,
  "stdoutRef": "artifact://release/2026.06.0/build-java/stdout.log",
  "stderrRef": "artifact://release/2026.06.0/build-java/stderr.log",
  "summary": "Maven test failure in db-provider",
  "changedFiles": [],
  "artifacts": [
    "artifact://release/2026.06.0/build-java/surefire-reports.zip"
  ]
}
```

The workflow context should store references and summaries, not unbounded logs.
Full logs belong in artifact storage with retention and access policy.

## Security Requirements

Release automation needs stricter controls than normal background tasks.

- Commands must come from approved workflow definitions or approved templates.
- The runner image must be versioned and auditable.
- Network egress must be policy controlled.
- Secrets must be scoped to the smallest task that needs them.
- Logs must be redacted before they are stored or sent to AI analysis.
- Publish and signing tasks require human approval.
- AI repair tasks must have bounded retry counts and clear write permissions.
- Workflow audit records must include effective policy, runner image, command
  template, artifact references, approvals, and repair attempts.
- Release artifacts should be reproducible from the recorded repository refs,
  workflow definition version, runner image, and command results.

## Phased Implementation

### Phase 1: Runtime Foundation

- Implement sandbox-backed execution for `run.shell`, `run.script`, and
  `run.container`.
- Define the command result contract.
- Add log capture, artifact storage references, and redaction.
- Add workflow and task metadata for execution security profiles.
- Keep publish tasks disabled until approval and secret policy are implemented.

### Phase 2: Java Release Parity

- Model the existing `light-bot` Java release flow as a workflow definition.
- Call the existing Java release scripts from sandbox tasks.
- Compare generated artifacts, tags, release notes, and publish behavior with
  the current `light-bot` path.
- Run several releases with `light-bot` retained as fallback.

### Phase 3: Rust Release Support

- Add Rust product release workflow definitions.
- Support Cargo build, test, package, image build, and publish tasks.
- Allow release requests to select one Rust product or a set of Rust products.
- Share the same approval and artifact model used by Java releases.

### Phase 4: ConfigProfile Release Gate

- Check out and validate `lightapi/config-profile-manifests`.
- Run `event-importer` dry-run for selected portal targets.
- Persist dry-run reports as workflow artifacts.
- Require approval for replacement deletes or missing-reference exceptions.
- Emit approved import events through the normal event-import path.

### Phase 5: AI Repair Loop

- Add AI failure classification for failed command tasks.
- Allow bounded AI patch attempts in sandbox workspaces.
- Create branches or pull requests for human review.
- Add retry policy and automatic escalation after uncertain or exhausted
  repairs.

### Phase 6: Publish and Verification

- Add per-task sandbox isolation for signing and publish tasks.
- Add post-publish verification for Maven, Cargo, Docker, GitHub releases, and
  portal import events.
- Add release dashboard and final release summary.
- Retire `light-bot` after Java parity and rollback procedures are proven.

## Risks and Open Questions

- The sandbox runner must be reliable enough for long-running release builds.
- Artifact retention needs a concrete storage backend and access policy.
- Secret handling must be designed before publish tasks are enabled.
- The AI repair scope must be narrow enough to prevent accidental broad
  refactors during release pressure.
- Cross-repository version coordination needs a clear source of truth.
- Rollback behavior for partially published releases must be defined per
  artifact type.
- The first implementation should decide whether AI patches create pull
  requests by default or only update the sandbox workspace for operator review.

## Recommendation

Moving Java and Rust releases to `light-workflow` is a good direction, provided
the migration treats `light-workflow` as the orchestrator and uses sandboxed
runners for command execution. This gives the release process durable state,
human approvals, AI-assisted diagnostics, and a single model for Java, Rust,
and ConfigProfile release gates.

The migration should be incremental. Keep `light-bot` as the Java fallback
until the workflow release path has matched it in real releases. Enable AI
analysis early, but keep AI-generated changes and all publish actions behind
explicit policy and human approval.
