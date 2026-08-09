# Local Model Provider Transport For LLM Gateway

## Status

Proposed design for implementation and qualification.

This design extends the completed OpenAI-compatible LLM gateway and the
Embedding Space Contract. It does not change the public `/v1` client contract.

## Decision Summary

The LLM gateway must support self-hosted model servers running on the same
machine, in the same Kubernetes cluster, or elsewhere on an organization's
private network. Self-hosted models are a first-class production deployment,
not a development-fixture exception.

Keep HTTPS mandatory for public provider destinations. Add explicit private
network profiles for operator-approved model endpoints:

- `public_tls` for public HTTPS providers;
- `private_tls` for a private endpoint protected by server TLS; and
- `private_plaintext` for an explicitly approved private HTTP endpoint when the
  operator accepts the transport risk.

mTLS remains a possible future strengthening of `private_tls`, but it is not
mandatory and is not part of the first implementation. Service-mesh-specific
transport is also deferred.

When a model runtime does not provide HTTPS, deploy `light-gateway` beside the
runtime as its TLS sidecar. The central `llm-gateway` connects to the sidecar
over HTTPS; the sidecar forwards over loopback to the model runtime:

```text
Application or knowledge service
              |
              | OpenAI-compatible HTTPS
              v
        logical llm-gateway
              |
              | private TLS
              v
   light-gateway model sidecar
              |
              | HTTP over loopback
              v
       Ollama / llama.cpp / vLLM
```

The sidecar is a transport-security boundary. It does not become another LLM
configuration authority, select Public Aliases, hold cloud provider
credentials, translate model semantics, or bypass LLM gateway policy.

## Motivation

Enterprise knowledge bases frequently contain material that cannot leave the
customer's controlled network. Customers therefore need to run embedding and
generation models on their own hosts or clusters. Many self-hosted runtimes
expose OpenAI-compatible APIs but listen on HTTP by default.

The current production contract rejects HTTP, loopback destinations, and
private-network destinations. That is a useful default for operator-configured
public providers because it prevents plaintext credential disclosure and
server-side request forgery. It is too broad for a reviewed, network-isolated
model-serving deployment.

The underlying LLM provider transport already accepts HTTP and HTTPS. The
production compiler and Portal control plane impose the stronger policy. This
design replaces that single policy with explicit trust profiles rather than
using `developmentFixtures` or adding an unrestricted `allowHttp` flag.

## Terminology

| Term | Meaning |
| --- | --- |
| `llm-gateway` | The logical inference gateway that authenticates callers, resolves Public Aliases, enforces policy and budgets, routes operations, validates provider responses, and writes audit records. |
| `light-gateway` | The general LightAPI reverse proxy. In this design, a restricted instance runs beside a model server to terminate TLS. |
| Model runtime | A self-hosted inference server such as Ollama, `llama-server`, or vLLM. |
| Provider endpoint | One materialized provider configuration: protocol, base URL, endpoint authentication, headers, and Network Profile. One or more Provider Deployments may reference it. |
| Model sidecar | A `light-gateway` instance colocated with one model runtime or one tightly coupled model-serving unit. |
| Network profile | The declared transport and destination trust contract for a Provider endpoint. |
| Network zone | An operator-managed set of DNS names, addresses, ports, workload identities, and enforcement controls that may host private model endpoints. |
| Trust bundle | One or more CA certificates used to authenticate a private TLS server. |
| Client identity | A client certificate and private key used by `llm-gateway` for mTLS. |
| Physical runtime identity | A stable, control-plane-issued identity for the model-server instance reached through an endpoint, independent of the Provider Deployment record and bound to live evidence. |
| Capacity domain | The smallest scheduler, accelerator, or host resource whose saturation can affect every deployment assigned to it. |
| Sidecar identity | The supported profile version, non-secret configuration digest, and certificate identity reported by a model sidecar and captured by live qualification. |

## Goals

- Make Ollama, llama.cpp, vLLM, and other OpenAI-compatible self-hosted servers
  production-capable Provider Deployments.
- Encrypt prompts, retrieved knowledge, tool input, and vectors whenever traffic
  crosses a host or an unencrypted application namespace.
- Reuse `light-gateway` as the supported TLS sidecar for runtimes without native
  TLS.
- Preserve the existing Public Alias, routing, pricing, audit, conformance, and
  Embedding Space Contract behavior.
- Retain SSRF, DNS-rebinding, redirect, credential, and private-network
  protections for public providers.
- Make every relaxation explicit, scoped, publication-validated, observable,
  and reversible.
- Support private CAs and certificate rotation without disabling hostname
  verification. Leave mTLS as an optional later enhancement.
- Bound gateway concurrency by the local runtime's effective parallelism and
  keep protected query, indexing, and standard traffic out of shared capacity
  domains when isolation is required.

## Non-Goals

- This design does not let callers submit provider URLs.
- It does not make `light-gateway` an Alias router or LLM protocol translator.
- It does not treat a private IP address as sufficient proof of trust.
- It does not permit arbitrary public HTTP provider URLs.
- It does not weaken provider conformance or embedding-space qualification for
  local models.
- It does not expose model-management, model-download, debug, runtime metrics,
  Web UI, or administrative runtime endpoints through the sidecar's inference
  listener. The first release serves only exact, authenticated sidecar health
  and identity paths on that listener. A separate operations listener and
  sidecar metrics endpoint are deferred.
- It does not require every self-hosted runtime to implement native TLS.

## Existing Foundation

The existing `light-gateway` implementation already supplies most data-plane
mechanics needed by the sidecar profile:

- `server.enableHttps`, `server.httpsPort`, `server.tlsCertPath`, and
  `server.tlsKeyPath` configure an HTTPS listener;
- the listener validates that the certificate and private key parse and match;
- `proxy.hosts` accepts a fixed `http://` or `https://` upstream;
- an HTTP upstream can be bound to `127.0.0.1` inside the model host or pod;
- upstream redirects are not part of LLM provider routing;
- `client.caCertPath` supplies a private CA bundle when `light-gateway` itself
  calls a TLS upstream; and
- `client.clientCertPath` plus `client.clientKeyPath` support outbound mTLS.

The current HTTPS listener authenticates the server to its clients. Requiring a
client certificate on that listener is a separate capability. This design does
not require that capability in the first release. A sidecar may use
server-authenticated TLS plus a rotated workload credential and network policy.

The current `llm-gateway` provider client disables redirects, deliberately
ignores ambient `HTTP_PROXY` and `HTTPS_PROXY` settings with `no_proxy()`, and
uses a custom DNS resolver. It does not yet accept a per-endpoint private CA or
client identity, and its production compiler rejects private destinations.
Those are implementation gaps addressed by this design. An explicit reviewed
egress-proxy contract is separate future work; process environment variables
must not silently change provider routing.

## Supported Topologies

### Native Private TLS

Use this when the model runtime supports HTTPS directly.

```text
llm-gateway -- HTTPS --> model runtime
```

Examples include vLLM with its SSL options and an OpenSSL-enabled
`llama-server`. The model endpoint presents a certificate whose SAN contains
the configured service name. The LLM gateway validates the chain against the
declared private trust bundle.

### Light Gateway TLS Sidecar

Use this when the model runtime exposes HTTP only, including the normal Ollama
deployment pattern.

```text
model host or pod
+-------------------------------------------------------+
| light-gateway :8443                                   |
|   - HTTPS listener                                    |
|   - workload authentication                           |
|   - exact method/path allowlist                       |
|   - bounded request/response handling                 |
|   - fixed upstream http://127.0.0.1:11434             |
|                         |                             |
|                         +--> Ollama :11434            |
+-------------------------------------------------------+
```

Only the sidecar port is exposed to the private network. The raw runtime port
is bound to loopback in the sidecar's network namespace and is blocked from
other workloads. This prevents bypassing sidecar authentication and limits.

The sidecar preserves OpenAI-compatible request paths, bodies, streaming, and
responses. For example, `/v1/embeddings` remains `/v1/embeddings` upstream.
When a runtime exposes only a proprietary endpoint such as `/api/embed`, a
protocol adapter or an additional provider codec is required; the TLS sidecar
must not silently reinterpret the API.

### Private Plaintext

Application HTTP is allowed for an explicitly selected private destination,
including another computer on a home network. It is never the default. The UI
and command path must explain that prompts, retrieved knowledge, vectors, and
responses are not encrypted by the application transport. Credentials are
forbidden on this profile in the first release.

Enterprise policy may prohibit remote plaintext or restrict it to loopback,
an encrypted overlay, or an isolated model-serving network. A home or lab
operator may accept HTTP to an approved RFC 1918 or unique-local address. The
gateway still blocks public, metadata, link-local, multicast, unspecified, and
other unsafe destinations. A `light-gateway` TLS sidecar remains the recommended
option for a remote HTTP-only runtime, but it is not mandatory for an operator
whose effective policy permits private HTTP.

## Network Profile Contract

The current production projection materializes one `ProviderConfig` for each
`providerId` and rejects conflicting materialization. Keep that ownership rule:
each Provider endpoint declares exactly one immutable Network Profile, and each
Provider Deployment references one Provider endpoint. Deployments that share a
`providerId` therefore share protocol, base URL, endpoint authentication,
headers, and Network Profile. Use a different `providerId` when any of those
values differ.

The conceptual compiled shape is:

```yaml
providers:
  ollama-embedding-sidecar:
    providerProtocol: openai_embeddings
    baseUrl: https://embedding-01.models.corp.example:8443/v1
    endpointAuth:
      mode: bearer
      credentialRef: credential://ollama-sidecar/workload
    networkProfile:
      mode: private_tls
      termination: light_gateway_sidecar
      networkZoneId: kb-model-serving
      tls:
        trustBundleRef: config://corp-model-ca-v3
        trustBundleSha256: 42b8...f10c
      connection:
        poolIdleTimeoutMs: 30000
        clientRefreshIntervalMs: 300000

deployments:
  tenant-embedding-local-v1:
    provider: ollama-embedding-sidecar
    physicalRuntimeId: models-host-01/ollama-embedding
    capacityDomainId: models-host-01/gpu-0
    sidecar:
      profileVersion: model-provider-sidecar/v1
      configSha256: a910...7d2e
```

The exact storage representation may use normalized columns and referenced
resources rather than one JSON object. The compiled runtime contract must be
strongly typed and reject unknown fields.

### Profile Semantics

| Mode | Destination | Required protection | Credentials |
| --- | --- | --- | --- |
| `public_tls` | Public DNS or IP | HTTPS with public or explicitly approved CA | Optional typed endpoint credential allowed |
| `private_tls` | Approved private DNS or IP | Server-authenticated HTTPS | Optional endpoint credential allowed |
| `private_plaintext` | Explicitly approved private DNS or IP | Operator accepts plaintext risk | Credential forbidden in the first release |

`termination` is an expected topology declaration and may be `native` or
`light_gateway_sidecar`. It is not evidence by itself and does not change client
protocol semantics. A sidecar declaration becomes trusted only when signed live
qualification matches the expected sidecar identity.

### What A Network Zone Means

A Network Zone is a named outbound allowlist, not a claim that every private
address is trustworthy. It owns the permitted DNS names, CIDRs, and ports for
one or more Provider endpoints and states which transport modes the operator
permits there. `allowedPorts` and reusable address constraints belong here, not
on a single-URL Network Profile. For example:

```yaml
networkZone:
  id: home-model-lan
  dnsNames: [ollama.home.arpa]
  cidrs: [192.168.1.0/24]
  ports: [11434]
  allowPrivateTls: true
  allowPrivatePlaintext: true
```

An enterprise zone might allow only `*.models.corp.example`, a model-serving
subnet, and port `8443`, with plaintext disabled. A home installation may allow
HTTP to a specific RFC 1918 address and port. The zone is enforced in addition
to firewalls or Kubernetes NetworkPolicy; it does not replace them.

Use a reusable Portal resource owned by the host or platform administrator.
Tenant application users cannot create arbitrary zones. Publication compiles
the selected DNS names, CIDRs, ports, and allowed transport modes into the LLM
gateway snapshot so enforcement does not depend on a caller-supplied label.

### How Private CA Bundles Are Delivered

A CA certificate is public material, but it is security-sensitive trust
configuration. Project only a versioned reference and SHA-256 digest. Resolve
the PEM bundle at runtime from a managed configuration mount or configuration
service. Do not place the PEM repeatedly in every Provider Deployment payload,
and never put a client private key in a projection.

This keeps publications small, makes rotation explicit, and lets every replica
verify that the resolved bundle matches the published digest. A standalone or
home installation may resolve the reference to a local file. An enterprise may
resolve it through its normal certificate-management integration.

Changing bytes behind a stable reference without publishing a new version and
digest is forbidden. During compilation, the gateway hashes the resolved PEM,
compares it with `trustBundleSha256`, and includes that resolved digest in the
provider-client reuse identity. A trust-bundle change therefore rebuilds the
TLS client and discards its connection pool even when the reference string did
not change.

### Immutability

The following values are part of the published provider/deployment contract:

- network profile mode;
- network zone;
- endpoint-authentication mode and credential-reference identity;
- trust-bundle identity, version, and digest;
- provider protocol;
- normalized base URL;
- physical runtime and capacity-domain identities; and
- expected sidecar profile version and configuration digest when applicable.

A change creates a new deployment revision and new conformance evidence. It
must not silently mutate an active physical destination. Certificate material
may rotate under a versioned reference using the staged procedure below, but a
change of trust authority is still a reviewed publication change.

### Credential Contract

The current `ProviderConfig.secret_ref` and `SecretResolver` require a non-empty
secret, and the provider client always emits `Authorization: Bearer <secret>`
for OpenAI protocols or `x-api-key` for Anthropic. That cannot represent normal
credential-free Ollama or `llama-server` deployments. Phase L1 must replace the
implicit protocol behavior with a typed endpoint-authentication contract:

- `none`, which performs no secret resolution and emits no credential header;
- `bearer`, which resolves one approved `credentialRef` and emits one Bearer
  credential; or
- `api_key`, which resolves one approved `credentialRef` and emits it only in a
  contract-approved header.

An empty string is not the representation of `none`. `private_plaintext`
requires `endpointAuth.mode: none` in the first release. An endpoint that needs
a credential must use TLS, normally by adding the supported sidecar.

When a sidecar authenticates `llm-gateway` and the loopback runtime also needs
an API key, those are separate credentials on separate hops. The endpoint
credential belongs to the Provider endpoint and is removed before proxying.
The runtime credential belongs to the sidecar publication and is injected from
a sidecar-owned secret reference after authentication; it is never carried in
`ProviderConfig.headers` and is never forwarded from the caller. Phase L1 must
define both slots even if most local runtimes use `runtimeAuth.mode: none`. The
current provider extra-header allowlist and credential-like-value rejection are
retained; they are not a second secret channel.

### Required Phase L1 Contract Changes

The first contract phase must land the non-transport fields that later phases
depend on:

- optional typed endpoint authentication and the distinct sidecar-to-runtime
  authentication slot;
- Network Profile, Network Zone, and resolved trust-bundle digests in provider
  client identity;
- physical-runtime identity, capacity-domain identity, effective parallelism,
  readiness/warmup policy, and local timeout bounds;
- endpoint-, deployment-revision-, transport-, and sidecar-bound live
  qualification evidence with a distinct evidence kind;
- runner key identity and signature fields for qualification authenticity; and
- an explicit local pricing basis so zero marginal price and amortized internal
  price are not ambiguous.

Deferring these shapes until the TLS client or live runner is implemented would
reopen the coordinated projection contract.

## Validation Rules

### Common URL Rules

- The base URL must have an `http` or `https` scheme and a host.
- User information, query strings, and fragments are forbidden.
- Redirects are disabled.
- The effective port must be permitted by the applicable profile policy and,
  for private profiles, declared by the Network Zone.
- The resolver filters answers to the applicable compiled address policy and
  fails when no permitted address remains. For private profiles that policy is
  the Network Zone; for public TLS it retains the globally-routable-address
  rules. An unrelated IPv4 or IPv6 answer is never used.
- The connector validates the selected socket peer address against the same
  compiled policy immediately after connection; DNS filtering alone is
  insufficient.
- Callers cannot override the authority, SNI, destination, or path prefix.
- Ambient HTTP proxy variables are ignored.

The current `ProviderDnsResolver` receives one
`allow_non_public_networks: bool`, rejects a public profile when any DNS answer
is forbidden, and classifies every non-globally-routable IPv6 address, including
`fc00::/7`, as forbidden. Do not turn that boolean into a broad production
escape hatch. The Network-Zone-aware resolver positively selects only compiled
CIDRs, including explicitly approved unique-local ranges, and fails when the
filtered set is empty.

`clientRefreshIntervalMs` is not a certificate- or trust-rotation mechanism. It
is the maximum age of the active provider client before a same-material client
and empty connection pool replace it, bounding how long DNS can remain hidden
behind connection reuse without interrupting active requests. The compiler
requires finite, policy-bounded `poolIdleTimeoutMs` and
`clientRefreshIntervalMs`. A material endpoint, zone, credential, or trust
change rebuilds immediately and never waits for this interval.

### Public TLS

- The URL scheme is `https`.
- Loopback, private, link-local, multicast, unspecified, broadcast, and cloud
  metadata destinations are forbidden.
- Every new connection uses checked DNS results. A pooled connection is not
  re-resolved while it remains open, so the client has an explicit finite idle
  timeout and is rebuilt on material profile, zone, endpoint, or trust changes.
- Provider credentials come only from approved secret references.

### Private TLS

- The URL scheme is `https`.
- The Provider endpoint references an approved Network Zone.
- The URL host and port must be members of that zone, and only resolved
  addresses in the zone may be connected.
- Certificate-chain and hostname verification are mandatory.
- The URL host is the TLS verification name and SNI value. The first release
  does not expose an independent `tls.serverName` override; address pinning is
  done in the resolver while the DNS host remains in the URL.
- An IP-literal URL is permitted only when zone policy allows it and the server
  certificate contains the matching IP SAN. DNS names are recommended for
  private CAs.
- `verifyHostname: false` and accept-invalid-certificate behavior are forbidden
  in production.
- mTLS may be added later as an optional strengthening without changing the
  meaning of `private_tls`.

### Private Plaintext

- The scheme is `http`.
- Public destinations are forbidden.
- The destination and port must be present in a Network Zone whose
  `allowPrivatePlaintext` policy is true.
- The operator receives a clear warning and explicitly accepts the lack of
  transport encryption. Enterprise policy may disable this choice.
- `endpointAuth.mode` must be `none`; credentials over private HTTP are not part
  of the first release.
- Fallback cannot escape to a less protected zone.

## Model Sidecar Security Profile

A general-purpose gateway configuration exposes more functionality than a
model sidecar needs. Provide a supported `model-provider-sidecar` profile with
these invariants:

1. HTTPS is enabled and the cleartext listener is disabled on the network
   interface.
2. The only upstream is a fixed loopback address and port.
3. Dynamic routing, `service_url`, controller discovery, and caller-selected
   upstreams are disabled.
4. Only required methods and paths are allowed, initially:
   - `POST /v1/chat/completions`;
   - `POST /v1/responses` when the runtime is conformant;
   - `POST /v1/embeddings`;
   - exact authenticated `/sidecar/health` and `/sidecar/identity` paths on the
     inference listener.
5. Runtime model-management, download, debug, metrics, Web UI, and native admin
   endpoints are denied.
6. The external Host header is not trusted to select an upstream.
7. Proxy authentication headers are validated and then removed or replaced
   before the loopback hop unless the model runtime needs a distinct local
   credential.
8. Hop-by-hop headers and caller-supplied forwarding headers are normalized.
9. Request, response, idle, connect, body-size, and streaming limits match or
   are tighter than the compiled LLM Deployment capabilities.
10. Prompt text, vectors, authorization data, and full model responses are not
    written to logs or metrics.

The profile is deny-by-default. `handler.paths` performs the exact
method-and-path selection; `unified-security` authenticates only after a path
has selected the inference chain. Prefix-based authentication is not a path
allowlist. A copy-safe core configuration therefore includes the allowlist and
a non-proxy default chain. The following is the Phase L3 target and is not
available until its two new terminal handlers land. Current handler collection
rejects an unknown handler or chain ID during configuration load, so this
profile fails to start on a pre-L3 Light Gateway binary rather than silently
degrading. Phase L3 registers both IDs in `GATEWAY_HANDLER_DESCRIPTORS` and adds
their request-dispatch behavior in the same binary release.

```yaml
server.ip: 0.0.0.0
server.enableHttp: false
server.enableHttps: true
server.httpsPort: 8443
server.tlsCertPath: /config/tls/server-chain.pem
server.tlsKeyPath: /config/tls/server-key.pem

handler.handlers:
  - sidecar-deny
  - sidecar-identity
  - correlation
  - unified-security
  - headers
  - proxy
  - health
handler.chains:
  model-inference:
    exec:
      - correlation
      - unified-security
      - headers
      - proxy
  sidecar-health:
    exec:
      - correlation
      - unified-security
      - health
  identity:
    exec:
      - correlation
      - unified-security
      - sidecar-identity
  deny:
    exec:
      - sidecar-deny
handler.paths:
  - path: /v1/chat/completions
    method: POST
    exec: [model-inference]
  - path: /v1/responses
    method: POST
    exec: [model-inference]
  - path: /v1/embeddings
    method: POST
    exec: [model-inference]
  - path: /sidecar/health
    method: GET
    exec: [sidecar-health]
  - path: /sidecar/identity
    method: GET
    exec: [identity]
handler.defaultHandlers:
  - deny

unified-security.enabled: true
unified-security.anonymousPrefixes: []
unified-security.pathPrefixAuths:
  - prefix: /v1/chat/completions
    jwt: true
  - prefix: /v1/responses
    jwt: true
  - prefix: /v1/embeddings
    jwt: true
  - prefix: /sidecar/health
    jwt: true
  - prefix: /sidecar/identity
    jwt: true

proxy.hosts: http://127.0.0.1:11434
proxy.rewriteHostHeader: true
```

This maximal example shows all three inference operations. The generator emits
only the exact entries declared and qualified for that sidecar; an
embedding-only runtime receives only `POST /v1/embeddings`. It derives the
`pathPrefixAuths` entries from the same operation set instead of installing one
broad `/v1` prefix. `handler.paths` remains the method/path security boundary,
because unified-security prefix matching is not exact by itself.

The target profile requires two new terminal handlers in Phase L3.
`sidecar-deny` returns a local 404 and cannot select an upstream.
`sidecar-identity` returns the non-secret identity contract described below.
The current `exception` handler ID is not a deny implementation: it has no
request-dispatch arm, and relying on that no-op behavior would make an unwritten
fallthrough invariant load-bearing.

The deny chain must be non-empty and contain no upstream- or content-selecting
handler, including `proxy`, `router`, `virtual`, `resource`, or
`path-resource`. The `model-provider-sidecar` profile generator and validator
enforce this rule; generic `handler.yml` validation does not, because an empty
default chain is valid fixed-upstream reverse-proxy behavior in ordinary Light
Gateway deployments. The generated profile also supplies the JWK or API-key
configuration, credential removal and optional runtime-credential injection,
request and streaming limits, and registry-disabled settings. Customers should
consume the generated profile rather than assemble those security-sensitive
settings from unrelated examples.

Generated-profile integration tests must assert a local 404 and no upstream
connection for at least `POST /api/tags`, `GET /v1/embeddings`, and, on an
embedding-only sidecar, `POST /v1/chat/completions`. They also assert that an
empty default chain is rejected by the model-sidecar profile generator or
profile-specific validator without changing generic handler semantics.

The existing `health` handler remains the fixed local `200 ok` liveness check;
it does not carry identity. `/sidecar/identity` uses the new handler. Both paths
are exact, authenticated, locally served, and never proxied in the first
release. A separate operations listener and sidecar metrics endpoint are
deferred; native runtime metrics remain unreachable through the sidecar.

## Authentication

The first release uses server-authenticated TLS. A scoped, rotated endpoint
credential may authenticate `llm-gateway` to the model sidecar. The sidecar
validates and removes it before proxying. If the model runtime also requires an
API key, the sidecar resolves the separate `runtimeAuth` reference and injects
that value only on the loopback hop. The central gateway does not hold both
secrets in one untyped header map. Network policy remains mandatory in managed
environments.

mTLS is optional, not mandatory, and is deferred from the first release. It may
later be added by extending the `light-gateway` HTTPS listener with a client-CA
bundle and a `requireClientCertificate` setting. That future extension must not
change the public LLM API or make existing server-authenticated TLS deployments
invalid.

Authentication is defense in depth, not a substitute for provider visibility
and Alias authorization in `llm-gateway`.

## Sidecar Identity And Registration Invariants

`termination: light_gateway_sidecar` is only an expected declaration. The new
`sidecar-identity` handler serves `/sidecar/identity` and exposes, without
secret material:

- sidecar profile name and version;
- canonical non-secret configuration SHA-256;
- certificate identity and expiry information;
- physical runtime identity; and
- the inference paths and methods enabled by that profile.

The signed live runner captures these values through the published endpoint and
binds them to its qualification result. The compiler accepts a sidecar profile
only when that evidence matches the deployment revision, Provider endpoint,
Network Profile digest, expected profile version, and expected configuration
digest.

All active Provider Deployments that claim the same `physicalRuntimeId` must use
the same approved endpoint boundary and Network Profile. Multiple models may be
served by one live-qualified runtime, but registering the same model runtime once
through its sidecar and again through a raw or weaker endpoint is rejected. Live
qualification also probes from outside the colocated host or pod and fails when
the declared raw runtime address is reachable.

Raw-port reachability evidence is valid only from a recorded external vantage.
The evidence carries a vantage kind, environment or cluster identity, source
workload identity, source Network Zone, and network-namespace identity. For a
Kubernetes sidecar the runner namespace must differ from the model Pod's shared
network namespace; a runner inside that Pod cannot prove external isolation. A
bare-metal probe similarly originates outside the model host.

An unreachable result caused by NetworkPolicy is useful but does not by itself
prove loopback binding. Signed qualification binds the live probe to admission
or manifest evidence showing the runtime loopback bind, `hostNetwork: false`,
absence of a raw-port Service, and the allowed container set. The runner records
a digest of that isolation evidence and the raw probe target rather than
publishing unnecessary internal topology.

## Private CA And Certificate Lifecycle

### Trust

The LLM gateway must resolve a versioned `trustBundleRef` and build a TLS client
for that deployment. It must not depend on modifying a process-global CA file
or disabling certificate checks. A public CA may be used for an internal DNS
name when organizational policy permits it; otherwise use the enterprise CA,
cert-manager issuer, SPIRE authority, or equivalent.

### Rotation

Use overlap rather than a flag day:

1. Publish a new trust-bundle version and digest containing the current and next
   CA when the authority changes.
2. Verify every LLM gateway replica resolved the advertised digest, rebuilt the
   affected provider client, discarded the old pool, and acknowledged the new
   publication.
3. Rotate sidecar server certificates.
4. Prove conformance and health through every eligible endpoint.
5. Remove the old CA through another versioned publication and repeat the
   acknowledgement check.

Expose certificate expiry and rotation status without logging private-key
material.

## Routing, Fallback, Conformance, And Qualification

Local deployments participate in normal operation-aware routing. Transport
profiles do not create new client operations.

- A chat deployment uses an approved Chat or Responses provider protocol.
- An embedding deployment uses the OpenAI Embeddings provider protocol.
- Every physical production deployment completes automated live qualification
  through its actual published URL, including the TLS sidecar when present.
- Fallback candidates must satisfy the requested operation, capability,
  network policy, and data-residency policy.
- An embedding Alias continues to require one compatible Embedding Space
  Contract across all eligible deployments.
- A local model change, quantization change that affects outputs, normalization
  change, prompt transform, or embedding weights change may require a new
  embedding-space revision even when dimensions remain unchanged.

### Local Runtime Capacity, Readiness, And Isolation

Local runtimes have physical constraints that a cloud-provider account does not
describe. Ollama may serialize work, load only a bounded number of models, and
evict an idle model. A vLLM instance reserves a fixed accelerator budget and
has bounded admission. The generic contract must describe the effective limits
without making provider-specific environment variables part of the public API:

```yaml
runtimeCapacity:
  physicalRuntimeId: models-host-01/ollama-embedding
  capacityDomainId: models-host-01/gpu-0
  maxParallelRequests: 2
  maxQueuedRequests: 4
  readinessPolicy: warm_before_eligible
  coldStartTimeoutMs: 180000
  streamSetupTimeoutMs: 30000
  requestTimeoutMs: 120000
```

The values are immutable deployment inputs, are included in live qualification,
and are bounded by host policy. Runtime-specific controls such as model
keep-alive, loaded-model count, queue length, and accelerator-memory fraction
remain in the deployment manifest, but qualification verifies that the claimed
effective capacity and timeouts are credible.

The compiler enforces `DeploymentConfig.concurrency <= maxParallelRequests`.
Gateway admission must also bound queued work rather than hiding an unbounded
runtime queue behind `requestTimeoutMs`. Local deployments use explicit
connect, stream-setup, request, and cold-start limits rather than inheriting
cloud defaults.

A runtime using `warm_before_eligible` is not routable until the configured
model is loaded or pinned and a warmup probe succeeds within
`coldStartTimeoutMs`. Cold loading is therefore a readiness transition, not a
normal user's first request. If the model is evicted or the runtime restarts,
health removes the deployment from eligibility, warmup runs again, and only
then is it returned to service. A cold-load miss must not be misclassified as
congestion and repeatedly trip paid fallback or quarantine.

The existing compiler separates Knowledge Base query, indexing, and standard
embedding lanes by deployment and provider-account quota group. Extend that
check to `capacityDomainId`. Distinct deployment records or server processes do
not prove isolation when they share one GPU or runtime scheduler. A policy that
requires protected query capacity must use disjoint capacity domains, and the
production exercise must load both lanes concurrently to prove the boundary.

### Local Pricing And Budget Semantics

Every local deployment still publishes an operation price and price version.
The owner explicitly selects one pricing basis:

- `amortized_internal` uses a non-zero chargeback rate derived from the
  organization's hardware, energy, license, or allocation convention; or
- `zero_marginal` records that the operator assigns no monetary charge to an
  additional request.

The basis is audit metadata, not an inference capability. A zero price does not
mean unlimited accelerator capacity; concurrency, queue, and capacity-domain
policy enforce the physical limit. Conversely, a monetary budget must not be
repurposed as the capacity control.

The current ambiguous-usage branches compute
`ambiguous_charge_micros.min(reserved).max(1)`. With a zero-price deployment,
`reserved` is zero, so the ledger charges one micro-unit without a matching
reservation. Phase L1 makes the minimum-charge floor conditional on a non-zero
reserved envelope: when `reserved == 0`, both generation and embedding
reconciliation charge zero while recording `usageComplete: false`. This is a
ledger invariant, not only a pricing-display correction.

Fallback preserves the current worst-case reservation principle. Before the
first attempt, the gateway reserves the summed price envelope for every attempt
the Alias may make. A route that starts on a zero-price local deployment and may
fall back to a paid cloud deployment is rejected before dispatch when the paid
envelope exceeds `maxCostMicros`; fallback is never an unbudgeted cost event.

### What Conformance Means

Conformance is machine-generated evidence that a claimed provider contract
actually behaves as the gateway expects. It is not a model-version allowlist
and it is not a field an administrator should type into a form.

Three related checks must remain distinct:

| Check | Scope | What it proves | When it runs |
| --- | --- | --- | --- |
| Codec conformance | Gateway provider codec and versioned fixture corpus | Request encoding, response decoding, errors, streaming, tools, usage, and embedding formats behave consistently | Build and gateway release |
| Live deployment qualification | Exact Provider Deployment URL, physical model, transport profile, and declared operations | The reachable server behaves compatibly through its real TLS sidecar or native endpoint | Registration, material configuration change, and scheduled refresh |
| KB embedding qualification | Every physical embedding deployment under one Embedding Space Contract | Dimensions, normalization, ordering, finite vectors, known-probe fingerprints, and space compatibility are stable | Before index promotion and after any model or transform change |

The "conformance matrix" is simply the coverage table across provider protocol,
operation, transport mode, and declared capability. It does not mean that the
Portal maintains a list of allowed Ollama, llama.cpp, or vLLM release numbers.
The runtime version may be recorded as diagnostic evidence when available, but
compatibility is established by tests against the endpoint rather than by
matching a version string.

For example, one deployment can pass OpenAI-compatible Chat but fail Responses,
or pass scalar embeddings but fail batch ordering or base64 output. Testing one
operation must not qualify all operations automatically.

### Current Implementation Status

Conformance has been removed from the editable Provider Deployment form and
from the Portal action panel. That is intentional: ordinary Portal
administrators must not submit or edit `PASS` evidence.

It has not been removed from the system. The current database still stores
state, digest, validity, and result evidence; command handlers still support
pending, completion, and due-refresh transitions; and the production gateway
projection still requires a complete `ConformanceResult`. Routing checks its
digest, provider protocol, physical model, tested operation, expiry, state, and
capability evidence.

The current type cannot prove the transport claims in this design.
`ConformanceResult` has no Provider endpoint, normalized URL, deployment
revision, Network Profile digest, Network Zone, physical runtime, or sidecar
identity. The compiler can therefore attach evidence from one endpoint to a
different endpoint when protocol and model happen to match. Its
`FixtureProvenance` values describe synthetic or captured codec fixtures; they
do not distinguish a codec result from a live network probe.

There is also an authenticity gap. `verify_digest()` recomputes a digest stored
inside the result. The implementation correctly describes this as integrity
binding, not authenticity. Anyone with direct database write access can compute
another internally consistent `PASS`. Removing the editable form protects the
normal Portal workflow but does not make database evidence authentic.

Finally, the checked-in Rust
`provider-conformance` runner executes the versioned JSON fixture corpus through
the gateway codecs. It does not make live network calls to the configured model
deployment. The command contract anticipates a trusted external runner, but no
complete worker that consumes `PENDING`, probes the endpoint, and records the
canonical result exists in this checkout. Until that worker is implemented,
the production workflow is incomplete even though the enforcement structures
remain.

### Live Evidence Contract

Phase L1 extends the evidence type before the worker is implemented. Keep
`FixtureProvenance` for fixture origin and add a result-level evidence kind such
as `codec_corpus`, `live_endpoint`, or `kb_embedding`. A routable production
deployment requires signed `live_endpoint` evidence containing at least:

```yaml
evidenceKind: live_endpoint
deploymentRevisionId: tenant-embedding-local-v1/r4
providerEndpointSha256: 3b82...119e
networkProfileSha256: 0f43...d201
physicalRuntimeId: models-host-01/ollama-embedding
capacityDeclarationSha256: be71...820a
sidecar:
  profileVersion: model-provider-sidecar/v1
  configSha256: a910...7d2e
  certificateIdentitySha256: 38d0...f4c1
  isolationEvidenceSha256: c552...08fa
  rawPortReachable: false
runnerVantage:
  kind: external_workload
  environmentId: production-ca-central-1
  sourceWorkloadId: provider-qualification-runner
  sourceNetworkZoneId: qualification-probes
  sourceNetworkNamespaceId: runner/qualification-7f94
  targetNetworkNamespaceId: models/embedding-01
  rawProbeTargetSha256: 0cb1...63ed
testedOperations: [embed]
testedAt: 2026-08-08T16:00:00Z
validUntil: 2026-08-15T16:00:00Z
signerKeyId: provider-qualification-2026-q3
signature: base64:...
```

`providerEndpointSha256` covers the normalized scheme, URL host, effective port,
path prefix, protocol, endpoint-authentication mode, and relevant header names,
but not secret values. `networkProfileSha256` covers the mode, Network Zone
revision, trust-bundle digest, expected termination, and pool/connection policy.
The sidecar and external-vantage fields are mandatory only for sidecar
termination. Evidence is rejected when the runner and target network namespaces
are the same or when the isolation-manifest digest is absent.

The trusted runner signs the canonical result with a runner-held key. The
gateway verifies the signature against public keys loaded from a protected
runner trust store that is independent of the evidence database; the projection
may select an approved key ID but cannot introduce a new trusted key. Signature
verification happens before state, expiry, operations, model, capabilities,
endpoint identity, and transport identity checks. The existing self-digest
remains useful for canonical integrity but is not accepted as proof of producer
identity. Key rotation and revocation update the protected trust store and the
versioned publication together.

The correct workflow is to retain machine-owned evidence, implement the live
runner, and expose at most read-only status and diagnostics in Portal. A home
operator should not edit conformance JSON, sign results, or choose a supported
runtime version; registration triggers the automated checks.

Live transport and protocol qualification must cover:

- certificate chain and hostname validation for `private_tls`;
- an explicit private-HTTP connection when `private_plaintext` is selected;
- exact method/path exposure;
- the expected sidecar profile, configuration digest, certificate identity, and
  locally served identity response;
- failure to reach the raw runtime port from a recorded external vantage,
  together with loopback/admission isolation evidence;
- streaming and disconnect behavior;
- body and response bounds;
- float/base64 embedding behavior;
- usage reporting and ambiguous accounting;
- warmup, cold restart, declared concurrency, queue saturation, and timeout
  behavior;
- sidecar restart and certificate rotation; and
- rejection before provider dispatch when the expected embedding space does
  not match.

## Control-Plane Changes

### Portal Resources

Add or extend strongly typed resources for:

- Provider Network Profile;
- Network Zone;
- TLS Trust Bundle reference;
- typed endpoint and sidecar-runtime authentication;
- physical runtime and capacity domain;
- local runtime capacity, warmup, and timeout declaration;
- local pricing basis; and
- expected sidecar profile identity.

Provider Deployment creation must offer only profiles and zones authorized for
the current host and environment. Global platform model authorities may publish
platform-owned profiles for global knowledge-base workloads.

The UI must not offer `verify hostname = false`. It should display the resolved
security posture, certificate owner, network zone, and any plaintext risk
accepted by the operator.

### Publication

The immutable projection carries identifiers, versions, policy, DNS names,
ports, address constraints, material digests, and approved runner key IDs. It
cannot introduce runner public keys, and it never carries private keys. Trust
bundles may be delivered through the existing secret/config mechanism or
resolved from a protected
runtime mount, but their digest and version are bound to the publication and to
provider-client reuse.

The compiler rejects:

- unknown network-profile modes;
- a scheme inconsistent with its profile;
- public HTTP;
- a private destination without an approved zone;
- plaintext plus a credential;
- TLS whose URL host, zone policy, and trust policy cannot perform normal
  hostname or IP-SAN verification;
- address or port constraints that do not contain the endpoint;
- missing, zero, or policy-exceeding pool idle and client refresh intervals;
- deployment concurrency above declared runtime parallelism;
- protected lanes that share a capacity domain;
- a fallback route that violates the Alias data-residency requirement;
- unsigned, expired, or endpoint/profile/runtime-mismatched live evidence;
- a sidecar profile without matching signed identity, isolation-manifest, and
  distinct external-vantage evidence; and
- duplicate registration of one physical runtime through a weaker endpoint.

### Clean Cutover

Because projection structures are deny-unknown-fields and digest-bound, this is
a coordinated control-plane and gateway contract change. Reuse the established
publication cutover procedure:

1. retain the complete pre-cutover artifact set;
2. stop publication while mixed schemas could be emitted;
3. deploy readers and writers that understand the new contract;
4. publish one complete root with regenerated conformance evidence;
5. assert the expected generation and digest on every replica; and
6. pair binary rollback with restoration of the previous records.

## Runtime Failure Semantics

| Condition | Classification | Retry behavior |
| --- | --- | --- |
| Unknown or invisible Alias | Client-visible not found | Do not retry another provider |
| Profile or expected-space mismatch | Client-visible unsupported feature | Do not dispatch |
| No permitted DNS answer or connected peer outside the network zone | Configuration/security invariant | Quarantine deployment; do not retry it |
| Invalid, expired, or hostname-mismatched certificate | Configuration/security invariant | Quarantine deployment and alert |
| Sidecar or physical-runtime identity mismatch | Configuration/security invariant | Quarantine deployment and require new signed qualification |
| Model cold, evicted, or warming | Deployment not ready | Do not send user traffic; run bounded warmup before eligibility |
| Declared local queue or concurrency exhausted | Capacity exhausted | Apply normal bounded eligible fallback; do not extend the request deadline |
| Sidecar temporarily unavailable | Provider unavailable | Normal bounded fallback to an eligible compatible deployment |
| Sidecar returns a protocol-invalid body | Provider conformance failure | Fail safely and quarantine according to policy |

Certificate failures must not be hidden as ordinary congestion. Audit and
metrics identify the public deployment and network profile without exposing
private keys, prompts, vectors, or unnecessary internal topology.

## Observability

Record or expose:

- network profile mode and termination type;
- publication generation and deployment identifier;
- TLS protocol and certificate expiry bucket;
- resolved trust-bundle digest and endpoint-authentication version, not their
  contents;
- handshake, hostname, peer-address, network-zone, and workload-authentication
  failures;
- sidecar profile version and non-secret configuration digest;
- sidecar availability, latency, response-size, timeout, and retry metrics;
- conformance state for every physical endpoint; and
- warmup state, queue saturation, declared versus observed parallelism, and
  capacity-domain health, without placing provider-specific operational details
  in the OpenAI-compatible response.

Never log request bodies, embedding vectors, provider credentials, certificate
private keys, or full authorization headers.

## Deployment Examples

### Ollama With Light Gateway

```text
Kubernetes Pod
├── light-gateway
│   ├── listens on 0.0.0.0:8443 with enterprise TLS
│   └── proxies approved /v1 paths to 127.0.0.1:11434
└── Ollama
    └── listens only on 127.0.0.1:11434
```

The Provider Deployment uses an OpenAI-compatible provider protocol and a URL
such as:

```text
https://ollama-embedding.models.svc.corp.example:8443/v1
```

Ollama's native `/api` administration and model-management surface is not
published through the sidecar.

Containers in one Kubernetes Pod share a network namespace. Kubernetes
NetworkPolicy cannot mediate the sidecar-to-runtime loopback hop. The boundary
therefore depends on Ollama binding only to `127.0.0.1` (for example through
`OLLAMA_HOST`), the Pod containing no unrelated or untrusted container, and no
Service publishing the raw runtime port. `hostNetwork: true` is forbidden for
this profile because it defeats the intended loopback boundary. Admission
policy validates these conditions, and live qualification proves the raw port
is unreachable from another workload.

### llama.cpp Native TLS

An OpenSSL-enabled `llama-server` may terminate TLS itself. The Provider
Deployment uses `termination: native`, its private CA, and the service DNS name.
Use the Light Gateway sidecar instead when the organization wants centralized
certificate rotation, consistent authentication, or a smaller exposed runtime
surface.

### vLLM Native TLS Or Sidecar

vLLM may use its SSL certificate, key, and CA settings directly. A sidecar
remains valid where the organization wants centralized certificate rotation,
consistent authorization, or a smaller exposed runtime surface.

### Runtime-Specific Qualification Checks

Runtime releases and OpenAI-compatible shims evolve, so these are probes rather
than a supported-version allowlist:

| Runtime | Live qualification must not assume |
| --- | --- |
| Ollama | Requested embedding dimensions, `encoding_format: base64`, usage fields, batch ordering, model keep-alive, or parallel request behavior work merely because the route exists. |
| `llama-server` | TLS build options, chat-template behavior, streaming framing, embedding batching, and usage reporting are identical across builds. |
| vLLM | GPU admission, queue behavior, streaming setup, embedding dimensions/encoding, and usage reporting match cloud OpenAI behavior without probing. |

Failed probes produce operation- or capability-specific diagnostics so an
operator can correct the runtime configuration without manually editing
evidence.

## Security Analysis

### Threats Addressed

- Passive or active interception of prompts, knowledge text, and vectors across
  the organizational network.
- Accidental provider credential disclosure over plaintext by requiring
  `endpointAuth.mode: none` for `private_plaintext`.
- SSRF to internal services or cloud metadata endpoints.
- DNS rebinding from an approved name to an unapproved address.
- Bypassing the sidecar through the raw model port.
- Exposure of model-management or debug endpoints.
- Caller-controlled provider selection or forwarding headers.
- Silent fallback from an approved local model to an incompatible or
  disallowed provider.

### Residual Risks

- A compromised model host can observe plaintext after TLS termination.
- A compromised sidecar can observe prompts and vectors in memory.
- Private CA compromise affects every endpoint using that trust authority.
- Local model drift can violate output or embedding semantics without strong
  conformance and model-artifact evidence.
- A shared GPU or provider account can still cause workload starvation unless
  query, indexing, and standard traffic use qualified capacity isolation.

These risks require host hardening, workload identity, least-privilege network
policy, model-artifact provenance, and the existing KB embedding-stability gate.

## Alternatives Considered

### Allow All HTTP Provider URLs

Rejected. It exposes credentials and data and turns a provider configuration
surface into unrestricted internal-network access.

### Use `developmentFixtures` In Production

Rejected. It is a broad testing bypass rather than a reviewed production trust
contract and weakens unrelated validation.

### Require Native TLS From Every Runtime

Rejected. It excludes widely used local runtimes and duplicates certificate
operations across model-serving products. The Light Gateway sidecar provides a
consistent supported boundary.

### Put TLS Only At A Distant Shared Ingress

Rejected as the default. If the ingress-to-model hop crosses the network in
plaintext, the sensitive portion remains exposed. Terminate TLS on the model
host or in the model pod when the applicable policy requires encryption.

### Treat Network Isolation As Equivalent To TLS

Rejected as the general rule. Private networks reduce exposure but do not
authenticate the model endpoint or protect against every internal observer.

## Delivery Plan

### Phase L1: Contract And Compiler

- Define the Network Profile, Network Zone, resolved trust-bundle,
  endpoint-authentication, sidecar-runtime-authentication, sidecar identity,
  physical-runtime, capacity-domain, readiness, timeout, and pricing-basis
  contracts.
- Extend `ConformanceResult` with evidence kind, deployment revision, endpoint,
  transport, physical-runtime, capacity, sidecar, signer, and signature binding.
- Thread the complete shapes through Portal DB, commands, projection, runtime
  configuration, client-reuse digest generation, signature verification, and
  audit.
- Preserve `public_tls` as the default and current behavior.
- Add publication-time scheme, address, port, credential, identity, capacity,
  pricing, conformance, and fallback checks.
- Preserve worst-case paid-fallback reservation and make the ambiguous-usage
  minimum-charge floor conditional on a non-zero reserved envelope.

### Phase L2: Private TLS Client

- Add per-endpoint private CA loading to `llm-gateway` and bind the resolved PEM
  digest to provider-client reuse.
- Derive verification name and SNI from the URL host; keep hostname verification
  and redirects fixed to safe values.
- Replace the public/private boolean with a Network-Zone-aware resolver and
  connector that filter DNS answers and validate the connected peer.
- Set explicit pool idle behavior, recycle same-material clients on the bounded
  DNS refresh interval, and rebuild immediately on material changes.
- Add certificate rotation and deployment quarantine behavior.

### Phase L3: Model Provider Sidecar

- Add a generated and documented `model-provider-sidecar` Light Gateway
  profile.
- Register terminal `sidecar-deny` and `sidecar-identity` IDs in
  `GATEWAY_HANDLER_DESCRIPTORS` and implement both dispatch arms. Make the exact
  path/method allowlist, mirrored authentication paths, and profile-validated
  terminal deny chain mandatory.
- Add endpoint-credential removal, separate runtime-credential injection,
  fixed health, and identity attestation. Keep both exact authenticated paths on
  the inference listener; the separate operations listener is deferred.
- Add Kubernetes admission guidance for loopback binding, no `hostNetwork`, no
  raw-port Service, and no unrelated container in the Pod.
- Add generated-profile integration tests proving administrative paths, wrong
  methods, and undeclared operations return a local 404 without an upstream
  connection.
- Qualify streaming, body limits, timeouts, disconnects, and header handling.

### Phase L4: Provider Qualification

- Qualify Ollama behind the sidecar.
- Qualify native-TLS and sidecar modes for llama.cpp and vLLM.
- Implement the signed live deployment runner, runner-key rotation, gateway-side
  signature verification, and read-only Portal status.
- Bind results to the exact endpoint, Network Profile, deployment revision,
  physical runtime, capacity declaration, and sidecar identity.
- Record the runner's external vantage and bind a failed raw-port probe to
  loopback/admission isolation evidence. Exercise warmup, cold start,
  concurrency, queue saturation, and local timeout behavior.
- Record runtime versions when available for diagnostics, but do not enforce a
  supported-version allowlist.
- Validate Chat, Responses, and Embeddings independently; do not infer support
  for one operation from another.

### Phase L5: Production Exercise

- Rotate CA and server certificates without downtime.
- Exercise DNS changes, expired certificates, invalid SANs, sidecar restart,
  model restart/eviction, trust-bundle client rebuild, fallback, and quarantine.
- Verify no prompt, KB text, vector, or credential appears in logs or evidence.
- Measure embedding query latency separately from indexing throughput.
- Prove indexing cannot starve protected query capacity by concurrently loading
  disjoint capacity domains.
- Exercise zero-price local routing followed by paid fallback and prove the paid
  worst-case envelope is reserved before dispatch.
- Assert an ambiguous accepted result with `zero_marginal` pricing has
  `reserved == 0`, `charged == 0`, and `usageComplete: false` for generation and
  embedding.
- Promote a KB index only after the Embedding Space Contract is verified through
  every eligible local deployment.

## Acceptance Criteria

1. An Ollama deployment may use an HTTPS Light Gateway sidecar or an explicitly
   approved, credential-free `private_plaintext` connection.
2. When a sidecar is selected, the raw Ollama or model-runtime port is
   loopback-bound and unpublished. Signed live qualification verifies it from a
   recorded, distinct external network namespace and binds the result to
   admission or manifest isolation evidence.
3. Public HTTP, unapproved private destinations, metadata addresses, redirects,
   DNS rebinding, and an out-of-zone connected peer are rejected before provider
   dispatch. Same-material clients and pools are recycled within the published
   DNS refresh interval; material changes rebuild them immediately.
4. Private TLS validates the configured CA and URL host; an independent SNI or
   verification-name override and invalid-certificate bypass are unavailable.
5. Private HTTP is available only by explicit operator choice within a Network
   Zone that permits it, requires `endpointAuth.mode: none`, and can be disabled
   by enterprise policy.
6. Only approved OpenAI-compatible inference methods and paths reach the
   sidecar proxy; unmatched paths, wrong methods, runtime administration, and
   runtime metrics are denied locally by a dedicated terminal handler and
   generated-profile tests.
7. The public `/v1/chat/completions`, `/v1/responses`, and `/v1/embeddings`
   contracts do not change.
8. Local pricing declares `zero_marginal` or `amortized_internal`; paid fallback
   is included in the pre-dispatch budget envelope, while physical limits are
   enforced independently by capacity admission. Ambiguous zero-price usage
   records zero reserved and charged micro-units with incomplete usage.
9. Every local physical deployment has runner-signed, current protocol and
   transport evidence bound to its published endpoint, deployment revision,
   Network Profile, physical runtime, capacity declaration, and sidecar identity
   when applicable. Sidecar raw-port evidence records a distinct external runner
   vantage and an isolation-manifest digest.
10. Every embedding fallback has the same immutable Embedding Space Contract.
11. Gateway concurrency does not exceed qualified runtime parallelism, cold
    models are warmed before eligibility, and protected lanes do not share a
    capacity domain.
12. A trust-bundle digest change rebuilds every affected client and drops its
    old connection pool before the publication is acknowledged.
13. Certificate rotation, runner-key rotation, and paired control-plane rollback
    are rehearsed.
14. Logs, metrics, errors, and conformance evidence contain no prompt text,
    vectors, credentials, or private keys.

## Resolved Design Decisions

- mTLS is optional and deferred; it is not required for the first release.
- Service-mesh-specific transport is not part of the first release.
- A separate sidecar operations listener and sidecar metrics endpoint are
  deferred. Exact authenticated health and identity paths remain on the
  inference listener in the first release.
- Network Zone is a reusable, administrator-owned Portal resource compiled into
  the gateway snapshot.
- Network Profile belongs to the materialized Provider endpoint. Deployments
  sharing a `providerId` share that complete endpoint configuration.
- A private CA bundle is resolved from managed configuration by versioned
  reference and verified against a published digest; PEM and private keys are
  not repeated in deployment projections. The resolved digest is part of
  provider-client reuse identity.
- An operator may select private HTTP to another computer when the selected
  Network Zone permits it. It is credential-free in the first release, and
  enterprise policy may prohibit it.
- The URL host is the TLS verification name and SNI value. Private-TLS IP
  literals require an IP SAN; no independent `tls.serverName` is exposed.
- Sidecar endpoint credentials and sidecar-to-runtime credentials are separate
  typed slots and are never carried together in provider extra headers.
- The generated sidecar uses dedicated terminal `sidecar-deny` and
  `sidecar-identity` handlers. The existing fixed `health` handler remains a
  liveness response and is not identity evidence.
- Physical runtime and capacity-domain identities are immutable, live-qualified
  routing inputs. Protected workload lanes must not share a capacity domain.
- Local prices explicitly distinguish zero marginal cost from amortized internal
  chargeback, and any paid fallback is reserved before the first attempt.
- Provider runtime versions are diagnostic evidence, not an allowlist. Actual
  protocol and capability behavior determines qualification.
- Conformance evidence is machine-owned. Portal may show read-only status but
  does not allow administrators to edit results; the runner signs live evidence
  and the gateway verifies producer authenticity and endpoint binding.

## References

- [Ollama OpenAI compatibility](https://docs.ollama.com/api/openai-compatibility)
- [Ollama network and proxy guidance](https://docs.ollama.com/faq)
- [llama.cpp server documentation](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md)
- [vLLM serve TLS options](https://docs.vllm.ai/en/latest/cli/serve/)
- [LLM Gateway Topology Per Host And Environment](../light-portal/llm-gateway-topology.md)
- [Global And Tenant Knowledge Bases For Shared Agent Retrieval](../light-portal/knowledge-base.md)
