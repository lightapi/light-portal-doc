# Light Agent

`light-agent` hosts agent execution. Some deployments run one general Agent;
`portal-config-loc` additionally starts specialized advisor and technical
support service instances from the same image with distinct service IDs and
ports. These are ordinary Compose services, not Compose profiles.

## Important environment variables

| Variable | Secret | Purpose |
| --- | ---: | --- |
| `LIGHT_AGENT_HOST_ID` | No | Portal host identity. |
| `LIGHT_AGENT_SERVICE_ID`, `SERVER_SERVICEID` | No | Runtime service/profile identity. |
| `LIGHT_AGENT_ENVIRONMENT`, `LIGHT_ENV_TAG` | No | Config Server and runtime environment selectors. |
| `LIGHT_AGENT_ADVERTISED_ADDRESS` | No | Address registered for callers. |
| `LIGHT_PORTAL_AUTHORIZATION` | Yes | Agent service token. |
| `LIGHT_AGENT_DELEGATION_SECRET` | Yes | Authenticates bounded delegation where enabled. |
| `LIGHT_AGENT_MODEL`, `LIGHT_AGENT_TEMPERATURE`, `CODEX_REASONING_EFFORT` | No | Model/runtime behavior overrides for configured profiles. |
| `CODEX_API_KEY`, `CODEX_ACCOUNT_ID` | Yes | Codex provider identity where that runtime is selected. |
| `LIGHT_AGENT_KNOWLEDGE_URL` | No | Knowledge API endpoint. |
| `LIGHT_AGENT_KNOWLEDGE_ALLOW_PRIVATE_PLAINTEXT` | No | Explicit development policy switch. |
| `AGENT_OPERATIONALSTORE_DATABASEURLFILE` | Yes, by content | Protected operational database URL file. |
| `AGENT_A2APOLICY_AUTHORIZATIONCONTEXTKEYFILE`, `AGENT_A2AOUTBOUND_AUTHORIZATIONCONTEXTKEYFILE` | Yes, by content | A2A authorization-context key files. |
| `RUST_LOG`, `AGENT_LOG_ANSI` | No | Logging controls. |

## Isolation

Service instances sharing an image are still separate runtime identities. Give
each instance its intended service ID, advertised address, Config Server
snapshot and operational ownership. Do not route two instances through one
identity merely to reduce configuration records.

Agent artifacts belong on the designated persistent artifact volume. Database
URLs and A2A keys are materialized before Agent starts; broad access to the
initial secret source should not be carried into the runtime container.
