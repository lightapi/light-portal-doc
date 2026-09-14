# Operations

This section documents the deployed Light Portal runtime: how the supported
Docker Compose distributions are assembled, how services receive configuration
and secrets, how product releases are upgraded and rolled back, and how
operators can diagnose startup and readiness failures.

Architecture and design pages explain why the platform is structured this way.
The operations pages describe the current executable contract. The Compose file
in each deployment repository remains the source of truth when a released
version differs from this documentation.

Read [Product Upgrade and Rollback](./operations/product-upgrade-rollback.md) for
version-specific instances, configuration snapshots, deployment pipelines, and
bounded release retention. The companion
[Product Upgrade Runtime Contract](./design/product-upgrade-runtime-contract.md)
records implementation limits and proposed code follow-ups.

Start with [Docker Compose Deployments](./operations/docker-compose.md) to choose
an environment and understand the configuration boundaries shared by all four
distributions.
