# Light OAuth IPv6 Support

## Problem

The Rust `light-oauth` service binds its HTTPS listener to `0.0.0.0`.
That is correct for IPv4, but it does not accept connections sent to an IPv6
address.

In a dual-stack container network, Docker DNS can return the IPv6 address for
`light-oauth` before the IPv4 address. A client that does not retry the next
address can fail even though the service is healthy on IPv4. One observed
failure is the gateway proxying `/oauth2/{providerId}/code` to
`https://light-oauth:6881` and receiving `ECONNREFUSED` on the IPv6 address.

## Goals

- Allow `light-oauth` to bind IPv4, IPv6, or a specific interface from config.
- Keep the current default behavior as IPv4 wildcard binding.
- Avoid breaking existing deployments whose `server.yml` does not contain the
  new property.
- Build the listener address with `SocketAddr` so IPv6 addresses are parsed
  correctly.

## Non-Goals

- Do not enable IPv6 for every deployment by default.
- Do not change TLS, OIDC, token, or database behavior.
- Do not change gateway upstream retry behavior in this change.

## Configuration

`light-oauth` adds a server bind IP property:

```yaml
ip: ${server_ip:0.0.0.0}
```

The default value remains:

```yaml
server_ip: "0.0.0.0"
```

To listen on IPv6 wildcard:

```yaml
server_ip: "::"
```

To listen on a specific IPv4 or IPv6 address:

```yaml
server_ip: "172.16.1.3"
```

```yaml
server_ip: "fdd0:0:0:1::3"
```

## Implementation

The Rust config model includes an `ip` field with a default of `0.0.0.0`.
The default keeps old external `server.yml` files working.

The listener address is built as:

```rust
let ip = config.ip.parse::<IpAddr>()?;
let addr = SocketAddr::new(ip, config.port);
```

This avoids string formatting problems with IPv6 addresses. For example,
`::` plus port `6881` must become `[::]:6881`, not `:::6881`.

## Deployment Guidance

Use IPv6 binding only when the runtime network is intentionally dual-stack and
other services can reach the IPv6 address. In a container environment, confirm
that:

- the container network has IPv6 enabled;
- the service has an IPv6 address;
- clients resolve or connect to the same address family;
- health checks cover the chosen address family.

For local or single-stack deployments, keep the default IPv4 binding.

## Verification

For IPv4 default:

```bash
curl -k https://light-oauth:6881/oauth2/<providerId>/keys
```

For IPv6 wildcard binding in a dual-stack network, verify from another
container:

```bash
curl -k -g https://[<light-oauth-ipv6>]:6881/oauth2/<providerId>/keys
```

If the client uses service DNS, verify that the first returned address family
is reachable:

```bash
getent ahosts light-oauth
curl -k -v https://light-oauth:6881/oauth2/<providerId>/keys
```
