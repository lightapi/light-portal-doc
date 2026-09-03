# Docker Compose Deployments

Light Portal has four maintained Compose distributions. They share the same
service architecture but serve different operational purposes.

| Distribution | Intended use | Primary Compose input | Public entry point |
| --- | --- | --- | --- |
| `portal-config-loc` | Local platform and feature development | `all-in-lt/docker-compose.yml` | `https://dev.lightapi.net` mapped to the local host by default |
| `portal-config-dev` | Shared public development environment | `docker-compose.yml` | `https://dev.lightapi.net` |
| `portal-config-bootstrap` | Enterprise VM bootstrap and Microsoft Entra SSO evaluation | `docker-compose.yml` plus `docker-compose.bootstrap.yml` | Customer DNS; the SSO listener defaults to host port `8445` |
| `light-portal-install` | End-user laptop installation | `docker-compose.yml`, managed through `install.sh` | `https://local.localhost` |

Use the distribution-specific pages for lifecycle commands and overrides:

- [portal-config-loc](./docker-compose/portal-config-loc.md)
- [portal-config-dev](./docker-compose/portal-config-dev.md)
- [portal-config-bootstrap](./docker-compose/portal-config-bootstrap.md)
- [light-portal-install](./docker-compose/light-portal-install.md)

The [service catalog](./docker-compose/services.md) explains each shared service
and its configuration contract once.

## Configuration precedence

Configuration crosses two precedence boundaries. Treating them as one list can
hide the value that actually won.

### Compose materialization

The deployment wrapper assembles interpolation inputs from the invoking shell
and its ordered `--env-file` arguments, then Compose creates the container's
final process environment from the service definition. The wrappers may add
release image pins and private provider, database, token, or cryptographic
values that a bare `docker compose` command does not load.

Use the deployment wrapper whenever containers may be created or recreated.
Inspect its ordered environment files and the resulting container environment
when diagnosing an override. Do not publish a fully rendered Compose document,
because it can contain secret values.

### Application placeholder resolution

For a placeholder such as `${gatewayEvidence.bindingId:...}`, the runtime checks
the process environment first, using the normalized uppercase name, and then
the active external `values.yml` supplied by the promoted Config Server
snapshot. The template/default value is used only when neither source provides
the property.

The effective value order is therefore:

1. Process environment, including explicit Compose `environment` entries.
2. The promoted snapshot's external `values.yml`.
3. The selected configuration template's placeholder default.
4. Application defaults where no configured value is present.

File selection is a separate rule: a snapshot-delivered file in the external
configuration directory can replace the corresponding local template. After
that file is selected, its placeholders still resolve process environment
before `values.yml`.

For example, a stale `GATEWAYEVIDENCE_BINDINGID` in Compose continues to win
over a corrected `gatewayEvidence.bindingId` in a newly promoted snapshot.
Check the container environment before concluding that the snapshot is wrong.

## Configuration classes

| Class | Examples | Handling rule |
| --- | --- | --- |
| Runtime selector | host ID, service ID, environment, environment tag | Must identify the intended Config Server instance exactly. |
| Non-secret property | port, timeout, feature state, schema name | May be stored in Compose or published configuration. |
| Secret reference | `env:NAME`, mounted secret path | May be published; it names the location but never contains the secret bytes. |
| Secret material | provider API key, database password, signing or sealing key | Keep outside Config Server snapshots and source control. |
| Generated artifact | config cache, event bundle, UI distribution, runtime credential file | Recreate through the owning deployment workflow; do not hand-edit container state. |

An environment variable is not automatically secret. Its value and purpose
determine how it must be managed.

## Shared startup order

The detailed dependency graph varies slightly, but the supported stacks follow
the same phases:

1. Start PostgreSQL.
2. Apply Portal, Knowledge and operational schemas.
3. Materialize runtime credential files and validate the operational contract.
4. Start OAuth, controller and Config Server.
5. Start Portal command/query services and Portal service.
6. Start Workflow, Gateway, LLM Gateway, Agent and Knowledge services.
7. Start demo services and optional A2A components.

`depends_on` orders container startup; it does not prove application readiness
unless the dependency uses a health check or a successful one-shot completion
condition.

## Operational database boundary

The stacks may use one PostgreSQL container, but the logical databases and
service roles remain separate. Portal catalog data belongs to `configserver`,
Knowledge data belongs to `knowledge`, and runtime evidence/state belongs to an
operational database such as `operations`. Each runtime identity has a bounded
role and schema search path.

Do not repair an operational projection by copying Portal catalog tables into
an operational schema. Correct the publication/projection contract and rebuild
derived state through its supported path.

## Safe validation

Before starting a changed stack, render it without printing secret values into
logs:

```bash
docker compose config --quiet
docker compose config --services
docker compose config --profiles
```

After startup, verify health and then inspect the first service-specific error:

```bash
docker compose ps
docker compose logs --since 10m SERVICE_NAME
```

Avoid publishing the output of a complete `docker compose config`; it expands
environment variables and can expose credentials.
