# LLM Gateway

`llm-gateway` is a separately deployed profile of the `light-gateway` image. It
loads the LLM handler and exposes OpenAI-compatible model, chat, responses and
embedding APIs. The standard Compose mapping is host port `8444` to container
port `8443`.

It must have its own Config Server instance identity. The public Portal Gateway
and LLM Gateway can use the same image without sharing the same snapshot.

## Important environment variables

| Variable | Required | Secret | Purpose |
| --- | ---: | ---: | --- |
| `LLM_GATEWAY_ENVIRONMENT` | Yes | No | Provider/routing environment selected by the runtime. |
| `llm_gateway_instance` | Conditional | No | Optional LLM Gateway instance identity used by publication/inventory flows that configure it; only `portal-config-loc` currently declares it. |
| `LIGHT_PORTAL_AUTHORIZATION` | Yes | Yes | Service token for protected Config Server/Portal access. |
| `GROQ_API_KEY` | For Groq routes | Yes | Groq provider credential. |
| `GEMINI_API_KEY` | For Gemini routes | Yes | Gemini provider credential. |
| `NVIDIA_API_KEY` | For NVIDIA routes | Yes | NVIDIA provider credential. |
| `AWS_BEARER_TOKEN_BEDROCK` | For the configured bearer-based Bedrock route | Yes | Bedrock provider credential. |
| `LIGHT_GATEWAY_LLM_AUDIT_DATABASE_URL` | When the configured audit sink requires it | Yes | LLM audit database connection. |
| `llm-router.auditRuntime.sinkDatabaseUrlEnv` | When audit is enabled | No | Names the environment variable containing the audit URL. |
| `LLM_REASONING_SEAL_KEY` | When reasoning sealing is prepared or active | Yes | Base64URL-encoded 32-byte AES-256-GCM key material. |
| `CLIENT_CACERTPATH`, `CLIENT_VERIFYHOSTNAME` | Deployment-specific | No | Outbound TLS trust policy. |
| `llm-router.requestTimeoutMs`, `llm-router.streamSetupTimeoutMs` | No | No | Request and streaming setup limits. |

## Reasoning seal

Some providers return opaque continuation state for a reasoning/tool-use turn.
For stateless `/v1/responses`, the Gateway cannot retain that state in process
memory. It seals the provider bytes and returns them as the reasoning item's
`encrypted_content`; the client returns the item on the next request.

The seal provides confidentiality and integrity and binds the envelope to the
tenant, public alias, client protocol, selected deployment and provider material
generation. On the next request, any replica with the same key set validates the
envelope, restores the provider state and pins the compatible deployment. It is
not a provider API key, database encryption key, audit key, or visible
chain-of-thought store.

The promoted non-secret snapshot carries only key IDs, generation, limits and a
reference such as `env:LLM_REASONING_SEAL_KEY`. Key bytes remain in the runtime
secret boundary. New envelopes use the current key; an optional previous key
supports controlled rotation.

When the state is `disabled`, no key is required. When it is `prepared` or
`active`, the referenced value must be unpadded URL-safe Base64 that decodes to
exactly 32 bytes. Every serving replica in the host/environment must resolve the
same active key set.

## Distribution wiring

The reasoning-seal feature and the secret that enables it are separate changes.
At the time of this documentation audit, the distributions wire them as follows:

| Distribution | Compose wiring | Required operator action |
| --- | --- | --- |
| `portal-config-loc/all-in-lt` | Declares `LLM_REASONING_SEAL_KEY` on `llm-gateway`, with a valid deterministic development fallback. | Override it through the private Portal environment file whenever sealed data must be confidential or the key lifecycle must be operator-controlled; never promote the checked-in development fallback. |
| `portal-config-dev` | Does not declare the variable on `llm-gateway`. | Keep reasoning seal disabled, or add secret wiring before promoting an active key reference. |
| `portal-config-bootstrap` | Does not declare the variable on the base `llm-gateway`. | Supply it through the enterprise secret boundary before activating reasoning seal. |
| `light-portal-install` | Does not declare the variable on `llm-gateway`. | Keep the feature disabled until the installer has a supported generated-secret path. |

This matrix describes wiring, not authorization to place key bytes in Git.

## Fail-closed behavior

The complete LLM router snapshot is compiled before it becomes active. A
missing or malformed active provider credential, reasoning key, routing record,
capability or pricing contract can reject the snapshot and place LLM routing in
an unavailable state. In that state, even `/v1/models` or an unrelated alias
can return `503` because no partial router is published.

Start diagnosis with the first `llm-router` startup error. An immediate 503
usually indicates local compilation/readiness failure; a delayed provider error
indicates a different path.
