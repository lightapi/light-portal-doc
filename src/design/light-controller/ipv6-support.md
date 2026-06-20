# Light Controller IPv6 Support

## Problem

The Rust `controller-rs` service is the control-plane endpoint for runtime
registration, discovery, MCP admin traffic, and portal event streams. In
dual-stack deployments, clients can resolve the controller hostname to either
IPv4 or IPv6. The controller listener and its TLS configuration must therefore
support IPv6 without changing the existing IPv4 deployment defaults.

The important distinction is between socket addresses and service metadata:

- the controller listener uses a socket address such as `0.0.0.0:8438` or
  `[::]:8438`;
- registered runtime instances publish a host address string plus a separate
  port, such as `fdd0:0:0:1::3` and `8443`.

## Current Behavior

`controller-rs` already stores its bind address as a Rust `SocketAddr`.
The default remains IPv4 wildcard binding:

```text
0.0.0.0:8438
```

The listener address can be overridden with `CONTROLLER_ADDR`.
For IPv6, the value must use bracketed socket-address syntax:

```bash
CONTROLLER_ADDR='[::]:8438'
```

This value is used directly by both server modes:

- HTTPS/WSS mode uses `axum_server::bind(settings.listen_addr)`.
- HTTP/WS mode uses `tokio::net::TcpListener::bind(settings.listen_addr)`.

There is no string concatenation of IP and port in the controller listener
path, so the common IPv6 failure form `:::8438` is avoided.

## Goals

- Support IPv4, IPv6, and dual-stack controller listener binding.
- Keep the current default as IPv4 wildcard binding.
- Keep the existing `CONTROLLER_ADDR` configuration contract.
- Accept runtime registration metadata that uses IPv4 literals, IPv6 literals,
  or DNS hostnames.
- Reject unspecified runtime registration addresses such as `0.0.0.0` and
  `::`, because those are bind addresses, not reachable service addresses.

## Non-Goals

- Do not enable IPv6 by default.
- Do not change controller WebSocket paths or JSON-RPC contracts.
- Do not change the runtime registration metadata shape.
- Do not add client-side IPv4 fallback in this change.

## Listener Configuration

Default IPv4 listener:

```bash
CONTROLLER_ADDR='0.0.0.0:8438'
```

IPv6 wildcard listener:

```bash
CONTROLLER_ADDR='[::]:8438'
```

Specific IPv6 interface:

```bash
CONTROLLER_ADDR='[fdd0:0:0:1::10]:8438'
```

Specific IPv4 interface:

```bash
CONTROLLER_ADDR='172.16.1.10:8438'
```

The brackets are required only because `CONTROLLER_ADDR` is a full socket
address. They separate the IPv6 literal from the port.

## TLS Configuration

The controller starts with TLS enabled by default. IPv6 listener support does
not remove the normal TLS hostname requirements.

For production, provide a certificate whose Subject Alternative Name covers the
DNS name or IP address clients use to reach the controller:

```bash
CONTROLLER_TLS_CERT_PATH=/config/server.pem
CONTROLLER_TLS_KEY_PATH=/config/server.key
CONTROLLER_TLS_TRUST_CERT_PATH=/config/ca.pem
```

For generated local self-signed certificates, include any IPv6 literal that
clients will use:

```bash
CONTROLLER_TLS_SERVER_NAME=localhost
CONTROLLER_TLS_ALT_NAMES='localhost,127.0.0.1,::1'
```

If clients connect by DNS name, prefer adding that DNS name to the certificate
SAN and keep clients using the name instead of a raw IP literal.

## Runtime Registration Metadata

Runtime services connect outbound to Light Controller and send
`service/register` metadata. The registration address is not a socket address;
the address and port are separate fields.

IPv6 registration metadata should use the raw IPv6 literal:

```json
{
  "serviceId": "com.networknt.light-gateway-1.0.0",
  "protocol": "https",
  "address": "fdd0:0:0:1::3",
  "port": 8443
}
```

Do not use brackets in the `address` field:

```json
{
  "address": "[fdd0:0:0:1::3]"
}
```

Brackets are only used when constructing URL authorities or socket addresses.
The controller validates registration addresses as IP literals or DNS hostnames
and rejects unspecified bind addresses such as `0.0.0.0` and `::`.

## Discovery Behavior

Discovery returns the registered address and port separately. Downstream
clients, such as `light-gateway`, are responsible for building a reachable
upstream authority. For IPv6 literals, clients must bracket the address when
they construct a URL or `host:port` authority:

```text
address = fdd0:0:0:1::3
port    = 8443
target  = [fdd0:0:0:1::3]:8443
```

## Deployment Guidance

Only configure the controller with `CONTROLLER_ADDR='[::]:8438'` when the host,
container network, Kubernetes Service, and ingress path are intended to accept
IPv6 traffic.

In a dual-stack environment, verify all of these:

- the controller process is listening on IPv6;
- DNS returns the expected address family;
- TLS SANs cover the hostname or IP clients use;
- runtime services can open outbound WebSocket connections to the controller;
- registered service metadata publishes reachable addresses, not wildcard bind
  addresses.

## Verification

From a peer in the same network:

```bash
getent ahosts <controller-host>
curl -k -g https://[<controller-ipv6>]:8438/health
curl -k -v https://<controller-host>:8438/health
```

For WebSocket clients, verify the same address family through the real endpoint:

```text
wss://<controller-host>:8438/ws/microservice
wss://<controller-host>:8438/ws/discovery
wss://<controller-host>:8438/ctrl/mcp
```

If a TLS client connects by IPv6 literal and fails certificate validation,
check the certificate SANs before changing the controller listener.
