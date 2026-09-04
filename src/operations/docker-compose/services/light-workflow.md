# Light Workflow

`light-workflow` executes published workflow definitions and exposes direct and
workflow-backed MCP invocation paths. The Compose deployments normally publish
host port `8436`.

## Configuration groups

| Variables | Purpose |
| --- | --- |
| `LIGHT_WORKFLOW_HTTP_ADDR` | Workflow HTTP listener. |
| `SERVER_ADVERTISEDADDRESS`, `SERVER_ENVIRONMENT` | Address and environment registered with Controller/Portal. |
| `SERVER_ENABLEREGISTRY`, `SERVER_STARTONREGISTRYFAILURE` | Registry behavior and startup policy. |
| `PORTALREGISTRY_PORTALURL` or `portalRegistry.portalUrl` | Portal registry endpoint. |
| `LIGHT_PORTAL_AUTHORIZATION` | Workflow service identity for configuration and downstream calls. |
| `WORKFLOW_INVOCATION_CALLER_SERVICE_IDS` | Allowed caller service identities. |
| `WORKFLOW_MAXIMUM_PARALLELISM` | Execution concurrency bound. |
| `WORKFLOW_IGNORE_USER_JWT_EXPIRY` | Explicit development/testing compatibility switch. |
| `WORKFLOW_A2A_AUTHORIZATIONCONTEXTKEYFILE` | Protected A2A authorization-context key. |
| `OPERATIONALSTORE_*` or `operationalStore.*` | Operational database, schema, binding and generation fences. |
| `RUST_LOG`, `WORKFLOW_LOG_ANSI` | Logging controls. |

Property names can appear in dotted form or as Compose-normalized uppercase
environment names. Preserve the exact spelling used by the selected Compose
file and service release.

## Configuration and storage

Workflow uses a mounted `startup.yml` to select its Config Server instance and
retains a validated snapshot in `light-workflow-config-cache`. Its operational
database URL is supplied through a protected file, not through the Portal
catalog database connection.

The approved binding includes host, environment, database, schema, service
owner, credential generation and minimum schema generation. The operational
schema contains workflow-owned runtime/projection data; Portal catalog tables
must not be assumed to be co-located.

All four Compose distributions run a `workflow-projection-sync` service. It
publishes the required Workflow definitions, bindings, grants, dependencies and
resolved endpoint metadata from the Config Server database into the
Workflow-owned operational schema every 30 seconds. Its initial minimum counts
are zero so a fresh stack can start before Portal event replay has populated the
catalog. `light-workflow` waits for the sync service's first successful pass;
later catalog changes are refreshed without restarting Workflow.

## Invocation identity

Gateway preserves the user's JWT in `Authorization` and sends its own service
identity in `X-Scope-Token`. Workflow authenticates both boundaries and uses its
own service token for protected downstream calls.

`WORKFLOW_INVOCATION_UNAVAILABLE` means the Gateway reached Workflow and
Workflow returned an unavailable response. Inspect Workflow logs and its
database/configuration before changing Gateway policy.
