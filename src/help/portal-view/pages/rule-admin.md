# Rule Admin

The Rule Admin page allows administrators to create and manage YAML rules, conditions, and actions.

For most users, they just need to pick up rules pre-defined in this page. We have defined some global rules to share with all tenants. Each tenant can create host-specific rules that can be used with the tenant.

When creating a new rule, the default condition security profile is strict. If standard profile is selected, a workflow task will be assigned to the `rule-admin` role for approval.

## References

- [Light Rule](https://www.networknt.com/light-fabric/crate/light-rule.html)
- [CEL Rule Conditions](https://www.networknt.com/light-fabric/design/cel-rule.html)
