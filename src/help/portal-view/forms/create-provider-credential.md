# Create Provider Credential

Use `/app/form/createProviderCredential` to associate a Provider Endpoint or
sidecar runtime with a versioned external secret reference. Open the form from **Administration >
GenAI Admin > LLM Models > Credentials** by choosing **Create provider
credential**.

Portal stores only the reference. Create the actual credential in the target
environment's supported secret manager before activating this record.

## Before You Begin

You need:

- a non-deleted Provider Endpoint and corresponding Deployment for an
  `ENDPOINT` credential, or a Deployment for `SIDECAR_RUNTIME`;
- an external secret-manager entry containing the provider credential;
- the URI syntax supported by the gateway's configured secret resolver; and
- an activation and optional expiration time for this version.

Do not paste the provider API key, token, password, JSON credential document, or
authorization header into any field.

## Form Fields

| Field | Required | Example | Description |
| --- | --- | --- | --- |
| Host Id | Yes | `01964b05-552a-7c4b-9184-6857e7f3dc5f` | Read-only host that owns the Credential and Deployment. |
| Credential Purpose | Yes | `ENDPOINT` | `ENDPOINT` is resolved by the central gateway; `SIDECAR_RUNTIME` is resolved only inside the provider sidecar. |
| Provider Endpoint | For `ENDPOINT` | `nvidia-free-embeddings` | Endpoint whose bearer/API-key authentication uses this reference. |
| Provider Deployment | Current create compatibility path | `nvidia-nemotron-3-embed-1b-loc` | Select the corresponding Deployment. It is mandatory for `SIDECAR_RUNTIME` and currently also required by the command create contract for Endpoint credentials. |
| Credential Version | Yes | `2` | Positive version number unique for the selected Deployment. Increment it for each rotation. |
| Secret Reference | Yes | `env:OPENAI_API_KEY` | Environment-variable reference resolved locally by the target gateway. This is a name, never the secret value. |
| Effective Time | Yes | `2026-08-15T14:00:00Z` | ISO-8601 timestamp when this version becomes eligible. Use an explicit timezone. |
| Expiration Time | No | `2026-11-15T14:00:00Z` | Optional ISO-8601 cutoff. It must be later than Effective Time. Leave it empty for no scheduled expiration. |
| Lifecycle Status | Yes | `PENDING` | New credentials are created as `PENDING` and are not publication-eligible until activated. |

Portal generates `providerCredentialId` and initializes `aggregateVersion`.
The form does not accept `active`; soft-delete state is backend-managed.

## Purpose and owner

For `ENDPOINT`, select the Provider Endpoint and its corresponding Deployment.
For `SIDECAR_RUNTIME`, select the Deployment and do not select an unrelated
Endpoint. All references must be non-deleted and owned by the selected host.

## Credential Version

Versions are unique per Deployment. A typical sequence is:

| Rotation | Credential Version | Effective Time |
| --- | ---: | --- |
| Initial credential | `1` | `2026-05-01T00:00:00Z` |
| First rotation | `2` | `2026-08-15T14:00:00Z` |
| Second rotation | `3` | `2026-11-15T14:00:00Z` |

Create a new version for rotation. Do not reuse a version number or overwrite an
older version to represent different secret material.

## Secret Reference

For instance-property delivery, use the environment-variable name available to
the gateway process:

```text
env:OPENAI_API_KEY
env:AZURE_OPENAI_API_KEY
env:NVIDIA_API_KEY
```

Kubernetes, Docker, or HashiCorp Vault injection may populate that environment
variable; Portal neither reads nor stores its value. Absolute external URIs
such as `vault://...` remain valid control-plane references only when the target
gateway is configured with a resolver that maps that exact reference. The
default instance-property path resolves `env:VARIABLE_NAME` directly. Portal
does not prove that the variable exists, so provision and test it on the target
gateway before activation.

Values such as `sk-live-...`, `Bearer ...`, raw JSON, passwords, and copied API
keys are forbidden. They can leak through events, logs, audit records, and UI
history even if entered accidentally.

## Effective And Expiration Times

Use ISO-8601 timestamps with a timezone, preferably UTC with `Z`:

```text
Effective Time:  2026-08-15T14:00:00Z
Expiration Time: 2026-11-15T14:00:00Z
```

Publication eligibility uses the database clock. Before `effectiveTs`, the row
is not eligible. At or after `expiresTs`, it is no longer eligible. An empty
expiration means the time window does not expire automatically; lifecycle state
can still revoke it.

## Lifecycle And Activation

The create form fixes lifecycle status to `PENDING`. This prevents a newly
entered, unverified reference from immediately satisfying the publication
credential gate.

After creation:

1. Confirm the external secret exists in the target environment.
2. Confirm the gateway's workload identity can resolve it.
3. Verify the activation window.
4. Open the update form and change the lifecycle to `ACTIVE` when ready.

`ACTIVE` or `ROTATING` credentials within their effective window can satisfy the
publication-candidate check. `PENDING`, `REVOKED`, and `EXPIRED` credentials
cannot.

## Submit The Credential

Choose **Create Provider Credential**. The form sends
`lightapi.net/genai/createLlmProviderCredential/0.1.0` and returns to the LLM
Model Control Plane after success.

## NVIDIA Endpoint credential

For the hosted Nemotron Endpoint, use:

| Field | Value |
| --- | --- |
| Credential Purpose | `ENDPOINT` |
| Provider Endpoint | `nvidia-free-embeddings` |
| Provider Deployment | The corresponding `nvidia/nemotron-3-embed-1b` Deployment |
| Credential Version | `1` |
| Secret Reference | `env:NVIDIA_API_KEY` |
| Effective Time | Current UTC time in ISO-8601 format |
| Expiration Time | Empty for the local demo unless the key has a known expiry |
| Lifecycle Status | `PENDING` |

Pass `NVIDIA_API_KEY` into the `light-gateway` process through runtime secret
injection or Compose environment expansion. Never commit its value to Portal
configuration. Change this row to `ACTIVE` only after the target gateway can
resolve the variable.

## Common Problems

- **Deployment list is empty**: confirm the Deployment exists, is not deleted,
  and belongs to the selected host.
- **Secret Reference is rejected**: enter `env:VARIABLE_NAME` (for example,
  `env:OPENAI_API_KEY`) or a URI supported by an explicitly configured resolver,
  not a raw credential.
- **Credential version already exists**: increment the version for that
  Deployment.
- **Expiration is rejected**: make it later than Effective Time and include a
  timezone.
- **Publication still fails**: a `PENDING` or not-yet-effective credential does
  not satisfy route health; activate it only after the external reference is
  verified.
- **403 on Create**: confirm access to
  `lightapi.net/genai/createLlmProviderCredential/0.1.0` and the required write
  permission.

For the full eligibility and rotation workflow, see the
[Credentials tab guide](../pages/llm-model-control-plane.md#credentials-tab).
