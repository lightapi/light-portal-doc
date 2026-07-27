# Access Control: Claim Mappings

The `claimMappings` property maps access-control permission dimensions to the
JWT claim names used by your identity provider.

- **Type:** Map of permission dimension to an array of claim names
- **Default:** `{}`
- **Config-server property prefix:** `access-control.claimMappings`

```yaml
claimMappings:
  roles:
    - realm_roles
    - application_roles
  groups:
    - member_of
  tenant:
    - tenant_id
```

In config-server `values.yml`, set individual map entries with fully qualified
property names:

```yaml
access-control.claimMappings.roles: [realm_roles, application_roles]
access-control.claimMappings.groups: [member_of]
access-control.claimMappings.tenant: [tenant_id]
```

## What It Is Designed For

The mapping allows policies to keep stable permission keys even when tokens use
deployment-specific claim names. It is shared by:

- role-based request authorization (`req-acc`);
- row and column response filters (`res-fil`); and
- MCP `tools/list` visibility evaluation.

The standard permission keys and their built-in claim aliases are:

| Permission key | Built-in JWT claim aliases |
| :--- | :--- |
| `roles` | `role`, `roles` |
| `groups` | `scp`, `grp`, `group`, `groups` |
| `positions` | `pos`, `position`, `positions` |
| `attributes` | `att`, `attribute`, `attributes` |
| `users` | `uid`, `user_id`, `sub` |

If a key has a non-empty configured mapping, its configured claim names replace
the built-in aliases for that key. Unmapped standard keys continue to use their
built-in aliases. When multiple claim names are listed, values from all present
claims are combined for matching.

Custom row or column dimensions are also supported. For example, a `tenant`
mapping makes the `tenant_id` claim available to `row.tenant` and `col.tenant`
policy entries. For an unmapped custom dimension, the runtime looks for a claim
with the same name as the dimension.

## Setup

1. Inspect the verified JWT claims produced by the deployment's identity
   provider.
2. Add a mapping only where the token's claim name differs from the built-in
   alias or where the policy uses a custom dimension.
3. Use plural keys (`roles`, `groups`, `positions`, `attributes`, and `users`)
   in `claimMappings`, even though row and column policy objects use singular
   dimension names such as `row.role` and `col.group`.
4. Reload the access-control configuration and test both a matching and a
   non-matching caller for each affected authorization or filter rule.

The older `toolsListAccessControl.claimMappings` location remains a compatibility
fallback. Top-level `claimMappings` takes precedence for the same key and is the
recommended location because it applies consistently across authorization,
response filtering, and MCP tool visibility.
