# Access Control: Default Deny

The `defaultDeny` property defines the fallback authorization policy for endpoints that do not have any explicitly configured rules in `rule.yml`.

## Configuration Options

```yaml
defaultDeny: true
```

* **`true`** (Default): The gateway fails closed. If a request is received for an endpoint with no mapping in `rule.endpointRules`, or no rules listed under `req-acc`, the request is denied.
* **`false`**: The gateway fails open. If an endpoint does not have explicit authorization rules, access is allowed by default.

---

## Behavior Separation

### HTTP API Access Control
* **`defaultDeny: true`**: Every HTTP endpoint exposed by the gateway must have a matching entry in `rule.yml` with at least one passing `req-acc` rule. Unconfigured endpoints will return a `403 Forbidden` response.
* **`defaultDeny: false`**: Only HTTP endpoints explicitly configured with `req-acc` rules in `rule.yml` are guarded. Unlisted API endpoints are publicly accessible without authentication/authorization checks.

### MCP Router Access Control
* **`defaultDeny: true`**: Every MCP tool must map to an endpoint key (e.g. `accounts@call`) in `rule.endpointRules` with a defined request access policy. If no policy is found, the tool call is blocked, returning a JSON-RPC authorization error to the calling AI agent.
* **`defaultDeny: false`**: The MCP router permits tool calls for any tools that do not have explicit rules configured in `rule.yml`. This is useful in staging or development environments where you want to expose new MCP tools without writing policy rules for every endpoint.
