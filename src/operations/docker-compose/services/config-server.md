# Config Server

`config-server` renders and serves runtime configuration selected by host,
service ID and environment tag. The Compose distributions normally publish it
on host port `8435` and mount Rust configuration through
`LIGHT_RS_CONFIG_DIR`.

## Inputs

| Input | Purpose |
| --- | --- |
| Portal database connection | Reads configuration instance, property and snapshot projections. |
| `LIGHT_RS_CONFIG_DIR` | Local startup and template directory. |
| `RUST_LOG` | Logging filter. |
| `CONFIG_LOG_ANSI` | ANSI log setting. |
| OAuth/JWKS configuration | Authenticates configuration clients. |
| Controller configuration | Registers the service and supports control-plane operations. |

## Snapshot selection

Clients identify an exact tuple including host, service and environment. A
snapshot for a similarly named host or service is not a fallback. Each client
also supplies a Portal authorization identity whose claims must be valid for
the requested instance.

Downloaded snapshots are commonly retained in a named `config-cache` volume.
The cache is part of startup resilience, but it can hide a publication mismatch
if an operator assumes a restart always fetches new configuration.

## Change behavior

Configuration becomes active at service startup or through an explicit reload
of a reloadable module. Copying a file into a cache directory does not itself
activate it. For a failed publication, compare the selected snapshot ID,
generation and source level with the value expected from Compose.

