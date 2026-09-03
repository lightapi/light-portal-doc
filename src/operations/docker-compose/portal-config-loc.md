# portal-config-loc

`portal-config-loc` is the authoring and full-stack development distribution.
The supported Rust-era stack is
`portal-config-loc/all-in-lt/docker-compose.yml`; the retired Java/Rust overlay
pair is not part of the current `all-in-lt` lifecycle.

## Intended use

- Platform and Portal feature development.
- Creation and validation of the canonical local event baseline.
- Local testing of Gateway, Workflow, Agent, Knowledge and LLM features.
- Running Portal View from a sibling checkout while backend services run in
  Compose.

## Lifecycle

From the repository root, prefer the deployment wrapper because it obtains
release assets, handles an empty event store and preserves the expected startup
sequence:

```bash
./scripts/deploy-local.sh lt
```

For a complete recreation:

```bash
REFRESH_RELEASE_ASSETS=true CLEAN_VOLUMES=true ./scripts/deploy-local.sh lt
```

The wrapper also adds the release image environment file and the private Portal
environment file, which defaults to
`~/.config/lightapi/light-portal.env`. There is no equivalent checked-in
`all-in-lt/.env`.

Do not run a bare `docker compose up -d` from `all-in-lt` after a wrapper
deployment. It targets the same default Compose project but omits those files,
so it can silently recreate containers with fallback image tags and empty
private inputs. Direct inspection and shutdown commands remain safe:

```bash
docker compose ps
docker compose down --timeout 30 --remove-orphans
```

Deleting volumes destroys local databases and caches. Use the repository's
documented recreation path rather than adding volume removal to routine restarts.

## Runtime shape

The default stack includes PostgreSQL, schema/bootstrap jobs, Light OAuth,
controller, Config Server, `hybrid-command`, `hybrid-query`, Portal service,
Light Gateway, the dedicated LLM Gateway, Workflow, three Agent service
instances (`light-agent`, `light-agent-advisor`, and
`light-agent-tech-support`), Knowledge API/admin/worker, and three demo
backends. `light-a2a` is under the `a2a` Compose profile.

Important host ports include `443` for Light Gateway, `8444` for LLM Gateway,
`8435` for Config Server, `8436` for Workflow, `6881` for OAuth, `8439` and
`8440` for the hybrid services, `2498` for Portal service, and `5432` for local
PostgreSQL access.

## Configuration and secrets

Service templates and startup selectors live under `all-in-lt/*/config`.
Provider credentials and other operator inputs may be loaded from the local
Portal environment file used by `deploy-local.sh`. Config Server supplies
promoted service properties; persistent service caches retain validated
snapshots across restarts.

Development-only values embedded in Compose are conveniences, not production
examples. In particular, cryptographic values must still satisfy the runtime
format contract. A readable placeholder is not interchangeable with random key
material.

The LLM reasoning seal is active only when the published `llm-router` snapshot
declares it active. In that case, `LLM_REASONING_SEAL_KEY` must be unpadded
Base64URL that decodes to exactly 32 bytes. See
[LLM Gateway](./services/llm-gateway.md).

## Source-of-truth rule

Author event-backed baseline changes here, validate them, export the signed
environment bundle, and then recreate downstream dev/install environments from
that bundle. Do not make `portal-config-dev` the canonical authoring database.
