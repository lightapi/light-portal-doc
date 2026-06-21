# List Rule

The List Rule page allows administrators to view, search, and manage YAML rules associated with specific service API endpoints.

This page is designed for users to add existing rules to the endpoint for request access control (`req-acc`) and response filter (`res-fil`).

The rule setup on this page associates one or more rules with the current endpoint. These CEL-backed rules are invoked from either the access-control handler for API access or the mcp-router handler for MCP access to enforce fine-grained authorization by matching the user security profile with the endpoint security definitions.

For more details on light rule and security configuration, please refer to the following resources:
- [Light Rule](https://www.networknt.com/light-fabric/crate/light-rule.html)
- [CEL Rule Conditions](https://www.networknt.com/light-fabric/design/cel-rule.html)
- [MCP Router Security](https://www.networknt.com/light-fabric/design/mcp-router.html#security-and-policy)
- [Access Control](https://www.networknt.com/light-fabric/design/access-control.html)


## Key Features

- **Filter Active Rules**: Toggle search filters to view active/inactive rules.
- **Add Rule to Endpoint**: Easily attach a rule to the selected endpoint.
- **Delete Rules**: Remove rule configurations from endpoints.
