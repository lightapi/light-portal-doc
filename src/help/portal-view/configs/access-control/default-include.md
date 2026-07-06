# Access Control: Default Include

The `defaultInclude` property determines the row-filtering fallback behavior when a user's request context does not match any role-based row filter conditions in the response filtering phase.

## Configuration Options

```yaml
defaultInclude: false
```

* **`true`**: The gateway retains all rows by default. If the user's claims do not match any configured role conditions, the response data is returned unfiltered (retaining all rows).
* **`false`**: The gateway filters out all rows by default. If the user's claims do not match any configured role conditions, the response payload returns empty (no rows).

---

## Behavior Separation

### HTTP API Access Control
When the response filtering (`res-fil`) phase invokes a row-filter action:
* If the user's roles or attributes do not match any role definition in the filter, `defaultInclude: false` cleanses the JSON array completely, returning an empty list `[]` to the client.
* If `defaultInclude: true` is configured, the gateway retains the original list of rows, logging a warning about the fallback bypass.

### MCP Router Access Control
When response filtering (`res-fil`) is applied to an MCP tool result:
* The JSON payload inside the tool response is filtered.
* If the agent/caller claims do not match the row-filter role specifications, `defaultInclude: false` empties the rows in the structured content.
* If `defaultInclude: true`, the MCP tool results remain intact and are delivered to the agent without row filtration.
