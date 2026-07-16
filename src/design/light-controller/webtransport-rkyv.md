# Configurable Controller Transport and Codec Profiles

## Status

This document defines a layered controller communication architecture in which
application semantics, serialization, framing, transport, and gateway routing
are separate decisions. It covers both the Rust runtime control channel and the
browser MCP path through `light-gateway`.

- **Status:** proposed architecture; Phase 0 completed with a no-go result, the
  separately justified WebSocket-only Phase 1 extraction is complete, and the
  inactive shared wire-profile/conformance foundation is implemented
- **Protocol baseline tested:** 2026-07-15
- **Implementation gate:** WebTransport implementation remains blocked until a
  future Phase 0 rerun satisfies the browser, native-library, and current-draft
  contracts
- **Controller:** `controller-rs`
- **Rust runtime client:** `light-fabric/crates/portal-registry`
- **Browser client:** `portal-view`
- **Gateway/BFF:** `light-fabric/apps/light-gateway`
- **Existing compatibility paths:** MCP-style JSON-RPC over WebSocket and
  runtime JSON-RPC over WebSocket
- **Experimental transports and codecs:** WebTransport and `rkyv`
- **Out of scope:** metrics ingestion, distributed controller state, browser
  `rkyv`, and automatic translation between different transports or codecs

WebTransport remains disabled. WebSocket and JSON remain the defaults until a
future feasibility run satisfies protocol compatibility, browser
authentication, gateway routing, deployment support, and performance gates.

## Problem

Rust services currently connect to `controller-rs` through
`/ws/microservice`. The channel carries JSON-RPC messages for:

- `service/register` and its acknowledgement;
- `service/update_metadata`;
- discovery lookup and subscriptions;
- controller-to-runtime commands;
- runtime-to-controller command responses;
- runtime notifications such as `notifications/log`;
- liveness messages.

The browser separately connects to `/ctrl/mcp` on `light-gateway`. The gateway's
WebSocket router authenticates and resolves the target during the HTTP/1 upgrade,
then Pingora tunnels the upgraded connection to `controller-rs` without parsing
MCP messages.

Both paths currently bind several independent choices together:

- MCP and runtime-control application semantics;
- JSON-RPC serialization;
- WebSocket message framing;
- TCP/TLS transport;
- gateway routing and authentication.

That coupling makes it difficult to determine whether a measured improvement
comes from QUIC multiplexing, a binary codec, or both. It also makes a future
browser WebTransport path appear to require `rkyv`, although the browser should
continue to use MCP JSON.

The current runtime channel is reliable and portable, but all messages in one
direction share one ordered WebSocket byte stream and JSON parsing. A
high-volume runtime notification can therefore delay a command response
traveling in the same service-to-controller direction.

The commonly cited example of an inbound log blocking an outbound controller
command is not precise. TCP is full-duplex: runtime logs travel toward the
controller while the command request travels toward the runtime. The risk that
must be measured is same-direction queueing, especially command responses
sharing the runtime's outbound path with log notifications.

The design must not assume that WebTransport or `rkyv` is faster for this
workload. Registration also includes JWT validation and persistence, and many
command results contain arbitrary JSON. Benchmarks must vary transport and
codec independently so the source of any improvement is measurable.

## Current Boundaries

The current end-to-end surfaces are:

| Surface or hop | Current protocol | Purpose |
| --- | --- | --- |
| Browser to `light-gateway` `/ctrl/mcp` | MCP-style JSON-RPC over WebSocket | Browser administrative calls and notifications |
| `light-gateway` to `controller-rs` `/ctrl/mcp` | Payload-opaque WebSocket tunnel | Route the authenticated browser session to the controller |
| Runtime to `controller-rs` `/ws/microservice` | JSON-RPC over WebSocket | Registration, discovery, commands, responses, and notifications |
| Discovery client to `controller-rs` `/ws/discovery` | JSON-RPC over WebSocket | Standalone discovery subscriptions |

This proposal keeps every existing endpoint and payload contract. It adds an
experimental WebTransport binding for runtime control and defines a future MCP
JSON binding through a WebTransport-aware gateway router. `/ws/discovery`
remains WebSocket-only in the initial implementation.

MCP remains the external command surface and JSON-RPC message contract. `rkyv`
is a serialization codec for the private Rust runtime-control profile; it is not
a replacement encoding for standard MCP clients.

The private Rust runtime-control profile includes registration, registry and
discovery operations carried on that controller connection, commands,
responses, and runtime notifications. It does not change general application
service-to-service APIs. Standalone discovery clients and non-Rust controller
clients remain on their explicitly supported JSON profiles unless a later
design adds another interoperable codec.

The existing `ServiceMetadata.protocol` field describes the runtime's
advertised application protocol, such as `https`. It must not be reused to
record the controller connection transport or wire codec.

## Layered Model

The implementation separates five layers:

```text
MCP handlers or runtime-control handlers
  -> logical requests, responses, notifications, and lifecycle events
  -> negotiated wire profile and codec
  -> message framing and logical channel mapping
  -> WebSocket or WebTransport session adapter
  -> optional light-gateway route resolver and transport proxy
```

The terms used by this document are:

- **Application protocol:** MCP or the private runtime-control protocol.
- **Codec:** JSON-RPC/JSON or the versioned `rkyv` wire schema.
- **Wire profile:** the complete application message contract, codec, framing,
  validation rules, limits, and version. A profile does not select a transport.
- **Transport:** WebSocket or WebTransport.
- **Router:** a gateway component that authenticates the incoming session,
  selects an upstream, and proxies the selected transport.

Transport configuration selects how a session is carried. Protocol negotiation
selects how its bytes are interpreted. A server accepts only explicitly allowed
profile and transport pairs; configurability does not imply support for every
Cartesian product.

### Supported Profile Matrix

| Surface | Wire profile | Codec | WebSocket | WebTransport | Initial decision |
| --- | --- | --- | --- | --- | --- |
| Browser MCP | `light-controller-mcp-json-v1` | JSON-RPC | Existing, required | Experimental after gateway and auth work | Preserve MCP interoperability |
| Runtime control | `light-controller-runtime-json-v1` | JSON-RPC | Existing, required | Experimental | Required to measure transport independently |
| Runtime control | `light-controller-runtime-rkyv-v1` | `rkyv` | Experimental binary frames | Experimental | Rust-only optimized candidate |
| Browser MCP | Any `rkyv` profile | `rkyv` | Not supported | Not supported | Browser binary MCP is out of scope |
| Standalone discovery | Existing JSON-RPC | JSON-RPC | Existing, required | Not initially supported | No change in the first release |

The current WebSocket paths predate profile negotiation. Absence of a profile
token on those paths means the existing JSON behavior. New binary behavior
requires an explicit negotiated token and must never be inferred from the first
payload bytes.

## Goals

- Make transport and codec selection independent while preserving allowlisted
  combinations.
- Add a multiplexed Rust-to-Rust control transport without removing the current
  WebSocket contract.
- Define MCP JSON over WebTransport without requiring browser `rkyv`.
- Reuse gateway route resolution, discovery, authorization, and limits without
  treating the current HTTP/1 upgrade tunnel as a WebTransport implementation.
- Keep controller business behavior identical across transports and codecs.
- Isolate controller commands and their responses from asynchronous runtime
  notifications.
- Use a validated, explicitly versioned `rkyv` format for stable Rust wire
  types.
- Support rolling upgrades where old Rust clients and all Java clients continue
  to use WebSocket.
- Configure accepted transports per controller surface so browser MCP, Rust
  runtime control, and standalone discovery can evolve independently.
- Let `portal-view` discover the gateway's current end-to-end MCP candidates at
  runtime instead of baking deployment readiness into the UI bundle.
- Bound memory, stream concurrency, message size, and validation work before
  accepting untrusted input.
- Provide explicit rollout, fallback, observability, and rollback behavior.
- Measure JSON over WebTransport and `rkyv` over WebSocket so codec and transport
  effects are isolated.
- Require measured improvement before changing any default.

## Non-Goals

- Do not replace `/ctrl/mcp` or its JSON-RPC payload contract.
- Do not describe a private `rkyv` encoding as standard MCP.
- Do not implement browser-side `rkyv` or require a WebAssembly decoder.
- Do not translate WebSocket to WebTransport or JSON to `rkyv` in the first
  gateway implementation.
- Do not require every allowed codec to use every transport.
- Do not require Java or other non-Rust runtimes to implement `rkyv`.
- Do not send general metrics or traces to `controller-rs` in the first release.
- Do not claim zero allocation or zero head-of-line blocking.
- Do not solve multi-replica command routing in this change.
- Do not automatically switch an established session between transports.
- Do not infer WebTransport availability from the HTTP version used to load the
  page or an unrelated UI resource.
- Do not use unchecked `rkyv` access for network data.
- Do not enable WebTransport by default in production deployments.

## Options Considered

| Option | Advantages | Costs and risks | Decision |
| --- | --- | --- | --- |
| Keep WebSocket and JSON | No deployment or compatibility change | Retains one ordered stream per direction and JSON overhead | Remains the baseline and fallback |
| JSON over WebTransport | Isolates transport effects and supports browser MCP without a new codec | Retains JSON parsing and requires UDP/HTTP3 deployment | Required experimental profile |
| Binary WebSocket frames with `rkyv` | Isolates serialization changes; works through current infrastructure | Does not provide independent streams; still Rust-specific | Required benchmark comparison |
| Multiple WebSocket connections | Separates control and high-volume events using mature infrastructure | More connection lifecycle and authentication state | Viable fallback if multiplexing is the only requirement |
| Raw QUIC with `rkyv` | Stable QUIC RFCs; simpler for native Rust peers | No WebTransport session semantics or future browser compatibility | Required design-spike comparison |
| WebTransport with `rkyv` | Independent streams, datagram capability, and HTTP/3 session model | Active draft, immature implementations, UDP deployment work | Rust runtime opt-in experiment |
| Protobuf over WebSocket or QUIC | Strong polyglot tooling and defined schema evolution rules | Parsing and generated-code cost; not zero-copy | Preferred alternative if polyglot use expands |
| Dedicated telemetry pipeline | Keeps control-plane load isolated; uses OTLP, Prometheus, or another telemetry protocol | Separate service and operational path | Preferred for metrics and traces |

WebTransport is justified only if independent streams, HTTP/3 integration, or
browser support provide value beyond raw QUIC or multiple WebSockets. The
runtime implementation spike must compare those alternatives rather than
treating WebTransport plus `rkyv` as one indivisible decision.

## Decision

Implement the layered profile model with these constraints:

1. Keep `/ws/microservice` unchanged, enabled by default, and available throughout
   migration. It may be disabled for the runtime surface only after that surface's
   client-fleet and network compatibility gates pass.
2. Keep `/ctrl/mcp` as MCP-style JSON-RPC regardless of transport.
3. Add `https://<controller-authority>/wt/microservice` over HTTP/3 and QUIC and
   support both runtime JSON and runtime `rkyv` profiles on it.
4. Permit the runtime `rkyv` profile over WebSocket binary frames for isolation
   testing, without changing the legacy JSON default.
5. Add browser MCP over WebTransport only after the gateway router and browser
   ticket-authentication flow pass their release gates.
6. Negotiate one immutable wire profile before decoding non-legacy payloads.
7. Use reliable streams for all initial WebTransport behavior; datagrams remain
   disabled.
8. Preserve the current `ControllerCommand` correlation, timeout, response, and
   connection-ID-guarded cleanup semantics inside `controller-rs`. The bounded
   admission controls in this design intentionally replace unbounded pending-state
   admission; preserving semantics does not mean preserving the absence of those
   limits.
9. Keep arbitrary tool arguments and results as bounded UTF-8 JSON bytes
   where the existing runtime contract is dynamic.
10. Keep the gateway payload-opaque in the initial WebTransport implementation;
    cross-transport and cross-codec translation require a separate decision.
11. Advance beyond experimental status only after compatibility, security,
    deployment, and benchmark gates pass.

## High-Level Architecture

```text
browser MCP path
  portal-view
    -> MCP JSON codec
    -> selected WebSocket or WebTransport adapter
    -> light-gateway matching transport router
    -> same transport and MCP JSON profile
    -> controller-rs /ctrl/mcp
    -> CommandRouter

runtime control path
  light-fabric portal-registry
    -> logical runtime-control messages
    -> selected JSON or rkyv codec
    -> selected WebSocket or WebTransport adapter
    -> controller-rs shared registration and command services

controller command path
  CommandRouter
    -> ControllerCommand channel
    -> selected live runtime session driver
```

The transport drivers must call the same controller service functions for:

- JWT identity checks;
- registration persistence;
- instance insertion and removal;
- portal and discovery notifications;
- metadata updates;
- pending-command completion and timeout handling;
- disconnect cleanup.

Transport- or codec-specific code must not duplicate those business rules.

## Gateway and BFF Routing

The current `light-gateway` WebSocket router is a payload-opaque HTTP/1 upgrade
proxy. It resolves a service from headers, query parameters, or path-prefix
configuration, applies authorization and connection limits, selects a discovered
upstream, and lets Pingora tunnel the upgraded connection. It does not terminate
MCP or translate JSON-RPC messages.

The WebTransport router should preserve that payload-opaque property, but it
cannot reuse the HTTP/1 tunnel implementation. It needs an HTTP/3/QUIC listener
and must act as a WebTransport server toward the browser and as a WebTransport
client toward `controller-rs`.

The reusable gateway boundary is a transport-neutral route resolver containing:

- path-prefix, header, and query-based service selection;
- discovery and direct-registry target selection;
- authentication and access-control decisions;
- connection and admission limits;
- routing-header cleanup, metrics, and reload behavior.

The WebSocket and WebTransport routers use that resolver but own separate
listener, handshake, timeout, and proxy state. The initial WebTransport router:

1. accepts an authenticated WebTransport CONNECT request;
2. selects the controller using the shared route resolver;
3. opens an upstream WebTransport session using the same wire profile;
4. maps the downstream MCP or runtime-control stream to its upstream peer;
5. maps each additional reliable stream with the same direction and role;
6. propagates backpressure, stream resets, draining, and session close reasons;
7. rejects datagrams because version 1 does not define a datagram mapping.

Path-based routing, BFF authentication, and profile negotiation are encrypted
inside HTTP/3, so a generic UDP forwarder cannot replace this router. A pure
QUIC layer-4 path is acceptable only for deployments with a fixed upstream that
do not need BFF policy or path-based service selection.

For the first implementation, transport must match across the gateway:

```text
WebSocket client -> WebSocket router -> WebSocket controller endpoint
WebTransport client -> WebTransport router -> WebTransport controller endpoint
```

Supporting WebSocket-to-WebTransport, WebTransport-to-WebSocket, JSON-to-`rkyv`,
or `rkyv`-to-JSON would turn the gateway into an application relay. That requires
message decoding, identity and cancellation mapping, independent buffering on
both sides, and a separate design and benchmark.

The current Pingora integration has no HTTP/3 or QUIC listener. The experimental
WebTransport service therefore runs alongside the existing Pingora TCP service
and shares only routing, policy, configuration, and observability components.
It must not delay or destabilize the existing HTTPS/WebSocket listener when the
feature is disabled or fails to initialize.

## Browser Transport Capability Discovery

The browser cannot discover the controller transport directly. It can detect
its local WebTransport API, but it cannot infer the selected controller, the
gateway-to-controller transport, enterprise UDP policy, or current route
readiness. `light-gateway` therefore exposes an authenticated HTTPS capability
resource on the controller BFF authority. That authority is same-origin by
default and is resolved as defined in [Browser BFF Authority](#browser-bff-authority):

```http
GET /ctrl/mcp/capabilities
```

An example response is:

```json
{
  "revision": "gw-42:controllers-17",
  "generatedAt": "2026-07-15T14:00:00Z",
  "expiresAt": "2026-07-15T14:00:30Z",
  "wireProfile": "light-controller-mcp-json-v1",
  "policy": "preferWebTransport",
  "candidates": [
    {
      "transport": "webtransport",
      "endpoint": "/ctrl/mcp",
      "ticketEndpoint": "/ctrl/mcp/ticket",
      "ready": true
    },
    {
      "transport": "websocket",
      "endpoint": "/ctrl/mcp",
      "negotiation": "legacy",
      "ready": true
    }
  ],
  "maxAgeSeconds": 30
}
```

`revision` is an opaque aggregate revision that changes whenever gateway policy,
listener or router readiness, the eligible target set, or any target's controller
capability revision changes. `generatedAt` and `expiresAt` use UTC. The gateway
also returns `ETag: "<revision>"`. Version 1 always returns a complete `200`
representation after HTTP-cache expiry rather than a bodyless `304`, because the
body carries an absolute expiry. Conditional revalidation requires a later
contract for refreshing that absolute expiry without retaining a stale body.

The response is gateway-derived deployment state, not a copy of browser feature
detection or raw controller configuration. A candidate is `ready` only when:

- the corresponding gateway listener and router are enabled and healthy;
- authentication, ticket issuance when applicable, and the allowed wire
  profile are configured;
- the shared route resolver has a healthy controller target that accepts the
  same transport and profile; and
- a recent same-transport synthetic probe has verified the gateway-to-controller
  leg.

Controller support is not inferred from route naming, a generic health response,
or deployment-wide configuration. Every controller instance exposes an
authenticated internal capability resource over its existing HTTPS listener:

```http
GET /internal/controller/capabilities
```

It returns `instanceId`, an opaque `revision`, generation and expiry timestamps,
listener readiness, and the enabled transport/profile set for each of `mcp`,
`runtime`, and `standaloneDiscovery`. It also reports draining state. The
revision changes whenever startup configuration, listener readiness, or draining
state changes; a process restart creates a new `instanceId`. For example:

```json
{
  "schemaVersion": 1,
  "instanceId": "controller-7f8c",
  "revision": "17",
  "generatedAt": "2026-07-15T14:00:00Z",
  "expiresAt": "2026-07-15T14:00:15Z",
  "draining": false,
  "listeners": {
    "websocket": { "ready": true },
    "webtransport": { "ready": true }
  },
  "surfaces": {
    "mcp": [
      {
        "transport": "websocket",
        "wireProfiles": ["light-controller-mcp-json-v1"]
      },
      {
        "transport": "webtransport",
        "wireProfiles": ["light-controller-mcp-json-v1"]
      }
    ],
    "runtime": [
      {
        "transport": "websocket",
        "wireProfiles": ["light-controller-runtime-json-v1"]
      },
      {
        "transport": "webtransport",
        "wireProfiles": [
          "light-controller-runtime-json-v1",
          "light-controller-runtime-rkyv-v1"
        ]
      }
    ],
    "standaloneDiscovery": [
      {
        "transport": "websocket",
        "wireProfiles": ["light-controller-runtime-json-v1"]
      }
    ]
  }
}
```

Unknown schema versions, expired responses, duplicate combinations, a transport
whose listener is not ready, or a draining instance are ineligible for new
sessions. The resource is available only to the gateway through the deployment's
approved service credential or mTLS identity; browser credentials and browser
connection tickets are not accepted.

For each candidate, the gateway intersects that instance declaration with its
own policy and route configuration, then runs a bounded transport-native probe
against a dedicated gateway-authenticated probe resource on the same controller
listener. The probe requests one surface and wire profile, completes transport
and profile negotiation, returns the controller capability revision, and closes.
It does not register a runtime, create an MCP session, enqueue a command, or
mutate controller state. Probe credentials, intervals, timeouts, concurrency,
and logs are bounded and independently configurable.

Because the first gateway implementation does not relay across transports, it
must never advertise a WebSocket candidate backed only by a WebTransport
controller endpoint, or the reverse. During a rolling controller upgrade, the
gateway builds a candidate-specific eligible target pool from per-instance
capability and probe results. It advertises the candidate only when that pool is
non-empty and pins each accepted session to a target from that pool for the
session lifetime. An instance that becomes stale, unready, or draining is removed
from new-session selection and changes the aggregate capability revision; an
existing session follows the draining rules rather than being silently moved to
another target.

The response uses `Cache-Control: private, max-age=30` or a shorter configured
value and `Vary: Origin, Cookie` where those fields affect authorization or
candidate policy. `portal-view` refreshes it after a failed candidate attempt or
cache expiry. A normal refresh or an authenticated runtime configuration signal
may reveal a new aggregate revision; when it does, the client discards candidates
from the old revision. Capability discovery reduces expected failures but does
not replace the actual handshake; a network path can change after the response
is generated.

Capability-fetch failure does not authorize a blind transport attempt. In
`auto` mode:

- `401` or `403` is an authentication or authorization failure; do not try a
  transport and wait for the login state to change;
- a malformed or semantically invalid response is `Internal`; reject it and do
  not infer a candidate;
- timeout, network failure, `429`, or `5xx` may use a still-fresh previously
  validated capability response, but otherwise no session is attempted and the
  client retries discovery with the existing jittered exponential backoff; and
- `404` or `501` means the gateway does not implement capability discovery. The
  auto-mode UI fails closed; an explicitly forced `websocket` build override is
  the compatibility escape for an old gateway.

Deploy the capability resource before deploying an auto-mode UI that depends on
it. These rules prevent a transient gateway failure from silently weakening a
`requireWebTransport` policy or guessing that legacy WebSocket is acceptable.

### Browser BFF Authority

All browser controller resources use one controller BFF authority and ingress
path prefix. `portal-view` resolves it with the same shared helper for capability
fetch, ticket issuance, WebSocket, and WebTransport:

1. use the configured `VITE_API_BASE_URL`, including its path prefix, when it is
   non-empty; otherwise
2. use `window.location.origin` and the deployment's normal ingress prefix.

Capability and ticket requests remain HTTPS requests with `credentials:
include` and the existing CSRF rules. The WebSocket URL changes only the scheme
to `ws` or `wss`; the WebTransport URL remains `https`. Redirects to a different
authority are rejected for ticket issuance and WebTransport establishment.

Same-origin deployment is the version 1 production recommendation. A deployment
that intentionally uses a different API authority must explicitly provide all
of the following before browser WebTransport is ready:

- credentialed CORS for capability and ticket HTTPS requests with an explicit
  portal Origin, never `*`;
- compatible secure cookie Domain and `SameSite` attributes for the authenticated
  BFF requests;
- the existing CSRF validation on ticket issuance;
- an Origin allowlist for WebSocket and WebTransport establishment; and
- browser and integration tests covering the exact portal and API authorities.

If any cross-origin prerequisite is absent, capability readiness is false and
the UI fails closed instead of constructing URLs from mixed authorities.

The HTTP version used for the page navigation or an ordinary API request is not
a selection signal. A page loaded over HTTP/2 can open a separate HTTP/3
WebTransport session, while an HTTP/3 page load does not prove that WebTransport
CONNECT, ticket authentication, or the gateway-to-controller QUIC leg works.
`nextHopProtocol` may be recorded as bounded diagnostic context only.

The gateway may advertise HTTP/3 for ordinary HTTPS traffic, and the browser may
select it automatically. `portal-view` does not force the HTTP version of normal
fetches. Only the WebTransport session requires the HTTP/3/QUIC behavior defined
by this design through `requireUnreliable: true` and the resulting reliability
check.

## WebTransport Protocol Maturity

At the time of this design update, WebTransport over HTTP/3 is still an active
IETF Internet-Draft. Draft versions can use different HTTP/3 settings and wire
codepoints. The selected Rust library must be verified against the exact draft
implemented by both peers and any intermediary.

Generic HTTP/3 support is not sufficient. The current WebTransport draft also
requires extended CONNECT, WebTransport settings, HTTP/3 datagrams, QUIC
datagrams, and stream-reset support. End-to-end interoperability must be tested
through every supported load balancer or proxy.

The required Phase 0 interoperability target is
`draft-ietf-webtrans-http3-16`. The 2026-07-15 spike did not find a supportable
tuple for that target: the tested Rust crates use legacy WebTransport-over-HTTP/3
codepoints, and the tested Chrome did not implement the required CONNECT header,
selected-protocol, and reliability API contract. Draft 16 is therefore a target,
not a verified baseline. A future implementation must pin and record the exact
WebTransport draft, Rust library version, browser version, and intermediary
behavior in the release notes and compatibility matrix. A change to any of them
requires rerunning the interoperability gate.

## Endpoint and Wire Profile Negotiation

The WebTransport resources are:

```text
https://<controller-authority>/wt/microservice  # runtime control
https://<gateway-authority>/ctrl/mcp             # browser MCP through BFF
```

The corresponding controller-side MCP resource remains `/ctrl/mcp`. The path
identifies the application surface; it does not select JSON versus `rkyv`.

Clients offer one or more wire profiles such as:

```text
light-controller-mcp-json-v1
light-controller-runtime-json-v1
light-controller-runtime-rkyv-v1
```

For WebTransport, the client sends profiles through the draft's
`WT-Available-Protocols` header and the server confirms one with `WT-Protocol`.
Browser JavaScript supplies this offer with `WebTransportOptions.protocols`; it
must not attempt to set `WT-Available-Protocols` directly in
`WebTransportOptions.headers`. After `ready` resolves, the browser verifies that
the selected `transport.protocol` is the single expected MCP profile.

For new WebSocket profiles, the client and server use
`Sec-WebSocket-Protocol`. Existing JSON WebSocket clients that do not offer a
wire profile retain their current behavior. The existing browser CSRF value in
this header is authentication metadata, not a wire profile. The gateway uses
the following deterministic rules:

1. Parse all offered tokens instead of selecting the first token.
2. Extract and validate exactly one `csrf.<value>` token when the browser path
   requires it.
3. Remove the CSRF token before forwarding a negotiated profile offer upstream.
4. Forward only recognized, endpoint-allowed wire-profile tokens.
5. Return only the profile selected by the upstream controller for a negotiated
   session; never echo a CSRF token as the selected wire profile.
6. Preserve the current CSRF-only behavior for legacy browser clients that do
   not offer a wire profile.

A server rejects a new negotiated session when no common allowed profile exists
or when the selected profile is not permitted on that endpoint and transport.
An explicit negotiated candidate never treats an absent selected token as a
successful negotiation. Legacy JSON is represented by an explicit client
candidate with `negotiation: legacy`; it sends no wire-profile token and is the
only candidate allowed to accept the existing no-profile response.

The negotiated token selects the complete application wire profile, including:

- application semantics and codec;
- frame header layout;
- numeric message kinds;
- archived type definitions;
- `rkyv` version and format-control features;
- validation and size limits;
- logical channel roles and error semantics.

Transport-specific details such as WebSocket frames versus WebTransport streams
remain the responsibility of the session adapter. A profile token must not
encode `websocket` or `webtransport`; the same profile may be allowed on either
transport by server policy.

Supporting a new incompatible wire shape requires a new profile token. During a
rolling upgrade, the controller should support the current and immediately
previous wire-profile versions.

## Runtime Authentication and Registration

Every non-legacy negotiated runtime session carries the service JWT in its
transport handshake:

```http
Authorization: Bearer <service-jwt>
```

For WebTransport this is the CONNECT request. For WebSocket it is the HTTP
upgrade request. The controller performs signature, issuer, audience, expiry,
and other token checks before accepting application messages. The accepted
claims are retained only for the pending session and are bound to the
registration that follows.

The current WebSocket path continues to carry the JWT in
`service/register.params.jwt`; that contract is unchanged. The runtime JSON
profile retains this field on WebTransport so its JSON bytes and behavior remain
comparable with the legacy path. When both handshake and registration JWTs are
present, they must identify the same service and environment; a mismatch closes
the session.

The runtime `rkyv` profile carries no JWT in `ClientHelloV1` and therefore always
requires handshake authentication on WebSocket and WebTransport.

The negotiated registration sequence is:

1. The client sends the WebSocket upgrade or WebTransport CONNECT request with
   the service JWT and offered wire profiles.
2. The controller validates the JWT and selects an endpoint-allowed wire
   profile before completing the handshake.
3. The controller rejects the handshake if authentication fails or no allowed
   profile can be selected; otherwise it accepts the transport session.
4. The client opens the session-control stream within the independent
   registration deadline.
5. The controller reads and validates `ClientHelloV1`.
6. It matches `service_id` and environment to the authenticated JWT claims
   using the same identity rules as the WebSocket path.
7. It validates address syntax, port, tags, and all other registration fields.
   Version 1 does not perform an active reachability probe during registration.
8. It persists registration and inserts the live instance.
9. It sends `ServerHelloV1` containing `runtime_instance_id` and connection
   settings.
10. It permits command and event streams only after the acknowledgement is sent.

An invalid JWT, identity mismatch, or invalid registration closes the session.
The client must not fall back to WebSocket for these failures because fallback
would mask an authentication or configuration error.

Authorization headers, JWTs, and registration payloads must be redacted from
normal logs and metrics labels.

## Browser and BFF Authentication

The current browser WebSocket path depends on behavior that does not carry over
to WebTransport:

- the browser automatically includes the `accessToken` cookie in the WebSocket
  upgrade;
- `portal-view` offers `csrf.<token>` through `Sec-WebSocket-Protocol`;
- the BFF validates the cookie and CSRF value and injects the authenticated
  bearer token into the upstream WebSocket handshake.

Browser WebTransport requests use Fetch credentials mode `omit`; cookies and
HTTP authentication are not sent automatically. The WebTransport profile token
also has real protocol-negotiation semantics and must not be overloaded with a
CSRF secret.

The browser path therefore uses a short-lived, single-use connection ticket.
Version 1 preserves the controller's current Bearer-token validation contract;
it does not introduce a second gateway identity envelope:

1. An authenticated browser sends `POST /ctrl/mcp/ticket` through the existing
   HTTPS BFF path with its normal cookies and `X-CSRF-TOKEN` protection.
2. The BFF validates or refreshes the current login exactly as it does for other
   protected HTTPS requests.
3. The BFF creates an opaque, cryptographically random ticket bound to the
   authenticated subject, roles, client, allowed Origin, `/ctrl/mcp`, selected
   wire profile, token expiry, and a nonce.
4. The BFF stores the ticket in a bounded replay cache together with the current
   validated or refreshed access token, its expiry, and the authenticated
   principal. The record has a configurable lifetime no greater than 60 seconds
   and is consumed atomically on first use. The access token is never placed in
   the browser-visible ticket. If the replay cache cannot prove a successful
   write with the required TTL, ticket issuance fails closed.
5. The browser opens WebTransport and supplies
   `Authorization: WebTransport <ticket>` in the CONNECT request headers.
6. The gateway validates the Origin allowlist, consumes the ticket, restores the
   authenticated principal, applies normal access control, and establishes the
   upstream WebTransport session.
7. The gateway injects the retained access token as
   `Authorization: Bearer <access-token>` in the upstream controller handshake,
   exactly as the current WebSocket BFF path does. The controller independently
   validates issuer, audience, expiry, required `portal.r` scope, subject, and
   client identity. The browser ticket is never forwarded to the controller.
8. Gateway role-based policy uses the restored principal. It must not assert
   roles to the controller until a separately reviewed controller claim-mapping
   contract exists.

The replay cache is security-sensitive credential storage. It must restrict
read access to the ticket consumer, encrypt or equivalently protect records at
rest and in transit, redact all values, and delete the complete record on
consumption or expiry. A cache implementation that cannot provide those
properties is not eligible for browser WebTransport.

Ticket consumption also fails closed when the replay cache is unavailable,
degraded, returns an ambiguous result, or cannot perform atomic consume. It must
not fall back to a process-local cache or accept a self-contained ticket without
replay protection.

All gateway nodes must synchronize UTC through the deployment's approved time
service and expose clock-synchronization health. The cache TTL is authoritative,
and each record also carries an absolute ticket expiry and access-token expiry;
the consumer enforces the earliest deadline. A positive expiry grace period is
not allowed because it could extend the 60-second hard maximum. If measured
clock error exceeds the configured readiness threshold, ticket issuance and
consumption fail closed until synchronization is healthy.

Target browser support for `WebTransportOptions.headers`, `protocols`,
`requireUnreliable`, the selected `protocol`, and the resulting `reliability`
value is a release gate. The browser constructs the session with the ticket
header, `protocols: ["light-controller-mcp-json-v1"]`, and
`requireUnreliable: true`. After connection it requires
`reliability == "supports-unreliable"`; a reliable-only connection is not
accepted as the HTTP/3/QUIC profile described by this document. Do not put the
ticket in a URL query parameter as a compatibility fallback because URLs are
commonly retained in proxy, access, and diagnostic logs. If the target browser
cannot meet this contract, browser WebTransport remains disabled or falls back
according to its configured mode.

`POST /ctrl/mcp/ticket` terminates in the authenticated HTTPS BFF handler before
route-prefix processing. Only a WebTransport CONNECT request for `/ctrl/mcp`
enters the WebTransport router. Method-aware tests must prove that ticket POSTs
cannot be proxied, upgraded, or rejected by the session router.

In a multi-replica gateway deployment, ticket issuance and consumption require
a shared replay cache or a proven affinity mechanism covering both requests. A
self-contained signed ticket without replay protection is insufficient because
it can be reused during its validity window.

The accepted WebTransport session must not outlive either the access-token
expiry or a configurable maximum session duration. The gateway arms that
deadline when it consumes the ticket, closes the session at the deadline, and
requires a new ticket before reconnecting. Immediate authorization revocation
is guaranteed only when the deployment provides a concrete revocation signal or
introspection mechanism consumed by the gateway. Without one, version 1 claims
expiry enforcement, not immediate revocation. Ticket values, user access
tokens, CSRF values, and upstream authorization headers are always redacted.

## Logical Channels and Transport Mapping

Version 1 uses reliable delivery only. Applications operate on logical channels;
the transport adapter decides whether those channels share a connection or use
independent streams.

| Logical channel | WebSocket mapping | WebTransport mapping | Contents |
| --- | --- | --- | --- |
| MCP session | One ordered WebSocket connection | One long-lived bidirectional stream | MCP JSON-RPC requests, responses, and notifications |
| Runtime session control | Messages on the runtime WebSocket | One long-lived bidirectional stream | Registration, metadata, discovery, ping/pong, and session errors |
| Runtime command | Messages correlated by request ID on the runtime WebSocket | One bidirectional stream per command | One command request and one command response |
| Runtime events | Messages on the runtime WebSocket | One long-lived unidirectional stream | Existing asynchronous notifications, including `notifications/log` |

WebSocket preserves message boundaries but provides one ordered data path per
direction. WebTransport streams are ordered byte streams and do not preserve
application message boundaries. Their adapters must apply the framing defined by
the negotiated wire profile.

The `rkyv` over WebSocket profile isolates codec cost for measurement; it does
not provide independent command and event streams. Avoid claiming WebTransport
multiplexing benefits for that combination.

### MCP Session Channel

The browser and controller exchange the existing MCP JSON-RPC messages without
semantic translation. WebSocket carries one JSON-RPC message per text frame.
WebTransport carries the same messages on one long-lived bidirectional stream
using the JSON framing below. Server notifications share that stream.

The first MCP request remains `initialize` according to the current controller
contract. A second MCP stream in the same WebTransport session is a protocol
violation in version 1.

### Runtime Session Control Channel

For WebTransport, the runtime opens this stream first. Registration must be its
first frame. The stream remains open for the session and carries low-volume
ordered control messages. Only one runtime session-control stream is allowed.

For WebSocket, these logical messages continue to share the existing runtime
connection. Registration and acknowledgement ordering remain unchanged.

### Runtime Command Channels

On WebTransport, the controller opens a new bidirectional stream for each
command. It writes one command request, closes its send direction, reads one
command response, and then releases the stream. JSON and `rkyv` profiles use the
same stream lifecycle with different payload framing.

On WebSocket, commands and responses remain messages on the existing connection.
The request ID is mandatory on every transport. It preserves audit correlation,
timeout handling, and late-response detection.

Command concurrency remains bounded by controller configuration and negotiated
limits. A command that cannot obtain transport capacity before its dispatch
deadline fails with a transport error; it must not wait indefinitely.

### Runtime Event Channel

On WebTransport, the runtime opens one unidirectional event stream after
registration. It carries framed asynchronous notifications separately from
command responses, so log traffic cannot sit in front of a command response in
the same application stream. On WebSocket, event messages remain on the shared
ordered connection.

The event path is reliable and flow-controlled. It is not fire-and-forget. The
runtime must use a bounded outbound event queue:

- control and lifecycle notifications are never silently dropped;
- log records may be dropped at the source when their queue is full;
- every dropped-log interval emits a counter and a sequence gap visible to the
  controller;
- a persistently blocked event stream is reset and the session is reconnected.

The controller continues to translate accepted runtime notifications to the
existing external MCP notification shape.

## JSON Wire Profile Framing

Existing JSON WebSocket behavior is unchanged: one UTF-8 JSON-RPC value is sent
in each text frame and binary frames are rejected for legacy sessions.

On WebTransport, each JSON message is encoded as:

```text
4-byte unsigned big-endian payload length
exactly that many UTF-8 JSON bytes
```

The length excludes the four-byte prefix. The receiver rejects a value above
the endpoint-specific message limit before allocating, reads exactly the
declared length with a deadline, validates UTF-8, and parses exactly one JSON
value. EOF before the complete payload is a truncated-message error. Zero-length
messages and trailing non-whitespace bytes are invalid.

This framing applies to both `light-controller-mcp-json-v1` and
`light-controller-runtime-json-v1` over WebTransport. It is part of those wire
profiles, not a generic property of WebTransport.

## rkyv Binary Frame Format

Every `light-controller-runtime-rkyv-v1` message begins with a fixed 16-byte
header encoded without `rkyv`:

| Offset | Size | Field | Encoding |
| --- | --- | --- | --- |
| 0 | 4 | Magic | ASCII `LCRK` |
| 4 | 1 | Wire-profile major | `1` |
| 5 | 1 | Flags | `0` in version 1 |
| 6 | 2 | Message kind | Unsigned little-endian integer |
| 8 | 4 | Payload length | Unsigned little-endian integer |
| 12 | 4 | Reserved | Must be zero |

The payload immediately follows the header and contains exactly one archived
root object. The payload length excludes the header. WebSocket/TLS and
WebTransport/QUIC already provide cryptographic integrity, so the application
frame does not add a checksum.

The receiver must:

1. Read the complete header with a deadline.
2. Validate magic, version, flags, message kind, and reserved bytes.
3. Reject a length above the limit before allocating the payload buffer.
4. Allocate an appropriately aligned buffer and read exactly the declared
   payload length.
5. Validate the archived root with `bytecheck` through a safe `rkyv` API.
6. Apply semantic limits such as string length, tag count, and allowed command
   names.
7. Copy only the fields that must survive the receive buffer or cross an
   asynchronous boundary.

On WebSocket, one binary message contains exactly one header and payload. On
WebTransport, EOF before the complete payload is a truncated-frame error. Extra
bytes are the start of the next frame only on long-lived control or event
streams.

### Message Kind Registry

Version 1 reserves these message kinds:

| Kind | Root type | Allowed logical channel |
| --- | --- | --- |
| 1 | `ClientHelloV1` | Session control |
| 2 | `ServerHelloV1` | Session control |
| 3 | `MetadataUpdateV1` | Session control |
| 4 | `DiscoveryRequestV1` | Session control |
| 5 | `DiscoveryResponseV1` | Session control |
| 6 | `DiscoveryChangedV1` | Session control |
| 7 | `PingV1` | Session control |
| 8 | `PongV1` | Session control |
| 9 | `SessionErrorV1` | Session control |
| 10 | `ServerDrainingV1` | Session control |
| 100 | `CommandRequestV1` | Command |
| 101 | `CommandResponseV1` | Command |
| 200 | `RuntimeNotificationV1` | Runtime events |

Unknown kinds are rejected before archived access. Adding a new kind does not
change an existing archived root type. Existing version 1 root types are
immutable after release.

## runtime-rkyv-v1 Wire Types

The type names below describe shared wire types for
`light-controller-runtime-rkyv-v1`, not the existing application structs in
either repository. Field order is part of the archived schema and is frozen when
that profile is released.

### Registration Types

`ClientHelloV1` contains:

| Field | Wire type | Semantic rule |
| --- | --- | --- |
| `service_id` | UTF-8 string | Non-empty; maximum 256 bytes; must match the authenticated service claim |
| `env_tag` | Optional UTF-8 string | Maximum 128 bytes; must agree with authenticated environment claims when present |
| `service_version` | UTF-8 string | Non-empty; maximum 128 bytes |
| `application_protocol` | UTF-8 string | Runtime's advertised protocol, such as `https`; maximum 32 bytes |
| `address` | UTF-8 string | Syntactically valid IP literal or DNS hostname; maximum 253 bytes; no registration-time reachability probe |
| `port` | `u16` | Must be greater than zero |
| `tags` | Vector of `WireTagV1` | Maximum 64 entries; keys sorted and unique |

The JWT is not present in `ClientHelloV1`; it comes from the authenticated
WebSocket upgrade or WebTransport CONNECT request.

`ServerHelloV1` contains:

| Field | Wire type | Semantic rule |
| --- | --- | --- |
| `runtime_instance_id` | 16-byte UUID | Authoritative ID returned by registration persistence |
| `connection_id` | 16-byte UUID | Identifies this live transport session |
| `heartbeat_interval_ms` | `u32` | Non-zero negotiated heartbeat interval |
| `max_control_payload_bytes` | `u32` | Server limit for session-control frames |
| `max_command_streams` | `u32` | Maximum concurrent controller command streams |

`WireTagV1` contains UTF-8 `key` and `value` strings. Each is limited to 256
bytes. Duplicate keys are invalid.

### Metadata and Discovery Types

`MetadataUpdateV1` contains optional `service_version`,
`application_protocol`, `port`, and complete replacement `tags` fields. The
same limits and validation rules as registration apply. `None` means no change.
`Some(empty tags)` clears all tags; empty strings and port zero are invalid.

`DiscoveryRequestV1` contains:

| Field | Wire type | Semantic rule |
| --- | --- | --- |
| `request_id` | UTF-8 string | Non-empty; maximum 128 bytes |
| `operation` | `u8` | `1` lookup, `2` subscribe, `3` unsubscribe |
| `service_id` | UTF-8 string | Non-empty; maximum 256 bytes |
| `env_tag` | Optional UTF-8 string | Maximum 128 bytes |
| `application_protocol` | Optional UTF-8 string | Maximum 32 bytes |

`DiscoveryResponseV1` contains the request ID, an optional
`DiscoverySnapshotV1`, and an optional `WireErrorV1`. Exactly one of snapshot
or error must be present.

`DiscoveryChangedV1` contains one `DiscoverySnapshotV1`. A discovery snapshot
contains the requested service ID, optional environment and application
protocol filters, and a bounded vector of `DiscoveryNodeV1` values. Each node
contains the current runtime instance ID, service identity, environment,
version, application protocol, address, port, tags, connection timestamps, and
connected state needed by the existing discovery contract.

The initial maximum number of nodes in one snapshot is 10,000. A larger result
is a resource-limit error rather than a partially serialized snapshot. The
frame-size limit also applies, and the receiver enforces whichever limit is
reached first.

### Liveness and Error Types

`PingV1` and `PongV1` contain the same `u64` nonce and signed 64-bit Unix
millisecond timestamp. A pong with an unexpected nonce does not satisfy the
heartbeat.

`SessionErrorV1` and command failures use `WireErrorV1`:

| Field | Wire type | Semantic rule |
| --- | --- | --- |
| `code` | `i32` | Stable application error code |
| `message` | UTF-8 string | Safe operator-facing summary; maximum 1,024 bytes |
| `data_json` | Optional byte vector | One valid JSON value within the frame-specific limit |

Error messages must not contain JWTs, authorization headers, or unredacted
sensitive payloads.

`ServerDrainingV1` contains a signed 64-bit Unix millisecond drain deadline and
a safe reason string limited to 1,024 bytes. A client stops issuing new control
requests, lets active command streams finish until that deadline, and reconnects
after the server closes the session.

### Command and Notification Types

`CommandRequestV1` contains a request ID limited to 128 bytes, a tool name
limited to 256 bytes, and `arguments_json`. `CommandResponseV1` contains the
same request ID, completion timestamp, and exactly one of `result_json` or
`WireErrorV1`.

`RuntimeNotificationV1` contains a method name limited to 256 bytes,
`params_json`, and monotonically increasing `u64` sequence number for the
current event stream. Sequence numbers restart at zero on a new registered
session. A gap tells the controller that the runtime dropped one or more
notifications before transmission.

All `*_json` fields are UTF-8 byte vectors containing exactly one valid JSON
value. Their content is validated only after the enclosing archive and byte
limits pass.

Version 1 deliberately uses numeric operation and message-kind fields rather
than a shared archived envelope enum. New independent kinds can be registered
without changing the layout of existing roots. Unknown numeric values are
errors; they are never mapped to a default operation.

## rkyv Wire Profile

The shared wire crate owns the only `rkyv` dependency used for this protocol.
Both controller and runtime consume the same published or otherwise pinned
crate version.

Version 1 fixes these format choices:

```text
rkyv major version: 0.8
endianness: little_endian
alignment: aligned
relative pointer width: pointer_width_32
validation: bytecheck enabled
UUID integration: uuid-1 enabled
```

Cargo feature unification must not silently change this profile. CI checks
`cargo tree -e features` for the controller and runtime release graphs and
rejects conflicting endianness, alignment, or pointer-width features.

Payloads are read directly into an aligned buffer. Network input always uses
validated access such as `rkyv::access`; unchecked access and unchecked
deserialization are prohibited.

Wire types must:

- use fixed-width integers instead of `usize` or `isize`;
- represent UUIDs consistently through the shared crate;
- represent timestamps as signed 64-bit Unix milliseconds;
- use sorted key-value vectors instead of unordered maps when deterministic
  bytes are required;
- avoid recursive or attacker-controlled deeply nested structures;
- avoid references to application structs whose layout can change
  independently;
- define semantic maximums for strings, lists, tags, and JSON byte fields.

Validation proves that bytes form a structurally valid archive. It does not
prove that a service ID, address, port, tool name, or authorization decision is
valid. Normal application validation remains mandatory.

Archived references borrow the receive buffer. They must not be stored in
controller state, moved into a spawned task, or held across an `.await` that can
outlive the buffer. Values needed by persistence, event publication, or the
existing JSON/MCP surfaces are converted into owned application types.

This boundary means the design is not zero-allocation end to end. It avoids
parsing and allocation only where handlers can consume archived values directly.

## Dynamic JSON Payloads

The existing command layer includes dynamic MCP arguments and results. Version
1 preserves them as bounded UTF-8 JSON byte fields inside otherwise typed wire
messages:

```text
CommandRequestV1
  request_id
  tool_name
  arguments_json

CommandResponseV1
  request_id
  completed_at
  result_json or structured error

RuntimeNotificationV1
  method
  params_json
  sequence
```

The receiver validates UTF-8 and parses JSON only when the existing handler
requires `serde_json::Value`. This preserves current command extensibility and
makes the performance limitation explicit. A future wire-profile version may
add typed payload kinds for measured hot paths without changing version 1.

## Schema Ownership and Evolution

Create a dependency-light shared crate, referred to here as
`controller-wire`, containing:

- wire-profile identifiers and compatibility metadata;
- the JSON length-prefix encoder and decoder;
- the 16-byte `rkyv` frame header encoder and decoder;
- runtime protocol and message-kind constants;
- immutable `v1` archived root types;
- semantic validation helpers;
- golden JSON and `rkyv` encoded fixtures;
- compatibility tests.

The crate must not depend on `controller-rs`, `portal-registry`, Tokio, Axum, or
a particular WebTransport implementation.

The existing duplicate registration structs in `controller-rs` and
`portal-registry` must not become independent `rkyv` schemas. Each side converts
between its application types and the shared wire types.

Versioning rules are:

- never add, remove, reorder, or change fields in a released archived root;
- never add a variant to a released archived enum;
- add a new message kind for a new independent payload;
- add a new wire-profile major version for an incompatible replacement;
- keep golden bytes for every released root type;
- test old-client/new-server and new-client/old-server negotiation;
- keep at least the current and previous wire-profile versions during
  rolling upgrades.

## Transport-Neutral Application Boundary

`controller-rs` already stores an `mpsc::Sender<ControllerCommand>` in each
live instance. Preserve this boundary. Application services exchange owned
logical messages and lifecycle events without importing Axum WebSocket,
Tungstenite, QUIC, WebTransport, or `rkyv` types.

The useful abstractions are deliberately small:

- an application session for registration, commands, responses, notifications,
  authentication state, and cleanup;
- a wire-profile adapter that encodes and decodes owned logical messages;
- a transport session that opens or accepts logical channels and moves bounded
  encoded messages;
- transport capabilities describing independent streams and datagrams.

A broad application-wide `Connection` trait is not required. The application
must not assume every transport supports independent streams, and the transport
must not inspect MCP methods or runtime command payloads.

On the Rust client, replace the WebSocket-specific outbound
`mpsc::Sender<tungstenite::Message>` boundary with a logical outbound enum. The
selected wire-profile adapter converts that enum to bounded bytes. The selected
transport adapter then maps those bytes to WebSocket messages or WebTransport
streams. Codec selection must not occur inside the transport driver.

On the controller, refactor the current WebSocket handlers so all transports
and codecs call shared functions for registration, inbound messages, pending
command completion, notification publication, and disconnect cleanup.

The gateway is intentionally below this application boundary. Its initial
WebSocket and WebTransport routers forward payload bytes and do not instantiate
the MCP or runtime codecs.

All supported profile and transport adapters must produce the same observable
application behavior for:

- registration acknowledgement;
- `runtime_instance_id` assignment;
- metadata and discovery updates;
- command results and timeouts;
- notifications;
- liveness timestamps;
- disconnect events and pending-command failure.

## Expected Implementation Surfaces

The initial implementation is cross-repository work.

In `controller-rs`, the main change surfaces are:

- `Cargo.toml` for the selected HTTP/3/WebTransport, JSON framing, and wire
  dependencies;
- `src/config.rs` for listeners, allowed profile pairs, and limits;
- `src/lib.rs` and `src/tls.rs` for coordinated TCP and UDP listeners;
- an authenticated internal capability handler and transport-native probe
  resources for per-instance transport/profile readiness;
- `src/routes/microservice.rs` to extract shared session behavior from the
  WebSocket driver;
- `src/routes/mcp.rs` to extract shared MCP behavior for WebSocket and
  WebTransport session adapters;
- `src/auth.rs` to separate token verification from post-CONNECT registration
  identity matching;
- `src/state.rs`, `src/types.rs`, and `src/command_router.rs` to preserve the
  existing command channel and connection-ID cleanup rules;
- integration tests for profile, transport, and fallback parity.

In `light-fabric`, the main change surfaces are:

- `crates/portal-registry/Cargo.toml`;
- `crates/portal-registry/src/client.rs` for transport-neutral logical queues
  plus independent codec and transport selection;
- `crates/portal-registry/src/protocol.rs` for conversion to the shared wire
  crate rather than a second archived schema;
- `crates/light-runtime/src/config.rs` and `runtime.rs` for client selection,
  URL derivation, TLS assets, and fallback settings;
- `frameworks/light-pingora/src/websocket.rs` to extract reusable route
  resolution without changing existing WebSocket behavior;
- a WebTransport router module and UDP/HTTP3 service with transport-specific
  limits and stream relay;
- `apps/light-gateway/src/main.rs` for coordinated TCP and UDP startup,
  readiness, reload, and shutdown;
- BFF ticket issuance, bounded replay-cache storage, Origin validation, and
  restoration of the authenticated principal;
- runtime handlers and tests for command, discovery, notification, heartbeat,
  reconnect, and draining parity.

In `portal-view`, the main change surfaces are:

- the controller context for transport preference and serial fallback;
- an authenticated capability client for `/ctrl/mcp/capabilities`, with the
  optional `VITE_CONTROLLER_TRANSPORT` override;
- one controller-BFF authority resolver shared by capability, ticket,
  WebSocket, and WebTransport URLs;
- an MCP session interface shared by WebSocket and WebTransport clients;
- the HTTPS ticket request and WebTransport CONNECT header;
- WebTransport JSON framing and notification handling;
- browser capability, authentication, reconnect, and cleanup tests.

Deployment repositories must add UDP exposure for each enabled WebTransport
listener and router. `light-4j` requires compatibility tests but no `rkyv` or
WebTransport implementation for the initial release.

## Initial Limits

All limits are configurable, but the server must start with finite defaults.

| Limit | Initial default |
| --- | --- |
| Registration/control frame payload | 1 MiB |
| Command request payload | 1 MiB |
| Command response payload | 16 MiB |
| Runtime notification payload | 1 MiB |
| MCP JSON message | 16 MiB, explicitly enforced on both transports |
| Queued outbound commands per runtime session | 64 |
| In-flight commands per runtime session | 64 |
| In-flight commands across the controller | 4096 |
| Concurrent command streams per WebTransport runtime session | 64 |
| Active WebTransport runtime sessions | 1000 |
| Session-control streams | 1 |
| Runtime event streams | 1 |
| MCP streams per WebTransport session | 1 |
| Registration deadline | 5 seconds, controlled independently from command timeouts |
| Heartbeat interval | 30 seconds |
| Missed heartbeat allowance | 1 interval |
| Browser connection-ticket lifetime | 30 seconds; hard maximum 60 seconds |
| Browser connection-ticket uses | 1, consumed atomically |
| Gateway ticket clock-skew readiness threshold | 2 seconds; no expiry grace |
| Maximum validation depth | 64 for any type that can contain nested data |
| WebTransport datagrams | Disabled |

Additional per-IP, per-user, per-Origin, and per-service session and ticket
limits must be set from load-test results before internet-facing deployment. A
length or count limit is checked before allocation or iteration wherever
possible.

The command queue capacity, in-flight-command limit, and concurrent-stream limit
are separate controls. The existing `COMMAND_CHANNEL_CAPACITY` describes a
bounded queue; it must not be reused as proof that pending commands or open
streams are bounded. Admission reserves an in-flight slot before inserting a
pending response entry or opening a command stream. When either the per-session
or global limit is reached, dispatch fails immediately with `Resource limit`
and does not enqueue or insert pending state.

Both WebSocket and WebTransport MCP handlers explicitly enforce the 16 MiB MCP
application-message limit. The implementation configures the WebSocket
frame/message limit rather than relying on a framework default, and the
WebTransport length prefix is rejected before allocation when it exceeds the
same limit.

## Liveness, Errors, and Cleanup

Transport-level TCP or QUIC activity is not sufficient to prove that the
application loop is healthy. The runtime sends the profile-specific ping message
on the session-control channel and expects its matching pong within the
heartbeat deadline. For `rkyv` these are `PingV1` and `PongV1`; the JSON profile
uses the existing JSON-RPC liveness messages. Any valid application message also
updates the instance's last-seen time.

Browser MCP sessions retain the existing MCP `ping` behavior and are also
subject to the gateway's idle and maximum-connection-duration limits.

Errors are classified as:

- **Unavailable:** UDP blocked, timeout, no route, or listener unavailable;
- **Unsupported:** the transport, wire profile, or allowed profile/transport
  pair is not supported;
- **Establishment failed:** the browser reported an opaque WebTransport failure
  before the session became ready and did not expose a more specific cause;
- **Unauthorized:** JWT is missing, invalid, or expired;
- **Invalid registration:** authenticated claims and registration disagree;
- **Protocol violation:** invalid frame, logical channel, ordering, or message
  kind;
- **Resource limit:** frame, queue, session, or stream limit exceeded;
- **Internal:** persistence or controller failure.

A malformed WebTransport command stream is reset without immediately killing a
healthy session when isolation is safe. Authentication failures, invalid
registration, duplicate required channels, repeated malformed frames, or
session-wide resource abuse close the entire session.

The browser error surface cannot reliably map every failed WebTransport CONNECT
to an HTTP status or server-side category. `responseHeaders` are available only
after the session is established, and a pre-establishment `ready` rejection may
deliberately hide whether the endpoint was unreachable or unwilling to accept
the session. Browser fallback therefore uses only client-observable facts:

- capability-fetch and ticket-issuance HTTP responses retain their explicit
  `Unauthorized`, `Unsupported`, `Resource limit`, or `Internal` categories;
- a synchronous absence of the required constructor or constructor option is
  `Unsupported`;
- a rejection before `ready` resolves, after successful capability and ticket
  requests, is `Establishment failed`; the browser must not relabel it as
  `Unauthorized`, `Unavailable`, or `Internal`;
- `preferWebTransport` may serially fall back to an advertised WebSocket
  candidate for `Establishment failed`, while `requireWebTransport` never does;
  and
- after `ready` resolves, profile negotiation and application errors are
  structured and follow the no-fallback rules.

The gateway and controller retain the authoritative server-side cause in
bounded telemetry even when the browser sees only `Establishment failed`. Both
transports enforce the same authentication and authorization policy, so browser
fallback is not an authorization bypass. Operators who cannot accept an opaque
pre-establishment downgrade must select `requireWebTransport`.

Disconnect cleanup must remain connection-ID guarded so a late task from an old
transport cannot remove a newly registered replacement connection.

## Transport and Profile Selection

Transport and codec remain independent, but fallback ordering must be
unambiguous. Clients therefore use an ordered list of explicit candidate pairs:

```yaml
portalRegistry:
  portalUrl: https://controller:8438
  controlCandidates:
    - transport: webtransport
      wireProfile: light-controller-runtime-rkyv-v1
      negotiation: required
    - transport: websocket
      wireProfile: light-controller-runtime-rkyv-v1
      negotiation: required
    - transport: websocket
      wireProfile: light-controller-runtime-json-v1
      negotiation: legacy
```

The production default contains only the legacy-compatible pair:

```yaml
controlCandidates:
  - transport: websocket
    wireProfile: light-controller-runtime-json-v1
    negotiation: legacy
```

`negotiation: required` sends the profile offer and requires the peer to select
that profile. `negotiation: legacy` is valid only for an existing JSON
WebSocket contract; it sends no wire-profile token and accepts the existing
no-profile handshake. This makes new-client-to-old-controller compatibility
explicit without allowing an absent selection to downgrade a binary or
WebTransport candidate.

Convenience modes such as `websocket`, `preferWebTransport`, and
`requireWebTransport` may be retained, but configuration loading must expand
them into and expose the ordered candidate pairs. The same rule applies to a
`preferRkyv` convenience setting. Operators must be able to see the effective
order and must not depend on an undocumented Cartesian-product ordering.

The existing `portalUrl` remains the base controller URL, including any ingress
path prefix. The client derives `/wt/microservice` and `/ws/microservice` without
discarding that prefix.

`portal-view` has one fixed wire profile,
`light-controller-mcp-json-v1`. Its default local mode is `auto`: fetch
`/ctrl/mcp/capabilities`, intersect the ready candidates with browser support,
and follow the gateway policy. The gateway policies are:

| Gateway policy | Behavior |
| --- | --- |
| `websocket` | Advertise and use the existing legacy WebSocket path; initial production default |
| `preferWebTransport` | Try an advertised WebTransport candidate first and then the advertised legacy WebSocket candidate for an allowed fallback error |
| `requireWebTransport` | Advertise WebTransport as required and fail the controller connection when it is unavailable |

The optional build-time override
`VITE_CONTROLLER_TRANSPORT=auto|websocket|webtransport` is intended for local
development, emergency compatibility, and controlled tests. `auto` is the
default. `websocket` forces the legacy WebSocket candidate;
`webtransport` requires WebTransport and does not silently fall back. The build
variable is not the source of deployment readiness: the same UI bundle should
work when gateway routes or controller transport sets change without a rebuild.
A future runtime-injected UI configuration may provide the same override without
changing the capability contract.

In `auto` mode, `portal-view` performs these steps after authentication and when
the first controller consumer requests a connection:

1. Fetch the authenticated capability resource. If there is no valid response
   or still-fresh cached response, apply the capability-fetch failure rules,
   schedule jittered backoff, and return without attempting either transport.
2. Check for the required local WebTransport constructor and option support.
3. If policy and candidates permit it, request a ticket and attempt
   WebTransport with a bounded connection timeout.
4. Require `light-controller-mcp-json-v1` as the selected protocol and
   `supports-unreliable` as the reliability mode before MCP initialization.
5. Fall back to the advertised legacy WebSocket candidate only for observable
   `Unavailable` or `Unsupported` failures, or for the explicitly opaque
   `Establishment failed` category under `preferWebTransport`.
6. Do not fall back for authentication, authorization, protocol, resource-limit,
   or internal errors.

The actual attempt, not user-agent sniffing, page `nextHopProtocol`, or a cached
previous success, determines whether the current enterprise network supports
the WebTransport path.

The gateway initially uses `matchIngress` upstream selection: WebSocket ingress
uses a WebSocket upstream and WebTransport ingress uses a WebTransport upstream.
No automatic cross-transport relay is allowed.

Fallback rules are:

- attempts are serial, never parallel;
- fallback is allowed only before runtime registration acknowledgement or MCP
  initialization succeeds;
- browser `preferWebTransport` may fall back for an opaque pre-`ready`
  `Establishment failed`; `requireWebTransport` may not;
- do not fall back for `Unauthorized`, invalid registration, protocol
  violation, resource-limit, or internal errors;
- browser ticket authentication or Origin failure is `Unauthorized`, not an
  indication that WebTransport is unsupported;
- log and count the normalized fallback reason without logging secrets;
- after an established session disconnects, retry its selected transport first
  with the existing jittered exponential backoff;
- do not keep two live registrations for the same client attempt;
- never try a transport/profile pair that is absent from the configured
  candidate list;
- `requireWebTransport` and required-profile policies prevent a network attacker
  or deployment error from silently forcing a downgrade.

Java `light-4j` clients do not receive the new setting and continue to use
WebSocket.

## Controller Configuration

Proposed server settings are:

```text
CONTROLLER_MCP_TRANSPORTS=websocket
CONTROLLER_RUNTIME_TRANSPORTS=websocket
CONTROLLER_STANDALONE_DISCOVERY_TRANSPORTS=websocket
CONTROLLER_WEBTRANSPORT_ADDR=<CONTROLLER_ADDR>
CONTROLLER_WEBTRANSPORT_MAX_SESSIONS=1000
CONTROLLER_WEBTRANSPORT_MAX_COMMAND_STREAMS=64
CONTROLLER_COMMAND_QUEUE_CAPACITY=64
CONTROLLER_MAX_IN_FLIGHT_COMMANDS_PER_SESSION=64
CONTROLLER_MAX_IN_FLIGHT_COMMANDS_GLOBAL=4096
CONTROLLER_REGISTRATION_TIMEOUT_MS=5000
CONTROLLER_MCP_MAX_MESSAGE_BYTES=16777216
CONTROLLER_WEBTRANSPORT_RUNTIME_PROFILES=light-controller-runtime-json-v1,light-controller-runtime-rkyv-v1
CONTROLLER_WEBTRANSPORT_MCP_PROFILES=light-controller-mcp-json-v1
CONTROLLER_WEBSOCKET_BINARY_PROFILES=
```

The three transport settings are comma-separated enabled sets; server-side order
has no preference semantics, duplicate values are invalid, and diagnostics emit
their normalized effective values. Runtime registry and discovery messages use
`CONTROLLER_RUNTIME_TRANSPORTS`;
`CONTROLLER_STANDALONE_DISCOVERY_TRANSPORTS` controls only `/ws/discovery` and
any future binding of that standalone surface. These settings apply only to
persistent controller communication surfaces; disabling WebSocket for one of
them does not disable the controller's normal HTTPS health or administrative
endpoints. Initial production settings contain only `websocket`. A dual
migration configuration can use:

```text
CONTROLLER_MCP_TRANSPORTS=websocket,webtransport
CONTROLLER_RUNTIME_TRANSPORTS=webtransport,websocket
CONTROLLER_STANDALONE_DISCOVERY_TRANSPORTS=websocket
```

This permits the browser to fall back on enterprise networks while Rust runtime
clients prefer WebTransport. A surface may be configured as WebTransport-only
after every client and network path for that surface is proven. In particular,
`CONTROLLER_MCP_TRANSPORTS=webtransport` removes browser WebSocket fallback
under the initial same-transport gateway design. Java and other clients that do
not implement WebTransport require a WebSocket-enabled surface.

`CONTROLLER_WEBTRANSPORT_ADDR` is a UDP socket address. It may use the same
numeric host and port as the existing TCP listener because TCP and UDP have
separate port spaces.

In version 1, controller listener addresses, enabled transport sets, and allowed
profile sets are startup-only. Changing them requires a controller restart and
produces a new controller capability revision. Client preference remains owned
by the ordered `controlCandidates` list; browser preference remains owned by
gateway `mcpTransportPolicy`. Server enabled sets do not create a third
preference source.

The WebTransport listener reuses the configured controller certificate and
private key but creates a QUIC-compatible TLS 1.3 configuration with HTTP/3
ALPN. Adding `h3` to the existing Axum TCP TLS configuration is not sufficient.

The WebTransport listener is enabled when any surface enabled set contains
`webtransport`. Startup is fail-fast when that listener, its TLS identity, or
required protocol extensions cannot be initialized. When no surface enables
WebTransport, failure to initialize experimental WebTransport code must not
affect the existing HTTPS/WebSocket listener.

Allowed-profile lists are deny-by-default. An empty MCP list disables direct
MCP WebTransport on the controller even when the runtime WebTransport listener
is enabled. `CONTROLLER_WEBSOCKET_BINARY_PROFILES` remains empty in production
until `rkyv` over WebSocket testing is explicitly approved.

## Gateway Configuration

Add a `webtransport-router.yml` module with route-resolution fields compatible
with `websocket-router.yml` and WebTransport-specific session and stream limits.
For example:

```yaml
defaultProtocol: https
defaultEnvTag: dev
pathPrefixService:
  /ctrl/mcp:
    serviceId: com.networknt.controller-1.0.0
    protocol: https
    envTag: dev
allowedProfiles:
  /ctrl/mcp:
    - light-controller-mcp-json-v1
mcpTransportPolicy: websocket
capabilityMaxAgeSeconds: 30
controllerCapabilityPath: /internal/controller/capabilities
controllerCapabilityStaleMs: 15000
controllerProbeIntervalMs: 5000
controllerProbeTimeoutMs: 2000
maxActiveSessions: 1000
maxStreamsPerSession: 1
ticketTtlMs: 30000
ticketClockSkewReadyMs: 2000
allowedOrigins:
  - https://portal.example.com
```

`mcpTransportPolicy` and `capabilityMaxAgeSeconds` are shared BFF policy
settings even if configuration composition presents them beside the
WebTransport router. They are not owned by only one router. The WebSocket and
WebTransport routers publish bounded readiness state to one capability
aggregator, which combines it with route and controller health.

The configuration shape is illustrative until implementation review, but these
contracts are required:

- `POST /ctrl/mcp/ticket` is handled by the HTTPS BFF before this route table,
  while WebTransport CONNECT for `/ctrl/mcp` enters this router;
- `GET /ctrl/mcp/capabilities` is handled by the authenticated BFF and reports
  only end-to-end candidates supported by the configured policy, healthy
  listeners, route resolver, and controller targets;
- controller capability responses and transport-native probe results must both
  be current within their configured stale thresholds before a target is
  eligible;
- route resolution code is shared with the WebSocket router rather than copied;
- activation follows the gateway handler/module model rather than an unrelated
  second enable flag;
- WebTransport-specific limits and allowed profiles are explicit;
- an empty or absent Origin allowlist rejects browser WebTransport;
- replay-cache unavailability, ambiguous atomic-consume results, or clock error
  beyond `ticketClockSkewReadyMs` makes ticket readiness false and fails ticket
  issuance and consumption closed;
- invalid startup config fails startup, while an invalid reload retains the
  last valid runtime;
- WebSocket and WebTransport route tables may differ, but drift is visible in
  diagnostics and configuration tests.

Gateway route, policy, limit, and capability configuration is reloadable. A
valid reload applies to new sessions and immediately removes disabled or unready
candidates from capability responses, producing a new aggregate revision.
Existing sessions remain pinned and continue until normal close, token or
maximum-duration expiry, target drain, or an explicit security revocation. A
routine policy reload does not reinterpret or migrate an established session.
When a route or listener must be removed, the gateway marks it draining, stops
new admission, waits for the configured drain deadline, and then closes any
remaining sessions with a categorized reason. An invalid reload keeps the last
valid configuration and revision.

## Deployment Requirements

Every supported controller deployment must explicitly expose every transport
enabled by its per-surface sets. A dual configuration exposes:

```yaml
ports:
  - "8438:8438/tcp"
  - "8438:8438/udp"
```

Kubernetes Services, firewall rules, security groups, ingress or Gateway API
resources, and load balancers must also permit UDP on the controller port.
The TCP listener remains available for normal HTTPS health and administrative
traffic even when all persistent controller surfaces are WebTransport-only.

A browser deployment additionally exposes the gateway's public HTTPS port over
both TCP and UDP, normally `443/tcp` and `443/udp`. The gateway-to-controller
network path must separately permit QUIC to the controller UDP port. Proving the
browser-to-gateway leg does not prove the gateway-to-controller leg.

An AWS Application Load Balancer is not the assumed WebTransport path. Use a
QUIC-aware Network Load Balancer or another proven end-to-end topology. Generic
HTTP/3 termination in Nginx or HAProxy is acceptable only after an integration
test proves the required WebTransport draft, extended CONNECT, datagrams, stream
resets, connection IDs, and draining behavior.

Existing HTTPS health endpoints prove TCP listeners only. Add WebTransport
readiness signals or synthetic probes for both the gateway and controller so
operators can distinguish:

- controller healthy, WebTransport disabled;
- controller healthy, WebTransport ready;
- controller healthy, WebTransport failed;
- gateway healthy, WebTransport router disabled;
- gateway healthy, browser ticket and upstream WebTransport route ready;
- gateway healthy, one WebTransport leg failed;
- complete controller failure.

## Multi-Replica Constraint

Current live instances, command senders, and pending requests are held in one
`controller-rs` process. PostgreSQL records audit and projection data; it is not
a live command router.

Until a separate distributed-session design is implemented:

- run one active controller replica for command routing; or
- provide an external routing mechanism that can direct every command to the
  process owning the target runtime session.

Load-balancer affinity for a QUIC connection keeps that connection on one
controller pod, but it does not make an MCP request arriving at another pod able
to use the session. QUIC connection migration also does not migrate application
state between controller pods.

This proposal must not be presented as enabling active-active controller
replicas.

## Graceful Draining

Gateway or controller shutdown follows this order:

1. Mark the affected WebTransport readiness false.
2. Stop issuing browser tickets and accepting new WebTransport sessions.
3. Stop opening new upstream gateway sessions and new runtime command channels.
4. Send the profile-specific runtime draining message; for `rkyv` this is
   `ServerDrainingV1`.
5. Allow in-flight MCP requests and runtime commands to complete for a bounded
   grace period.
6. Fail remaining pending work with a transport error.
7. Close upstream and downstream WebTransport sessions with explicit reasons,
   then close WebSocket sessions under the existing policy.
8. Let clients reconnect with jittered backoff and obtain a new browser ticket
   where required.

Connection draining is not transparent failover. A reconnected runtime must
perform registration again and receive the authoritative connection ID.

## Security Requirements

- Use TLS 1.3 and normal certificate and hostname verification.
- Apply the existing JWT issuer, audience, expiry, service identity, and
  environment checks.
- Require a non-empty Origin allowlist for browser WebTransport and compare the
  complete normalized origin, not a suffix or substring.
- Authenticate the public browser capability resource and expose only public
  endpoints, bounded policy names, profile tokens, and readiness; do not expose
  upstream controller addresses, instance IDs, or probe details.
- Authenticate the internal controller capability and probe resources with a
  dedicated least-privilege gateway service identity or mTLS identity, restrict
  them to the gateway network path, reject browser tickets and user credentials,
  rate-limit them, and redact probe credentials. The internal `instanceId` and
  revision must never be copied into the public capability response.
- Protect ticket issuance with the existing cookie authentication and CSRF
  checks; bind tickets to one route, origin, principal, profile, expiry, and use.
- Consume tickets atomically from a bounded replay cache and never accept them
  from URL query parameters.
- Fail ticket issuance and consumption closed when the replay cache is
  unavailable, degraded, or cannot prove atomic single-use behavior; never use
  a local-cache or unprotected signed-ticket fallback.
- Require synchronized gateway clocks, enforce the earliest cache, ticket, and
  access-token deadline, and do not extend the ticket hard maximum with clock
  tolerance.
- Treat replay-cache records as credential storage when they retain an upstream
  access token: restrict access, protect data at rest and in transit, and delete
  the complete record on consumption or expiry.
- Do not assume browser WebTransport carries cookies or HTTP authentication.
- Require the gateway to inject the retained Bearer token upstream and the
  controller to validate it independently; restored gateway roles are not
  controller claims.
- Enforce access-token expiry and maximum session duration with a gateway timer;
  claim immediate revocation only when a concrete signal or introspection
  mechanism is configured and tested.
- Authenticate before accepting application streams or allocating large
  application buffers beyond the strict handshake allowance.
- Enable QUIC address validation or Retry for untrusted network exposure when
  supported by the selected implementation.
- Limit unauthenticated connections, authenticated sessions, streams, frame
  sizes, queue sizes, tickets, and bytes per time window.
- Validate JSON length, UTF-8, and one-value framing before dispatch.
- Validate every `rkyv` archived root with `bytecheck` and then apply semantic
  validation.
- Never invoke `rkyv` unchecked access on network bytes.
- Reject endpoint, transport, and wire-profile combinations that are not
  explicitly allowlisted.
- Treat downgrade from a required transport or profile as an error, not an
  automatic fallback.
- Redact tickets, JWTs, cookies, CSRF values, authorization headers, and
  sensitive command payloads.
- Treat unknown wire-profile versions and message kinds as errors, not as a
  reason to guess a Rust type.
- Fuzz JSON framing, binary frame parsing, and archived validation with
  arbitrary bytes.
- Close sessions that repeatedly violate limits instead of continuing to
  allocate and log indefinitely.

## Backpressure and Fairness

Independent QUIC streams remove retransmission ordering between streams, but
they share connection congestion control and implementation scheduling.
WebTransport does not automatically make a command high priority.

The implementation must:

- reserve bounded capacity for command streams;
- prevent the event reader from monopolizing the controller task executor;
- use bounded browser, gateway, controller, and runtime queues;
- apply backpressure across both legs of a proxied WebTransport stream rather
  than buffering an unbounded slow side;
- cap streams waiting for an upstream mapping and fail closed when the upstream
  session cannot accept more;
- expose queue saturation and stream-acquisition latency;
- avoid spawning an unbounded task for every incoming stream;
- time out stalled reads and writes;
- test fairness under log load and packet loss.

If the selected library exposes stream scheduling, the policy may prefer command
streams over runtime events. Correctness must not depend on nonstandard priority
behavior.

## Datagrams and Telemetry

Version 1 does not use WebTransport datagrams.

QUIC datagrams are unreliable and unordered. They have no explicit flow control,
cannot be fragmented across QUIC packets, and may be delayed or dropped by the
sender or receiver under congestion. Their use requires an application contract
for maximum size, batching, sequence numbers, timestamps, loss accounting, and
overload behavior.

Metrics and traces already have dedicated ecosystem protocols. Sending them to
`controller-rs` would expand the controller into a telemetry ingestion service
and could couple telemetry load to command availability. Any future datagram
use requires a separate design comparing at least OTLP, Prometheus-compatible
delivery, and a dedicated collector.

If datagram metrics are ever approved, cumulative snapshots are preferred over
loss-sensitive deltas, with periodic reliable checkpoints.

## Observability

Add metrics with bounded labels for:

- active sessions by component, hop, transport, and negotiated wire profile;
- connection attempts, accepted sessions, and categorized failures;
- fallback count and reason;
- capability responses and refreshes by bounded policy and candidate set, plus
  candidate attempts rejected because readiness changed before handshake;
- capability-fetch failures and discovery backoff by bounded error category;
- registration and authentication latency;
- browser ticket issuance, consumption, expiry, replay rejection, and
  Origin rejection without ticket or Origin values as labels;
- replay-cache health, atomic-consume failures, and gateway clock-synchronization
  readiness without cache keys or ticket values as labels;
- current in-flight commands by session and globally, plus rejections by queue,
  in-flight, stream, and session limit;
- gateway downstream-to-upstream session and stream mapping failures;
- command stream acquisition, command latency, timeout, and reset count;
- JSON and `rkyv` frame validation, semantic validation, and size-limit
  failures;
- active and blocked streams;
- event queue depth and dropped log records;
- bytes sent and received by logical channel and gateway hop;
- QUIC RTT, loss, and migration when exposed by the library;
- drain duration and forced session closes.

Structured logs should include connection ID, runtime instance ID after
registration, gateway hop, transport, wire profile, logical channel, and
normalized error category. Do not use ticket IDs, service JWTs, user tokens,
full payloads, Origin values, or unbounded peer values as metric labels.

The runtime instance's application `protocol` metadata remains unchanged.
Expose the controller transport through diagnostics or a separate optional
`controlTransport` field only after checking event, database, and UI consumers.

## Rollout Plan

### Phase 0: Feasibility and Baseline Gate

- Measure allocations, CPU, memory, throughput, and command latency on the
  existing WebSocket path.
- Include idle connections, registration storms, command traffic, and concurrent
  log notifications.
- Record payload sizes and identify how much time is actually spent in JSON.
- Pin one Rust WebTransport implementation and prove controller and Rust-client
  interoperability against the exact supported draft.
- Prove payload-opaque, same-transport WebTransport stream relay across both
  gateway legs, including reset, backpressure, close, and draining.
- Prove that the gateway capability resource reflects end-to-end route and
  per-instance controller readiness, revisions, candidate-specific target pools,
  and transport-native probes, and never treats a page's HTTP version as
  availability.
- Prove browser ticket issuance, atomic consumption, protected credential
  storage, upstream Bearer injection, Origin enforcement, profile selection,
  `requireUnreliable`, and expiry-driven session close in every target browser.
- Prove the target browser's observable failure behavior: explicit capability
  and ticket HTTP failures retain their categories, pre-`ready` WebTransport
  rejection becomes `Establishment failed`, preference mode may fall back, and
  required mode may not.
- Prove the shared controller-BFF authority resolver in the supported
  same-origin deployment and in every explicitly supported cross-origin
  deployment.
- Prove the required UDP, HTTP/3, certificate, and WebTransport behavior through
  each supported development and production load-balancer topology.
- Select the shared replay cache and prove atomic fail-closed behavior,
  synchronized-clock readiness, and hard-expiry enforcement; decide the owner
  and release process for `controller-wire` and the benchmark workload.

Phase 0 is an approval gate. Phase 1 must not begin until these artifacts are
reviewed, the pinned compatibility tuple is recorded, and no unresolved item
requires changing the authentication trust model, gateway topology, or wire
profile boundaries. A failed spike keeps WebTransport disabled. A shared-session
refactor may still proceed when it is separately justified as WebSocket
hardening or preparation for binary WebSocket/raw QUIC evaluation, but it must
not introduce or assume WebTransport behavior.

The 2026-07-15 Phase 0 implementation produced that failed-spike result. Native
direct and same-transport relay mechanics, current certificate reuse, bounded
reconnect, and Redis atomic consume passed. Chrome 150 did not send the supplied
Authorization header. The server observed the supplied profile offer, and
stream echo/reset/close passed, but Chrome did not expose the selected protocol,
response headers, or required reliability result. The pinned `wtransport 0.7.1`
native client also discarded response headers, and its protocol generation did
not implement draft 16. Production WebTransport remains disabled and Phase 1
was not approved on a WebTransport justification. The executable evidence and
closure decision are in `implementation/light-controller/phase0`.

The separately justified WebSocket-only Phase 1 extraction completed on
2026-07-15. It introduced bounded command admission, explicit WebSocket message
limits, transport-neutral controller session modules, a logical-message
`PortalRegistryClient`, a private WebSocket adapter, and shared legacy JSON
fixtures. It did not enable WebTransport or change the Phase 0 decision. The
closure record and executable gates are in
`implementation/light-controller/phase1`.

The transport-independent shared wire-profile foundation completed on
2026-07-15. `light-fabric/crates/controller-wire` now exclusively owns the
version 1 profile tokens, framing, immutable archived roots, bounded validation,
semantic limits, golden bytes, dependency-purity policy, and pinned `rkyv`
feature policy. Both `portal-registry` and `controller-rs` compile and test
owned conversion boundaries against the same fixtures. This completes
implementation-plan Phase 2, not the broader design Phase 2 below: no listener,
negotiation, binary WebSocket profile, or WebTransport behavior is enabled.
The closure record and executable gates are in
`implementation/light-controller/phase2`.

### Phase 1: Extract Shared Session Behavior

- Refactor `controller-rs` runtime and MCP message handling into
  transport- and codec-neutral service functions.
- Replace the Rust client's tungstenite-specific outbound channel with logical
  messages.
- Separate wire-profile adapters from WebSocket and WebTransport session
  adapters.
- Keep behavior and wire output unchanged.
- Run the complete existing WebSocket test suite.

Gateway route-resolver extraction remains part of the later gateway phase; it
was not required for the controller/client shared-session boundary.

### Phase 2: Runtime Profile Matrix

The shared crate and conformance portion is complete. Every transport-enabling
item in this design phase remains blocked by the Phase 0 no-go.

- Add the shared `controller-wire` crate and golden fixtures.
- Add the UDP/HTTP3 listener, enabled when any controller surface enabled set
  contains `webtransport`.
- Implement runtime JSON over WebTransport first.
- Implement runtime `rkyv` over WebSocket binary frames and WebTransport.
- Verify that JSON and `rkyv` use the same logical WebTransport channel model.
- Add ordered transport/profile candidates to the Rust client.
- Keep all production configurations in `websocket` mode.

### Phase 3: Browser MCP and Gateway Router

- Add the gateway UDP/HTTP3 service and payload-opaque WebTransport router.
- Add the authenticated MCP capability resource and short-lived readiness
  synthesis across both gateway legs.
- Add ticket issuance, shared replay-cache behavior, Origin enforcement, and
  authenticated-principal restoration.
- Add MCP JSON framing and WebTransport support to `portal-view` and
  `controller-rs`.
- Add `portal-view` auto-selection and its build-time force override without
  changing MCP/JSON-RPC 2.0 application semantics.
- Require WebTransport header and protocol-negotiation support in every target
  browser.
- Keep browser production configuration in `websocket` mode.

### Phase 4: Controlled Opt-In

- Enable approved candidate pairs for selected Rust services in a deployment
  with verified UDP routing.
- Enable `preferWebTransport` for a small browser cohort only after both gateway
  legs and ticket authentication are proven.
- Observe fallback, ticket, validation, queue, memory, and command-latency
  metrics by profile and hop.
- Exercise rolling upgrades, draining, UDP blocking, and rollback.

### Phase 5: Default Decision

Make no default change unless:

- behavior parity and compatibility tests pass;
- fuzzing finds no panic or unsafe-access path;
- supported deployment topologies pass end-to-end tests;
- target browsers support the required WebTransport headers, protocols,
  `requireUnreliable`, selected-protocol, and reliability checks;
- ticket replay and multi-replica gateway tests pass;
- the measured benefit is material for the target workload;
- per-session memory and operational complexity are acceptable;
- rollback to WebSocket has been exercised.

If these gates fail, retain WebSocket or choose the simpler binary-WebSocket or
raw-QUIC alternative.

## Verification Plan

### Protocol and Unit Tests

- Allowed and rejected endpoint/transport/profile combinations.
- Per-surface transport enabled sets enable only the configured MCP, runtime, and
  standalone-discovery endpoints and derive WebTransport listener activation
  correctly.
- Legacy WebSocket clients without a profile retain existing JSON behavior.
- WebSocket and WebTransport profile negotiation select the same wire contract.
- WebSocket token permutations prove that `csrf.*` is consumed only as
  authentication metadata, is never selected as a negotiated wire profile, and
  does not depend on client token ordering.
- Required negotiation rejects an absent selected token; only an explicit
  `negotiation: legacy` JSON WebSocket candidate accepts the no-profile path.
- Ordered candidate expansion and downgrade-policy tests.
- Capability-response construction includes only policy-allowed, healthy,
  same-transport end-to-end candidates and applies revision, ETag, generation,
  expiry, private-cache, and `Vary` rules.
- Internal controller capabilities reject unauthorized callers, validate schema
  and expiry, change revision for readiness and draining changes, and describe
  only enabled transport/profile pairs.
- Transport-native probes authenticate, negotiate the requested surface and
  profile, return the matching controller revision, obey bounds, and never
  mutate registration, MCP, command, or discovery state.
- Capability-fetch `401`/`403`, `404`/`501`, `429`, timeout, malformed response,
  and `5xx` cases follow the specified no-guessing and backoff behavior.
- `portal-view` `auto`, forced-WebSocket, and required-WebTransport overrides
  produce the expected ordered attempts without changing the wire profile.
- The controller-BFF authority resolver preserves configured ingress prefixes,
  uses one authority for all four browser controller operations, rejects
  cross-authority redirects, and fails closed when cross-origin prerequisites
  are absent.
- Server enabled-set permutations produce the same result regardless of input
  order; duplicate or unknown transports are rejected. Client candidate order
  remains observable and authoritative.
- JSON length-prefix round trips, partial prefixes, invalid UTF-8, oversized
  lengths, empty payloads, trailing bytes, and multiple values.
- Golden bytes for every version 1 root type.
- Header round trips and rejection of invalid magic, flags, lengths, kinds, and
  reserved bytes.
- Cross-target fixture reads for all supported release targets.
- Schema compatibility checks using old committed fixtures.
- Semantic limits for strings, tags, lists, JSON, and timestamps.
- No unchecked `rkyv` access in production modules.
- Fuzz arbitrary headers and payloads without panic, excessive allocation, or
  unbounded validation work.

### Integration Tests

- WebSocket registration and commands remain unchanged.
- Runtime JSON over WebTransport registration, metadata, discovery, commands,
  responses, notifications, heartbeat, and cleanup match JSON over WebSocket.
- Runtime `rkyv` over WebSocket and WebTransport produces the same application
  behavior as runtime JSON.
- Browser MCP JSON requests, responses, notifications, cancellation, reconnect,
  and close behavior match across WebSocket and WebTransport.
- Capability refresh, stale readiness, controller rolling upgrades, and a route
  becoming unavailable between discovery and handshake produce categorized
  retry or fallback behavior.
- Mixed controller revisions create candidate-specific target pools; sessions
  are pinned to eligible targets, draining or stale targets receive no new
  sessions, and aggregate revision changes invalidate old candidates.
- The gateway WebTransport router maps reliable streams, reset, backpressure,
  draining, and close without parsing MCP JSON.
- Cross-transport and cross-codec gateway routes are rejected.
- Ticket expiry, replay, wrong route, wrong Origin, wrong profile, token expiry,
  and concurrent consumption are rejected.
- Replay-cache write failure, outage, degradation, ambiguous consume, and loss
  of atomicity fail ticket issuance or consumption closed without a local
  fallback.
- Gateway clock error below, at, and above the readiness threshold never extends
  the ticket hard maximum and enforces the earliest applicable deadline.
- Multi-replica ticket issuance and consumption uses the configured shared cache
  or proven affinity behavior.
- Ticket consumption injects the retained Bearer token upstream, the controller
  independently validates it, credential cache records are deleted, and the
  session closes no later than token expiry or maximum duration.
- Browser WebTransport rejects a wrong selected profile and a reliable-only
  session; `requireUnreliable` and the target-browser API contract are tested.
- Controller restart and client reconnect.
- Registration timeout and partial frames.
- Invalid, expired, wrong-audience, wrong-service, and wrong-environment JWTs.
- Oversized frames, too many streams, stalled readers, and blocked writers.
- Queue, per-session in-flight, global in-flight, stream, and session limits are
  exercised independently, including admission races and cleanup after timeout.
- Command timeout, late response, stream reset, and session close races.
- Serial candidate fallback when UDP is blocked or a profile is unsupported.
- An opaque browser pre-`ready` rejection falls back only in
  `preferWebTransport`; `requireWebTransport` fails without a WebSocket attempt.
- Explicit capability or ticket authentication, authorization, resource, and
  internal failures never enter the opaque-establishment fallback path.
- HTTP/2 page plus successful WebTransport, and HTTP/3 page plus failed
  WebTransport CONNECT or upstream QUIC, prove that page `nextHopProtocol` does
  not select the controller transport.
- No fallback for observable authentication, registration, protocol, resource,
  or internal failures before establishment, or for their structured forms
  after establishment.
- Old Rust client to new controller, new Rust client to old controller, and Java
  client to new controller.
- Controller drain with in-flight commands.
- Gateway policy reload affects new admission and capability revision without
  reinterpreting established sessions; listener removal drains and closes at
  the configured deadline; invalid reload retains the last valid revision.

### Deployment Tests

- Direct TCP and UDP access on the same numeric port.
- Docker Compose with explicit TCP and UDP mappings.
- Every supported Kubernetes and load-balancer topology.
- Browser-to-gateway and gateway-to-controller QUIC tested independently and
  together.
- Enterprise-network profiles that block UDP or WebTransport CONNECT fall back
  to an advertised WebSocket candidate without requiring a UI rebuild.
- Target browser matrix for CONNECT headers, profile negotiation, certificate
  validation, stream behavior, and network fallback.
- QUIC connection-ID routing and migration where claimed.
- TCP health remains available when experimental WebTransport is disabled.
- Synthetic probes distinguish gateway ingress, gateway upstream, and
  controller UDP or HTTP/3 failure.

### Benchmark Profiles

Compare at least:

1. runtime JSON-RPC over the legacy single-channel WebSocket;
2. runtime JSON-RPC over WebTransport using one ordered bidirectional stream;
3. runtime JSON-RPC over WebTransport using the proposed multiplexed topology;
4. runtime `rkyv` over one binary WebSocket channel;
5. runtime `rkyv` over WebTransport using one ordered bidirectional stream;
6. runtime `rkyv` over WebTransport using the proposed multiplexed topology;
7. runtime `rkyv` over raw QUIC with the closest equivalent single-stream and
   multiplexed topologies;
8. browser MCP JSON over WebSocket through `light-gateway`;
9. browser MCP JSON over WebTransport through `light-gateway`.

Treat codec, transport, framing, and stream topology as separate benchmark
variables:

- JSON versus `rkyv` on the same transport and topology measures codec cost.
- Single-stream versus multiplexed WebTransport with the same codec measures
  topology and head-of-line effects.
- Single-channel WebSocket versus single-stream WebTransport is the closest
  transport comparison, but native framing still differs and must be reported;
  it must not be described as a pure transport-only measurement.
- Legacy WebSocket versus multiplexed WebTransport measures the complete
  proposed operational change, not one isolated variable.

All paired cases use identical logical messages, concurrency, payload mixes,
warmup, and connection counts. Results report the selected wire profile,
transport, topology, WebTransport draft/library tuple, and browser reliability
mode so a reliable-only implementation cannot be mislabeled as the QUIC case.

Run profiles for:

- many idle registered sessions;
- registration bursts;
- small commands and responses;
- large dynamic JSON results;
- command responses concurrent with runtime log notifications;
- packet loss, reordering, and constrained bandwidth.

Record CPU and memory separately for browser, gateway, controller, and runtime,
plus allocations, bytes on the wire for each hop, registration rate, ticket
latency, command p50/p95/p99 latency, event drops, and reconnect time. Publish
the hardware, message mix, connection count, browser version, and network
conditions with results.

## Risks and Mitigations

| Risk | Mitigation |
| --- | --- |
| WebTransport draft or library changes | Pin and publish compatibility; keep feature experimental and WebSocket available |
| UDP blocked in customer networks | Explicit client modes, serial preference-mode fallback for opaque pre-establishment failure, synthetic readiness, and no fallback in required mode |
| Browser WebTransport omits cookies | Use CSRF-protected HTTPS ticket issuance and an authenticated CONNECT header |
| Target browser lacks CONNECT header support | Keep browser WebTransport disabled; do not use query-string tickets |
| Browser establishes reliable-only WebTransport instead of HTTP/3/QUIC | Set `requireUnreliable`, verify `reliability`, and reject or fall back before MCP initialization |
| Ticket theft or replay | Short lifetime, route/origin/profile binding, atomic one-use replay cache, redacted logs |
| Ticket cache exposes retained access tokens | Restrict and protect cache records, redact values, consume atomically, and delete the complete record on use or expiry |
| Replay cache is unavailable or returns ambiguous state | Fail ticket issuance and consumption closed; never degrade to a local cache or replayable ticket |
| Gateway clock skew changes ticket validity | Require clock-synchronization readiness, enforce cache and absolute expiry, and allow no positive grace beyond the hard maximum |
| Gateway principal and controller identity diverge | Inject the retained Bearer token upstream and require independent controller validation; do not invent role claims |
| Gateway QUIC service destabilizes TCP proxy | Separate listener/runtime, independent readiness, resource limits, failure isolation |
| One gateway WebTransport leg is healthy and the other fails | Per-leg probes, categorized metrics, and no session acceptance until upstream establishment succeeds |
| Capability response is stale or overstates end-to-end readiness | Short private cache lifetime, same-transport synthetic probes, refresh after failure, and actual handshake as authority |
| Browser hides the specific WebTransport establishment cause | Preserve explicit capability and ticket HTTP errors; use `Establishment failed` for opaque pre-`ready` rejection, retain the detailed cause in server telemetry, and require WebTransport where downgrade is unacceptable |
| Capability request itself fails | Use only a still-fresh validated response; otherwise attempt no transport and retry discovery with jittered backoff |
| Page HTTP version is mistaken for controller reachability | Never select from `nextHopProtocol`; use gateway candidates, browser feature detection, and the real session attempt |
| WebTransport-only MCP removes enterprise fallback | Use dual per-surface transport enabled sets until UDP and WebTransport CONNECT are proven for the complete client fleet |
| Wire-profile or transport downgrade | Ordered explicit client candidates, unordered server enabled sets, required-mode policy, reject unlisted pairs |
| `rkyv` schema drift | Shared wire crate, immutable roots, protocol negotiation, golden fixtures |
| Malformed archive or resource exhaustion | Safe validation, preallocation limits, semantic bounds, fuzzing, session quotas |
| No meaningful performance gain | Benchmark against simpler alternatives before changing defaults |
| Dynamic JSON still dominates | Measure it; add typed payloads only in a new version for proven hot paths |
| Event traffic affects commands | Separate event and command streams, bounded queues, fairness tests |
| Multi-replica request reaches wrong pod | Keep single active replica or design a distributed session router separately |
| Load balancer supports HTTP/3 but not WebTransport | Require end-to-end draft-specific integration tests |
| WebSocket and WebTransport route config drifts | Shared resolver, diagnostics, and configuration parity tests |
| CSRF token is selected as a WebSocket wire profile | Parse tokens by role, strip CSRF before upstream negotiation, and never use first-token selection |
| Fallback creates duplicate registrations | Serial attempts, registration acknowledgement boundary, connection-ID-guarded cleanup |
| Operational complexity exceeds benefit | Preserve WebSocket default and define a complete rollback path |

## Phase 0 Decisions and Reopen Questions

The failed feasibility run locks the following decisions without authorizing
production implementation:

- WebTransport remains disabled and WebSocket/JSON remains the production path.
- Planned gateway replacement uses drain when possible and bounded client
  reconnect after interruption. There is no zero-downtime QUIC preservation
  claim.
- The replay-store candidate is a shared Redis-compatible service using
  hash-only keys, protected values, hard TTL, `SET NX PX`, atomic `GETDEL`, TLS,
  ACLs, and fail-closed outage behavior. There is no local production fallback.
- Internal capability and probe resources use a dedicated gateway mTLS identity.
- `controller-wire` remains a dependency-light, independently versioned crate
  owned by `light-fabric` and consumed by `controller-rs`.
- WebSocket and WebTransport route files remain separate initially with a shared
  resolver and enforced parity diagnostics.
- The nine-case benchmark manifest and required workload/metric set are locked
  by the Phase 0 evidence package.

Reopen WebTransport feasibility only when a candidate Rust stack implements the
selected current draft and exposes request/response negotiation in both roles,
and a target shipping browser passes CONNECT headers, profile negotiation,
`requireUnreliable`, reliability, reset, close, and stream tests end to end.
Deployment environments, enterprise UDP/CONNECT behavior, production load
targets, and any distributed controller session router remain later questions
because the mandatory local tuple failed first.

## References

- [WebTransport over HTTP/3, current IETF draft](https://datatracker.ietf.org/doc/draft-ietf-webtrans-http3/)
- [W3C WebTransport API](https://www.w3.org/TR/webtransport/)
- [QUIC transport, RFC 9000](https://www.rfc-editor.org/rfc/rfc9000.html)
- [QUIC datagrams, RFC 9221](https://www.rfc-editor.org/rfc/rfc9221.html)
- [`rkyv` documentation](https://docs.rs/rkyv/latest/rkyv/)
- [`rkyv` format documentation](https://rkyv.org/format.html)
- [Protocol Buffers overview](https://protobuf.dev/overview/)
- [AWS Application Load Balancer listeners](https://docs.aws.amazon.com/elasticloadbalancing/latest/application/load-balancer-listeners.html)
- [AWS Network Load Balancer listeners](https://docs.aws.amazon.com/elasticloadbalancing/latest/network/load-balancer-listeners.html)
