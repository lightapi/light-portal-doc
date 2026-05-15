# Agent Skill And API Endpoint Discovery

## Problem

The GenAI chat flow has two separate concepts that are easy to confuse:

- The `light-gateway` MCP endpoint is the runtime server that lists and executes
  tools. An agent should call the gateway for `tools/list` and `tools/call`.
  A listed tool may be backed by a downstream MCP server or by a gateway-routed
  HTTP/OpenAPI endpoint.
- Portal-query is the catalog service for skills, tools, and agent
  assignments. The agent should read this catalog through the `genai-query`
  API, cache it locally, and search it during chat.
- The controller registry remains a runtime control-plane service for
  registration, discovery, and cache-management commands. It should not own the
  portal skill/tool catalog and should not execute downstream MCP or REST calls.

During chat, `light-agent` should use its local catalog cache to find relevant
skills, then call `tools/list` on the gateway to verify executable tools. Tool
execution still goes through the gateway. If the catalog cache is empty or
stale, the agent should refresh it from portal-query. If portal-query is
temporarily unavailable, the agent should still be able to use the gateway tool
list directly.

The missing piece is a portal-managed catalog that explains which API endpoints
exist, which endpoint projections are invokable by agents, which skills they
belong to, and which agents are allowed or expected to use those skills. Without
that catalog, the agent can list executable gateway tools, but it has no domain
guidance beyond each tool description.

## Goals

- Keep the gateway as the runtime source of truth for MCP tool execution.
- Keep direct gateway `tools/list` and `tools/call` working even when no skills
  have been authored.
- Treat API endpoints as the generic capability unit. MCP tools, OpenAPI
  operations, JSON-RPC methods, and future protocol operations should all become
  endpoint-level capabilities before they are exposed to agents.
- Populate a portal endpoint and tool catalog from API version parsing,
  LightAPI descriptions, gateway-discovered MCP tools, manually pasted MCP
  `tools/list` payloads, and gateway-routed REST tools.
- Let portal users create skills that contain instructions and curated tool
  selections.
- Let portal users assign skills to agent definitions.
- Use the `genai-query` API and spec as the portal-query access surface for
  skills, tools, and agent assignments.
- Let the agent cache the effective catalog locally and reload it when
  controller cache-management invalidation is triggered.
- Make skills useful for progressive disclosure without requiring every MCP tool
  to be wrapped before it can be called.
- Store semantic routing metadata for endpoint capabilities so the agent or
  portal-query can perform macro-filtering, keyword search, vector ranking,
  context viability checks, and safety filtering.

## Non-Goals

- Do not move MCP request routing or downstream REST calls into the controller.
- Do not implement `skill/search` in controller-rs. Controller-rs can
  invalidate the agent cache, but portal-query owns catalog reads.
- Do not use config-server as the first delivery path for the skills/tools
  catalog. The agent can fetch from portal-query and cache locally.
- Do not require every gateway tool to have a skill before it is executable.
- Do not replace the existing MCP Gateway registry design. This design extends
  it with agent-facing skill curation.
- Do not implement embeddings in the first phase. Keyword search is enough for
  the initial local catalog search.
- Do not limit the catalog to MCP tools. The UI may use "tool" when referring
  to LLM tool-calling, but the persistent capability model should be endpoint
  first.
- Do not use skill assignments as the only authorization control. Gateway
  policy and downstream authorization still apply at execution time.

## Concepts

| Concept | Responsibility | Example |
| --- | --- | --- |
| API Endpoint | Canonical endpoint-level capability stored by API version. It may come from OpenAPI, MCP `tools/list`, LightAPI, JSON-RPC, or another protocol. | `/v1/accounts@get`, `getRandomNumber@call` |
| Tool | Agent-facing projection of an endpoint as an executable LLM function. The runtime call is made by name through the gateway. | `getAccounts` calling `GET /v1/accounts` |
| Skill | Domain guidance plus a curated set of tools. It helps an agent decide what to expose and how to reason. | "Account Management" using account read and create tools |
| Agent | Runtime worker that receives a user prompt, discovers skills and tools, calls the LLM, then executes requested tools through the gateway. | `account-agent` |
| Gateway | MCP server and router. It owns runtime `tools/list` and `tools/call` behavior. | `light-gateway` `/mcp` |
| Portal Query | Catalog API service for reading skills, tools, tool params, skill-tool mappings, and agent-skill assignments. | `genai-query` API |
| Controller Registry | Runtime control-plane service for service metadata, discovery, and cache invalidation. | cache-management MCP tool |
| Portal | Authoring UI and persistence layer for tools, skills, and agent assignments. | Tool Catalog, Skill Editor, Agent Skill Assignment |

## Target Architecture

The target flow keeps runtime execution and control-plane metadata separate.

```text
Portal UI
  -> writes api_endpoint_t, tool_t, tool_param_t, skill_t, skill_tool_t, agent_skill_t

light-gateway /mcp
  -> lists executable tools from mcp-router.tools and downstream MCP servers
  -> executes tools/call against downstream MCP or REST services

portal-query genai-query API
  -> serves skill/tool/agent-skill catalog reads from portal data

controller-rs portal registry
  -> registers agents and sends cache-management invalidation commands

light-agent
  -> loads assigned skills and mapped tools from portal-query
  -> caches the effective catalog locally
  -> searches cached skills during chat
  -> lists executable tools from light-gateway
  -> calls selected tools through light-gateway
```

For the account-agent example:

1. The gateway exposes account tools such as `getAccounts` and
   `getAccountByNo`.
2. Portal stores the canonical endpoint rows in `api_endpoint_t`.
3. Portal publishes selected endpoint rows into `tool_t` as agent-invokable
   capabilities.
4. An operator creates an "Account Management" skill in `skill_t`.
5. Portal links that skill to the account tools through `skill_tool_t`.
6. Portal assigns the skill to the account agent through `agent_skill_t`.
7. At startup or cache reload, the agent reads the assigned catalog through
   `genai-query` and caches it locally.
8. At chat time, the agent searches its local catalog cache.
9. The agent combines matched skill instructions with the gateway tool
   definitions.
10. Any tool call still goes to `light-gateway` `tools/call`.

## Source Of Truth

The gateway is the runtime source of truth for executable tools. If a tool is
not available from the gateway, the agent should not be able to execute it just
because it exists in the portal database.

`api_endpoint_t` is the canonical portal endpoint catalog. It stores the
endpoint identity, protocol method, path, logical tool schema, endpoint
description, and raw tool metadata for one API version.

`tool_t` is the agent-facing projection of an endpoint. It stores the tool name,
agent description, implementation type, optional endpoint reference, response
schema, active flag, semantic routing fields, and semantic embedding. The full
metadata object should still be preserved in `api_endpoint_t.tool_metadata` for
import/export and agent cache payloads.

The portal database is the control-plane catalog. It stores:

- operator-friendly descriptions,
- skill instructions,
- agent assignments,
- governance metadata,
- cached or imported tool schemas.

Tool sync should be idempotent. The recommended unique identity is:

```text
host_id + api_version_id + endpoint
```

Gateway exposure is a separate deployment selection. The catalog should sync all
endpoint rows for an API version, then let the user choose which endpoint/tool
projections are deployed to a specific gateway instance.

For runtime-executable projections, the gateway identity is:

```text
hostId + serviceId + envTag
```

The access token used for portal catalog or gateway deployment APIs should carry
matching `host`, `sid`, and `env` claims. Portal-query must verify those claims
against the requested `hostId`, `serviceId`, and `envTag` before returning or
changing catalog data.

Runtime verification means checking whether an endpoint projection is actually
listed by a deployed gateway through `tools/list`. This should be done against
the selected gateway instance when an operator is preparing or reviewing a
gateway deployment. A later host-wide diagnostics view can aggregate all
registered gateways, but phase 2 does not need host-wide verification as the
default.

Runtime verification is not part of the persistence projection. The persistence
layer should store catalog state, endpoint/tool metadata, and inactive drift
state, but it should not call a live gateway. The portal UI, deployment review
flow, or a diagnostics endpoint should call the selected gateway's `tools/list`
with the operator or service credential, compare the returned tool names and
schemas with the catalog, and surface the result as deployment drift.

If a previously imported endpoint or tool disappears from the gateway, the sync
process should mark the catalog projection inactive instead of deleting it
immediately. This preserves skill mappings and gives operators a clear drift
signal.

## Current Data Model

The database already has the main tables needed for this design:

- `skill_t`: skill name, description, `content_markdown`, embedding placeholder,
  version, and active flag.
- `tool_t`: agent-facing tool catalog with name, description, implementation
  metadata, endpoint reference, and response schema.
- `tool_param_t`: parameter-level metadata and validation schema.
- `agent_skill_t`: maps agent definitions to skills.
- `skill_tool_t`: maps skills to tools for progressive disclosure.
- `api_endpoint_t`: MCP or REST endpoint metadata, including `tool_schema` and
  `tool_metadata`.

The current phase 2 persistence path can preserve semantic metadata in
`api_endpoint_t.tool_metadata` before dedicated routing columns exist. That is
acceptable for import/export compatibility and for small catalogs searched from
the agent's local cache. It should not be treated as the final indexed search
shape. Before portal-query performs database-side macro-filtering over large
catalogs or before vector ranking becomes a production dependency, promote the
high-use routing fields to first-class columns or indexed relationships and
backfill them from `tool_metadata`.

The existing MCP Registry design already maps MCP tools into `api_endpoint_t`.
OpenAPI parsing also creates endpoint rows. This design uses `tool_t` as the
agent-facing catalog row and links it back to `api_endpoint_t` when the tool
originates from an API endpoint.

Recommended mapping for gateway-imported tools:

| Gateway tool field | Portal storage |
| --- | --- |
| `name` | `tool_t.name` and `api_endpoint_t.endpoint_name` |
| `description` | `tool_t.description` and `api_endpoint_t.endpoint_desc` |
| `inputSchema` | `api_endpoint_t.tool_schema` and generated `tool_param_t` rows |
| Gateway route metadata | gateway exposure metadata keyed by `hostId`, `serviceId`, and `envTag` |
| Downstream REST path | `tool_t.api_endpoint` and `api_endpoint_t.endpoint_path` |
| Downstream method | `tool_t.api_method` and `api_endpoint_t.http_method` |
| Safety flags | indexed tool metadata plus `api_endpoint_t.tool_metadata.safety` |

`tool_t.implementation_type` should be a standardized enum aligned with the
LightAPI Description execution model. Endpoint-backed tools should use a
LightAPI endpoint implementation type rather than preserving every downstream
transport as a different tool implementation. The downstream protocol remains
in the endpoint and LightAPI request metadata.

Recommended first enum values:

| Implementation type | Use |
| --- | --- |
| `lightapi_endpoint` | Any agent-invokable API endpoint described by `api_endpoint_t` and LightAPI metadata. |
| `java` | In-process Java implementation. |
| `python` | Script-backed Python implementation. |
| `javascript` | Script-backed JavaScript implementation. |

For `lightapi_endpoint`, execution still goes through gateway `tools/call` when
the endpoint is exposed to a gateway. The source protocol, such as MCP,
OpenAPI, JSON-RPC, OpenRPC, or gRPC, belongs in `api_endpoint_t`,
`tool_metadata`, and the LightAPI request description.

## Endpoint-First Capability Model

Agents and skills should operate over endpoint capabilities, not only over MCP
tools. MCP remains the runtime protocol for tool-calling through the gateway,
but the catalog should support any endpoint that can be represented as an
agent-invokable capability.

Recommended capability layers:

1. `api_endpoint_t`: canonical endpoint row for the API version.
2. `tool_t`: agent-facing executable projection of the endpoint.
3. `tool_param_t`: normalized top-level input parameters derived from the
   endpoint's JSON Schema.
4. `skill_tool_t`: curated relationship between a skill and a tool projection,
   including per-skill overrides such as priority, examples, or approval notes.
5. `agent_skill_t`: assignment of skills to agent definitions.

This model supports these source types:

| Source | Endpoint identity | Tool projection |
| --- | --- | --- |
| MCP `tools/list` | `<toolName>@call` | Tool name is the MCP tool name; method is `call`. |
| OpenAPI | `<path>@<method>` | Tool name comes from operation id or generated endpoint name. |
| LightAPI Description | `operation.endpointId` or `<operationId>@<method>` | Tool name comes from operation id or curated agent metadata. |
| JSON-RPC/OpenRPC | `<method>@call` | Tool name is the method or curated operation name. |
| gRPC | `<service>/<method>@call` | Tool name is the curated operation name. |

`tool_param_t` should be generated from the logical input schema, not from wire
transport details alone. For OpenAPI, the logical input schema should merge
path parameters, query parameters, and request body into one object. For MCP,
the logical input schema is the MCP `inputSchema`. For JSON-RPC, it is the
logical params schema.

## Semantic Routing Metadata

The customer-required semantic routing fields should be first-class indexed
catalog data, not only JSON metadata. They are used for macro-filtering before
expensive keyword, vector, or LLM ranking, so the common filter fields must be
queryable through normal portal-query indexes.

Recommended indexed fields or relationships:

- domain and semantic namespace,
- sensitivity tier,
- semantic weight,
- target personas,
- active state,
- source protocol and implementation type,
- portal category and tag relationships.

Recommended phase 2 column names for endpoint and tool projections:

| Field | Suggested column or relationship | Source fallback |
| --- | --- | --- |
| Domain | `routing_domain` | `tool_metadata.routing.domain`, LightAPI capability group, OpenAPI tag. |
| Semantic namespace | `semantic_namespace` | `tool_metadata.routing.semanticNamespace`, LightAPI `info.namespace`. |
| Sensitivity tier | `sensitivity_tier` | `tool_metadata.routing.sensitivityTier`, LightAPI visibility or safety metadata. |
| Semantic weight | `semantic_weight` | `tool_metadata.routing.semanticWeight`, default `1.0`. |
| Source protocol | `source_protocol` | LightAPI operation protocol, OpenAPI, MCP, JSON-RPC, gRPC. |
| Target personas | join table or indexed array | `tool_metadata.routing.targetPersonas`, LightAPI agent metadata. |

The full structured payload should still be preserved in
`api_endpoint_t.tool_metadata` so LightAPI import/export, gateway config
generation, and agent cache payloads have one portable metadata object.

Recommended `api_endpoint_t.tool_metadata` shape:

```json
{
  "routing": {
    "domain": "finance.accounts",
    "category": "account-management",
    "semanticNamespace": "prod.accounts.core",
    "targetPersonas": ["account-agent", "customer-support-agent"],
    "semanticDescription": "Retrieves account profile and status information when a user asks about an existing account.",
    "semanticKeywords": ["account lookup", "customer account", "balance", "status"],
    "contextRequirements": {
      "requiredInputs": ["accountNo"],
      "requiredContext": ["host_id"]
    },
    "dependencies": [
      {
        "endpoint": "/v1/accounts/{accountNo}@get",
        "relation": "frequently_chained_after"
      }
    ],
    "semanticWeight": 0.75,
    "sensitivityTier": "Internal-Only",
    "fallbackEndpoint": "/v1/accounts@get",
    "embedding": {
      "model": "tool-description-embedding",
      "source": "semanticDescription"
    }
  },
  "safety": {
    "read_only": true,
    "destructive": false,
    "humanApprovalRequired": false
  }
}
```

Recommended ownership:

| Metadata | Primary storage | Notes |
| --- | --- | --- |
| Domain and namespace | Indexed endpoint/tool columns plus `tool_metadata.routing` | Used for macro-filtering before vector ranking. |
| Categories and tags | Existing portal tag/category tables plus `tool_metadata.routing` | Reuse the portal taxonomy instead of creating a separate endpoint taxonomy. |
| Target personas | Indexed mapping or array plus `tool_metadata.routing.targetPersonas` | Used to filter the effective catalog for the current agent. |
| Rich capability description | `tool_t.description` plus `tool_metadata.routing.semanticDescription` | `tool_t.description` should be the concise LLM-facing description. |
| Synonyms and keywords | `tool_metadata.routing.semanticKeywords` | Used by keyword search and embedding source text. |
| Embedding vector | `tool_t.description_embedding` | The embedding provider must produce the configured vector dimension, currently 384, or the column must be migrated. |
| Required state/context locks | `tool_metadata.routing.contextRequirements` | The router should exclude non-viable tools before LLM tool injection. |
| Dependency mappings | `tool_metadata.routing.dependencies` | Used for chain suggestions, prefetch, or warm-up. |
| Priority score | Indexed column plus `tool_metadata.routing.semanticWeight` | Numeric multiplier for ranking ties. |
| Sensitivity tier | Indexed column plus `tool_metadata.routing.sensitivityTier` | Used before disclosure and before execution. |
| Fallback target | `tool_metadata.routing.fallbackEndpoint` | Runtime fallback should still respect gateway policy. |
| Destructive/read-only flags | `tool_metadata.safety` and existing gateway `toolMetadata` | Runtime enforcement belongs in gateway or policy, not only in prompts. |

The first semantic search implementation can work from the agent's local cache:

1. Filter by host, active flag, assigned skill, domain, namespace, target
   persona, and sensitivity tier.
2. Exclude endpoints whose required context is not available in the current
   workflow or chat state.
3. Rank by keyword matches over skill text, endpoint name, tool name,
   description, semantic keywords, and LightAPI capability text.
4. When embeddings are populated, combine vector similarity with the keyword
   score and multiply by `semanticWeight`.
5. Call gateway `tools/list` and intersect the ranked set with currently
   executable tools before exposing schemas to the LLM.

## Embedding Recommendation

Keep the first production embedding dimension at 384 because the current
Postgres vector column is already `VECTOR(384)` and the first catalog use case
is routing over short endpoint descriptions, not long document retrieval.

Recommended model strategy:

- Use a provider abstraction with configured `embedding_model`,
  `embedding_dimension`, and `embedding_source`.
- For OpenAI-hosted embeddings, use `text-embedding-3-small` with the
  dimensions parameter set to 384.
- For on-prem or firewall-restricted deployments, use a local embedding service
  that is configured to emit 384-dimensional vectors.
- Store enough metadata to know how a vector was created: model, dimension,
  source text hash, source field, and generated timestamp.
- Re-embed when the semantic description, keywords, domain, or model config
  changes.

The portal catalog write path should remain in the portal service layer that
owns `api_endpoint_t` and `tool_t` persistence. Because the current portal
command/query services are Java, the Java side should own transactions,
versioning, and persistence of embedding results. A Rust service or worker can
still generate embeddings behind an internal API or queue consumer, especially
if local model performance is better there. In that model, Java requests or
consumes the vector and writes it through the normal portal persistence path.

## LightAPI Description Enrichment

LightAPI Description should be the preferred enrichment source for endpoint
capabilities. OpenAPI and MCP `tools/list` are good at initial extraction, but
LightAPI adds the agent-oriented context needed for high-accuracy routing:

- endpoint identity and stable `endpointId`
- domain, tags, lifecycle, visibility, and capability group
- logical input schema and request mapping
- result schema and result cases
- examples and behavior notes
- progressive disclosure metadata
- agent-facing descriptions, personas, keywords, context requirements, and
  guardrails

Recommended merge priority for endpoint metadata:

1. Portal operator overrides.
2. Endpoint-level LightAPI Description.
3. API-level inherited LightAPI Description context.
4. OpenAPI/OpenRPC/protobuf/MCP source extraction.
5. Gateway runtime `tools/list` discovery.

This keeps runtime discovery useful while letting curated LightAPI descriptions
provide richer semantic routing without hand-authoring every endpoint as an
independent skill.

Phase 2 persistence should be treated as the receiver for this metadata, not as
the extractor. The openapi-parser, a LightAPI Description parser, or a dedicated
ingestion worker must emit the enriched endpoint payload on the API version
event. At minimum, the event payload for each endpoint should include:

- `endpointId`, endpoint identity, protocol, method, path, name, and
  description,
- logical `toolSchema` generated from the LightAPI operation input contract,
- `toolMetadata.routing` with namespace, domain, capability group, personas,
  keywords, context requirements, sensitivity tier, and semantic weight where
  present,
- `toolMetadata.safety` from LightAPI safety, visibility, idempotency, and
  destructive-operation hints,
- response schema or result metadata when it is available for the tool
  projection.

If the parser only emits the base OpenAPI or MCP fields, the catalog remains
valid but only has low-enrichment metadata. The phase 2 implementation should
record that as an ingestion gap, not as a persistence defect.

## Portal Catalog Contract

The agent should read skills and tools through the `genai-query` API in
portal-query. The source spec is:

```text
genai-query/src/main/resources/spec.yaml
```

The current spec already includes catalog endpoints for the main entities:

- `getAgentSkill` and `getFreshAgentSkill`
- `getSkill` and `getFreshSkill`
- `getSkillTool` and `getFreshSkillTool`
- `getSkillDependency` and `getFreshSkillDependency`
- `getTool` and `getFreshTool`
- `getToolParam` and `getFreshToolParam`

Phase 2 should add a dedicated effective catalog endpoint instead of forcing the
agent to compose many generic query endpoints. The endpoint should still live in
`genai-query`, not controller-rs.

Recommended endpoint behavior:

- verify the caller's token claims before reading catalog rows,
- require request `host_id`, `service_id`, and `env_tag`,
- match token `host`, `sid`, and `env` claims to those request values,
- return only endpoint/tool projections valid for that host, service, and
  environment,
- include active endpoint metadata, tool schemas, safety metadata, routing
  metadata, and skill mappings relevant to the agent,
- support a freshness or version field so the agent can cache the result.

The agent should cache the returned structure locally:

```json
{
  "host_id": "00000000-0000-0000-0000-000000000000",
  "agent_def_id": "00000000-0000-0000-0000-000000000000",
  "catalog_version": 42,
  "skills": [
    {
      "skill_id": "00000000-0000-0000-0000-000000000000",
      "name": "Account Management",
      "description": "Use account tools to inspect and manage customer accounts.",
      "content_markdown": "Prefer read-only tools before create or update tools.",
      "tools": [
        {
          "tool_id": "00000000-0000-0000-0000-000000000000",
          "endpoint_id": "00000000-0000-0000-0000-000000000000",
          "name": "getAccounts",
          "endpoint": "/v1/accounts@get",
          "api_type": "openapi",
          "description": "List account summaries.",
          "input_schema": {
            "type": "object",
            "properties": {}
          },
          "routing_metadata": {
            "domain": "finance.accounts",
            "semanticNamespace": "prod.accounts",
            "semanticKeywords": ["account list", "customer accounts"],
            "sensitivityTier": "Internal-Only"
          },
          "safety": {
            "read_only": true,
            "destructive": false
          }
        }
      ]
    }
  ]
}
```

For phase 2, the agent definition identity is the agent API version identity.
`agent_definition_t.agent_def_id` stores the same UUID as
`api_version_t.api_version_id`; the table is an agent-specific profile extension
for model and runtime settings, not a second standalone agent registry. The
agent display name comes from `api_t.api_name`, so `agent_definition_t` does not
duplicate the API name. API Admin continues to own the API/API-version
lifecycle, Instance Admin continues to own deployed instances, and the Agent
Definition page edits the profile for that API version.

The previous registry `skill/search` response shape was:

```json
{
  "skills": [
    {
      "skill_id": "00000000-0000-0000-0000-000000000000",
      "name": "Account Management",
      "description": "Use account tools to inspect and manage customer accounts.",
      "tool_name": "getAccounts",
      "input_schema": {
        "type": "object",
        "properties": {}
      }
    }
  ]
}
```

That flattened shape can remain as an internal compatibility DTO while the
agent is migrated, but it should not be the long-term external contract. The
target cache shape should support a skill with multiple tools:

```json
{
  "skills": [
    {
      "skill_id": "00000000-0000-0000-0000-000000000000",
      "name": "Account Management",
      "description": "Use account tools to inspect and manage customer accounts.",
      "content_markdown": "Prefer read-only tools before create or update tools.",
      "tools": [
        {
          "name": "getAccounts",
          "description": "List account summaries.",
          "input_schema": {
            "type": "object",
            "properties": {}
          }
        }
      ]
    }
  ]
}
```

Migration rule:

- Remove the controller-rs `skill/search` placeholder.
- The agent can temporarily accept both the flattened shape and the nested
  `tools` shape while its portal-query client is being migrated.
- After migration, the nested effective catalog shape becomes the preferred
  internal cache contract.

Agent identity can come from token claims, configured agent definition, or
request fields. If inference is not enough, pass explicit fields to the
portal-query catalog call:

```json
{
  "agent_def_id": "00000000-0000-0000-0000-000000000000",
  "host_id": "00000000-0000-0000-0000-000000000000",
  "service_id": "com.networknt.account-agent-1.0.0",
  "env_tag": "dev"
}
```

## Runtime Behavior

The agent should treat the portal catalog as helpful guidance, not as a hard
dependency for basic tool use.

Recommended behavior:

1. At startup, call the `genai-query` API to load the effective agent catalog.
2. Cache the catalog locally under `host_id`, agent identity, and catalog
   version.
3. During chat, search the local catalog with the user prompt.
4. If matched skills are returned, add skill instructions to the prompt context.
5. If matched skills include tool mappings, prefer those tools for the LLM tool
   list.
6. Call gateway `tools/list` to verify executable tools and obtain the current
   runtime schemas.
7. Intersect skill-selected tool names with gateway-listed tools.
8. If no skills match, or the local catalog is unavailable, fall back to gateway
   `tools/list`.
9. Execute all LLM tool calls through gateway `tools/call`.

When portal data changes, controller cache management can invalidate the
agent's local catalog cache. Reload behavior should match the agent's initial
loading strategy:

- if the agent loads the catalog during startup, invalidation should trigger an
  eager reload so the next chat request sees current metadata;
- if the agent loads the catalog on the first request, invalidation can clear
  the cache and let the next request reload lazily.

This keeps the account-agent usable before the portal skill catalog is fully
populated and avoids making controller-rs part of the catalog query or execution
path.

## Portal UI

### Endpoint Catalog And Tool Projection

The catalog UI should be endpoint-first but still show the tool projection that
agents will see. It should let operators:

- browse `api_endpoint_t` rows by API, API version, endpoint, method, source,
  and active state,
- import or resync endpoint capabilities from OpenAPI, MCP `tools/list`,
  manually pasted MCP tools payloads, LightAPI descriptions, and selected
  gateway runtime surfaces,
- publish selected endpoint rows into `tool_t` as agent-invokable tools,
- generate or refresh `tool_param_t` rows from the logical input schema,
- see tool name, description, input schema, downstream endpoint, API type,
  semantic namespace, domain, personas, sensitivity tier, and runtime
  executable state,
- compare catalog metadata against source specs and current gateway
  `tools/list`,
- mark missing endpoint projections inactive,
- override operator-facing descriptions without changing gateway config,
- review and edit semantic routing metadata such as keywords, context
  requirements, fallback endpoint, priority weight, read-only, destructive,
  sensitive, or human-approval-required.

The first implementation should not depend only on live gateway access. It can
import from the endpoint rows produced by API version parsing, including manual
MCP `tools/list` JSON pasted into the API version spec field. Gateway
`tools/list` should then be used to verify which imported projections are
currently executable by a deployed gateway.

### Skill Editor

The Skill Editor should let operators:

- create and update `skill_t` rows,
- write `content_markdown` instructions,
- link tools through `skill_tool_t`,
- set tool access level and per-skill config,
- preview which tools the skill would expose for a sample prompt,
- activate or deactivate skills.

Skill content should be short and operational. It should describe when to use
the skill, how to interpret the tools, and any sequencing rules. It should not
contain secrets.

### Agent Skill Assignment

The Agent Skill Assignment UI should let operators:

- select an agent definition,
- assign one or more active skills through `agent_skill_t`,
- set priority and sequence,
- preview the final skill list for that agent,
- verify that each assigned skill still has at least one executable gateway
  tool.

## Portal-query And Agent Cache Implementation

Catalog lookup should be implemented through the `genai-query` API. The agent
should fetch the assigned active catalog, cache it locally, and run progressive
disclosure search against the cache.

Initial algorithm:

1. Resolve `host_id` and agent identity from token claims, configured agent
   definition, service registration metadata, or request fields.
2. Use `genai-query` endpoints to load active `agent_skill_t` rows for the
   agent.
3. Load the linked active `skill_t`, `skill_tool_t`, `tool_t`,
   `tool_param_t`, and related `api_endpoint_t` data.
4. Build a nested effective catalog grouped by skill, with each skill carrying
   its mapped tools, schemas, endpoint identity, safety flags, and routing
   metadata.
5. Cache the effective catalog locally with a catalog version or max aggregate
   version.
6. During chat, macro-filter cached entries by agent persona, domain,
   namespace, sensitivity tier, active state, and available workflow context.
7. Rank cached entries by simple text matching over
   `skill_t.name`, `skill_t.description`, `skill_t.content_markdown`,
   `tool_t.name`, `tool_t.description`, endpoint name, endpoint description,
   and semantic keywords.
8. Intersect the final candidate list with gateway `tools/list` before
   exposing tool schemas to the LLM.

Controller cache management should invalidate this local cache when portal
catalog data changes. After invalidation, the agent reloads from portal-query.

Later algorithm:

- Add vector search over `skill_t.description_embedding` and
  `tool_t.description_embedding`.
- Add vector search over endpoint semantic descriptions and LightAPI
  capability text.
- Include skill dependency expansion from `skill_dependency_t`.
- Use dependency mappings and fallback endpoints for chain planning, prefetch,
  and failure repair.
- Include inactive or missing-tool diagnostics for portal admin views, not for
  normal agent search.

## Gateway Implementation

The gateway should keep the MCP data-plane contract stable:

- `tools/list` returns the executable tool set for the caller.
- `tools/call` routes by tool name to downstream MCP servers or REST services.
- Gateway policy remains authoritative at execution time.
- Gateway does not depend on `skill_t` or `agent_skill_t` to execute tools.

The gateway can expose an administrative sync endpoint later, but the first
portal sync can call the existing MCP `tools/list` endpoint with an operator or
service credential.

`mcp-router.tools` in `values.yml` should stay a runtime execution projection,
not the full semantic registry. It should include the fields the gateway needs
to list and call tools, plus safety metadata that must be enforced at runtime.
Richer semantic routing metadata should stay in portal-query and the agent
cache unless the gateway needs it for a concrete runtime policy decision.

## Security Rules

- Skill assignment narrows what the agent should offer to the LLM, but it does
  not grant runtime authorization by itself.
- Gateway access control, endpoint scopes, OAuth token claims, and downstream
  service authorization still decide whether a tool call is allowed.
- Tool schemas and descriptions are not trusted input. They should be validated
  before storing and escaped when rendered.
- Skill content must not contain secrets, tokens, private keys, or passwords.
- A stale catalog row must not make a removed gateway tool executable.
- A stale local agent cache must be intersected with gateway `tools/list`
  before exposing tools to the LLM.
- Controller cache invalidation only forces reload; it does not grant access to
  catalog rows or executable tools.
- Sensitive or destructive tool metadata should be enforced by the gateway or a
  policy layer, not only by prompt instructions.
- Sensitivity tier must be checked before catalog disclosure. An agent without
  clearance for `Restricted-PII` should not receive the endpoint description or
  schema even if a skill references it.
- Context requirements are not only prompt hints. If required context is
  missing, the endpoint should be excluded or routed to an ask/workflow step
  that obtains the missing value.

## Failure Handling

| Failure | Expected behavior |
| --- | --- |
| Portal-query catalog load fails at startup | Start with an empty catalog cache and fall back to gateway `tools/list`. |
| Portal-query catalog reload fails after invalidation | Keep the previous cache if available, mark it stale, retry with backoff, and still verify tools through gateway `tools/list`. |
| Gateway `tools/list` fails | Continue chat without tools or return a clear tool-unavailable response. |
| Skill references missing tool | Omit the missing tool from the runtime tool list and surface drift in portal admin UI. |
| Gateway rejects `tools/call` | Return the tool error to the LLM loop and log the gateway response. |
| Catalog sync sees changed schema | Update catalog schema, mark the tool as changed, and preserve operator metadata. |
| LightAPI enrichment conflicts with source spec | Preserve the source invocation contract, mark the semantic metadata conflict for review, and do not overwrite operator overrides. |

## Phased Implementation

### Phase 1: Preserve Direct MCP Baseline

- Keep agent tool execution through gateway `tools/call`.
- Remove the controller-rs `skill/search` placeholder before it becomes a
  dependency.
- Ensure agent falls back to gateway `tools/list` when no catalog cache is
  available.
- Keep direct gateway `tools/list` and `tools/call` working without portal
  skills.

### Phase 2: API Endpoint Catalog Sync

- Add portal UI for endpoint-first import and resync.
- Use existing API version parsing to populate `api_endpoint_t` for OpenAPI and
  MCP tools, including manual MCP `tools/list` payloads accepted in the API
  version spec field.
- Sync all endpoint rows for the API version into the endpoint catalog. Do not
  limit the catalog to the endpoints currently selected for one gateway
  instance.
- Import or refresh LightAPI Description metadata for endpoint enrichment.
- Publish selected endpoint rows into `tool_t` as agent-facing tool
  projections.
- Generate `tool_param_t` from each endpoint's logical input schema.
- Link every API-origin tool projection back to `api_endpoint_t.endpoint_id`.
- Store semantic routing metadata in indexed endpoint/tool fields and preserve
  the full metadata payload in `api_endpoint_t.tool_metadata`.
- If the first code slice only writes `tool_metadata`, keep that as a
  compatibility step and add the indexed routing-column migration before
  database-side macro-filtering or production vector ranking is enabled.
- Let users select which endpoint projections should be exposed to a specific
  gateway instance. This deployment selection is separate from endpoint catalog
  sync.
- Verify runtime executability outside persistence with gateway `tools/list`
  for the selected gateway instance when a gateway is reachable.
- Mark disappeared or non-executable projections inactive instead of deleting
  them.
- Add drift indicators for schema, description, safety metadata, and semantic
  routing metadata changes.

### Phase 3: Skill Authoring

- Add portal UI for `skill_t`.
- Add tool linking through `skill_tool_t`.
- Add preview of selected tools and effective prompt instructions.
- Keep embeddings optional.

### Phase 4: Agent Assignment

- Add portal UI for `agent_skill_t`.
- Let operators assign active skills to agent definitions.
- Add validation that assigned skills have active tools.

### Phase 5: Real Skill Search

- Add the dedicated `genai-query` effective catalog endpoint with token
  verification against `host`, `sid`, and `env` claims.
- Implement the agent portal-query client using that endpoint.
- Build and cache the nested effective catalog for the agent.
- Start with local macro-filtering and keyword matching over cached skills,
  endpoint metadata, and tool projections.
- Wire controller cache-management invalidation to clear or reload the agent
  catalog cache.
- Add vector ranking after 384-dimensional embeddings are populated and combine
  it with `semanticWeight`.

### Phase 6: Semantic Routing And Governance

- Add approval, ownership, audit, and versioning around tool imports and skill
  changes.
- Add safety-policy enforcement for destructive or sensitive tools.
- Add sensitivity-tier disclosure checks, context-lock validation, fallback
  routing, and dependency-aware prefetch or warm-up where the runtime supports
  it.
- Add reports for agents with no skills, skills with no tools, and catalog
  tools not executable by the gateway.

## Resolved Phase 2 Decisions

- Phase 2 endpoint catalog sync covers all endpoint rows for an API version.
  Gateway exposure is a separate step where users select which endpoint/tool
  projections to deploy to a specific gateway instance.
- Runtime verification means checking the selected gateway instance's
  `tools/list` response to confirm that a deployed endpoint projection is
  executable there. It is not the same as endpoint catalog sync and should be
  implemented in the portal UI, deployment review flow, or diagnostics layer,
  not inside the persistence projection.
- Gateway exposure identity is `hostId + serviceId + envTag`. The token used
  for portal APIs must carry matching `host`, `sid`, and `env` claims.
- `tool_t.implementation_type` should be standardized and aligned with the
  LightAPI Description execution model. Endpoint-backed tools should use the
  standardized endpoint implementation type, with downstream protocol stored in
  endpoint and LightAPI metadata.
- High-use semantic routing fields should be indexed columns or indexed
  relationships, with the full structured payload preserved in
  `api_endpoint_t.tool_metadata`. JSON-only persistence is only an interim
  import/export-compatible shape for small catalogs or local-cache search.
- LightAPI Description enrichment requires an upstream parser or ingestion
  worker to emit enriched endpoint payloads. The persistence layer can store
  `tool_schema`, `tool_metadata.routing`, and `tool_metadata.safety`, but it
  does not derive those fields from the raw LightAPI document by itself.
- Endpoint category and tag classification should reuse the existing portal tag
  and category system.
- Embeddings should start at 384 dimensions to match the current `VECTOR(384)`
  schema. Use a provider abstraction so hosted OpenAI embeddings or local
  embedding services can be swapped without changing the catalog schema.
- `genai-query` should expose a dedicated effective catalog endpoint. Its token
  verification must match request `host_id`, `service_id`, and `env_tag`
  against token `host`, `sid`, and `env` claims.
- Cache reload behavior depends on the loading strategy. Startup-loaded
  catalogs should eagerly reload after invalidation. First-request-loaded
  catalogs can reload lazily on the next request.
- Phase 2 focuses on tool and endpoint metadata. Skill-specific metadata and
  per-skill tool config should be designed later with the skill authoring
  phase.

## Recommendation

Implement this as a progressive control-plane enhancement. The gateway remains
the execution path, and portal-authored skills become the agent guidance layer
served by portal-query. The agent should cache the effective catalog locally and
reload it after controller cache-management invalidation. This lets MCP tools
work immediately through `tools/list` and `tools/call`, while still giving
portal operators a clean path to organize tools into skills, assign those
skills to agents, and improve retrieval over time.
