# Create LLM Model

Use the **Create LLM Model** form to add a physical provider model to the LLM
global Model Catalog shared by every host. Open it from **Marketplace > LLM
Model Catalog** and choose **Create**. Only platform catalog administrators
should have permission to use this command.

This guide applies only to `/app/form/createLlmModel`. For registrations,
deployments, aliases, policies, and publication, see the
[LLM Model Control Plane](./llm-model-control-plane.md) guide.

## Required Fields

| Field | Description |
| --- | --- |
| Global Catalog | Read-only `true`; catalog Models are platform-global and are not owned by the selected host. |
| Provider Type | Provider identifier, such as `openai`. |
| Physical Model Id | The model identifier recognized by the provider. |
| Model Family | The provider's model family or product family. |
| Context Token Limit | Maximum context size. Enter an integer greater than zero. |
| Output Token Limit | Maximum generated output size. Enter an integer greater than zero. |

`Model Version` is optional, and `Lifecycle Status` defaults to `DRAFT`.
`active` is backend-managed: create and update keep the model active, while the
delete command soft-deletes it.

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
- generate
- embed
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

Categories and tags are optional. The selectors show active global taxonomy
values registered for the `llm_model` entity type. Host-specific taxonomy
cannot be assigned to a global model.

## NVIDIA Nemotron embedding example

For the `light-knowledge` demo, use these values for the NVIDIA catalog Model:

| Field | Value |
| --- | --- |
| Provider Type | `nvidia` |
| Physical Model Id | `nvidia/nemotron-3-embed-1b` |
| Model Family | `nemotron-3-embed` |
| Model Version | Leave empty unless the provider publishes a stable version identifier |
| Lifecycle Status | `DRAFT` initially |
| Context Token Limit | `4096` |
| Output Token Limit | `1` because the current generic schema requires a positive value; embedding calls do not generate output tokens |
| Modalities | `["text"]` |
| Operations | `["embed"]` |

Use this Declared Capabilities object:

```json
{
  "embedding": {
    "dimensions": [2048],
    "defaultDimension": 2048,
    "encodings": ["float"],
    "normalization": "l2",
    "distanceMetrics": ["cosine"],
    "inputTypes": ["query", "passage"]
  }
}
```

NVIDIA currently documents only the native 2048-dimensional output for this
hosted model. Document indexing must use passage semantics and retrieval must
use query semantics. The catalog capability declaration records that contract;
the qualified provider adapter must still send the correct provider request.
See the [NVIDIA NIM support matrix](https://docs.nvidia.com/nim/nemo-retriever/text-embedding/latest/support-matrix.html).

## Create the Record

Review the values and choose **Create LLM Model**. The form sends the
`createLlmModel` command and preserves `modalities` and `operations` as arrays
and `declaredCapabilities` as an object. After a successful command, the
browser returns to **GenAI Admin > LLM Models**.

## Common Problems

- **Create is blocked after editing JSON or YAML**: choose **Apply** to commit
  the draft, or **Reset** to discard it.
- **JSON or YAML error**: correct the highlighted syntax and choose **Apply**
  again. The last valid value remains unchanged.
- **Required-field validation**: provide every required field and use positive
  integers for both token limits.
- **No categories or tags are available**: confirm that global taxonomy values
  are active and registered for `llm_model`.
- **403 on Create**: confirm access to the
  `lightapi.net/genai/createLlmModel/0.1.0` command endpoint with the required
  write scope and role permission.
