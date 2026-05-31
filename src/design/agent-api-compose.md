# Agent API Compose And Multi-Agent Workflow

## Problem

`portal-config-loc` and `portal-config-dev` are being updated so local Docker
Compose stacks can run `light-agent` beside the portal services, demo APIs, and
gateway. The first implementation adds one `light-agent` directly to the main
compose file and points the gateway direct registry at `http://light-agent:8083`.

That works for a single account agent, but it does not scale cleanly for the
next phase:

- the base portal stack should remain usable without demo APIs or agents,
- demo APIs and agents should be startable as an optional local package,
- all services must still share the same Docker network,
- multiple `light-agent` instances need unique runtime identities,
- each agent needs a different effective skill/tool/workflow catalog,
- workflows need to orchestrate API access across multiple specialized agents.

The design goal is to split deployment concerns without splitting the runtime
network or the control-plane model.

## Goals

- Move the two demo APIs and local `light-agent` services into a separate
  Docker Compose overlay file.
- Keep the overlay on the same Docker network as the portal stack, gateway,
  controller, config-server, Postgres, and hybrid services.
- Support multiple `light-agent` containers from the same image with different
  service ids, advertised addresses, ports, model settings, agent definitions,
  skills, tools, and workflows.
- Keep `light-gateway` as the MCP runtime path for `tools/list` and
  `tools/call`.
- Keep portal-query as the source for the effective agent catalog.
- Use `skill_workflow_t` and `wf_definition_t` to connect skills to executable
  workflows.
- Use `light-workflow` for deterministic orchestration, retries, human tasks,
  assertions, audit, and multi-agent coordination.

## Non-Goals

- Do not move the demo APIs or agent services into a different Compose project
  by default.
- Do not create a second Docker network for the demo APIs and agents.
- Do not make one agent container host multiple unrelated agent definitions.
- Do not move MCP tool execution into controller-rs or portal-query.
- Do not require every gateway tool to be wrapped by a skill before baseline
  gateway tool execution works.
- Do not store workflow definitions inside `skill_t`.

## Compose File Split

Use the main compose files for platform services and a separate overlay for demo
APIs plus agents.

Recommended files:

| Repo | Base files | Agent/API overlay |
| --- | --- | --- |
| `portal-config-dev` | `docker-compose.yml` | `docker-compose.agent-api.yml` |
| `portal-config-loc/all-in-pg` | `docker-compose.yml`, `docker-compose-rust.yml` | `docker-compose.agent-api.yml` |
| `portal-config-loc/all-in-lt` | `docker-compose.yml`, `docker-compose-rust.yml` | `docker-compose.agent-api.yml` |

The base stack should own shared infrastructure:

- Postgres,
- config-server,
- controller,
- hybrid-query,
- hybrid-command,
- light-gateway,
- light-workflow,
- OAuth and other platform services.

The overlay should own optional local workloads:

- `demo-customer-profile-api`,
- `demo-offer-decision-api`,
- `light-agent-account`,
- `light-agent-offer`,
- future specialized agents.

The overlay is intended to be started with the base files in the same Compose
command. In that mode Docker Compose creates or reuses one project default
network, and every service can resolve every other service by service name.

Example for `portal-config-dev`:

```sh
docker compose \
  -f docker-compose.yml \
  -f docker-compose.agent-api.yml \
  up -d
```

Example for `portal-config-loc/all-in-pg`:

```sh
docker compose \
  -f docker-compose.yml \
  -f docker-compose-rust.yml \
  -f docker-compose.agent-api.yml \
  up -d
```

If the overlay must be started separately, it must still use the same Compose
project name as the base stack. Otherwise Docker will create a second default
network and the gateway will not resolve the agent and demo API service names.

## Network Contract

The preferred local contract is the Compose default network for the active
project. Do not declare a separate network in the overlay when the overlay is
run with the base stack.

Service-to-service URLs should use Compose service DNS names:

```text
http://light-agent-account:8083
http://light-agent-offer:8083
http://demo-customer-profile-api:8080
http://demo-offer-decision-api:8080
```

Host port mappings are only for browser or curl access from the developer
machine. They should not be used by gateway, agents, workflows, or demo APIs to
call each other.

For agent containers, use a stable service name and advertised address:

```yaml
server.advertisedAddress: ${LIGHT_AGENT_ADVERTISED_ADDRESS:light-agent-account}
server.httpPort: ${LIGHT_AGENT_HTTP_PORT:8083}
```

The internal port can stay `8083` for every agent because each agent is a
different container. Only host-published ports must be unique.

## Agent Service Identity

Each agent instance needs a unique runtime identity. The identity is not just
the Docker service name.

Recommended identity fields:

| Field | Purpose | Example |
| --- | --- | --- |
| Compose service | Docker DNS name and local lifecycle unit. | `light-agent-account` |
| `server.serviceId` | Runtime service id registered with controller and gateway. | `com.networknt.agent.account-1.0.0` |
| `server.environment` | Runtime environment tag. | `dev` |
| `server.advertisedAddress` | Address other services use for this agent. | `light-agent-account` |
| `LIGHT_AGENT_HOST_ID` | Host or tenant boundary for portal catalog and memory. | `01964b05-552a-7c4b-9184-6857e7f3dc5f` |
| `LIGHT_AGENT_AGENT_DEF_ID` | Agent definition id, currently aligned with API version id. | account agent API version id |
| Model provider config | Runtime model settings for the agent instance. | `codex`, `gpt-5.5` |

The same image can run multiple agents. Compose injects different environment
variables and config-server startup values into each service.

Example overlay shape:

```yaml
services:
  light-agent-account:
    image: ${LIGHT_AGENT_IMAGE:-networknt/light-agent:latest}
    ports:
      - ${ACCOUNT_AGENT_PORT:-8083}:8083
    volumes:
      - ./light-agent-rust/config:/config:ro
      - ./light-controller-rust/ca.pem:/keystore/ca.pem:ro
    environment:
      LIGHT_RS_CONFIG_DIR: /config
      DATABASE_URL: postgres://postgres:secret@postgres:5432/configserver
      LIGHT_PORTAL_AUTHORIZATION: "${LIGHT_AGENT_LIGHT_PORTAL_AUTHORIZATION:-}"
      LIGHT_AGENT_HOST_ID: "${LIGHT_AGENT_HOST_ID:-01964b05-552a-7c4b-9184-6857e7f3dc5f}"
      LIGHT_AGENT_AGENT_DEF_ID: "${ACCOUNT_AGENT_DEF_ID:-}"
      LIGHT_AGENT_SERVICE_ID: com.networknt.agent.account-1.0.0
      LIGHT_AGENT_ADVERTISED_ADDRESS: light-agent-account
      LIGHT_AGENT_MODEL: "${ACCOUNT_AGENT_MODEL:-gpt-5.5}"
      CODEX_API_KEY: "${ACCOUNT_AGENT_CODEX_API_KEY:-}"
      CODEX_ACCOUNT_ID: "${ACCOUNT_AGENT_CODEX_ACCOUNT_ID:-}"
      CODEX_REASONING_EFFORT: "${ACCOUNT_AGENT_CODEX_REASONING_EFFORT:-low}"
      RUST_LOG: "${ACCOUNT_AGENT_RUST_LOG:-info}"
      AGENT_LOG_ANSI: "false"

  light-agent-offer:
    image: ${LIGHT_AGENT_IMAGE:-networknt/light-agent:latest}
    ports:
      - ${OFFER_AGENT_PORT:-8084}:8083
    volumes:
      - ./light-agent-rust/config:/config:ro
      - ./light-controller-rust/ca.pem:/keystore/ca.pem:ro
    environment:
      LIGHT_RS_CONFIG_DIR: /config
      DATABASE_URL: postgres://postgres:secret@postgres:5432/configserver
      LIGHT_PORTAL_AUTHORIZATION: "${LIGHT_AGENT_LIGHT_PORTAL_AUTHORIZATION:-}"
      LIGHT_AGENT_HOST_ID: "${LIGHT_AGENT_HOST_ID:-01964b05-552a-7c4b-9184-6857e7f3dc5f}"
      LIGHT_AGENT_AGENT_DEF_ID: "${OFFER_AGENT_DEF_ID:-}"
      LIGHT_AGENT_SERVICE_ID: com.networknt.agent.offer-1.0.0
      LIGHT_AGENT_ADVERTISED_ADDRESS: light-agent-offer
      LIGHT_AGENT_MODEL: "${OFFER_AGENT_MODEL:-gpt-5.5}"
      CODEX_API_KEY: "${OFFER_AGENT_CODEX_API_KEY:-}"
      CODEX_ACCOUNT_ID: "${OFFER_AGENT_CODEX_ACCOUNT_ID:-}"
      CODEX_REASONING_EFFORT: "${OFFER_AGENT_CODEX_REASONING_EFFORT:-low}"
      RUST_LOG: "${OFFER_AGENT_RUST_LOG:-info}"
      AGENT_LOG_ANSI: "false"
```

The example deliberately avoids `container_name`. Compose service names already
provide stable DNS on the project network, and omitting `container_name` avoids
cross-project name collisions.

## Gateway Registry

The gateway should route to agent services through Docker DNS names, not host
addresses. For the local direct registry:

```yaml
direct-registry.directUrls:
  com.networknt.agent.account-1.0.0: http://light-agent-account:8083
  com.networknt.agent.offer-1.0.0: http://light-agent-offer:8083
```

The same rule applies to demo APIs. Gateway route targets should be service
names on the shared Compose network.

When an agent is registered through controller, its runtime identity should
match the config-server tuple used by the container:

```text
host + serviceId + envTag
```

The agent should keep `server.enableRegistry: true` so controller can discover
it and send catalog cache invalidation notifications.

## Effective Agent Catalog

Each agent loads its effective catalog from portal-query with:

```text
hostId + agentDefId + serviceId + envTag
```

The effective catalog includes:

- the agent definition,
- assigned skills from `agent_skill_t`,
- tool projections from `skill_tool_t` and `tool_t`,
- tool parameters from `tool_param_t`,
- workflow mappings from `skill_workflow_t`,
- workflow definitions from `wf_definition_t`,
- policy diagnostics for tools that should not be exposed.

The agent caches the effective catalog locally. Controller cache-management
messages should clear that cache when skills, tools, workflows, or assignments
change. On the next chat turn, the agent refreshes the catalog from
portal-query.

Gateway execution stays separate from catalog reads:

```text
portal-query
  -> effective catalog, skills, tools, workflows, policies

light-gateway
  -> tools/list
  -> tools/call
```

If portal-query is temporarily unavailable, the direct gateway tool list can
remain usable for baseline tool execution. If a tool is in the catalog but is
not returned by gateway `tools/list`, the agent must not execute it.

## Capability Model

Agents should be specialized by catalog assignment rather than by image build.

Recommended specialization:

| Agent | Service id | Skills | Typical tools | Workflows |
| --- | --- | --- | --- | --- |
| Account agent | `com.networknt.agent.account-1.0.0` | Account lookup, profile enrichment | customer profile API tools | profile lookup, profile validation |
| Offer agent | `com.networknt.agent.offer-1.0.0` | Offer eligibility, decision explanation | offer decision API tools | offer decision, approval check |
| Advisor agent | `com.networknt.agent.advisor-1.0.0` | Cross-domain recommendation | account and offer read tools | customer advisory orchestration |
| Coordinator agent | `com.networknt.agent.coordinator-1.0.0` | Routing and task planning | agent invocation tools, workflow tools | multi-agent workflow start |

The capability boundary is the effective catalog:

- `agent_skill_t` assigns skills to the agent,
- `skill_tool_t` controls which tools a skill can expose,
- `skill_workflow_t` controls which workflows a skill can start or reference,
- workflow and gateway policy still enforce runtime access.

This keeps the runtime image generic while making each agent instance
purpose-built.

## Workflow Orchestration

`light-workflow` should orchestrate multi-step API and agent flows. Agents
provide reasoning and tool selection inside their assigned domain, while
workflow provides deterministic control flow.

Recommended orchestration responsibilities:

| Component | Responsibility |
| --- | --- |
| Portal | Author skills, tools, workflow mappings, and agent assignments. |
| portal-query | Serve the effective catalog to each agent. |
| controller | Register agents and invalidate agent catalog caches. |
| light-gateway | Execute MCP tools and route API calls. |
| light-agent | Reason over assigned skills and call allowed gateway tools. |
| light-workflow | Run multi-agent plans, API sequences, assertions, retries, and human tasks. |

Example advisory flow:

1. A user starts an advisory request.
2. The coordinator agent or portal UI starts a workflow in `light-workflow`.
3. The workflow calls the account agent with the `customer-profile` skill.
4. The account agent reads its effective catalog and calls customer profile
   tools through `light-gateway`.
5. The workflow validates the profile response with an `assert` task.
6. The workflow calls the offer agent with the `offer-decision` skill.
7. The offer agent calls offer decision tools through `light-gateway`.
8. The workflow applies policy checks, optional human approval, and final
   response shaping.

The workflow is the durable orchestration record. Agent chat history and memory
can support reasoning, but they should not be the only source of orchestration
state.

## Skill To Workflow Mapping

Use `skill_workflow_t` to link a skill to one or more workflow definitions:

| Column | Use |
| --- | --- |
| `host_id` | Tenant boundary. |
| `skill_id` | Skill that can use the workflow. |
| `wf_def_id` | Workflow definition in `wf_definition_t`. |
| `workflow_role` | `primary`, `validation`, `remediation`, `approval`, or `test`. |
| `start_mode` | `manual`, `agent`, `portal`, or `scheduled`. |
| `config` | Skill-specific workflow input defaults and safety hints. |
| `active` | Publication flag. |

The effective catalog should include these mappings so the agent can decide
whether a user request should be answered directly, routed to a tool, or handed
to a workflow.

For destructive or externally visible operations, the skill should prefer a
workflow mapping over direct tool execution. The workflow can add approval,
assertions, idempotency keys, retries, and audit events.

## API Access Pattern

Agents should not call downstream business APIs directly. They should use the
gateway data plane:

```text
light-agent
  -> light-gateway /mcp tools/list
  -> light-gateway /mcp tools/call
  -> downstream MCP server or REST/OpenAPI-backed tool
```

Workflows should also use gateway-backed calls when invoking API operations:

```yaml
do:
  - get-profile:
      call: mcp
      with:
        session: gateway
        tool: customer_profile_get
        arguments:
          customerId: "${ .customerId }"
```

When workflow needs reasoning, it should call an agent task:

```yaml
do:
  - review-offer:
      call: agent
      with:
        agent: com.networknt.agent.offer-1.0.0
        skill: offer-decision
        input:
          customerId: "${ .customerId }"
          profile: "${ .profile }"
```

The exact agent invocation transport can evolve, but the logical contract is
stable: workflow names the agent and skill, and the called agent uses its
effective catalog to constrain tools and workflow options.

## Local Configuration Layout

Use one shared config template when agents differ only by environment
variables:

```text
light-agent-rust/
  config/
    startup.yml
    client.yml
    values.yml
```

Use per-agent config folders only when the bootstrap or runtime config needs to
diverge beyond service id, advertised address, model, or agent definition:

```text
light-agent-rust/
  account/config/
  offer/config/
  advisor/config/
```

The recommended first phase is the shared template plus per-service Compose
environment overrides. This avoids copying the same config files for every
agent.

Keep secrets outside git:

- portal bearer token,
- provider API keys,
- provider account ids,
- customer CA material,
- database credentials outside local defaults.

## Rollout Plan

### Phase 1: Compose Overlay

- Add `docker-compose.agent-api.yml` beside the current base compose files.
- Move demo APIs and local `light-agent` services into the overlay.
- Rename the first agent service to `light-agent-account`.
- Remove `container_name` from agent services.
- Update gateway direct registry entries to service DNS names.
- Verify the rendered compose model with the base and overlay files together.

### Phase 2: Multiple Agent Instances

- Add one overlay service per specialized agent.
- Assign unique service ids and host ports.
- Add portal agent definitions for each service id and env tag.
- Assign skills through `agent_skill_t`.
- Assign tools through `skill_tool_t`.
- Assign workflows through `skill_workflow_t`.
- Verify each agent can load a distinct effective catalog.

### Phase 3: Workflow Orchestration

- Create workflow definitions for cross-agent API access.
- Add workflow mappings to skills.
- Let coordinator or portal UI start workflows for multi-step tasks.
- Use gateway MCP calls for API operations.
- Use agent tasks only where domain reasoning is required.
- Add policy checks for destructive tools and approval-required workflows.

### Phase 4: Operational Hardening

- Add health checks for every agent and demo API.
- Add startup validation that each agent has a non-empty effective catalog when
  `LIGHT_AGENT_AGENT_DEF_ID` is configured.
- Add gateway drift diagnostics comparing catalog tools with gateway
  `tools/list`.
- Add cache invalidation verification after skill, tool, or workflow changes.
- Add docs for common local run commands and expected service URLs.

## Design Decisions

- **Overlay Scope**: The first overlay will include both the account and offer agents, together with the two demo APIs.
- **Port Publishing**: Every agent will publish its own UI port and register with the control plane independently. Chat clients will discover agents via controller registration, and `light-gateway` will discover them via explicit `direct-registry` entries.
- **Workflow Triggers**: Workflow start requests will go through a dedicated workflow command API for the first implementation.
- **Agent Orchestration**: Agent-to-agent calls will not be exposed as direct gateway tools. Multi-agent flows are orchestrated exclusively via `light-workflow`. Currently, `call: agent` tasks are native, catalog-backed model calls executed directly by the workflow engine (bypassing the containerized `light-agent` tool loops). The containerized agents are primarily used by chat clients. Future implementations may choose to invoke the containerized agent services from workflow.
