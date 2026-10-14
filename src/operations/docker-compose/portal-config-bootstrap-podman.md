# portal-config-bootstrap on Red Hat with Podman

`portal-config-bootstrap` can reuse its Compose model with Podman and the
Python `podman-compose` provider. Docker Engine and Docker Compose are not
required. The existing scripts do, however, invoke `docker compose`, `docker
exec`, `docker run`, `docker inspect`, and `docker logs`. Use the scoped CLI
adapter below to preserve the bootstrap lifecycle, then qualify the installed
provider against the stack's dependency and health-check requirements.

This procedure was checked against the repository's scripts and Compose files.
It has not been exercised on a Red Hat EC2 instance. Parsing the Compose model
alone does not establish that the complete stack works with a particular
Podman/podman-compose version.

## 1. Choose one execution identity

Use **rootful Podman** for the existing topology unless corporate policy
requires rootless operation. The base gateway publishes `443:8443`; rootless
Podman normally cannot publish ports below 1024. The stack also uses bind mounts
for PostgreSQL data and initialization files, and includes services running as
container UID 0 and services using `LOCAL_UID`/`LOCAL_GID`.

Run setup, image loading, registry login, validation, and all lifecycle commands
as the same identity. Rootful and rootless Podman have different image stores,
containers, networks, volumes, and registry credentials. Mixing `podman` and
`sudo podman` commonly looks like missing images or missing containers.

For the examples below, enter an administrator-approved root shell and work in
a dedicated deployment checkout, for example `/srv/lightapi/portal-config-bootstrap`:

```bash
sudo -i
cd /srv/lightapi/portal-config-bootstrap
```

The default private input file now resolves under `/root/.config/lightapi`.
Set `LIGHT_PORTAL_ENV_FILE` explicitly if private inputs are elsewhere. Do not
run this stack alongside another stack using the same fixed container names
(including `postgres`) or published ports.

If rootless operation is mandatory, create a separately reviewed deployment
variant using an unprivileged gateway host port, such as `8443`, and an approved
load balancer or reverse proxy on 443. Update the wrapper's hard-coded
`https://localhost/` checks as well as public URLs and redirect URIs. Qualify
bind-mount UID mappings and database ownership; changing the port alone is not
a complete rootless conversion. Do not lower the host's privileged-port limit
as an incidental bootstrap workaround.

## 2. Install and select the Compose provider

Install `podman` and `podman-compose` from the organization's approved RHEL
repositories or internal package mirror:

```bash
dnf install podman podman-compose
podman --version
podman-compose --version
command -v podman podman-compose
```

Availability of `podman-compose` depends on the RHEL release and enabled
repositories. If the package is unavailable, obtain an approved package from
the platform team; do not assume public EPEL or public Python package downloads
are permitted. Also provide the existing scripts' host utilities, including
Bash, Python 3, curl, awk, sha256sum, and unzip where required by asset staging
or database recreation.

`podman compose` is a provider dispatcher, not a Compose implementation. Pin
its provider if operators want to use that spelling:

```bash
export PODMAN_COMPOSE_PROVIDER="$(command -v podman-compose)"
podman compose version
```

The adapter below calls `podman-compose` directly, so it cannot accidentally
select Docker Compose. Neither `podman-docker` nor a Docker-compatible socket
is needed for these CLI operations. A shell alias such as `alias docker=podman`
does not solve the scripts' noninteractive Bash invocations.

## 3. Add a deployment-local CLI adapter

Keep the adapter outside the repository and enable it only for the deployment
shell. If company policy also prohibits an executable *named* `docker`, use
the source adaptation described at the end instead.

```bash
install -d -m 0755 /srv/lightapi/podman-compat
cat > /srv/lightapi/podman-compat/docker <<'SH'
#!/usr/bin/env bash
set -euo pipefail

if [[ "${1:-}" != compose ]]; then
  exec podman "$@"
fi
shift

# Older podman-compose releases accept only one --env-file. Retain the
# scripts' input order by concatenating their simple dotenv files.
args=()
env_files=()
quiet=false
is_config=false
while (($#)); do
  case "$1" in
    --env-file)
      (($# >= 2)) || { echo 'missing --env-file argument' >&2; exit 2; }
      env_files+=("$2")
      shift 2
      ;;
    --env-file=*)
      env_files+=("${1#*=}")
      shift
      ;;
    config)
      is_config=true
      args+=("$1")
      shift
      ;;
    --quiet|-q)
      quiet=true
      shift
      ;;
    *)
      args+=("$1")
      shift
      ;;
  esac
done

# Only config --quiet is translated; fail rather than silently reinterpret
# a future use of --quiet with another subcommand.
if [[ "$quiet" == true && "$is_config" != true ]]; then
  echo 'adapter supports --quiet only with config' >&2
  exit 2
fi

env_tmp=''
cleanup() {
  if [[ -n "$env_tmp" ]]; then
    rm -f -- "$env_tmp"
  fi
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

if ((${#env_files[@]})); then
  umask 077
  env_tmp="$(mktemp "${TMPDIR:-/tmp}/portal-podman-env.XXXXXX")"
  for env_file in "${env_files[@]}"; do
    [[ -f "$env_file" ]] || { echo "missing environment file: $env_file" >&2; exit 2; }
    cat -- "$env_file" >> "$env_tmp"
    printf '\n' >> "$env_tmp"
  done
  args=(--env-file "$env_tmp" "${args[@]}")
fi

if [[ "$quiet" == true ]]; then
  podman-compose "${args[@]}" >/dev/null
else
  podman-compose "${args[@]}"
fi
SH
chmod 0755 /srv/lightapi/podman-compat/docker
export PATH="/srv/lightapi/podman-compat:$PATH"
hash -r
command -v docker
docker --version
```

The final command reports Podman. The adapter forwards engine commands with
their original argument boundaries and stdin, including streamed event imports
and SQL. It invokes Compose as a child so temporary environment files are
removed on normal exit. The temporary file is mode 0600; use a protected
`TMPDIR` on tmpfs if required by local secret-storage policy.

This adapter covers the shell bootstrap lifecycle, not every Docker Compose
feature. In particular, `scripts/portal-view-release.py` requests
`config --format json`; the adapter does not convert YAML output to JSON. If
the installed provider lacks that option, stage and verify the signed Portal
View release on an approved release machine and transfer its complete artifacts
using the existing release procedure. Do not assume the asset-release helper
will run on this EC2 host merely because shell bootstrap validation passes.
Running that helper locally requires separate JSON-output compatibility work
and qualification.

Environment concatenation is for **simple, literal `KEY=value` files**. Later
duplicate keys must win, and exported shell variables must retain precedence;
check this on the installed provider before activation. Avoid cross-file
`${VARIABLE}` expansion, multiline values, and shell expressions in these
inputs. Do not `source` the private files. If more complex dotenv semantics are
required, qualify a provider with native multiple-`--env-file` support and
adapt the wrapper to forward those flags without concatenation.

The adapter intentionally hides rendered stdout for `config --quiet`, since
the model contains credentials. Provider errors still reach stderr; review and
redact diagnostics before sharing them. Do not use shell tracing (`set -x`) or
publish a rendered private Compose model.

## 4. Prepare corporate-network access and images

Configure the deployment identity's proxy variables when outbound access
requires a proxy. Use the organization's actual proxy and bypass list:

```bash
export HTTPS_PROXY='http://proxy.corporate.example:8080'
export HTTP_PROXY="$HTTPS_PROXY"
export NO_PROXY='localhost,127.0.0.1,::1,.corporate.example'
export https_proxy="$HTTPS_PROXY" http_proxy="$HTTP_PROXY" no_proxy="$NO_PROXY"
```

Host image pulls and host curl downloads need their own access. Runtime
containers may also need outbound access for Microsoft Entra discovery/JWKS
and other configured providers. Podman can propagate proxy variables into
containers; ensure the runtime bypass list includes internal service names,
such as `postgres`, `controller`, `config-server`, `light-oauth`, and
`hybrid-query`. Verify this with the approved provider rather than assuming
host proxy settings are sufficient. Do not embed proxy credentials in this
guide or shell history.

Install corporate CA certificates into RHEL's approved trust store and run
`update-ca-trust`. For registry-specific trust, use the supported Podman
`/etc/containers/certs.d/<registry-host[:port]>/ca.crt` configuration. Container
and JVM trust stores are separate from host trust; configure them when runtime
HTTPS is intercepted. Preserve certificate verification and signed-release
verification; do not solve trust errors by disabling TLS verification.

The Compose files contain short image names, including
`timescale/timescaledb:latest-pg17` and `networknt/...`. Podman can prompt for
short-name resolution, which is unsuitable for unattended bootstrap. Configure
approved short-name aliases/registry mirrors in `registries.conf`, or use
fully qualified image references in the deployment copy. Set image variables
in `docker-images.env` where supported; hard-coded image references must also
be handled. Preserve release tags/digests rather than substituting arbitrary
`latest` images. Log in to private registries as the deployment identity.

For disconnected deployment, transfer approved image archives and load them
into the same Podman store:

```bash
podman load -i /srv/lightapi/images/portal-images.tar
podman images
```

The archive must include every active Compose image **and** images used by
one-off script commands, especially `EVENT_IMPORTER_IMAGE`. Loaded tags must
match the effective model. Prestage signed assets, baseline bundles and trusted
release keys through the existing release procedure; preserve signature and
digest checks. `BOOTSTRAP_DEPLOY_SKIP_PULL=true` only skips the wrapper's later
Compose pull, not missing-image pulls during earlier `up` or `run` commands.
`--recreate-database` still downloads its archive; use an approved internal
`BOOTSTRAP_EVENTS_ARCHIVE_URL` when necessary.

Allow required corporate DNS and outbound endpoints, including the approved
registry, release/CDN endpoints and Microsoft Entra endpoints. Limit EC2
security-group and host-firewall ingress to the intended clients and listeners.
The base model exposes PostgreSQL and several application ports; review all
published ports before allowing access. Public browser DNS, certificate SANs,
Entra redirect URI and cookie domain must agree. The SSO listener defaults to
8445, while the base gateway listens on host 443.

## 5. Apply SELinux labels to the deployment mounts

Keep SELinux enforcing. Many current bind mounts have no label option; the SSO
UI mount already uses `:ro,Z`. Unlabelled mounts can cause permission failures
despite correct Unix permissions. Apply labels in the dedicated EC2 deployment
copy of **both** Compose files:

- Use `:z` for writable bind directories shared by containers.
- Use `:ro,z` for read-only bind files/directories shared by containers.
- Use `:Z`/`:ro,Z` only for paths exclusively used by one container.
- Leave named volumes as named volumes; do not add host-path relabel options.

For example, preserve these destinations and add shared labels:

```yaml
services:
  postgres:
    volumes:
      - ./postgres-db/data:/var/lib/postgresql/data:z
      - ./postgres-db/init-environment.sh:/docker-entrypoint-initdb.d/00-init-environment.sh:ro,z
      - ./postgres-db/lib:/docker-entrypoint-initdb.d/lib:ro,z
```

These lines illustrate edits to existing entries, not a complete replacement
for PostgreSQL's volume list. Review every other bind mount too, including
configuration, CA files, TLS material, secrets and UI assets. Some paths are
shared across services; applying private `:Z` labels repeatedly can make a
previous container lose access. Use shared labels where paths or overlapping
directory trees are shared. Relabel only dedicated deployment content, never
system directories or an entire home directory. Unix ownership and file modes
still apply; ensure non-root service UIDs can read their intended secrets and
write their intended data without making secrets world-readable.

If access fails, inspect `ls -Z`, container logs and administrator-visible AVC
records (`ausearch -m AVC -ts recent`). Correct labels or ownership rather than
using `chmod -R 777`, disabling SELinux, or discarding the database directory.

## 6. Qualify the installed provider before startup

Record the RHEL, Podman and podman-compose versions. With the adapter on PATH,
first run the repository's example-input contract check:

```bash
./scripts/validate-bootstrap.sh
```

This checks the example model and shell syntax; it does not validate private
inputs, image availability or runtime behavior. Do not replace unsupported
Compose features with weaker startup semantics to make parsing pass.

Check environment precedence with nonsecret fixtures:

```bash
check_dir="$(mktemp -d)"
printf 'CHECK_IMAGE=docker.io/library/alpine:3.20\n' > "$check_dir/first.env"
printf 'CHECK_IMAGE=docker.io/library/alpine:3.21\n' > "$check_dir/second.env"
cat > "$check_dir/compose.yml" <<'YAML'
services:
  check:
    image: ${CHECK_IMAGE:?missing CHECK_IMAGE}
YAML
(unset CHECK_IMAGE; docker compose -f "$check_dir/compose.yml" \
  --env-file "$check_dir/first.env" --env-file "$check_dir/second.env" config)
CHECK_IMAGE=docker.io/library/alpine:3.22 docker compose \
  -f "$check_dir/compose.yml" --env-file "$check_dir/first.env" \
  --env-file "$check_dir/second.env" config
```

Expect `3.21` in the first rendering and `3.22` in the second. These commands
only render nonsecret fixtures and do not pull or start containers. Remove the
fixture directory after review. Use it also to confirm that `config --quiet`
produces no model output and that a missing required variable exits nonzero.

Before using the full lifecycle, qualify a small disposable Compose stack with
an approved local image and a separate project name. Verify:

| Requirement | Why bootstrap needs it |
| --- | --- |
| Two `-f` files and ordered environment inputs | Base topology plus enterprise BFF overlay and private overrides |
| `config --format json`, if local release tooling is used | Portal View release helper reads a JSON effective model; otherwise prestage releases elsewhere |
| Required/nested variable substitution and project naming | Image pins, required credentials and the bootstrap network |
| `service_healthy` dependency conditions | Database, controller, OAuth and Config Server readiness |
| `service_completed_successfully` dependency conditions | Successful one-shot initialization/schema jobs before applications |
| Failure propagation for unhealthy/failed dependencies | Applications must not start after failed schema validation |
| `up -d --no-deps`, `up -d --remove-orphans`, `pull`, `restart`, `ps`, `down` | Commands used by bootstrap and delta-import scripts |
| Podman `exec -i`, `run --rm -i --network`, DNS and inspect templates | SQL, event imports, readiness checks and discovery of the real network |

Older providers can accept a dependency condition yet implement it differently.
Test both successful and failed one-shot jobs, and delayed/unhealthy services.
If a gate fails, obtain an approved newer provider or implement explicit
equivalent orchestration before activation. Do not remove the conditions or
skip operational-schema/registration gates. A compatibility adapter translates
CLI spelling; it cannot supply missing Compose orchestration behavior.

## 7. Use the existing bootstrap lifecycle

Prepare signed release assets, SSO UI, TLS files and private environment inputs
using the [bootstrap guide](./portal-config-bootstrap.md) and repository README.
Then run from the deployment directory with the adapter still on PATH:

```bash
export LIGHT_PORTAL_ENV_FILE='/srv/lightapi/private/light-portal.env'
export BOOTSTRAP_ENV_FILE="$PWD/.env.bootstrap"
# Only for fully prestaged images:
export BOOTSTRAP_DEPLOY_SKIP_PULL=true
./scripts/restart-bootstrap-stack.sh
```

The wrapper assembles `docker-images.env`, the private Portal input file, then
the bootstrap input file, and defaults the project to `light-portal-bootstrap`.
It validates SSO assets/private values, starts PostgreSQL, handles baseline
import and projections, applies patches/deltas, waits for operational-store
registrations, refreshes configuration snapshots, then starts the full stack
and runs health checks. Keep this ordering. A bare `podman-compose up -d` with
only the base file bypasses necessary bootstrap work.

Normal restart does not request database recreation. Use
`--recreate-database` only when deliberately replacing the database with the
signed baseline; it stops the stack and preserves the old bind directory as a
timestamped backup. The adapter does not change those semantics.

For diagnostics, use the same identity:

```bash
podman ps -a
podman logs --tail 100 postgres
podman inspect -f '{{.State.Running}}' postgres
podman inspect -f '{{range $name, $_ := .NetworkSettings.Networks}}{{println $name}}{{end}}' postgres
podman exec postgres psql -h localhost -U postgres -d configserver -tAc 'select 1;'
```

Verify the discovered network and container-to-container DNS before event
imports. If setting `EVENT_IMPORT_NETWORK` explicitly, use the actual Podman
network name, not a guessed directory-based default. Inspect one-shot job exit
codes and application health, then test the corporate public URL and an actual
Entra sign-in/token exchange. The wrapper's local curl checks use `-k` and
several base development hostnames; passing them is not proof of corporate
certificate trust, external routing or SSO success.

The shell PATH change does not persist across logout, `sudo`, cron or systemd.
For a managed boot service, set its working directory, execution identity,
PATH and private input paths explicitly, and validate its startup ordering.
Qualify reboot behavior separately; a successful interactive startup does not
establish boot-time recovery.

## Alternative: explicit source adaptation

If a compatibility executable is disallowed, update all lifecycle consumers in
a maintained deployment branch: use an engine array defaulting to `podman`
and a Compose array defaulting to `podman-compose`, pass ordered environment
inputs through a qualified helper, and implement quiet config validation without
printing credentials. Some scripts already expose `CONTAINER_CMD`, but the
restart wrapper, validator, PostgreSQL wait, patch application, event-delta
import, snapshot refresh and log collection still contain hard-coded Docker
calls. Setting `CONTAINER_CMD=podman` alone is insufficient. Qualify the entire
startup path after that change, not just the first failing command.

See [Podman Compose](https://docs.podman.io/en/latest/markdown/podman-compose.1.html),
[Podman run and volume labels](https://docs.podman.io/en/latest/markdown/podman-run.1.html),
and the [podman-compose provider](https://github.com/containers/podman-compose)
for version-specific behavior. Use the documentation matching the approved
RHEL packages when it differs from the latest upstream release.
