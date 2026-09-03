# portal-config-dev

`portal-config-dev` is the shared development deployment. It is derived from
`portal-config-loc/all-in-lt` but keeps environment-specific DNS, certificates,
tokens, service identities and persistent data.

## Intended use

- The public development environment at `dev.lightapi.net`.
- Integration testing against shared services and realistic TLS/DNS routing.
- Validation of promoted Config Server snapshots and release images.

It is not the authoring source for canonical event-backed Portal data. Author
and validate that data in `portal-config-loc`, export it, then recreate or
update dev through the supported bundle/import workflow.

## Runtime shape

The single `docker-compose.yml` contains PostgreSQL, schema and operational
bootstrap jobs, OAuth, controller, Config Server, hybrid services, Portal
service, Gateway, dedicated LLM Gateway, Workflow, Agent, Knowledge services and
demo backends. `light-a2a` is optional through the `a2a` profile.

Gateway normally publishes host port `443`; LLM Gateway publishes `8444`.
Public routing uses `dev.lightapi.net` and `devsignin.lightapi.net`. Both names
must resolve to the deployment host and match the promoted Gateway snapshot and
TLS assets.

## Configuration sources

- `docker-compose.yml` defines the container topology and environment wiring.
- Service directories contain `startup.yml`, certificates and template files.
- `~/.config/lightapi/light-portal.env` is the default private environment file
  consumed by `scripts/restart-dev-stack.sh`.
- Config Server supplies promoted runtime properties for the exact host,
  service ID and environment tag.
- Named config-cache volumes preserve the last validated snapshots.

Keep provider keys, Portal authorization tokens, database credentials and
cryptographic keys outside Git. A Compose variable that is absent can render as
an empty value, but a feature published as active may reject that empty value.

## Lifecycle

Use the repository wrapper so database recreation, asset synchronization and
startup order remain coordinated:

```bash
./scripts/restart-dev-stack.sh
```

Use `--recreate-database` only when intentionally rebuilding the environment
from its canonical input. Review the repository README before destructive
options.

After a configuration change, distinguish three operations:

- Restart reloads process-local environment and startup files.
- Explicit Config Server reload applies only reloadable modules.
- Recreating a config-cache volume removes retained snapshots and should be a
  deliberate recovery action.

## Release discipline

Dev should run published, pinned release inputs wherever the Compose contract
provides an image variable. A container restart does not refresh an image tag or
a cached release environment automatically. Confirm image IDs and active
snapshot generations when validating a newly released feature.

