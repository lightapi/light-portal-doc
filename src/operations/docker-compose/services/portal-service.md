# Portal Service

`portal-service` is the Rust Portal-facing service for APIs and platform
integrations that do not reside in the Java hybrid hosts. The Compose stacks
normally publish host port `2498`.

## Configuration

| Variable | Purpose |
| --- | --- |
| `LIGHT_RS_CONFIG_DIR` | Mounted service configuration directory. |
| `LIGHT_PORTAL_AUTHORIZATION` | Service identity used for protected Portal/configuration calls when required. |
| `RUST_LOG` | Rust logging filter. |
| `PORTAL_LOG_ANSI` | ANSI log setting. |

Portal service depends on PostgreSQL and Config Server; some distributions also
gate it on Controller or OAuth. The current Compose file is authoritative for
the exact dependency conditions.

When a route fails, distinguish the public Gateway response from Portal
service behavior. Confirm that the request reached port `2498`, then inspect the
service's active snapshot and database identity.

