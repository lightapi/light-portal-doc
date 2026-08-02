# Create Policy Binding

Use this form to assign a Model Policy to an Agent, Client, Principal, or
Product Profile. Optionally scope the assignment to a Public Alias. For a
policy-selected Agent, mark exactly one Alias Binding as the Agent Default.

## Fields

| Field | Description | Example |
| --- | --- | --- |
| Host Id | Read-only tenant boundary supplied by Portal. The selected Policy and Alias must belong to this host. | `10000000-0000-4000-8000-000000000001` |
| Model Policy | Policy being assigned. The dropdown lists non-deleted Policies for the selected host; verify that the chosen lifecycle state is appropriate before use. | `governed-chat-standard` (`60000000-0000-4000-8000-000000000060`) |
| Subject Type | Namespace that defines how Subject Id is interpreted: `AGENT`, `CLIENT`, `PRINCIPAL`, or `PRODUCT_PROFILE`. | `AGENT` |
| Subject Id | Exact stable identifier from the selected subject namespace. For `AGENT`, use the Agent Definition Id. The Binding table has no foreign key to the four different subject systems, so confirm this value carefully. | `10000000-0000-4000-8000-000000000099` |
| Public Alias | Optional Alias that scopes this assignment. It is required when Agent Default is selected. The dropdown lists non-deleted Aliases for the host; verify that the Alias is lifecycle-active and published where it will be used. | `governed-chat` (`20000000-0000-4000-8000-000000000020`) |
| Agent Default | Select only for an `AGENT` Binding with a Public Alias. It makes this Alias the Policy's selected default for that Agent. Only one active default is allowed for the same Policy and Agent. | `true` |

## Agent Default Example

```json
{
  "modelPolicyId": "60000000-0000-4000-8000-000000000060",
  "subjectType": "AGENT",
  "subjectId": "10000000-0000-4000-8000-000000000099",
  "publicAliasId": "20000000-0000-4000-8000-000000000020",
  "agentDefault": true
}
```

For a policy-selected Agent, the current resolver matches `subjectId` to the
Agent Definition Id and requires exactly one active default Alias. A missing
default produces `NO_DEFAULT`; multiple matching defaults are treated as
ambiguous and model resolution fails.

## Non-Agent Example

```json
{
  "modelPolicyId": "60000000-0000-4000-8000-000000000060",
  "subjectType": "PRINCIPAL",
  "subjectId": "user-1234",
  "publicAliasId": "20000000-0000-4000-8000-000000000020",
  "agentDefault": false
}
```

Client, Principal, and Product Profile Bindings are control-plane assignments
for an approved policy compiler or authorization integration. They are not
automatically enforced by the current Agent resolver or by merely storing the
row.

Before saving an Agent Default, confirm that the Agent selects this Model Policy
and that the Alias has eligible, published Routes and provider material. The
backend generates Model Policy Binding Id and Aggregate Version. The `active`
state is backend-managed through soft delete and is not part of this form.
