# Access Control: Enabled

The `enabled` property acts as the master switch for the access control runtime within the gateway.

## Configuration Options

```yaml
enabled: true
```

* **`true`**: The access control system is active. Both request authorization and response filtering are enforced.
* **`false`**: The access control system is bypassed. All incoming requests and downstream responses are permitted to pass through without evaluation.

---

## Behavior Separation

### HTTP API Access Control
When set to `false`, the HTTP handler chain bypasses request authorization (`req-acc`) and response filtering (`res-fil`) checks. Requests are forwarded directly to downstream microservices, and responses are returned unfiltered.

### MCP Router Access Control
When set to `false`, the MCP router bypasses security checks for tool calls (`tools/call`):
* AI agents can invoke any configured MCP tool without `req-acc` checks.
* Response payloads from downstream tools are returned to the agent without `res-fil` filtering.

> [!NOTE]
> Even if `enabled` is set to `false`, access rules defined in `rule.yml` remain loaded in memory, allowing them to take effect immediately when access control is re-enabled or reloaded.
