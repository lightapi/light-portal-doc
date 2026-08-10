# Update Provider Endpoint

Use `/app/form/updateLlmProviderEndpoint` to revise a provider transport profile
or lifecycle. Host Id, Provider Endpoint Id, Resolved Trust SHA-256, and
Aggregate Version are read-only.

The authentication and network invariants from
[Create Provider Endpoint](./create-llm-provider-endpoint.md) still apply. In
particular, `BEARER` must leave API Key Header empty, while `API_KEY` requires
lowercase `authorization` or `x-api-key`.

For the hosted NVIDIA embedding Endpoint, preserve:

- Protocol `openai_embeddings`;
- Base URL `https://integrate.api.nvidia.com/v1`;
- authentication `BEARER` with no API Key Header;
- profile `PUBLIC_TLS` with no Zone or trust bundle; and
- termination `NATIVE`.

Use the Credential update/rotation workflow to change `NVIDIA_API_KEY`; do not
change Endpoint fields to carry a new secret. An Endpoint update affects a
gateway only after a new valid publication is applied.
