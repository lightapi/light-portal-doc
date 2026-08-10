# Update Model Policy

Use this form to revise a Model Policy's name, governance objects, or lifecycle.
The change remains control-plane data until a supported publication mapping is
validated and a new immutable gateway candidate is applied.

The **Host Id**, **Model Policy Id**, and **Aggregate Version** are read-only.
Aggregate Version provides optimistic concurrency protection: reload the
Policies tab if another update has advanced it.

The six policy fields accept JSON or YAML objects. Choose an editor tab, make
the change, and select **Apply** before saving. The example keys below are
illustrative. An accepted object does not guarantee runtime enforcement; each
key requires an approved compiler mapping and compatible gateway support.

## Fields

| Field | Description | Example |
| --- | --- | --- |
| Host Id | Read-only tenant boundary supplied by the portal. | `10000000-0000-4000-8000-000000000001` |
| Model Policy Id | Read-only stable identifier generated when the Policy was created and referenced by Bindings or Agent configuration. | `60000000-0000-4000-8000-000000000060` |
| Policy Name | Recognizable name unique within the host. Renaming does not change the stable Model Policy Id. | `governed-chat-standard-v2` |
| Access Policy | Object describing intended subject and operation access. Operations use the control-plane vocabulary `generate` or `embed`. | `{"allowedSubjectTypes":["AGENT"],"allowedOperations":["generate"]}` |
| Budget Policy | Object describing intended spending controls. Monetary examples use integer micros. | `{"maxCostMicrosPerRequest":400000,"monthlyCostMicros":40000000}` |
| Content Policy | Object describing intended content logging and handling. | `{"loggingMode":"METADATA","allowPromptLogging":false}` |
| Cache Policy | Object describing intended cache behavior. | `{"enabled":false}` |
| PII Policy | Object describing intended handling for personally identifiable data. | `{"mode":"REDACT","allowedKinds":["EMAIL","PHONE"]}` |
| Native Extension Policy | Object allowlisting provider-specific request extensions. | `{"openai":{"allowedRequestFields":["service_tier"]}}` |
| Lifecycle Status | `DRAFT`, `ACTIVE`, `SUSPENDED`, or `RETIRED`. A Policy cannot return to `DRAFT` after leaving it, and `RETIRED` is terminal. | `ACTIVE` |
| Aggregate Version | Read-only record version submitted with the update. Reload after a conflict instead of changing it manually. | `4` |

## Complete Example

```json
{
  "modelPolicyId": "60000000-0000-4000-8000-000000000060",
  "policyName": "governed-chat-standard-v2",
  "accessPolicy": {
    "allowedSubjectTypes": ["AGENT"],
    "allowedOperations": ["generate"]
  },
  "budgetPolicy": {
    "maxCostMicrosPerRequest": 400000,
    "monthlyCostMicros": 40000000
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
    "allowedKinds": ["EMAIL", "PHONE"]
  },
  "nativeExtensionPolicy": {
    "openai": {
      "allowedRequestFields": ["service_tier"]
    }
  },
  "lifecycleStatus": "ACTIVE",
  "aggregateVersion": 4
}
```

Do not place API keys, passwords, bearer values, authorization headers, or
other raw secrets in a policy object. Use the Credentials tab for external
secret references.

Before suspending or retiring a Policy, review its Bindings and any Agent that
selects its Model Policy Id. After any enforceable change, create and apply a
new valid publication; an existing gateway snapshot does not update in place.
The `active` state is backend-managed through soft delete and is not part of
this form.

For the NVIDIA Knowledge Base aliases, use operation `embed` if a Policy is
needed at all. Keep `apiKey` and `input_type` out of the policy: the API key is
represented by the Credential's `env:NVIDIA_API_KEY` reference, while the
query-versus-passage request transformation belongs in the approved embedding
adapter.
