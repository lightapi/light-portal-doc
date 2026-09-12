# Build an external agent with a light-a2a sidecar

The Rust support-triage example shows how to integrate your own agent into Light
Fabric. You implement business behavior. `light-a2a` supplies the A2A protocol
boundary and the platform's published authorization and task-handling machinery.
The first example is deterministic: it needs no LLM subscription or model key.

## Understand the components

```text
A2A client -> light-gateway -> light-a2a -> support-triage backend
                               |            127.0.0.1:9010
                               +-> operational database / artifact storage
```

The last hop is private loopback in a shared container network namespace. The
backend implements `light-a2a-backend/v1`; it is not a public A2A server. The
sidecar translates authorized A2A operations into signed backend requests.
It does not forward the caller's raw bearer token. The backend still enforces
business rules and task ownership.

Portal models the layers separately:

| Entity | Meaning in this example |
| --- | --- |
| Product/version `agt` | Runtime and configuration contract; existing publication code requires this product |
| Runtime instance | The deployed `light-a2a`, with its own service ID, environment and credential |
| API/API version and Agent definition | The logical support-triage agent; `agentDefId == apiVersionId` |
| Skill | The published `support-triage` capability |
| Gateway instance/API association | Where the logical agent is exposed |
| A2A binding | Selects the runtime, local backend, signing and retention profiles, and access policy |

Do not create a new `a2a` product solely for this example. A native `light-agent`
already supports A2A without this sidecar. An existing remote A2A server uses
`REMOTE_A2A` federation, which is a different deployment from this local
`EXTERNAL_SIDECAR` example.

## Build and test the business backend

Clone `networknt/light-example-rs` and `networknt/light-fabric` into sibling
directories. Use the toolchain required by their Cargo workspaces. From
`light-example-rs`:

```sh
cargo test --locked -p demo-support-triage-agent
./build.sh 0.1.0-local-triage --local --app demo-support-triage-agent
python3 apps/demo-support-triage-agent/scripts/smoke-demo.py
```

The smoke starts a disposable backend container, signs a test request, checks
replay rejection and idempotent retry, then restarts it and queries the stored
result. It uses temporary test identities and never changes your Portal database.
This establishes backend contract behavior. It does **not** establish Portal
publication, Gateway authorization or complete sidecar readiness.

Example input is a text message: “Production outage affecting all users”. The
result includes `category: availability`, `priority: high`, suggested next steps,
and `automaticActionTaken: false`. The default mode does not create tickets or call a model. The optional local
LLM mode below calls the existing LLM Gateway and still performs no actions.

Read `apps/demo-support-triage-agent/src/lib.rs` to change the classification.
The `a2a-backend` crate supplies the HTTP adapter and signature verification.
The example advertises synchronous invocation and status reconciliation. It
rejects streaming and cancellation and advertises those capabilities as false.

## Exercise the actual light-a2a router

With the sibling `portal-config-loc` checkout available, run from `light-example-rs`:

```sh
python3 apps/demo-support-triage-agent/scripts/test-sidecar.py
```

This provisions an isolated PostgreSQL container using the canonical operational
migration bundle, then runs the actual `light-a2a` router against the backend.
It verifies A2A message invocation, task persistence and retrieval after sidecar
state restart. The script deletes its own database container and temporary files.
It never accesses the running Portal database.

This is a debug-build integration fixture with an explicitly unsigned test Agent
Card and simulated Gateway-signed invocation. It verifies the real sidecar and
backend code, but does not test Config Server bootstrap, live Portal publication,
Agent Card signing or Gateway policy. Production deployment still requires the
normal signed publication described below. Release builds reject the fixture's
unsigned Agent Card.

## Prepare Portal authority

This section requires a running Portal with operational-store provisioning,
A2A authoring support and a configured light-oauth signing service. These are
prerequisites, not artifacts supplied by the disposable backend smoke.

1. Create an `agt` runtime instance for your chosen Host and environment. For the
   local standalone service use `com.networknt.light-a2a-1.0.0`, environment `dev`.
   Give it its own bootstrap/registration credential and map the A2A configuration
   catalog. Use only one live deployment for that workload identity.
2. Register the logical support-triage API/API version and Agent definition,
   assign its Skill and public alias `support-triage`, and publish the definition
   and Skills. Create its association with the target Gateway instance.
3. Author a retention profile and an external-facade signing profile, with a
   current managed signing-key reference. The signing purpose is
   `A2A_CARD_EXTERNAL_FACADE`; private key material stays in the signing service.
4. Create the backend transport profile using the exact values below.
5. Create the A2A binding with `implementationKind=EXTERNAL_SIDECAR`,
   `deploymentMode=SIDECAR`, agent reference `support-triage`, the runtime instance,
   Gateway association, approved backend profile, retention and signing profiles.
   Select `a2a-v03-jsonrpc` for the text-message example below. Set an inbound
   public path, such as `/a2a/support-triage`, your allowed public host, and explicit
   allowed principal prefixes appropriate to your organization.
6. In the A2A publication dialog, select **Preview**, review the candidate, and
   **Sign and stage**. This prepares and signs the Agent Card and stages the
   generated property changes. It does not move the active snapshot.
7. Create and activate the runtime and Gateway Config Server snapshots, then
   perform the normal reload/redeployment. Export the activated runtime values
   as a flat JSON object for the backend configuration helper.

The transport profile is:

| Field | Value |
| --- | --- |
| `contractVersion` | `light-a2a-backend/v1` |
| `contractDigest` | Output of the command below; do not invent a digest |
| `origin` | `http://127.0.0.1:9010/` |
| `audience` | `support-triage-backend` |
| `contextKeyFile` | `/run/secrets/triage-context-key` |
| `requestTimeoutMs` | `5000` |
| `maximumRequestBytes` | `16384` |
| `maximumResponseBytes` | `16384` |
| `dataBoundaryDigest` | Digest of your reviewed data-boundary policy |

```sh
docker run --rm networknt/demo-support-triage-agent:0.1.0-local-triage \
  /app/service --contract-digest
```

Publish these exact capabilities:

```json
{
  "contractVersion": "light-a2a-backend/v1",
  "streaming": false,
  "cancellation": false,
  "statusReconciliation": true,
  "acceptedContentModes": ["text/plain"],
  "maximumArtifactBytes": 65536
}
```

Configure the retention profile's maximum artifact bytes to at least 65536.
This example emits no artifacts, but the contract and publication require a
positive declared artifact limit. Use no streaming, push or extended-card
features in the public profile unless the selected implementation supports them.

## Configure and deploy the pair

Generate the backend expectation from the activated values rather than manually
copying publication IDs or computing a replacement policy digest:

```sh
python3 apps/demo-support-triage-agent/scripts/prepare-backend.py \
  --values /absolute/private/active-a2a-values.json \
  --host-id YOUR_HOST_UUID \
  --output /absolute/private/backend.json
```

Use a flat JSON object with either Config Server keys
`a2a.a2aPolicy.bindings` and `a2a.runtimePolicy.envTag`, or raw snapshot property
keys `a2aPolicy.bindings` and `runtimePolicy.envTag`. Do not mix the forms. The
bindings value can be a JSON list or a string containing that list. The environment
tag is required; no `dev` default is inferred. Export a resolved tag explicitly
when the snapshot relies on a template default. The selected binding must be the activated `support-triage` binding.
The helper trusts the operator-provided export and refuses to overwrite a file.
It does not publish or activate Portal data.

Copy the canonical `light-fabric/apps/light-a2a/config/*.yml` templates into a
private runtime config directory and provide `values.yml` for your deployment.
It must identify the Host, service and environment, Config Server URI/CA, registry
URL, operational and artifact stores, and secret file paths. For the supplied
Compose pair set `server.advertisedAddress: support-triage-a2a`, HTTP port 8448,
and disable HTTPS on that internal listener if the environment defaults differ.
`runtimePolicy` and `a2aPolicy.bindings` come from the activated snapshot.

Provision three distinct kinds of credentials:

- The runtime's Portal bootstrap/registration credential, supplied as
  `TRIAGE_LIGHT_PORTAL_AUTHORIZATION` in a private env file.
- The backend context key shared only by this backend and its sidecar, mounted
  in both at `/run/secrets/triage-context-key`.
- The sidecar's scoped database URL files and Gateway-to-sidecar authorized-context
  key, at the paths specified in its effective configuration.

Use protected files readable by UID/GID 999. The generated `backend.json` is mode
0600 and initially owned by the generating user; transfer it and the secret
files to the runtime owner before mounting. Do not commit runtime files. The
Docker build excludes `.runtime` directories.

Copy `apps/demo-support-triage-agent/deploy/example.env` to a private file and
replace every placeholder. `TRIAGE_PORTAL_NETWORK` selects the existing network
where Config Server, Controller, PostgreSQL and Gateway are reachable. Build the
sidecar with `light-fabric/apps/light-a2a/build.sh VERSION --local` and select
that exact image. Then, from `light-example-rs`:

```sh
docker compose --env-file /absolute/private/triage.env \
  -f apps/demo-support-triage-agent/deploy/compose.yml up -d --wait
```

A dedicated `triage-network` container owns the shared namespace. Both applications
join it, so either application can restart without replacing the namespace. The
sidecar waits for backend health. Use Compose to restart or recreate the namespace
container and its dependents together.
The backend port has no host mapping. The host A2A mapping defaults to
`127.0.0.1:8458`; Gateway uses `support-triage-a2a:8448` internally.

For a deployment already running the standalone `all-in-lt` light-a2a service,
replace that deployment with this pair for the same instance. Do not register
two sidecars with the same service identity or treat this separate Compose
project as an automatic repair of the existing full-stack deployment.

## Call the public A2A endpoint

Use the path and host selected in the published binding, through the Gateway.
Supply your authorized caller credential through your usual client configuration.
First fetch the Agent Card at the discovery path for that binding and verify
that the supported skills and non-streaming capability match your publication.

For the published A2A 0.3 JSON-RPC profile, send this body to the agent's public
path (generate a new message ID for each new request):

```json
{
  "jsonrpc": "2.0",
  "id": "triage-1",
  "method": "message/send",
  "params": {
    "message": {
      "role": "user",
      "messageId": "triage-example-1",
      "metadata": {"skillId": "support-triage"},
      "parts": [{"kind": "text", "text": "Production outage affecting all users"}]
    }
  }
}
```

The Gateway authorizes the public request and signs its internal invocation.
The sidecar admits the A2A task, signs a new private backend invocation and calls
loopback. The business result is persisted before being returned; the sidecar
updates its own task record. Directly sending the public JSON-RPC body to the
backend will not work: that endpoint requires the private signed contract.

## Qualification and troubleshooting

After completing Portal authoring, verify both Compose health checks, retrieve
the public Agent Card, invoke through Gateway, and inspect the completed task.
Repeat a normal pair restart and verify task retrieval. Recreate both containers
together after backend replacement or publication changes, because the shared
network namespace and pinned publication identity must remain aligned.

A Config Server 401 followed by `missing portal registration token` means the
runtime has no usable bootstrap/registration credential. An empty binding list
or expired projection requires publication/activation work. A backend capability
or signature mismatch requires comparing the activated profile, generated
backend configuration, contract digest and mounted key. Increasing readiness
wait time does not repair any of these conditions.

The example's file store is deliberately single-process and bounded to 1,000
tasks/16 MiB. It has no retention worker. Replace it with transactional durable
storage and defined retention before using the example as a production agent.
The automated tests establish backend contract, Docker restart behavior, and
real sidecar routing/task persistence against disposable PostgreSQL;
full Portal/Gateway qualification is a separate deployment step.

### Local LLM-backed deployment

For the `portal-config-loc/all-in-lt` demonstration, the AgentDefinition selects
the real `assistant-dev` model alias. The backend calls the existing
`llm-gateway` using the optional `llm` configuration:

```json
"llm": {
  "endpoint": "https://llm-gateway:8443/v1/chat/completions",
  "model": "assistant-dev",
  "tokenFile": "/run/triage-llm/user.jwt",
  "caFile": "/app/config/ca.pem"
}
```

Add this object to the generated backend JSON before mounting it. Provision an
authorized local operator token in `.runtime/llm-user.jwt`; authorize that user
and Host for the LLM endpoint and alias using the existing Gateway access policy.
This is a local test credential, separate from the incoming A2A caller token and
from the sidecar's service registration credential. Renew it through OAuth when
it expires. Never put token contents in events, source control or the tutorial.

The base `all-in-lt/docker-compose.yml` includes `demo-support-triage-agent`,
its `light-a2a` sidecar, and a secret initialization service. No extra overlay is
needed. A dedicated infrastructure container owns their shared network namespace;
the backend listens only on `127.0.0.1:9010`; it receives only its own context key and LLM credential.
The sidecar also mounts a distinct Gateway-to-sidecar authorization key.

Before starting a fresh copy, provision the Git-ignored `.runtime/backend.json`,
`service.jwt`, `llm-user.jwt`, `triage-context-key`, and `gateway-context-key`.
Files must be readable by UID 999. The two context keys are independently
generated random secrets; publish the backend key path in its transport profile.
Keep the managed Agent Card signing private key in the OAuth signing directory.

Use the regular local deployment command after publishing and activating both
runtime and Gateway snapshots. In this stack, the Portal Gateway has logical
environment `dev` and deployment tag `loc`; the A2A runtime uses `dev` for both.
Choose the Gateway instance actually serving the public endpoint when creating
the Instance API association.

The exact imported events, immutable publication references, image digests and
live qualification results are recorded in
`light-portal-event/genai/20260912-support-triage/README.md`.

An LLM-backed result identifies `classifier: llm-gateway` and
`model: assistant-dev`. Model errors fail the task instead of silently switching
to deterministic output. Category, priority and suggested steps are validated;
`automaticActionTaken` always remains false.

As of the local September 12 qualification, the backend and sidecar start and
register, but Gateway publication 2 is still STAGED. An earlier failed snapshot
blocked the Gateway graph; its event is excluded from replay by the current
policy. The event record above documents the required recovery. Public discovery,
invocation and restart-persistence checks must pass before calling this deployment
fully activated.
