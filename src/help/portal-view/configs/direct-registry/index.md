# Direct Registry Configuration

The direct registry resolves a `serviceId` (and an optional environment tag) to
one or more target hosts from a static configuration instead of a service
registry. It resides in `direct-registry.yml` and is managed through the
portal-view interface and config server with properties named
`direct-registry.<property>`.

It is supported by both the Java implementation in `light-4j` and the Rust
implementation in `light-fabric`, and it is used for local development, for
targets that are not registered in the controller, and as a fallback when the
portal registry is unavailable. It is a transitional solution until service
discovery from the controller covers every deployment.

## Overview of Configuration Properties

| Property | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| **[directUrls](./direct-urls.md)** | Object | `{}` | Maps a service id, optionally with an environment tag, to one or more target urls. |

## Lookup Order

1. The gateway looks up `serviceId|envTag` when an environment tag is present.
2. It falls back to the plain `serviceId` entry.
3. When neither exists, discovery from the portal registry is used.

In `light-fabric`, portal-registry discovery is attempted first, and
direct-registry is the fallback when discovery is unavailable or returns no
usable endpoint.
