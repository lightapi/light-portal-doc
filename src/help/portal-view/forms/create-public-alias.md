# Create Public Alias

Use this form to create a stable, environment-specific model name and define
the policy requirements that its provider routes must satisfy. Applications
use the alias name instead of a provider deployment or physical model ID.

Only **Environment** and **Alias Name** are required in addition to the
read-only host. Start new aliases in `DRAFT`, add and validate their routes,
pricing, and credentials, and then change the lifecycle to `ACTIVE` when the
alias is ready for publication.

## Fields

| Field | Description | Example |
| --- | --- | --- |
| Host Id | Read-only tenant boundary supplied by the portal. All referenced records must belong to this host. | `10000000-0000-4000-8000-000000000001` |
| Environment | Environment in which clients use the alias. Routes attached to the alias must use registrations from the same environment. | `prod` |
| Alias Name | Stable model name presented to applications and agents. It must be unique within the host and environment. | `governed-chat` |
| Operations | JSON or YAML array of operations allowed for the alias. Use **Apply** after editing structured data. | `["chat_completions"]` |
| Required Capabilities | JSON or YAML object of capabilities every eligible route must support. An empty object adds no capability constraint. | `{"tools":true,"streaming":true}` |
| Maximum Input Tokens | Optional maximum number of input tokens accepted through this alias. | `128000` |
| Maximum Output Tokens | Optional maximum number of output tokens generated through this alias. | `8192` |
| Maximum Request Bytes | Optional maximum serialized request size. This remains a governance limit unless the publication compiler and gateway version support projecting it. | `1048576` |
| Data Classification | Optional classification used when evaluating data-handling and route policy. Use the classification vocabulary established for the host. | `internal` |
| Logging Mode | Desired logging policy: `NONE`, `METADATA`, or `REDACTED`. Supported settings are translated into gateway audit policy during publication. | `METADATA` |
| PII Mode | Desired PII policy: `DENY`, `REDACT`, `TOKENIZE`, or `ALLOW`. Choose the most restrictive mode compatible with the use case. | `REDACT` |
| Lifecycle Status | Alias lifecycle. `DRAFT` is the safe create default; `ACTIVE` aliases are considered for publication, `DEPRECATED` marks a migration period, and `RETIRED` removes the alias from use. | `DRAFT` |
| Replacement Alias | Optional active alias selected as the intended successor. This is a migration reference, not an automatic redirect. | `governed-chat-v2` |
| Alias Visibility | `PUBLIC` exposes the alias for normal discovery and routing. `INTERNAL_LEGACY` restricts it to one selected agent definition. | `PUBLIC` |
| Bound Agent Definition | Required only for `INTERNAL_LEGACY`; select the agent that may resolve this alias. Leave it empty for `PUBLIC`. | `Legacy Support Agent` (`10000000-0000-4000-8000-000000000099`) |

`Operations` and `Required Capabilities` accept JSON or YAML. After changing an
editor value, choose **Apply** before submitting the form.

## Example

For a generally available production chat alias:

```json
{
  "environment": "prod",
  "aliasName": "governed-chat",
  "operations": ["chat_completions"],
  "requiredCapabilities": {
    "tools": true,
    "streaming": true
  },
  "maxInputTokens": 128000,
  "maxOutputTokens": 8192,
  "maxRequestBytes": 1048576,
  "dataClassification": "internal",
  "loggingMode": "METADATA",
  "piiMode": "REDACT",
  "lifecycleStatus": "DRAFT",
  "aliasVisibility": "PUBLIC"
}
```

For an `INTERNAL_LEGACY` alias, select a **Bound Agent Definition**. A `PUBLIC`
alias must not have a bound agent. The backend creates the Public Alias Id and
aggregate version. The `active` state is also backend-managed through soft
delete and is not part of this form.
