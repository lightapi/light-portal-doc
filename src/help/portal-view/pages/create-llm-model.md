# Create LLM Model

Use the **Create LLM Model** form to add a physical provider model to the LLM
Model Catalog for the selected host. Open it from **Marketplace > LLM Model
Catalog** and choose **Create**.

This guide applies only to `/app/form/createLlmModel`. For registrations,
deployments, aliases, policies, and publication, see the
[LLM Model Control Plane](./llm-model-control-plane.md) guide.

## Required Fields

| Field | Description |
| --- | --- |
| Host Id | The selected host. The form supplies this read-only value. |
| Provider Type | Provider identifier, such as `openai`. |
| Physical Model Id | The model identifier recognized by the provider. |
| Model Family | The provider's model family or product family. |
| Context Token Limit | Maximum context size. Enter an integer greater than zero. |
| Output Token Limit | Maximum generated output size. Enter an integer greater than zero. |

`Model Version` is optional. `Lifecycle Status` defaults to `DRAFT`, and
`Active` defaults to enabled.

## Structured Fields

`Modalities`, `Operations`, and `Declared Capabilities` are stored as typed
arrays or objects. Do not enter JSON or YAML as a quoted string.

### Modalities and Operations

These fields open on the **Form** tab. Add one string per array item. You can
also use the **JSON** or **YAML** tab, for example:

```json
["text", "image"]
```

```yaml
- chat_completions
- embeddings
```

### Declared Capabilities

This open-ended object starts on the **JSON** tab. The Form tab is unavailable
because the current schema does not prescribe capability property names. Enter
an object whose keys and values describe the provider model, for example:

```json
{
  "streaming": true,
  "tools": true
}
```

The equivalent YAML is:

```yaml
streaming: true
tools: true
```

After changing JSON or YAML, choose **Apply**. Apply parses the draft, checks
its root type and schema constraints, and updates the form model only when it
is valid. Choose **Reset** to discard the draft and restore the last valid
value. The Create action remains blocked while a structured draft is invalid
or has not been applied.

## Categories and Tags

Categories and tags are optional. The selectors show active global and
host-specific taxonomy values registered for the `llm_model` entity type. A
taxonomy value belonging to another host or entity type cannot be assigned.

## Create the Record

Review the values and choose **Create LLM Model**. The form sends the
`createLlmModel` command and preserves `modalities` and `operations` as arrays
and `declaredCapabilities` as an object. After a successful command, the
browser returns to **Marketplace > LLM Model Catalog**.

## Common Problems

- **Create is blocked after editing JSON or YAML**: choose **Apply** to commit
  the draft, or **Reset** to discard it.
- **JSON or YAML error**: correct the highlighted syntax and choose **Apply**
  again. The last valid value remains unchanged.
- **Required-field validation**: provide every required field and use positive
  integers for both token limits.
- **No categories or tags are available**: confirm that the taxonomy values
  are active and registered for `llm_model` on the selected host.
- **403 on Create**: confirm access to the
  `lightapi.net/genai/createLlmModel/0.1.0` command endpoint with the required
  write scope and role permission.
