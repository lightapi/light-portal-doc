# Create Model Policy

Use this form to create reusable model-governance intent for one host. A Model
Policy is not assigned merely by creating it: use the Bindings tab afterward to
associate it with an Agent, Client, Principal, or Product Profile and,
optionally, a Public Alias.

The six policy fields accept JSON or YAML objects. Choose an editor tab, enter
the object, and select **Apply** before saving. The example keys below are
illustrative governance vocabulary, not a promise that every key is enforced.
The backend accepts extensible objects, while runtime enforcement requires an
approved publication mapping and a gateway that supports the mapped fields.

## Fields

| Field | Description | Example |
| --- | --- | --- |
| Host Id | Read-only tenant boundary supplied by the portal. The generated Policy and all of its Bindings belong to this host. | `10000000-0000-4000-8000-000000000001` |
| Policy Name | Required, recognizable name unique within the host. Use a stable governance name rather than a provider or Deployment identifier. | `governed-chat-standard` |
| Access Policy | Object describing intended subject and operation access. The example vocabulary must be mapped by the publication implementation before it can affect runtime authorization. | `{"allowedSubjectTypes":["AGENT","CLIENT"],"allowedOperations":["chat_completions"]}` |
| Budget Policy | Object describing intended per-request or period spending controls. Monetary examples use integer micros, where `1000000` micros is one currency unit. | `{"maxCostMicrosPerRequest":500000,"monthlyCostMicros":50000000}` |
| Content Policy | Object describing intended logging and prompt or response handling. | `{"loggingMode":"METADATA","allowPromptLogging":false}` |
| Cache Policy | Object describing intended cache use and constraints. | `{"enabled":false}` |
| PII Policy | Object describing intended PII handling and applicable kinds. | `{"mode":"REDACT","allowedKinds":["EMAIL"]}` |
| Native Extension Policy | Object allowlisting provider-specific request fields outside the portable model contract. Keep it narrowly scoped by provider. | `{"openai":{"allowedRequestFields":["service_tier"]}}` |
| Lifecycle Status | Administrative state. `DRAFT` is the create default; use `ACTIVE` only after review. `SUSPENDED` temporarily removes intended eligibility and `RETIRED` is terminal. | `DRAFT` |

## Complete Example

```json
{
  "policyName": "governed-chat-standard",
  "accessPolicy": {
    "allowedSubjectTypes": ["AGENT", "CLIENT"],
    "allowedOperations": ["chat_completions"]
  },
  "budgetPolicy": {
    "maxCostMicrosPerRequest": 500000,
    "monthlyCostMicros": 50000000
  },
  "contentPolicy": {
    "loggingMode": "METADATA",
    "allowPromptLogging": false
  },
  "cachePolicy": {
    "enabled": false
  },
  "piiPolicy": {
    "mode": "REDACT",
    "allowedKinds": ["EMAIL"]
  },
  "nativeExtensionPolicy": {
    "openai": {
      "allowedRequestFields": ["service_tier"]
    }
  },
  "lifecycleStatus": "DRAFT"
}
```

Empty objects are valid when a policy domain is not yet specified. Do not put
API keys, passwords, bearer values, authorization headers, or other raw secrets
in any policy object. Provider credentials belong in the Credentials tab.

After creation, review the Policy, create the required Bindings, and use the
publication workflow to translate supported policy intent into a new immutable
gateway candidate. Creating the row alone does not change a running gateway.
The backend generates Model Policy Id and Aggregate Version. The `active` state
is backend-managed through soft delete and is not part of this form.
