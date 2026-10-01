# Outbound TLS trust for public and enterprise APIs

## Status

Proposed production design, revised after review. Configuration examples below
describe proposed capabilities unless explicitly marked current. This document
does not authorize implementation, deployment, or a change to Workflow token
semantics. Production implementation, deployment, and Workflow G03 remain
separately gated.

## Problem and recommendation

Light Gateway must connect to public HTTPS APIs and enterprise services signed
by private certificate authorities. A private CA file must not accidentally
exclude public roots, and adding public roots must not silently widen an existing
private-only trust policy.

Introduce explicit outbound trust modes: platform roots, configured roots only,
and platform roots plus configured roots. Implement them by runtime composition
in the existing patched `pingora-core` connector. Preserve current behavior when
the new mode is absent. Every connection made under an explicit mode verifies
both the certificate chain and the destination hostname or IP SAN.

Operators should trust approved CA roots, rather than collecting each API's
server certificate. A public API whose certificate chains to an installed public
root normally needs no API-specific certificate configuration. A private API
requires its organization's approved CA. A self-signed server needs explicitly
approved trust material or, preferably, a certificate issued by that private CA.

## Current implementation and observed failure

The inspected `light-fabric` source connects the client CA configuration to
Pingora's global outbound `ServerConf.ca_file`:

- `frameworks/light-pingora/src/lib.rs`, `upstream_ca_file`: selects
  `client.tls.caCertPath`, then `client.caCertPath`, then
  `bootstrap.bootstrapCaCertPath`; validates the PEM bundle and returns its path.
- `PingoraRuntime::run`: assigns that path to `server_conf.ca_file` once, at
  startup.
- `Cargo.toml` replaces `pingora-core` with the local `patches/pingora-core`.
  In `patches/pingora-core/src/connectors/tls/rustls/mod.rs` the connector starts
  with an empty root store and loads either the configured CA file or platform
  roots. These sources are alternatives, not an additive union.
- Platform roots come from `pingora-rustls::load_platform_certs_incl_env_into_store`,
  which uses `rustls-native-certs` and honors `SSL_CERT_FILE` / `SSL_CERT_DIR`.
- `apps/light-gateway/src/main.rs` sets `peer.options.verify_hostname = false`
  for every upstream when `client.tls.verifyHostname` is false. The connector
  then selects `VerificationMode::SkipHostname`: the chain is checked, the name
  is not. An empty SNI selects `VerificationMode::SkipAll`.
- `apps/light-gateway/docker/Dockerfile` installs the OS `ca-certificates` package.

The main Compose file sets `CLIENT_CACERTPATH: /config/ca.pem` and
`CLIENT_VERIFYHOSTNAME: "false"` for `light-gateway`; `workflow-mcp-test-gateway`
and `llm-gateway` have the same pair. The inspected running Gateway's outbound
GitHub connection failed with `UnknownIssuer`, SNI `api.github.com`, and returned
HTTP 502. Selecting the private CA file prevented the connector from loading
public roots.

Incoming listener certificates, upstream server trust, and mTLS client identity
are separate concerns. Trusting Gateway's local CA in curl fixes curl-to-Gateway
verification; it does not fix Gateway-to-upstream verification. Disabling curl
verification does not change the Gateway's outbound trust store either.

## Why hostname verification is mandatory

Today, internal routes with hostname verification disabled accept any certificate
issued by the private CA. Adding public roots to the same global store without
enabling hostname verification would make those routes accept any publicly
issued certificate, including one an attacker obtains for a domain they own.
Verifying only selected destinations does not prevent that: the store is shared,
and a certificate may chain through different anchors on different connections.

Therefore no explicit mode may run with hostname verification disabled, on any
connection. Separate trust domains need separate stores, which this design
provides only through separate Gateway instances (see 4b below). Per-destination
trust stores with their own verification policies are a possible future feature,
not part of v1.

## Rejected alternative: deployment-managed combined PEM bundle

Current capabilities allow generating a PEM file containing the runtime's public
roots plus approved private CAs and pointing `client.tls.caCertPath` at it. This
needs no code, but the deployment must reproduce the image's public bundle,
regenerate it whenever the CA package, image, or enterprise policy changes, and
recreate Gateway. A copied bundle freezes old trust, including removed roots.
`/etc/ssl/certs/ca-certificates.crt` is a Debian-family convention, not a portable
contract, and a bundle built on a workstation can differ from the image's store.

It remains an acceptable temporary local workaround, subject to the same
hostname-verification requirement. It is not the recommended production design.

## Design: runtime trust modes in the patched connector

### Configuration

```yaml
tls:
  verifyHostname: true
  trustMode: platform-plus-configured
  caCertPath: /config/enterprise-ca.pem
```

| Mode | Sources | Intended use |
| --- | --- | --- |
| absent (legacy) | Current selection, unchanged | Existing deployments |
| `platform` | Platform roots only | Public APIs, or enterprise roots already installed in the runtime store |
| `configured-only` | Approved PEM bundle only | Restricted private trust domains |
| `platform-plus-configured` | Platform roots plus approved PEM bundle | Public and private enterprise APIs from one Gateway |

Reuse `caCertPath` as the configured bundle reference through the established
client configuration mapping and flat-property compatibility. The production
property catalog and Portal snapshot compiler must recognize `trustMode`; unknown
values are rejected, not ignored.

### Source selection

| Mode | Required source selection |
| --- | --- |
| Absent | Preserve current selection and precedence exactly, including bootstrap fallback |
| `platform` | Ignore configured and bootstrap CA sources; require nonempty platform roots |
| `configured-only` | Require an explicitly configured, nonempty, valid bundle; no bootstrap fallback, no platform roots |
| `platform-plus-configured` | Require both a configured nonempty valid bundle and nonempty platform roots; no bootstrap fallback |

Missing files, malformed certificates, an empty required store, or platform
loader errors fail startup with a clear diagnostic. Any explicitly supplied
source that is missing, unreadable, or contains an invalid certificate fails
startup even when another source supplies usable roots; partial loading must
never silently reduce the intended trust set. Never fall back to a reduced or
broader trust set. Deduplicate certificates by DER fingerprint.

### Integration point

Carry the mode from `upstream_ca_file`'s replacement into the connector through
`ServerConf` or the connector options, and replace the either/or root-store
construction in `patches/pingora-core/src/connectors/tls/rustls/mod.rs`:

```rust
match trust_mode {
    Legacy => { /* existing if/else, unchanged */ }
    Platform => load_platform_certs_incl_env_into_store(&mut ca_certs)?,
    ConfiguredOnly => load_ca_file_into_store(path, &mut ca_certs)?,
    PlatformPlusConfigured => {
        load_platform_certs_incl_env_into_store(&mut ca_certs)?;
        load_ca_file_into_store(path, &mut ca_certs)?;
    }
}
```

Keep the change inside the existing patch; no upstream Pingora API is required.
Implementation still needs configuration propagation, validation, diagnostics,
and the tests below.

### Verification identity

In every explicit mode:

- Effective hostname verification must be true after configuration mapping and
  environment overrides. An effective `verifyHostname: false`, including the
  current `CLIENT_VERIFYHOSTNAME: "false"` Compose override, fails startup; it is
  never silently overridden.
- Every TLS peer must carry a valid verification identity. An empty identity is
  rejected instead of selecting `SkipAll`. DNS destinations verify DNS SANs; IP
  destinations verify IP SANs. The router derives the identity from the URL host,
  so an IP destination has a non-empty identity; the absence of a DNS SNI
  extension for an IP destination is not itself a failure.

Legacy mode keeps its current verification behavior.

### `SSL_CERT_FILE` and `SSL_CERT_DIR`

Platform loading honors these variables, as `rustls-native-certs` does. In
`platform` and `platform-plus-configured` modes they may replace the native store
as the platform source; this is documented operator behavior, not an error.
`configured-only` never invokes the platform loader, so they have no effect there.
Startup diagnostics state whether platform roots came from the native store or
from an override variable, naming the variable but not printing its value.
An override is an explicitly supplied source: if it is missing, empty, or
contains an invalid certificate, startup fails, even when the other variable or
the configured bundle supplies usable roots. If the platform loader reports
per-certificate or per-file errors alongside successfully loaded roots, treat
those errors as failures rather than accepting the partial result. Other TLS
clients keep their own policies.

### Startup-only loading and diagnostics

For Linux v1, automatic platform discovery uses `openssl-probe` to select the
system bundle and OpenSSL hash directory. Load every selected source through the
strict loader, rather than delegating loading to rustls-native-certs 0.7's
permissive helper. An absent optional discovery candidate is not required to
exist. Once selected, an unreadable, empty or invalid source fails even when
another source has valid roots. Explicit FILE/DIR overrides replace discovery;
configured-only does not discover or load platform sources. Legacy loading is
preserved separately. Linux container qualification remains the supported v1
scope; no native Windows/macOS qualification is implied.

Supported explicit bundles contain ordinary `CERTIFICATE` PEM blocks, with
comments or descriptive text permitted outside those blocks. Every block must
parse and contain valid certificate DER; malformed, truncated or invalid blocks
fail the entire source even alongside valid certificates. Empty/comment-only
bundles fail. Unsupported PEM blocks, including private keys, fail rather than
being skipped. `TRUSTED CERTIFICATE` blocks are rejected with a diagnostic:
their trust/rejection attributes are not supported by v1 and must not be discarded
by relabeling the block. Use an approved ordinary certificate bundle whose trust
semantics have been reviewed.

The restart-required guard also applies when mode is absent: legacy CA/hostname
changes require restart. Rotating a CA file at the same path can block
token/client/sidecar reload aliases. A failed preflight prevents other selected
modules in Reload All from applying. Rejection leaves the existing connector
active; it does not restore changed files on disk. Restore the approved files
or restart with the separately approved candidate.

v1 loads and validates trust once, at startup. Adopting changed platform or
private roots requires a controlled restart; an already-built connector does not
reload roots when files change. At startup, log the mode, selected source
categories, the platform-source origin, certificate counts per source after
deduplication, and an effective trust digest over the mode and sorted DER
fingerprints. Diagnostics contain no tokens, private keys, or headers.

### Minimal restart-required reload guard

Existing client configuration reload could otherwise report success while the
connector keeps its startup store. On reload, compare the candidate's mode,
configured CA reference and current file content, and hostname verification
policy with the startup values. If any differ, reject the reload with an explicit
`restart required` result and leave the prior configuration active, without
partially applying related client TLS settings. An invalid candidate returns a
validation error instead. Reloads with unchanged trust proceed normally.

Richer reporting, such as separate requested and active digests, and hot reload
of the connector and its pools are deferred. Do not claim hot reload until the
connector and every affected pool rebuild safely.

### Scope and security boundaries

v1 covers ordinary Gateway router/proxy upstream TLS. Config-server bootstrap,
controller connections, token exchange, MCP outbound clients, and model-provider
clients use separate TLS builders; their policies are unchanged and should be
inventoried before any later adoption of a shared resolver.

A CA trust store authenticates server certificates; it does not authorize network
destinations. Preserve SNI derived from the destination, approved schemes and
ports, route restrictions, ACLs, and fixed credential destinations. An approved
enterprise interception CA may authenticate intercepted public hosts; adding one
is an explicit operator trust decision. In combined mode, a configured private CA
can authenticate any hostname for which it issues a matching certificate.

### Platform support

v1 qualifies the Linux Gateway container image only and verifies that the
container uses its own store rather than the host's. Native Windows and macOS
deployments are unqualified. Distroless or minimal images require deliberate
root-store provisioning.

## Implementation and acceptance gates

1. Implement the trust modes, source selection, verification-identity rules,
   startup diagnostics, and reload guard in the existing patch and runtime
   configuration. Add the catalog and Portal snapshot mappings.
2. Qualify against isolated TLS servers signed by two independent CAs, one
   standing in for platform roots and one for an enterprise CA, with no public
   API dependency:
   - each mode's inclusion and exclusion, and legacy behavior unchanged;
   - wrong DNS SAN and wrong IP SAN rejected even when the issuer is trusted;
   - untrusted issuer rejected; empty identity rejected;
   - startup failure for missing, malformed, or empty required sources;
   - effective `verifyHostname: false` rejected, including YAML true overridden
     by environment false, the reverse case, and effective true accepted;
   - `SSL_CERT_FILE` and `SSL_CERT_DIR` precedence, plus missing, empty, and
     invalid override sources, including an invalid source alongside another
     source that supplies usable roots;
   - the reload guard returns `restart required` for a changed mode, CA reference,
     or CA file content at an unchanged path, and new connections keep the
     startup store until restart.
3. Exercise the real connector, not only the root-store helper. Cover both the
   ordinary configuration path and the modified-configuration branch where
   `SkipHostname` / `SkipAll` are selected, since behavior there is not assumed
   identical.
4. Qualify the Linux container image.

## Deployment and migration

Enabling an explicit mode is an owner-controlled deployment step, separate from
implementation.

### SAN inventory

For each affected Gateway instance, inventory internal TLS upstreams: the DNS
names or IP addresses Gateway actually uses, and each certificate's SANs. Record
which certificates would fail hostname or IP SAN verification. The result selects
4a or 4b.

### 4a — Combined trust on the existing Gateway

Use when the inventory shows a manageable number of certificates to reissue.

1. Reissue certificates whose SANs do not cover their actual destination names;
   IP destinations need IP SANs. Preserve the local CA those services need.
2. Set hostname verification true in managed client configuration and remove
   conflicting overrides, including `CLIENT_VERIFYHOSTNAME`. Inspect the final
   effective setting, not only YAML.
3. Set `trustMode: platform-plus-configured` with the enterprise bundle.
4. Create the normal Portal snapshot and restart. Capture the startup trust
   digest and effective verification setting, then check public and internal
   upstream TLS. On failure, restore the prior approved configuration through the
   normal lifecycle; never disable verification to recover.

### 4b — Optional separate platform-only Gateway

Use when internal certificate migration cannot complete before external access
is needed. This is a deployment choice, not an additional v1 implementation
requirement.

- The external instance uses the new `platform` mode with hostname verification
  true. `platform` mode is required because the legacy path falls back to
  `bootstrap.bootstrapCaCertPath` even without `CLIENT_CACERTPATH`, which would
  again exclude public roots.
- Add it as a service in the main Compose file, not an overlay, with its own
  Portal configuration: handler chain, ACL rules, header mutation, router, and
  outbound credential reference.
- Before selecting it as a Workflow target, verify Workflow's existing
  Gateway-origin and credential-forwarding rules. Exchanged LONG tokens are only
  sent to the single configured Gateway origin
  (`apps/light-workflow/src/executor.rs`, `long_http_target_allowed`, using
  `bound_mcp` `gateway_url`), so a second origin would reject those calls. Either
  keep Workflow's target on the existing Gateway origin, for example by routing
  the external path from the existing Gateway to the platform-only instance, or
  bring any change to the allowed origin to separate review.
- A second Gateway implies no authorization change. It enforces the same user
  and application authentication and endpoint ACLs, and credential forwarding
  rules stay as they are.
- When the existing Gateway forwards to the external instance, only the external
  instance injects the outbound API credential. The first hop must preserve the
  user and application credentials the external instance needs for its own
  authentication and ACL checks. Do not apply the G02 header mutation, which
  removes caller credentials and inserts the PAT, on the first hop.
- Qualify the Gateway-to-Gateway hop separately: TLS identity verification of the
  external instance, forwarding of user and application credentials, ACL denial
  at the external instance, and fixed routing that callers cannot override.
  Keeping Workflow on its approved origin does not by itself prove this hop is
  configured correctly.

The existing Gateway stays in legacy mode until its own migration under 4a.

### Live qualification

After the selected deployment, the owner performs the G02 live read
qualification for public API access and confirms an internal TLS upstream and
config-server/bootstrap connectivity remain healthy. Do not enable global
combined trust while any route on that instance remains hostname-unverified.

## Related design

- [Local Model Provider Transport For LLM Gateway](local-model-provider-transport.md)
- [Light Gateway](../light-gateway.md)

These transports may have distinct policy and lifecycle requirements; this
document does not supersede their destination or private-network controls.
