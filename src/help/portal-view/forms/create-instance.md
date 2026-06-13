# Create Instance

Use this form to create a product/service instance.

After submission, the instance can be linked to API versions, client apps,
runtime endpoints, and configuration records.

Important fields:

- `instanceName`: user-facing instance name
- `productVersionId`: product version for the instance
- `serviceId`: service identifier
- `environment`, `region`, and `lob`: deployment metadata
- `ownerPositionId`: optional position owner for team access

## Environment Configuration Templates

The `environment` field provides a dropdown of standard environments defined globally in `light-portal` (e.g., `dev`, `sit`, `uat`, `stg`, `prd`). 

When setting up a host, you can customize configurations at this environment level. By doing so, the environment acts as a **configuration template**. 

For example, if you customize the `dev` environment for your host, any new instances you create that select `dev` as their environment will automatically inherit those customized properties. This prevents you from needing to repeatedly define the same baseline configuration for every single instance.

Of course, this inheritance is flexible: if a specific instance requires unique settings, you can override those environment-level properties directly at the instance level.

## Env Tag

The `envTag` (Environment Tag) acts as a label to logically separate an instance based on its configuration, deployment namespace, or simply to serve as an alias for the same Service ID. 

Critically, the combination of **Host ID**, **Service ID**, and **Env Tag** is used to uniquely identify an instance. This unique triad is what the system uses to load the correct configuration from the config server and to register the instance to the controller.

By default, the options in the Env Tag dropdown mirror the standard global `environment` list. However, because it supports host-specific overrides, each host or tenant can add their own customized Env Tags via the [Ref Table Admin](../pages/ref-table-admin.md) page (by creating a table named `environment` under their Host ID).
