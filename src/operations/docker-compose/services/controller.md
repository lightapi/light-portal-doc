# Controller

`controller` is the Rust control-plane runtime used for service registration,
control transport and bounded execution coordination. It is normally reachable
inside the Compose network rather than published directly to the host.

## Configuration groups

| Variables | Purpose |
| --- | --- |
| `CONTROLLER_ADDR`, `CONTROLLER_EXECUTION_PORT` | Listener and execution transport addresses. |
| `CONTROLLER_HOST_ID`, `CONTROLLER_USER_ID` | Portal identity and ownership context. |
| `DATABASE_URL`, `DATABASE_MAXIMUM_POOL_SIZE` | Portal control-plane database connection. |
| `CONTROLLER_EXECUTION_DATABASE_URL_FILE` | Protected operational execution database URL. |
| `CONTROLLER_EXECUTION_BINDING_ID`, `CONTROLLER_EXECUTION_BINDING_DIGEST` | Approved operational-store binding. |
| `CONTROLLER_EXECUTION_EXPECTED_DATABASE`, `CONTROLLER_EXECUTION_MINIMUM_SCHEMA_GENERATION` | Database and migration fences. |
| `CONTROLLER_EXECUTION_ENVIRONMENT`, `CONTROLLER_EXECUTION_REQUIRED_SCOPE` | Runtime environment and authorization boundary. |
| `MICROSERVICE_JWKS_URL`, `MICROSERVICE_JWT_AUDIENCE` | JWT verification contract. |
| `CONTROLLER_TLS_CERT_PATH`, `CONTROLLER_TLS_KEY_PATH`, `CONTROLLER_TLS_TRUST_CERT_PATH` | TLS identity and trust. |
| `CONTROLLER_RUNNER_ENABLED`, `CONTROLLER_MCP_MUTATIONS_ENABLED` | Explicit capability switches. |

## Dependencies and readiness

Controller depends on PostgreSQL, OAuth where JWT verification is required, and
successful operational bootstrap/validation. A valid operational binding must
match host, environment, database, schema generation and digest; bypassing one
field weakens the binding contract.

Runtime services often depend on Controller registration. Check Controller logs
before diagnosing downstream registry timeouts.

