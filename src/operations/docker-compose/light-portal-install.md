# light-portal-install

`light-portal-install` packages the local platform for users who want Docker
Compose as the only runtime dependency and do not need sibling source checkouts.

## Intended use

- A complete local Portal at `https://local.localhost`.
- Product evaluation and demonstrations.
- Repeatable installation from released images and signed assets.

It is not a production secret-management example. Fixed local/demo identities
exist to make installation self-contained.

## Lifecycle

For a checked-out repository:

```bash
./install.sh install
./install.sh status
./install.sh logs
./install.sh stop
```

Use the README's explicit reinstall procedure when intentionally recreating
databases or refreshing release assets. Routine restart should preserve the
PostgreSQL volume and service caches.

## Runtime shape

The Compose file includes the Portal database and bootstrap jobs, OAuth,
controller, Config Server, hybrid services, Portal service, Gateway, dedicated
LLM Gateway, Workflow, Agent, Knowledge API/admin/worker and demo services.
`light-a2a` is available under the `a2a` profile.

The primary browser endpoint is host port `443`. The local certificate is
self-signed, so a browser warning is expected only for the documented local
hostname.

## Configuration and secrets

The installer downloads and extracts versioned runtime/UI assets. Checked-in
Compose supplies local-only identities and writes runtime secret material into
protected container-local files where a service requires a file reference.
Provider API keys remain user inputs in `.env` and must not be committed.

The PostgreSQL container holds separate logical databases for Portal,
Knowledge, and per-host operational state. Runtime roles and schema search paths
enforce the boundary even though the databases share one container.

When a released Config Server snapshot activates an optional cryptographic
feature, its local secret must satisfy that feature's encoding and length
contract. Starting without an LLM provider key is allowed; activating a
reasoning-seal reference with malformed key material is not.

## Upgrade checks

After upgrading, verify the downloaded asset version, running image IDs,
database migration completion, Config Server snapshot generation, and health of
the public Gateway. A successful installer command is not sufficient if the
live endpoint is still using an older image or cached snapshot.

