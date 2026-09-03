# Light OAuth

`light-oauth` issues and validates OAuth/OIDC tokens and exposes the JWKS used by
other services. The Compose deployments normally publish HTTPS on host port
`6881`.

## Configuration

| Input | Purpose |
| --- | --- |
| `LIGHT_RS_CONFIG_DIR` | Mounted bootstrap/template directory. |
| `RUST_LOG` | Rust logging filter. |
| `OAUTH_LOG_ANSI` | Enables or disables ANSI log output. |
| Portal database role | Reads OAuth client, key and user projections from the Portal database. |
| Config files and TLS material | Listener, handler, certificate and client settings. |

OAuth normally starts after PostgreSQL and, where applicable, operational
secret initialization. Config Server and most authenticated services depend on
OAuth readiness because they require JWKS or tokens.

## Operational notes

- The configured JWKS URL must resolve from inside each consuming container;
  `localhost` refers to that consumer, not the OAuth container.
- Issuer, audience, host name and certificate SAN must describe the same
  environment.
- OAuth key and client projections must exist before health at the transport
  layer is treated as authentication readiness.
- Never copy a Portal token between service identities merely to make startup
  pass. Each service token must have its intended subject, service ID and scope.

