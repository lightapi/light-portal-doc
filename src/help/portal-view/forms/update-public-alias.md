# Update Public Alias

Use this form to revise the policy, lifecycle, visibility, or migration details
of an existing alias. Route records remain separate; update them from the
**Routes** tab when changing which deployments serve the alias.

The **Host Id**, **Public Alias Id**, and **Aggregate Version** are read-only.
The aggregate version provides optimistic concurrency protection so an update
does not silently overwrite a newer change.

## Fields

| Field | Description | Example |
| --- | --- | --- |
| Host Id | Read-only tenant boundary supplied by the portal. | `10000000-0000-4000-8000-000000000001` |
| Public Alias Id | Read-only identifier generated when the alias was created. Routes and policy bindings refer to this value. | `20000000-0000-4000-8000-000000000020` |
| Environment | Environment in which clients use the alias. Attached routes must resolve through registrations in the same environment. | `prod` |
| Alias Name | Stable model name presented to applications and agents. It must remain unique within the host and environment. | `governed-chat` |
| Operations | JSON or YAML array of allowed operations. Use **Apply** after changing structured data. | `["chat_completions"]` |
| Required Capabilities | JSON or YAML object of capabilities every eligible route must support. | `{"tools":true,"streaming":true}` |
| Maximum Input Tokens | Optional alias-level input token limit. | `128000` |
| Maximum Output Tokens | Optional alias-level generated token limit. | `8192` |
| Maximum Request Bytes | Optional serialized request-size limit. Runtime enforcement depends on publication compiler and gateway support. | `1048576` |
| Data Classification | Optional classification used by data-handling and route policy. | `internal` |
| Logging Mode | Desired logging policy: `NONE`, `METADATA`, or `REDACTED`. Supported settings are translated to gateway audit policy during publication. | `REDACTED` |
| PII Mode | Desired PII policy: `DENY`, `REDACT`, `TOKENIZE`, or `ALLOW`. | `TOKENIZE` |
| Lifecycle Status | `DRAFT`, `ACTIVE`, `DEPRECATED`, or `RETIRED`. Use `DEPRECATED` while directing clients toward a replacement and `RETIRED` when the alias must no longer be used. | `DEPRECATED` |
| Replacement Alias | Optional active successor alias. It cannot be the alias being edited and does not automatically redirect requests. | `governed-chat-v2` |
| Alias Visibility | `PUBLIC` for normal discovery and routing, or `INTERNAL_LEGACY` for a single bound agent. | `INTERNAL_LEGACY` |
| Bound Agent Definition | Required for `INTERNAL_LEGACY` and prohibited for `PUBLIC`. | `Legacy Support Agent` (`10000000-0000-4000-8000-000000000099`) |
| Aggregate Version | Read-only record version included with the update command. Reload the record if another update has advanced it. | `6` |

## Example

The following update deprecates a legacy, agent-bound alias and identifies its
replacement:

```json
{
  "publicAliasId": "20000000-0000-4000-8000-000000000020",
  "environment": "prod",
  "aliasName": "legacy-agent-chat",
  "operations": ["chat_completions"],
  "requiredCapabilities": {
    "tools": true
  },
  "maxInputTokens": 64000,
  "maxOutputTokens": 4096,
  "maxRequestBytes": 524288,
  "dataClassification": "internal",
  "loggingMode": "REDACTED",
  "piiMode": "TOKENIZE",
  "lifecycleStatus": "DEPRECATED",
  "replacementAliasId": "20000000-0000-4000-8000-000000000021",
  "aliasVisibility": "INTERNAL_LEGACY",
  "boundAgentDefId": "10000000-0000-4000-8000-000000000099",
  "aggregateVersion": 6
}
```

Changing `replacementAliasId` records migration intent only. Move client
traffic by updating clients or routing configuration explicitly. The `active`
state is backend-managed through soft delete and is not part of this form.
