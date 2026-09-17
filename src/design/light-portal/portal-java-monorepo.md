# Portal Java Monorepo

## Status

Proposed on 2026-09-16. Not yet implemented.

This is the optional Phase 0 of
[Portal Service Consolidation Into Rust](./portal-service-rust-consolidation.md).
It is also useful on its own if the Rust migration is delayed.

## Decision

Move every portal `*-command` and `*-query` repository, plus `hybrid-command`
and `hybrid-query`, into the existing `light-portal` repository as Maven
modules. Keep full git history.

Nothing changes at runtime:

- Each service module still builds its own small jar with the same
  `artifactId`, for example `user-command-<version>.jar`.
- `hybrid-command` and `hybrid-query` still build shaded server jars and Docker
  images, and still load service jars from `/service/*`.
- Handler IDs, `spec.yaml`, config, events, and the database are unchanged.

What changes is how the code is stored, built, versioned, and released.

## Context

### Current State

Measured on 2026-09-16:

- 29 `*-command` and 29 `*-query` repositories, plus `hybrid-command`,
  `hybrid-query`, and `light-portal` (`common-util`, `command-common`,
  `db-provider`). All are at version `2.3.8-SNAPSHOT`.
- No service module depends on another service module. Each depends only on
  light-4j and the three `light-portal` libraries.
- Each service `pom.xml` is about 420 to 440 lines, almost all duplicated:
  repositories, properties, plugin versions, javadoc, and source setup.
- Every service build creates a javadoc jar during `package`. For
  `user-command` this jar is about 4.3 MB, while the real jar is about 100 KB.
- `light-portal/db-provider` and `command-common` are **shaded into**
  `hybrid-command.jar` and `hybrid-query.jar`. A change to them requires new
  hybrid images, not just new service jars.
- Builds and releases are driven by per-repository scripts in
  `devops/workspace`:
  - `copy-service-local.sh`, `copy-service-dev.sh`, `copy-service-test.sh`:
    use `mgitstatus` to find changed repositories, run `mvn clean install` in
    each, then copy `target/<name>-*.jar` into `hybrid-*/service`.
  - `publish.sh`: runs `mvn clean install deploy -DperformRelease` in about 60
    directories, one after another.
  - `update-asset.sh`, `daily-release.sh`, `release-docker-images.sh`:
    reference individual repository directories.
  - `reindex-gitnexus.sh`, `create-gitnexus-groups.sh`: index per repository.
- Eight repositories (`light-portal`, `config-command`, `config-query`,
  `deployment-command`, `instance-command`, `instance-query`, `oauth-command`,
  `oauth-query`) have a GitHub `sync` branch workflow: a customer pushes updates
  to `sync`, and `sync-auto-pr.yml` opens a PR to `master`. `oauth-query` also
  has `master-to-sync.yml`.

### Problems This Solves

1. **Atomic changes.** A feature touching `db-provider`, a command handler, and
   a query handler becomes one commit and one PR instead of three to five.
2. **No install ordering or stale SNAPSHOTs.** Today `light-portal` must be
   `mvn install`ed before its dependents, or they build against an old
   SNAPSHOT from `~/.m2` or Central. Inside one reactor build, Maven resolves
   module dependencies from source.
3. **AI agents see the whole contract.** One checkout, one `CLAUDE.md`, one
   GitNexus index, and one test command cover the persistence method, the
   handler, and its `spec.yaml`.
4. **Less build configuration.** About 25k lines of duplicated POM move into
   one parent. A light-4j or Jackson upgrade becomes a one-line change.
5. **Faster daily builds.** Javadoc and source jars move into the release
   profile, and the reactor builds modules in parallel (`-T 1C`).
6. **Simpler scripts.** Change detection per repository and the long
   `publish.sh` are replaced by reactor commands.

### Problems This Does Not Solve

- Two languages: Java and Rust are still maintained side by side.
- Memory use of the JVM services.
- The separate `light-portal-event` data repository (events, not code). It is
  out of scope.

## Target Layout

```text
light-portal/
  pom.xml                     # aggregator + parent (packaging pom)
  CLAUDE.md, AGENTS.md        # merged agent guidance
  common-util/                # unchanged location
  command-common/             # unchanged location
  db-provider/                # unchanged location
  command/
    pom.xml                   # command parent: shared deps (rpc-router, email, ...)
    attribute-command/
    category-command/
    ...
    workflow-command/
  query/
    pom.xml                   # query parent
    attribute-query/
    ...
    workflow-query/
  hybrid/
    hybrid-command/           # shaded server jar + docker/
    hybrid-query/
  dist/
    pom.xml                   # collects service jars for deployment (see below)
  .github/workflows/
```

The three library modules stay where they are so `light-portal` history and
paths do not change.

### POM Structure

- **Root `pom.xml`** (`net.lightapi:light-portal`, packaging `pom`):
  - `<version>${revision}</version>` with `revision=2.3.8-SNAPSHOT`, using
    `flatten-maven-plugin` so published POMs have concrete versions.
  - All shared `properties`, `repositories`, `distributionManagement`,
    `dependencyManagement` (light-4j, Jackson BOM, CloudEvents, JUnit), and
    `pluginManagement`.
  - `release` profile (activated by `-DperformRelease`): sources, javadoc,
    and gpg. Javadoc is **not** built by default.
- **`command/pom.xml` and `query/pom.xml`**: dependencies every handler module
  in that group uses, so each service POM lists only what is special to it.
- **Service `pom.xml`**: parent reference, `artifactId`, `name`, `description`,
  and any extra dependencies. Target size: about 20 to 40 lines.
- **`hybrid-command` and `hybrid-query`**: keep the shade setup. Their Docker
  build context stays the module directory.

### Deployment Output: Small Jars Remain

Each service module still produces `target/<artifactId>-<version>.jar`, and
`mvn deploy` still publishes each one to Maven Central under its current
coordinates, because external users depend on them.
Deployment continues to copy thin jars into `hybrid-*/service`.

To remove the `find` logic in the copy scripts, the `dist` module uses
`maven-dependency-plugin:copy-dependencies` (or an assembly) to collect them:

```text
dist/target/service/hybrid-command/*.jar   # every *-command jar
dist/target/service/hybrid-query/*.jar     # every *-query jar
dist/target/hybrid-command.zip             # same format install.sh downloads
dist/target/hybrid-query.zip
```

Scripts copy these directories as they are. `light-portal-install/install.sh`
keeps downloading `hybrid-command.zip` and `hybrid-query.zip` unchanged.

Independent jar deployment still works: rebuild one module with
`mvn -pl command/user-command -am package` and copy its jar. The only
limitation is the same as today: changes to `db-provider` or `command-common`
also need new hybrid images, because those libraries are shaded.

### Everyday Commands

```bash
# Full build with tests
mvn -T 1C clean install

# One service and what it depends on
mvn -pl command/user-command -am install

# Everything affected by a db-provider change
mvn -pl db-provider -amd install

# Release
mvn -T 1C clean deploy -DperformRelease
```

## Implementation Plan

### Step 1: Freeze And Prepare (Half A Day)

1. Announce a short freeze on all portal Java repositories.
2. Merge or close open branches. Known examples: `config-command` has
   `issue29` and `issue32`.
3. **Confirm the `sync` branches are still clean.** As of 2026-09-16, the
   customer's contributions are fully merged. Recheck just before Step 2 that
   no `sync` branch in the eight repositories is ahead of `master`.
4. Record each repository's `master` HEAD SHA in the migration PR description.

### Step 2: Import With History (Scripted, About An Hour)

For each repository, with `git filter-repo` in a temporary clone:

```bash
git clone git@github.com:lightapi/user-command.git /tmp/import/user-command
cd /tmp/import/user-command
git filter-repo --to-subdirectory-filter command/user-command \
                --tag-rename '':'user-command-'
cd ~/workspace/light-portal
git remote add import-user-command /tmp/import/user-command
git fetch import-user-command --tags
git merge --allow-unrelated-histories --no-edit import-user-command/master
git remote remove import-user-command
```

- Use `command/<name>` for command repos, `query/<name>` for query repos, and
  `hybrid/<name>` for the two hybrid repos.
- The tag rename prevents tag clashes between repositories.
- `git log --follow` and `git blame` keep working in the new paths.
- Remove the imported `target/`, `log/`, `mvnw*`, and `.pre-commit-config.yaml`
  copies. Keep one Maven wrapper and one pre-commit config at the root.

Do this on a branch (`monorepo`) so the step can be rerun from scratch.

### Step 3: Parent POM And Module POMs (Half A Day To A Day)

1. Move shared configuration into the root `pom.xml`, then add `command/pom.xml`
   and `query/pom.xml`.
2. Rewrite each service POM down to its parent, identity, and extra
   dependencies. This is mechanical and can be scripted or done by an agent.
3. Check that the effective POM of each module has the same dependency tree as
   before: compare `mvn dependency:tree` output before and after for every
   module.
4. Move javadoc and sources into the `release` profile.
5. Add `flatten-maven-plugin` and check that one published POM has a concrete
   version.

### Step 4: Build Parity (Half A Day)

1. `mvn -T 1C clean install` passes, including all tests.
2. For each service, the class list in the new jar matches the old jar
   (`unzip -l` diff, ignoring `META-INF` timestamps).
3. `hybrid-command.jar` and `hybrid-query.jar` contain the same classes as
   before.
4. `dist` produces `hybrid-command.zip` and `hybrid-query.zip` with the same
   jar file names as the current release assets.
5. Start `light-portal-install` locally with the new assets and run the
   existing `light-portal-test` regression suite.

### Step 5: Tooling And CI (Half A Day)

| Item | Change |
|------|--------|
| `copy-service-local.sh`, `-dev.sh`, `-test.sh` | Build `light-portal` once; copy from `dist/target/service/*` |
| `publish.sh` | One `mvn clean deploy -DperformRelease` |
| `update-asset.sh` | Point `GENAI_COMMAND_DIR`/`GENAI_QUERY_DIR` at the modules, or build via `-pl` |
| `daily-release.sh`, `release-docker-images.sh` | Build hybrid images from `hybrid/hybrid-*` |
| `reindex-gitnexus.sh`, `create-gitnexus-groups.sh` | Remove per-repository entries; index `light-portal` once |
| `.github/workflows` | One `sync-auto-pr.yml` and `master-to-sync.yml` on `light-portal` for the customer's single `sync` branch |
| CI build | `mvn -T 1C verify` on PR |
| Dependabot or Renovate | One configuration at the root |

### Step 6: Agent Guidance (A Few Hours)

- Merge the roughly 60 `CLAUDE.md`/`AGENTS.md` files into one root file. Keep
  a short module-level file only where a module has real special rules
  (for example `genai`, `config`, `oauth`, `workflow`).
- Document the layout, the build commands above, and the rule that changes to
  shared libraries need hybrid image rebuilds.
- Update the GitNexus group definitions.

### Step 7: Cutover (Half A Day)

1. Merge the `monorepo` branch into `light-portal` `master`.
2. In each old repository: add a final commit whose README points to the new
   path, then archive the repository on GitHub (read-only; history and links
   keep working).
3. Transfer open GitHub issues to `light-portal`, or close them with a link.
4. Remove the old directories from `~/workspace` after confirming nothing
   references them (`grep -r` across `devops`, `light-portal-install`, and
   `light-portal-doc`).
5. Publish one release from the monorepo to Maven Central and deploy to dev,
   then test. Check that a project outside the monorepo can resolve one
   published service jar and its parent POMs.
6. Tell the `sync` customer that `light-portal` is ready and the old
   repositories are archived.

**Total effort:** about 3 to 4 working days, mostly mechanical, with most of
the time in Steps 3 to 5 checks.

## Rollback

Until Step 7, the old repositories are untouched and remain the source of truth.
Rolling back means deleting the `monorepo` branch.

After Step 7, unarchive the old repositories. Changes made in the monorepo in
the meantime can be exported back with `git filter-repo --subdirectory-filter`.
This should not be needed if Step 4 passes.

## Risks

| Risk | Mitigation |
|------|------------|
| Customer `sync` flow breaks or loses in-flight changes | Branches are clean and the customer has agreed to move; recheck before Step 2 and tell them when cutover is done |
| Dependency tree changes silently when POMs are deduplicated | Compare `dependency:tree` per module; compare jar contents |
| Full build becomes slow | `-T 1C`, javadoc only on release, `-pl ... -am` for targeted builds |
| External users of Central artifacts see a change | Coordinates and jar contents stay the same; check flattened POMs have no `${revision}` and that the published parent POM resolves; test one external build against the first monorepo release |
| Scripts still point at old directories | `grep` sweep in Step 7; archive old repositories so stale scripts fail loudly |
| Tag name clashes | `--tag-rename` prefix during import |

## Resolved Decisions

Decided on 2026-09-16:

1. **Customer `sync` flow.** The customer's contributions are merged and clean.
   After cutover, they move to one `sync` branch on `light-portal`. Step 7
   includes telling them the cutover is done.
2. **Maven Central publishing continues.** Some users still depend on the
   published jars. Every library and service module keeps its current
   `groupId`/`artifactId` and is published on each release. The root, `command`,
   and `query` parent POMs are published too, because published module POMs
   refer to them.
3. **Placeholder modules stay.** `blog`, `news`, `page`, `form`, `template`,
   `document`, and `error` move into the monorepo like every other module. They
   hold features planned for when there is capacity.
