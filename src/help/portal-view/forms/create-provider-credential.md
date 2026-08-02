# Create Provider Credential

Use `/app/form/createProviderCredential` to associate a provider Deployment with
a versioned external secret reference. Open the form from **Administration >
GenAI Admin > LLM Models > Credentials** by choosing **Create provider
credential**.

Portal stores only the reference. Create the actual credential in the target
environment's supported secret manager before activating this record.

## Before You Begin

You need:

- a non-deleted provider Deployment under the selected host;
- an external secret-manager entry containing the provider credential;
- the URI syntax supported by the gateway's configured secret resolver; and
- an activation and optional expiration time for this version.

Do not paste the provider API key, token, password, JSON credential document, or
authorization header into any field.

## Form Fields

| Field | Required | Example | Description |
| --- | --- | --- | --- |
| Host Id | Yes | `01964b05-552a-7c4b-9184-6857e7f3dc5f` | Read-only host that owns the Credential and Deployment. |
| Provider Deployment | Yes | `OpenAI GPT-4o Production` | Non-deleted host-scoped Deployment that will use this credential. The selector submits its `providerDeploymentId`, for example `7ee18d9d-9db4-4f56-8eba-9ca880755962`. |
| Credential Version | Yes | `2` | Positive version number unique for the selected Deployment. Increment it for each rotation. |
| Secret Reference | Yes | `vault://llm/openai-production/api-key` | External secret URI resolved by the target gateway environment. This is a location, never the secret value. |
| Effective Time | Yes | `2026-08-15T14:00:00Z` | ISO-8601 timestamp when this version becomes eligible. Use an explicit timezone. |
| Expiration Time | No | `2026-11-15T14:00:00Z` | Optional ISO-8601 cutoff. It must be later than Effective Time. Leave it empty for no scheduled expiration. |
| Lifecycle Status | Yes | `PENDING` | New credentials are created as `PENDING` and are not publication-eligible until activated. |

Portal generates `providerCredentialId` and initializes `aggregateVersion`.
The form does not accept `active`; soft-delete state is backend-managed.

## Provider Deployment

The selector lists active, host-scoped Deployment labels and submits the stable
Deployment ID. The command rejects a missing, deleted, or cross-host reference.
Choose the endpoint that is actually configured to use the external credential.

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

The value must be an absolute URI with a scheme followed by `://`. For example:

```text
vault://llm/openai-production/api-key
credential://production/openai-primary
```

These are syntax examples. Use only schemes and paths supported by the secret
resolver configured for the target gateway. Portal validates the URI shape but
does not prove that the referenced secret exists or that the gateway can read
it. Provision and test the secret before activation.

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

## Common Problems

- **Deployment list is empty**: confirm the Deployment exists, is not deleted,
  and belongs to the selected host.
- **Secret Reference is rejected**: enter a URI such as
  `vault://llm/openai-production/api-key`, not a raw credential.
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
