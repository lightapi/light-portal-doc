# Operations

This section documents the deployed Light Portal runtime: how the supported
Docker Compose distributions are assembled, how services receive configuration
and secrets, and how operators can diagnose startup and readiness failures.

Architecture and design pages explain why the platform is structured this way.
The operations pages describe the current executable contract. The Compose file
in each deployment repository remains the source of truth when a released
version differs from this documentation.

Start with [Docker Compose Deployments](./operations/docker-compose.md) to choose
an environment and understand the configuration boundaries shared by all four
distributions.

