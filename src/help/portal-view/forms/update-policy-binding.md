# Update Policy Binding

Use this form to change the Policy assignment, subject, optional Alias scope, or
Agent Default selection on an existing Binding.

The **Host Id**, **Model Policy Binding Id**, and **Aggregate Version** are
read-only. Aggregate Version provides optimistic concurrency protection; reload
the Bindings tab if another change has advanced it.

## Fields

| Field | Description | Example |
| --- | --- | --- |
| Host Id | Read-only tenant boundary supplied by Portal. | `10000000-0000-4000-8000-000000000001` |
| Model Policy Binding Id | Read-only identifier generated when the Binding was created. | `70000000-0000-4000-8000-000000000070` |
| Model Policy | Policy assigned by this Binding. The dropdown lists non-deleted Policies for the host. | `governed-chat-standard` (`60000000-0000-4000-8000-000000000060`) |
| Subject Type | Namespace for Subject Id: `AGENT`, `CLIENT`, `PRINCIPAL`, or `PRODUCT_PROFILE`. Changing it also changes the meaning of Subject Id. | `AGENT` |
| Subject Id | Exact stable identifier in the selected namespace. For `AGENT`, this must be the Agent Definition Id used by model resolution. | `10000000-0000-4000-8000-000000000099` |
| Public Alias | Optional Alias scope. It is required when Agent Default is selected. | `governed-chat-v2` (`20000000-0000-4000-8000-000000000021`) |
| Agent Default | For an `AGENT` Binding, selects this Public Alias as the Policy default. Clear the previous default before or while assigning another one so only one active default remains. | `true` |
| Aggregate Version | Read-only record version submitted with the update. Reload after an update conflict instead of editing it manually. | `3` |

## Complete Example

```json
{
  "modelPolicyBindingId": "70000000-0000-4000-8000-000000000070",
  "modelPolicyId": "60000000-0000-4000-8000-000000000060",
  "subjectType": "AGENT",
  "subjectId": "10000000-0000-4000-8000-000000000099",
  "publicAliasId": "20000000-0000-4000-8000-000000000021",
  "agentDefault": true,
  "aggregateVersion": 3
}
```

If Agent Default is selected, the form requires `subjectType=AGENT` and a Public
Alias. The database also allows at most one active default for the same Policy
and Agent. If another Binding currently owns that default, update it to
`agentDefault=false` before saving this one.

Review the Agent Definition before changing `modelPolicyId`, `subjectType`, or
`subjectId`; a mismatch can leave a policy-selected Agent without a resolvable
default. Ensure a replacement Alias is eligible and published before directing
an Agent to it. The gateway does not query this Binding row during an inference
request, and the `active` state is backend-managed through soft delete rather
than this form.

For the NVIDIA Knowledge Base demo, preserve the distinction between
`kb-index` and `kb-query` when changing an Alias scope. Pointing both workload
identities at one Binding does not create independent provider capacity or
quota; that isolation is established by eligible Routes and their Deployments.
