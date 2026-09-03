# Hybrid Command And Query

`hybrid-command` and `hybrid-query` host the Java Portal command and query
modules. They remain separate services even when they share a PostgreSQL
database and Config Server environment.

## Network role

| Service | Default host port | Responsibility |
| --- | ---: | --- |
| `hybrid-command` | `8439` | Validated state changes, event append, outbox and command-side integrations. |
| `hybrid-query` | `8440` | Portal read models, projections, searches and scheduled projection work. |

## Important environment variables

| Variable | Service | Purpose |
| --- | --- | --- |
| `INSTANCE_CLONE_PLAN_HMAC_KEY`, `INSTANCE_CLONE_PLAN_HMAC_KEY_ID` | Both | Signs/verifies instance-clone plans. |
| `WORKFLOW_TOOL_ACCESS_APPROVAL_WF_DEF_ID`, `WORKFLOW_TOOL_ACCESS_APPROVAL_VERSION`, `WORKFLOW_TOOL_ACCESS_APPROVAL_DIGEST` | Command | Pins the approval workflow contract. |
| `A2A_SIGNING_SERVICE_URL` | Command | Optional signing-service integration. |
| `LIGHT_KNOWLEDGE_ADMIN_COMMAND_URL` | Command | Private Knowledge administration command endpoint. |
| `NOREPLAY_EMAIL_PASSWORD` | Command | Notification integration secret where enabled. |
| `LIGHT_WORKFLOW_RULE_TEST_URL` | Query | Workflow rule-test integration. |
| `LIGHT_KNOWLEDGE_CONTROL_SNAPSHOT_SIGNING_KEY` | Query | Signs Knowledge control snapshots. |
| `embedding-task.enabled`, `embedding-task.provider`, `embedding-task.endpoint`, `embedding-task.model`, `embedding-task.dimension` | Query | Optional asynchronous embedding-task configuration. |
| `embedding-task.apiKey` | Query | Secret provider credential for the asynchronous embedding task; keep it outside source control. |
| `JAVA_TOOL_OPTIONS` | Query | JVM runtime sizing and operational flags. |

These services consume event-backed Portal state. Repair projection lag through
the consumer/replay lifecycle; do not edit read-model rows to simulate command
success.
