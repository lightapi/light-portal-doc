# Access Control: Access Rule Logic

The `accessRuleLogic` property determines the logic applied when evaluating multiple request authorization (`req-acc`) rules for a single endpoint.

## Configuration Options

```yaml
accessRuleLogic: any
```

* **`any`** (Default): At least one matching request authorization rule must evaluate to `true` (logical OR). If any matching rule allows the request, access is granted.
* **`all`**: Every matching request authorization rule must evaluate to `true` (logical AND). If any rule fails, access is denied.

---

## Behavior Separation

### HTTP API Access Control
Applies when an HTTP API endpoint maps to multiple `req-acc` rules in `rule.yml`.
* Under `any` logic, the gateway permits the request if any matched CEL or role condition succeeds.
* Under `all` logic, every matched rule is executed, and all must succeed for the gateway to forward the request to the backend.

### MCP Router Access Control
Applies when an MCP tool endpoint (derived from the tool name and method, e.g. `accounts@call`) matches multiple `req-acc` rules.
* Under `any` logic, a tool call is authorized as long as one rule allows it.
* Under `all` logic, a tool call is authorized only if all matching rules allow it.
