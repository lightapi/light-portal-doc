# Faster Local Rust Image Builds

## Status

Implemented on 2026-09-25 in `light-fabric` and `portal-service`. Build and
selection behavior has not yet been runtime-qualified or timed.

## Goal

Shorten local image builds and releases for the Rust apps in `light-fabric` and
`portal-service`. When requested, build only images affected by files currently
changed in either working tree. “Changed” means staged, unstaged, and untracked
files relative to that repository's `HEAD`; no comparison ref is required.

Keep the existing full-build and explicit single-app/service flows. The
changed-app path is opt-in, reports its selected images before building, and
can be combined with the existing local-only mode to avoid Docker Hub pushes.

## Previous Build Behavior

### `light-fabric`

The root [`build.sh`](../../../light-fabric/build.sh) accepts `--app` for one
app, `--local` to skip pushes, and
`--no-cache`. By default it builds nine release apps. For each selected app,
it runs a host `cargo build`, then runs `docker build`. The Dockerfile
independently compiles the binary inside a Rust builder image; it does not
consume the host build output. The Dockerfiles copy workspace source before
running Cargo, so source edits invalidate the Docker compile layer.

### `portal-service`

The root [`build.sh`](../../../portal-service/build.sh) accepts `--service`,
`--local`, and `--no-cache`. Its
default is three images: `config-server`, `light-oauth`, and `portal-service`.
It builds each image from one shared
[`docker/Dockerfile`](../../../portal-service/docker/Dockerfile), which
compiles that binary inside Docker. The Docker context is the workspace parent so the build
can read both the `portal-service` and sibling `light-fabric` checkouts. The
Dockerfile copies their app and crate trees before compiling.

Neither script currently chooses apps from local Git changes. `--local`
already provides the requested build-without-publishing switch in both repos.

## Proposed Interface

Add an opt-in `--changed` flag to both scripts:

```bash
# Preview the selected app set, build it, and keep images local.
./build.sh 2.3.5-dev.20260909.2338 --changed --local

# Build and publish only selected light-fabric images.
./build.sh 2.3.5-dev.20260909.2338 --changed

# portal-service uses the same selection and local-only conventions.
./build.sh 2.3.5-dev.20260909.2338 --changed --local
```

`--changed` applies to the selected app/service set. If combined with `--app`
or `--service`, selection is the intersection: the named app is built only if
it is affected. If no selected app is affected, exit successfully with a clear
“no affected images” message and do not build or push anything. The full build
remains the default when `--changed` is omitted.

With `--changed` and publishing enabled, push only the affected version tags
and update `latest` only for those same images. This intentionally produces a
partial release set; omit `--changed` when a coordinated release requires all
images at the requested version. Prefer `--changed --local` while reviewing
which images were selected.

## Change Detection

Collect paths with NUL-delimited Git status output, including staged,
unstaged, deleted, renamed, and untracked paths. Do this independently in
`light-fabric` and `portal-service`; `portal-service` builds must also inspect
uncommitted files in its sibling `light-fabric` dependency checkout. Do not
include ignored build outputs such as `target/`.

Map changed files to Cargo packages using workspace metadata and package
manifest locations, then follow reverse dependency edges from each changed
package to the selected binary packages. This captures changes in shared
crates without rebuilding unrelated apps. A changed app directory, including
its config copied into an image, affects that app's image. A package that is a
transitive dependency of multiple selected apps affects every dependent image.

Use conservative all-app invalidation for workspace-level inputs that can
change dependency resolution or compilation globally: root Cargo manifests and
lockfiles, Rust toolchain or Cargo configuration, shared Docker build files,
and build-selection logic. In `portal-service`, changes to the shared
Dockerfile affect all three service images. Changes to either repo's build
script affect selection/build orchestration but need not by themselves mark
application binaries as changed; the implementation should make this explicit
and test it.

The selector should print changed paths grouped by repository, the reason each
image was selected, and the final image list. On Git or Cargo metadata errors,
fail closed with a diagnostic rather than silently treating the tree as clean.

## Docker Build Improvements

### 1. Keep Cargo outputs between image builds

Enable Docker BuildKit and add cache mounts to every Rust builder stage for the
Cargo registry, Git checkout cache, and `target` directory. Give each cache a
stable ID scoped by repository, Rust toolchain, and compilation target. This
allows Cargo to reuse downloaded crates and compiled dependencies when a
changed source file causes the Docker `RUN cargo build` step to execute again.
Because a mounted `target` directory is not part of the builder image layer,
copy the just-built executable to an ordinary builder path such as `/out` in
the same `RUN` step, then copy `/out` into the runtime image. Otherwise the
final `COPY --from=builder` cannot see the binary stored in the cache mount.

Docker's `--no-cache` does not clear BuildKit cache mounts. Preserve a true
cold-build diagnostic by giving `--no-cache` a fresh, invocation-specific
cache ID (or by adding an explicit cache-disabling option); do not imply that
`--no-cache` emptied persistent Cargo caches. Normal builds should reuse stable
cache IDs.

The cache is an optimization only. Builds must remain correct when the cache
is empty, evicted, or shared between sequential image builds. Do not share a
target cache across incompatible Rust versions or targets. Continue building
images sequentially unless cache locking and resource use are measured first.

### 2. Remove duplicate host compilation in `light-fabric`

Remove the host `cargo build` from root `build.sh` once the image build remains
the sole source of the packaged binary. The current Dockerfiles compile again
inside their builder stages, so the host result does not save Docker work.
Preserve each Dockerfile's target-specific toolchain, especially the
`x86_64-unknown-linux-musl` build for `light-agent`.

### 3. Reduce `portal-service` build context

The current workspace-parent context can include unrelated sibling checkouts
and generated files in context transfer. Add a filtered context for the two
required repositories, or use BuildKit named contexts so the Docker build can
read only the needed `portal-service` and `light-fabric` paths. Keep path
dependencies and any Cargo development-dependency manifests needed for locked
resolution; an incomplete filtered context must fail in qualification, not be
hidden by an unlocked build.

First measure context transfer and cache behavior. Defer splitting dependency
manifest layers or pruning copied source trees until the simpler Cargo cache
change is measured: workspace manifests and path dependencies make hand-built
Docker layers easy to invalidate incorrectly.

## Implementation Notes

- Both build scripts accept `--changed`, using staged, unstaged, and
  untracked Git changes and Cargo package dependency closure selection.
- `portal-service` checks both working trees and uses BuildKit named contexts
  plus a Docker ignore file to limit source contexts to required repositories.
- Release Dockerfiles use BuildKit Cargo cache mounts. `light-fabric` no longer
  performs the unused host-side Cargo build.
- Files under a root `contracts/` directory belong to no Cargo package; they
  select the packages whose Rust sources reference that contract directory,
  or every image when no reader is found.
- `light-fabric` offers only release images to the selector unless an
  optional image is named with `--app`.
- `--no-cache` prunes its invocation-specific Cargo cache mounts on exit.
- `portal-service` builds every selected image before pushing, supports
  `--skip-latest`, and labels images with both source revisions.
- `light-fabric` CI runs the selector unit tests and the build orchestration
  harness.
- Run the selection scenarios and cold/warm build timing before treating the
  change as qualified or claiming a measured speedup.

## Acceptance Criteria

- Existing full builds, explicit app/service selection, `--local`, and
  `--no-cache` keep their current meaning.
- `--changed` includes staged, unstaged, and untracked source/config changes
  and sees changes in `portal-service`'s sibling `light-fabric` checkout.
- Shared dependency edits select all and only dependent images; global build
  inputs conservatively select all images.
- A clean tree selects no images and never pushes tags.
- A local-only build never calls `docker push`.
- BuildKit caches improve warm-build time without changing the resulting
  runtime image contents or relying on cache presence for correctness.
- The `portal-service` image build still resolves locked path dependencies from
  both repositories.
- Measurements report full build and changed-only build times separately.
