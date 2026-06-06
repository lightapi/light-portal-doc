# Product Version Config Mapping Automation

The `portal-view` config update page depends on product-version applicability
metadata before it can show configurable properties for instance, API, app, and
app-api scopes. The metadata is stored in two product release mapping tables:

- `product_version_config_t`
- `product_version_config_property_t`

The current Rust bootstrap data is generated into import files:

- `event-importer/events/local/09-rust-product-version-configs.json`
- `event-importer/events/local/08-rust-product-version-config-properties.json`

The same import-file approach can be used for Java products, but it does not
scale well if every Java or Rust release requires a hand-maintained set of
mapping events across all portal instances. This design proposes a release
mapping automation model that keeps the existing event-sourced write path and
removes the need to manually recreate mapping files for every product release.

## Problem

Product versions are released often. Each new release can introduce a new
`productVersionId`, and the config update page only knows which configs and
properties are applicable when mappings exist for that exact product version.

Without automation:

- new releases have empty config update views until mappings are imported
- each portal instance must be updated separately
- Java and Rust products need parallel manual processes
- copying JSON import files by hand can drift from the actual product config
  schema
- support teams cannot safely tell whether an empty page means "no configs" or
  "missing mappings"

The automation must support two release modes:

- release all Java products
- release all Rust products

It must also support applying the mappings to every active portal host or
tenant that owns product versions.

## Current Model

`product_version_config_t` maps a product version to a config:

```text
host_id + product_version_id + config_id
```

`product_version_config_property_t` maps a product version to a config
property:

```text
host_id + product_version_id + property_id
```

The event types already exist:

- `ProductVersionConfigCreatedEvent`
- `ProductVersionConfigDeletedEvent`
- `ProductVersionConfigPropertyCreatedEvent`
- `ProductVersionConfigPropertyDeletedEvent`

The command APIs already exist:

- `product/createProductVersionConfig/0.1.0`
- `product/deleteProductVersionConfig/0.1.0`
- `product/createProductVersionConfigProperty/0.1.0`
- `product/deleteProductVersionConfigProperty/0.1.0`

The projection handlers insert into the mapping tables through the event
processor. The preferred automation path is therefore event-based, not direct
SQL.

## Goals

- Auto-populate config mappings for every new Java or Rust product release.
- Preserve event replay, auditability, and projection rebuild behavior.
- Support all portal hosts with one release operation.
- Avoid hard-coded `productVersionId` values in reusable release manifests.
- Support dry-run reporting before events are emitted.
- Keep manual override and cleanup possible through existing mapping commands.
- Make generated events idempotent enough for safe retry.
- Detect missing config and property definitions before a release appears
  complete.

## Non-Goals

- Do not change the config override hierarchy.
- Do not write directly to `product_version_config_t` or
  `product_version_config_property_t`.
- Do not make the config update page infer product applicability by scanning
  all config properties at runtime.
- Do not require schema-registry completion before mappings can be automated.
- Do not force all organizations to use the same product mappings if they need
  host-specific customization.

## Recommended Approach

Use a release mapping manifest as the source of truth, then generate normal
product mapping events from that manifest.

The manifest is portable. It uses logical product, config, and property names,
not database-only IDs. The generator resolves IDs against each target portal
host before creating events.

```json
{
  "runtimeFamily": "rust",
  "releaseSet": "rust-2026-06",
  "products": [
    {
      "productId": "gtw",
      "productVersion": "1.0.1",
      "light4jVersion": "2.3.4",
      "inheritFrom": {
        "productVersion": "1.0.0"
      },
      "configs": [
        {
          "configName": "client",
          "properties": [
            "tls",
            "timeout",
            "proxyHost"
          ]
        }
      ]
    }
  ]
}
```

For Java products, the same structure is used with
`"runtimeFamily": "java"`. If a release set upgrades every Java product, the
manifest contains every product and version in that release set.

## Generator Responsibilities

The generator takes:

- `hostId` or `allHosts=true`
- runtime family: `java`, `rust`, or both
- release set or manifest path
- dry-run flag

For each host and product entry, it resolves:

- `productVersionId` from `hostId + productId + productVersion`
- `configId` from `configName`
- `propertyId` from `configName + propertyName`

Then it emits:

- one `ProductVersionConfigCreatedEvent` for each config
- one `ProductVersionConfigPropertyCreatedEvent` for each property

If `dryRun=true`, no events are emitted. The response returns a report:

```json
{
  "hostId": "01964b05-552a-7c4b-9184-6857e7f3dc5f",
  "releaseSet": "rust-2026-06",
  "products": [
    {
      "productId": "gtw",
      "productVersion": "1.0.1",
      "productVersionId": "019f...",
      "configsToCreate": 15,
      "propertiesToCreate": 183,
      "alreadyMappedConfigs": 0,
      "alreadyMappedProperties": 0,
      "missingConfigs": [],
      "missingProperties": []
    }
  ]
}
```

Dry run must fail the release when any required product version, config, or
property cannot be resolved.

## Inheritance From Previous Version

`inheritFrom` is useful for frequent releases, but it should not be the only
source of truth.

Recommended rules:

- If a manifest lists explicit configs and properties, use the manifest.
- If `inheritFrom` is set and the manifest omits `configs`, copy mappings from
  the source product version.
- If both are set, start from the inherited mappings and apply explicit
  additions/removals from the manifest.
- If the new product version has `breakConfig=true`, require an explicit
  manifest. Do not silently inherit.
- If `breakConfig=false`, inheritance is allowed, but dry run should still
  compare the inherited mappings against any known generated config metadata.

Example:

```json
{
  "productId": "api",
  "productVersion": "1.0.2",
  "inheritFrom": {
    "productVersion": "1.0.1"
  },
  "remove": [
    {
      "configName": "old-config"
    }
  ],
  "add": [
    {
      "configName": "new-config",
      "properties": ["enabled", "endpoint"]
    }
  ]
}
```

This gives release automation a low-maintenance path for patch releases while
still allowing breaking releases to declare exact applicability.

## Event Idempotency

The generator should produce deterministic event IDs so the same release
operation can be retried safely.

Use a stable namespace string such as:

```text
hostId|releaseSet|productVersionId|configId
hostId|releaseSet|productVersionId|propertyId
```

The aggregate subject should match the mapping aggregate identity used by the
event model. The projection table keys include `hostId`, `productVersionId`,
and either `configId` or `propertyId`, so event generation must include those
values in `data` even when an enricher can resolve them.

Direct IDs are preferred in generated events:

```json
{
  "type": "ProductVersionConfigCreatedEvent",
  "aggregatetype": "ProductVersionConfig",
  "data": {
    "hostId": "01964b05-552a-7c4b-9184-6857e7f3dc5f",
    "productId": "gtw",
    "productVersion": "1.0.1",
    "productVersionId": "019f...",
    "configName": "client",
    "configId": "0196...",
    "aggregateVersion": 0,
    "newAggregateVersion": 1
  }
}
```

The human-readable names are still useful for audit and diagnostics, but the
projection should not depend on name resolution after the generator has already
resolved the IDs.

## Command API Option

Add a new product command:

```text
product/syncProductVersionConfigMappings/0.1.0
```

Request:

```json
{
  "hostId": "01964b05-552a-7c4b-9184-6857e7f3dc5f",
  "runtimeFamily": "rust",
  "releaseSet": "rust-2026-06",
  "manifest": {},
  "allHosts": false,
  "dryRun": true,
  "mode": "manifest"
}
```

Modes:

- `manifest`: resolve mappings from a supplied or registered manifest
- `inherit`: copy mappings from a source product version
- `backfill`: create missing mappings for existing product versions
- `verify`: report missing mappings without creating events

The command handler should not directly update projection tables. It should
emit the same child events that the existing create mapping commands emit.

For large all-host release sets, the command can either:

- emit all mapping events in one transaction per host, or
- enqueue one mapping job per host and product

The second option is safer for large releases because a single missing property
does not block unrelated hosts and products.

## Importer Option

The event importer should support a generator mode:

```bash
event-importer generate-pv-config-mappings \
  --manifest events/releases/rust-2026-06.json \
  --host 01964b05-552a-7c4b-9184-6857e7f3dc5f \
  --dry-run
```

For deployment bundles, the generator can write normal JSON import files:

```text
events/generated/08-product-version-config-properties-rust-2026-06.json
events/generated/09-product-version-configs-rust-2026-06.json
```

This is the fastest migration path because it extends the current Rust import
process. It also lets teams review the generated events before importing them.

The importer path is best for bootstrap and local environments. The command API
path is better for live portal operations where the release needs to update all
hosts without copying files into each deployment.

## Release Flow

Recommended release pipeline:

1. Generate or update config/property definitions for Java or Rust products.
2. Create the new `ProductVersionCreatedEvent` rows for every product in the
   release set.
3. Run mapping dry-run for all target hosts.
4. Fail the release if dry-run reports unresolved configs or properties.
5. Emit mapping events.
6. Verify `product_version_config_t` and
   `product_version_config_property_t` counts for each product version.
7. Smoke-test `getConfigUpdateProperties` for at least one instance, API, app,
   and app-api target for the release.

For patch releases where config does not change, the pipeline can use
`inheritFrom` and verify that the new version receives the same mapping counts
as the previous version.

For breaking config releases, the pipeline should require an explicit manifest
and should report added and removed configs/properties in the release note.

## Backfill Existing Product Versions

Backfill is needed for product versions that already exist but have missing
mappings.

Backfill should support:

- one product version
- all versions of one product
- all products in one runtime family
- all active product versions for all hosts

Backfill must be conservative:

- create only missing active mappings
- never delete existing mappings unless the request explicitly uses a removal
  manifest
- report conflicting or inactive config/property definitions
- keep generated events deterministic

Backfill output should include counts by host, product, and product version so
operators can confirm why a config update page was empty before the fix.

## Host and Tenant Handling

The manifest is host-neutral. The generator resolves IDs per host.

For `allHosts=true`, the generator should query active hosts that have matching
product versions and generate mappings per host. If a host does not have the
target product version, it should be reported as skipped, not failed, unless
the release request marks that product version as required for every host.

Host-specific overrides are allowed through optional manifest sections:

```json
{
  "hostOverrides": {
    "01964b05-552a-7c4b-9184-6857e7f3dc5f": {
      "products": [
        {
          "productId": "gtw",
          "remove": [
            { "configName": "experimental" }
          ]
        }
      ]
    }
  }
}
```

The default path should be shared manifests. Host overrides should be rare and
visible in dry-run output.

## Observability

The generator or command should publish a structured summary:

- release set
- runtime family
- host count
- product count
- generated config mapping events
- generated property mapping events
- skipped existing mappings
- missing product versions
- missing configs
- missing properties
- failed hosts

The config update page empty-state message should reference this operational
check: if an instance has no applicable config properties, verify the product
version has config and config property mappings.

## Phased Implementation

### Phase 1: Manifest Generator for Importer

- Add Java and Rust mapping manifests.
- Generate JSON import files from host-neutral manifests.
- Use direct IDs in generated events.
- Add dry-run validation and count reports.
- Use this path to backfill current local/dev deployments.

### Phase 2: Sync Command

- Add `syncProductVersionConfigMappings`.
- Support `dryRun`, `manifest`, `inherit`, and `verify`.
- Emit normal mapping events instead of direct SQL.
- Add RBAC so only product/release admins can run it.

### Phase 3: Release Pipeline Integration

- Call dry-run during Java and Rust release workflows.
- Fail release on unresolved mappings.
- Emit mapping events after product versions are created.
- Record mapping summary in release artifacts.

### Phase 4: Runtime Drift Detection

- Add scheduled or on-demand verification.
- Report active product versions with zero config mappings.
- Report config properties referenced by manifests but missing from
  `config_property_t`.
- Add a portal-view diagnostics link from the config update page.

## Open Questions

- Should release manifests live in `event-importer`, each product repository,
  or a dedicated release metadata repository?
- Should `ProductVersionCreatedEvent` optionally carry a `configMappingPolicy`
  field, or should mapping remain a separate release step?
- Do we need an organization-level policy to prevent inheritance for selected
  regulated products?
- Should removal manifests emit delete events immediately, or only warn until a
  release admin confirms?

## Recommendation

Implement Phase 1 first for immediate Java and Rust parity, then add the sync
command for live all-host operations.

The long-term target is release-time automation:

- product release creates product versions
- mapping dry-run validates every host
- mapping events are emitted or imported
- config update page works for the new release without manual follow-up

This keeps the config update page simple and keeps product applicability in the
event-sourced product release model where it belongs.
