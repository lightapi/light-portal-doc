# Direct Registry: directUrls

`directUrls` maps a service id to the hosts that serve it, so that a request can
be routed without service discovery.

- **Type:** Map of service id to one or more urls
- **Default:** `{}`

```yaml
directUrls:
  code: http://192.168.1.100:6881,http://192.168.1.101:6881
  token: http://192.168.1.100:6882
  com.networknt.test-1.0.0: http://localhost,https://localhost
  command|0000: https://192.168.1.142:8440
  command|0001: https://192.168.1.142:8441
  command|0002: https://192.168.1.142:8442
```

The key is the service id. When the same service is deployed to several
environments, append the environment tag to the service id with a vertical bar,
as in `command|0000`. The value is a single url, or several urls separated by
commas when the service has multiple instances to load balance between. Each url
must use `http` or `https` and must contain a host.

For config-server injection, the same map can be written as a JSON string or as
a `key=value&key=value` string:

```yaml
directUrls: {"code":"http://192.168.1.100:6881","command|0000":"https://192.168.1.142:8440"}
```

```yaml
directUrls: code=http://192.168.1.100:6881&command|0000=https://192.168.1.142:8440
```

## Base Path for a Path-Based Kubernetes Ingress

When the target service runs in a Kubernetes cluster behind an ingress that
routes on a path prefix, the namespace and service are part of the url and the
ingress strips them before the request reaches the pod. Put that prefix in the
url as its path:

```yaml
directUrls:
  com.networknt.petstore-1.0.0: https://api.example.com/namespace1/service1
  com.networknt.petstore-1.0.0|dev: https://api.example.com/namespace1/service1-dev
```

With the entry above, a request for `/v1/pets` is sent to
`https://api.example.com/namespace1/service1/v1/pets`. The ingress uses
`/namespace1/service1` to select the pod and removes it, so the pod receives the
original `/v1/pets` request. A url without a path, such as
`https://192.168.1.142:8440` for a VM deployment, is unaffected.

Note the following when the base path is used:

- The ingress must be configured to strip the prefix. Examples are the nginx
  `rewrite-target` annotation and the `URLRewrite` filter with
  `ReplacePrefixMatch` in the Gateway API.
- The pod does not know its public path. Any absolute url a service returns,
  such as a `Location` redirect, a cookie `Path`, an OAuth redirect uri, or the
  `servers` entry of an OpenAPI specification, must be configured with the
  public base path by the service itself.
- The `Host` header and the TLS SNI are taken from the host of the url, not from
  the base path, so host-based ingress rules keep working.
- A service registered with the controller advertises the same thing with the
  reserved `basePath` registration tag, which it sets through `basePath` in its
  `server.yml`. An entry in `directUrls` is only needed for a service that is not
  registered.

Where the base path is applied:

| Runtime | Component | Behavior |
| :--- | :--- | :--- |
| `light-fabric` | Router, proxy, WebSocket, A2A, MCP tools | The path of the url is used as the upstream path prefix of every request. |
| `light-fabric` | OAuth token, JWK, and SPA auth lookups | The configured uri is appended to the url, so the base path is kept. |
| `light-4j` | `Cluster.serviceToUrl` and `Cluster.services` | The url and uri returned include the base path. |
| `light-4j` | `Http2Client.callService`, `Http2ServiceRequest`, MCP tools | The base path is prepended to the path of the request. |
| `light-4j` | `light-router` and `http-sidecar` | Undertow proxies to the host url, which includes the base path. |

In `light-4j` the base path is carried as a `basePath` url parameter so that it
is not mixed up with the path of a discovery url, which holds the service id.
The parameter is derived from the url and does not need to be configured.

An alternative to a path-based ingress is a host-based one, such as
`https://service1.namespace1.api.example.com`, which needs no prefix stripping
and leaves the paths of the service untouched.
