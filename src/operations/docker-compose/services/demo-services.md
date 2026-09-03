# Demo Services

The maintained Compose stacks include small backends used by tutorials,
workflow/MCP examples and daily regression tests.

| Service | Default host port | Purpose |
| --- | ---: | --- |
| `demo-customer-profile-api` | `8085` | Customer profile data used by Customer 360 workflows. |
| `demo-offer-decision-api` | `8086` | Offer/decision backend used by orchestration examples. |
| `demo-insurance-claim-mcp-server` | `8087` | MCP backend used by insurance claim and passthrough tests. |

## Configuration

Each service has a service-specific configuration-directory variable, an
optional external configuration directory, `LIGHT_PORTAL_AUTHORIZATION`,
`RUST_LOG`, and a service-specific ANSI logging switch. They depend on Config
Server and Controller; some distributions also wait for OAuth.

These are regression fixtures, not substitute implementations for customer
services. Preserve stable response contracts used by Hurl and workflow tests.
When a workflow test fails, call the demo service directly from the Compose
network before attributing the result to Workflow or Gateway.

