# portal-config-bootstrap

`portal-config-bootstrap` extends the public dev topology for an enterprise VM
bootstrap and Microsoft Entra sign-in evaluation.

## Compose inputs

The base platform is defined by `docker-compose.yml`. The enterprise BFF is an
additive overlay in `docker-compose.bootstrap.yml`. Do not extend a one-file
`docker compose config` example into an `up` command: the lifecycle wrapper
assembles additional image, private Portal, bootstrap and project-name inputs.

`restart-bootstrap-stack.sh` supplies environment files in this order when they
exist:

1. Repository `docker-images.env` for released image pins.
2. `LIGHT_PORTAL_ENV_FILE`, defaulting to
   `~/.config/lightapi/light-portal.env`, for shared private runtime inputs.
3. `BOOTSTRAP_ENV_FILE`, defaulting to `.env.bootstrap`, for enterprise
   overrides.

It reads `COMPOSE_PROJECT_NAME` from the bootstrap file and defaults it to
`light-portal-bootstrap`. The wrapper validates the resulting effective Compose
model before changing the running stack.

## Lifecycle

Validate the Compose and shell-script structure with the checked-in example
inputs:

```bash
./scripts/validate-bootstrap.sh
```

This is a repository contract check; it deliberately uses
`.env.bootstrap.example` and is not a rendering of the live deployment.

Validate the real private inputs and restart the deployed stack through:

```bash
./scripts/restart-bootstrap-stack.sh
```

The wrapper checks the required SSO artifact files and rejects missing or
placeholder Entra, token-exchange and Portal authorization values before its
effective `docker compose config --quiet` check.

To deliberately recreate the database from the current signed baseline:

```bash
./scripts/restart-bootstrap-stack.sh --recreate-database
```

That option downloads and verifies `events.zip` against the trusted pinned
Ed25519 release key, preserves the existing database as a timestamped backup,
initializes a fresh database and forces the full baseline import. Do not use it
for a routine restart.

## Runtime difference

The base OAuth BFF remains available while `portal-bff-sso` adds a second
`light-gateway` runtime identity. The SSO BFF has its own Config Server
selector, `msal-exchange` handler chain, Microsoft verifier, confidential token
exchange client, cookies, TLS material, config cache and SSO-enabled Portal View
artifact.

The SSO listener defaults to host port `8445`; enterprise DNS or a load balancer
normally presents it on `443`. Do not point two runtime identities at the same
Config Server instance merely because they use the same container image.

## Required private inputs

Create `.env.bootstrap` from `.env.bootstrap.example` and keep it out of source
control. Required inputs include the Microsoft tenant and client identity,
token-exchange client credentials, Portal authorization for the SSO runtime,
customer hostname and TLS configuration.

`VITE_SSO_ENABLED` and Microsoft SPA settings are build-time Portal View inputs.
Changing them requires rebuilding the SSO UI artifact, not just restarting the
container.

## Operational rules

- Use customer-issued certificates for shared use; self-signed generation is
  for isolated evaluation only.
- Preserve the base and SSO Config Server identities independently.
- Validate redirect URI, cookie domain, certificate SAN and public DNS as one
  contract.
- Treat `.env.bootstrap`, token material and TLS private keys as secrets.
- Promote the enterprise snapshot before expecting the second BFF to become
  ready.

See [Portal BFF and SSO](./services/portal-bff-sso.md) for the service contract.
