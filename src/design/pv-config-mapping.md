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
- release one or more Rust products

It must also support tenant-specific product versions without copying the same
standard config mappings into every tenant.

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

## Product Versioning Policy

The release process must separate three related but different concepts:

```text
release train change != product artifact change != config contract change
```

A Java release train can have one shared version number for coordination, but
that does not mean every product necessarily has a changed config contract. At
the same time, a product can legitimately need a new product version even when
its own repository did not change. For example, if a shared `light-4j` module
changes and every Java product must be rebuilt to pick up that dependency, each
rebuilt artifact is a real product release.

Recommended policy:

- Create a new product version when the product artifact changes.
- Treat common library upgrades as product artifact changes for every rebuilt
  product.
- Do not create a new product version for a product that is not rebuilt and not
  redeployed as part of the release.
- Treat config mapping as a separate decision from product version creation.
- If the config contract is unchanged, inherit the previous product version's
  profile link.
- If the config contract changed or `breakConfig=true`, require an explicit
  profile manifest.

This lets Java keep the operational benefit of release trains while preventing
unnecessary mapping maintenance. Rust can continue independent product
versioning because Rust products are already released separately.

If the portal needs to show that an unchanged product participated in a Java
release train, model that as release-set membership, not as a new product
version. A release set can link to the existing `productVersionId` for
unchanged products and to the new `productVersionId` for rebuilt products.

The release metadata should record why a product version exists:

```json
{
  "releaseReason": "light4j-dependency-upgrade",
  "artifactChanged": true,
  "sourceChanged": false,
  "configChanged": false,
  "breakConfig": false,
  "configMappingPolicy": "inheritProfileFromPrevious"
}
```

Decision matrix:

| Case | Product Version | Mapping Action |
| --- | --- | --- |
| Product source changed and config changed | create new version | explicit profile manifest |
| Product source changed but config unchanged | create new version | inherit previous profile link |
| Shared Java dependency changed and product rebuilt | create new version | inherit profile link unless config changed |
| Product not rebuilt and not redeployed | no new version | no mapping action |
| Breaking config change | create new version | explicit profile manifest required |

## Goals

- Auto-populate config mappings for every new Java or Rust product release.
- Preserve event replay, auditability, and projection rebuild behavior.
- Support all portal hosts with one release operation without per-host mapping
  event amplification.
- Avoid hard-coded `productVersionId` values in reusable release manifests.
- Support dry-run reporting before events are emitted.
- Keep manual override and cleanup possible through existing mapping commands.
- Make generated events idempotent enough for safe retry.
- Detect missing config and property definitions before a release appears
  complete.

## Non-Goals

- Do not change the config override hierarchy.
- Do not write directly to config mapping projection tables.
- Do not make the config update page infer product applicability by scanning
  all config properties at runtime.
- Do not require schema-registry completion before mappings can be automated.
- Do not force all organizations to use the same product mappings if they need
  host-specific customization.

## Recommended Approach

Use `ConfigProfile` as the reusable config contract, then link tenant product
versions to the profile.

The existing `product_version_config_t` and
`product_version_config_property_t` tables are host-scoped because
`product_version_t` is host-scoped. That model works for tenant-specific
extensions, but it is expensive for standard product mappings because every
host receives a duplicate copy of the same config/property rows.

The profile model separates the global product config contract from the
tenant's product release:

```text
ConfigProfile = standard config contract for a product/runtime/framework line
ProductVersion = tenant-owned release artifact/version
ProductVersionConfigProfile = tenant product version points to standard profile
```

For example, every tenant can have its own internal `lg` product version while
all of those versions point to the same `light-gateway-java-2.3.5` config
profile if their config contract is the same.

The existing product-version mapping tables remain useful, but their role
changes:

- `config_profile_config_t` and `config_profile_property_t` hold standard
  global applicability.
- `product_version_config_profile_t` links a tenant product version to the
  standard profile.
- `product_version_config_t` and `product_version_config_property_t` hold
  tenant-specific additions or legacy direct mappings.

This removes the need for `allHosts=true` to generate the same mapping events
for every tenant. A release creates or updates one profile, then each tenant
product version emits one profile-link event.

## Schema Proposal

The profile tables are global because `config_t` and `config_property_t` are
already global definitions.

```sql
CREATE TABLE config_profile_t (
    profile_id           UUID PRIMARY KEY,
    profile_name         VARCHAR(255) NOT NULL,
    runtime_family       VARCHAR(32) NOT NULL,
    product_id           VARCHAR(8) NOT NULL,
    light4j_version      VARCHAR(32),
    contract_version     VARCHAR(64) NOT NULL,
    profile_desc         VARCHAR(1024),
    aggregate_version    BIGINT DEFAULT 1 NOT NULL,
    active               BOOLEAN NOT NULL DEFAULT TRUE,
    delete_user          VARCHAR(255),
    delete_ts            TIMESTAMP WITH TIME ZONE,
    update_user          VARCHAR(255) DEFAULT SESSION_USER NOT NULL,
    update_ts            TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE UNIQUE INDEX config_profile_unique_idx
    ON config_profile_t(runtime_family, product_id, contract_version)
    WHERE active = true;

CREATE TABLE config_profile_config_t (
    profile_id           UUID NOT NULL,
    config_id            UUID NOT NULL,
    aggregate_version    BIGINT DEFAULT 1 NOT NULL,
    active               BOOLEAN NOT NULL DEFAULT TRUE,
    delete_user          VARCHAR(255),
    delete_ts            TIMESTAMP WITH TIME ZONE,
    update_user          VARCHAR(255) DEFAULT SESSION_USER NOT NULL,
    update_ts            TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    PRIMARY KEY(profile_id, config_id),
    FOREIGN KEY(profile_id) REFERENCES config_profile_t(profile_id) ON DELETE CASCADE,
    FOREIGN KEY(config_id) REFERENCES config_t(config_id) ON DELETE CASCADE
);

CREATE TABLE config_profile_property_t (
    profile_id           UUID NOT NULL,
    property_id          UUID NOT NULL,
    aggregate_version    BIGINT DEFAULT 1 NOT NULL,
    active               BOOLEAN NOT NULL DEFAULT TRUE,
    delete_user          VARCHAR(255),
    delete_ts            TIMESTAMP WITH TIME ZONE,
    update_user          VARCHAR(255) DEFAULT SESSION_USER NOT NULL,
    update_ts            TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    PRIMARY KEY(profile_id, property_id),
    FOREIGN KEY(profile_id) REFERENCES config_profile_t(profile_id) ON DELETE CASCADE,
    FOREIGN KEY(property_id) REFERENCES config_property_t(property_id) ON DELETE CASCADE
);

CREATE TABLE product_version_config_profile_t (
    host_id              UUID NOT NULL,
    product_version_id   UUID NOT NULL,
    profile_id           UUID NOT NULL,
    aggregate_version    BIGINT DEFAULT 1 NOT NULL,
    active               BOOLEAN NOT NULL DEFAULT TRUE,
    delete_user          VARCHAR(255),
    delete_ts            TIMESTAMP WITH TIME ZONE,
    update_user          VARCHAR(255) DEFAULT SESSION_USER NOT NULL,
    update_ts            TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    PRIMARY KEY(host_id, product_version_id),
    FOREIGN KEY(host_id, product_version_id)
        REFERENCES product_version_t(host_id, product_version_id) ON DELETE CASCADE,
    FOREIGN KEY(profile_id) REFERENCES config_profile_t(profile_id) ON DELETE RESTRICT
);
```

Using a separate `product_version_config_profile_t` link table is preferred
over adding `config_profile_id` to `product_version_t` because it keeps the
product version aggregate smaller and lets profile linking be introduced as a
separate event stream. If a future product version needs multiple profiles, the
primary key can be extended to `(host_id, product_version_id, profile_id)` with
an `order_index` column.

`ON DELETE RESTRICT` on `product_version_config_profile_t.profile_id` is
intentional. A profile cannot be deleted while any tenant product version is
linked to it. Operators must first migrate linked product versions to another
profile, unlink them, or delete the tenant product versions.

The database constraints only apply to hard deletes. Because projections use
soft deletes, command handlers must manually reject profile deletion while
active product-version profile links exist, and the `ConfigProfileDeletedEvent`
projection must mark active `config_profile_config_t` and
`config_profile_property_t` rows inactive.

Recommended event types:

- `ConfigProfileCreatedEvent`
- `ConfigProfileDeletedEvent`
- `ConfigProfileConfigCreatedEvent`
- `ConfigProfileConfigDeletedEvent`
- `ConfigProfilePropertyCreatedEvent`
- `ConfigProfilePropertyDeletedEvent`
- `ProductVersionConfigProfileLinkedEvent`
- `ProductVersionConfigProfileUnlinkedEvent`

The existing `ProductVersionConfigCreatedEvent` and
`ProductVersionConfigPropertyCreatedEvent` remain valid for host-specific
direct mappings.

## Query Resolution

`getConfigUpdateProperties` should resolve applicable configs/properties from
both profile mappings and direct product-version mappings:

```sql
-- profile-backed standard mappings
SELECT cpc.config_id
FROM product_version_config_profile_t pvcp
JOIN config_profile_t cp ON cp.profile_id = pvcp.profile_id
JOIN config_profile_config_t cpc ON cpc.profile_id = pvcp.profile_id
WHERE pvcp.host_id = :hostId
  AND pvcp.product_version_id = :productVersionId
  AND pvcp.active = true
  AND cp.active = true
  AND cpc.active = true

UNION

-- tenant-specific direct additions and legacy mappings
SELECT pvc.config_id
FROM product_version_config_t pvc
WHERE pvc.host_id = :hostId
  AND pvc.product_version_id = :productVersionId
  AND pvc.active = true;
```

The property query follows the same pattern with
`config_profile_property_t` and `product_version_config_property_t`.

If a tenant must remove a standard profile property for its own product
version, the clean path is to assign a different profile for that product
version. Direct mapping tables are additive and should not try to represent
negative overrides unless a future exclusion table is explicitly added.

## Manifest Source

The manifest is portable. It uses logical product, config, and property names,
not database-only IDs. It defines a config profile once, then links product
versions to that profile.

```json
{
  "runtimeFamily": "java",
  "releaseSet": "java-2026-06",
  "profiles": [
    {
      "profileName": "light-gateway-java-2.3.5",
      "productId": "lg",
      "light4jVersion": "2.3.4",
      "contractVersion": "light-gateway-java-2.3.5",
      "configs": [
        {
          "configName": "client",
          "properties": [
            "verifyHostname",
            "tokenServerUrl"
          ]
        }
      ]
    }
  ],
  "products": [
    {
      "productId": "lg",
      "productVersion": "2.0.0",
      "releaseReason": "product-change",
      "artifactChanged": true,
      "sourceChanged": true,
      "configChanged": false,
      "breakConfig": false,
      "configMappingPolicy": "linkProfile",
      "configProfileRef": {
        "productId": "lg",
        "contractVersion": "light-gateway-java-2.3.5"
      },
      "inheritFrom": {
        "productVersion": "1.9.9"
      }
    }
  ]
}
```

For Java products, a shared Java dependency upgrade can create new tenant
product versions while reusing the same profile if the config contract did not
change. If the config contract changed, the release creates a new profile and
links rebuilt product versions to it.

If a Java release train includes products that were not rebuilt, those products
should be linked to the release set but should not receive new
`productVersionId` values or new mapping events.

## Generator Responsibilities

The generator takes:

- optional `hostId`, product, or release-set filters for profile links
- runtime family: `java`, `rust`, or both
- release set or manifest path
- dry-run flag

For each profile entry, it resolves:

- `configId` from `configName`
- `propertyId` from `configName + propertyName`
- existing `profileId` from `runtimeFamily + productId + contractVersion`, or
  a deterministic new `profileId`

Then it emits profile events only for missing or changed profile mappings:

- one `ConfigProfileCreatedEvent` for each new profile
- one `ConfigProfileConfigCreatedEvent` for each profile config
- one `ConfigProfilePropertyCreatedEvent` for each profile property
- in `syncProfile` replacement mode, one `ConfigProfileConfigDeletedEvent` or
  `ConfigProfilePropertyDeletedEvent` for each active profile mapping that is
  no longer present in the manifest

Profile deletion or replacement must be explicit. The default sync mode should
be additive so a partial manifest cannot accidentally remove a property from
every tenant linked to the profile. A delete-capable sync must require
`replace=true` or an equivalent explicit flag and must show affected linked
product versions in dry-run output.

For each product entry, it resolves:

- `productVersionId` from `hostId + productId + productVersion`
- `profileId` from `configProfileRef`

Then it emits:

- one `ProductVersionConfigProfileLinkedEvent` per tenant product version
- optional direct `ProductVersionConfigCreatedEvent` and
  `ProductVersionConfigPropertyCreatedEvent` only for tenant-specific
  additions

If `dryRun=true`, no events are emitted. The response returns a report:

```json
{
  "releaseSet": "java-2026-06",
  "profiles": [
    {
      "profileName": "light-gateway-java-2.3.5",
      "profileId": "019f...",
      "configsToCreate": 15,
      "propertiesToCreate": 183,
      "alreadyMappedConfigs": 0,
      "alreadyMappedProperties": 0,
      "missingConfigs": [],
      "missingProperties": []
    }
  ],
  "products": [
    {
      "hostId": "01964b05-552a-7c4b-9184-6857e7f3dc5f",
      "productId": "lg",
      "productVersion": "2.0.0",
      "productVersionId": "019f...",
      "profileId": "019f...",
      "linkToCreate": true,
      "alreadyLinked": false
    }
  ]
}
```

Dry run must fail the release when any required product version, profile,
config, or property cannot be resolved.

## Inheritance From Previous Version

`inheritFrom` is useful for frequent releases, but it should usually inherit a
profile link, not copy rows.

Recommended rules:

- If the config contract is unchanged, link the new product version to the same
  profile as the previous product version.
- If a manifest lists an explicit profile with configs/properties, create or
  update that profile and link the product version to it.
- If `configMappingPolicy=inheritProfileFromPrevious`, copy the previous
  profile link.
- If `inheritFrom` is set and the manifest omits `configProfileRef`, copy the
  profile link from the source product version.
- If both inheritance and `add`/`remove` are set, create a new profile derived
  from the inherited profile, apply the changes, and link to the new profile.
- If the new product version has `breakConfig=true`, require an explicit
  profile manifest. Do not silently inherit.
- If `breakConfig=false`, inheritance is allowed, but dry run should still
  compare the inherited mappings against any known generated config metadata.
- If `configChanged=false`, profile-link inheritance is the default mapping
  policy.
- If `configChanged=true`, require either explicit `configs` or explicit
  `add`/`remove` sections.

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
runtimeFamily|productId|contractVersion
profileId|configId
profileId|propertyId
hostId|productVersionId|profileId
hostId|productVersionId|configId
hostId|productVersionId|propertyId
```

The aggregate subject should match the mapping aggregate identity used by the
event model. Profile aggregate subjects do not need `hostId`. Product-version
profile links and direct tenant mappings do need `hostId` and
`productVersionId`.

Direct IDs are preferred in generated events:

```json
{
  "type": "ProductVersionConfigProfileLinkedEvent",
  "aggregatetype": "ProductVersionConfigProfile",
  "data": {
    "hostId": "01964b05-552a-7c4b-9184-6857e7f3dc5f",
    "productId": "gtw",
    "productVersion": "1.0.1",
    "productVersionId": "019f...",
    "profileId": "019f...",
    "profileName": "light-gateway-java-2.3.5",
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
product/syncProductVersionConfigProfiles/0.1.0
```

Request:

```json
{
  "hostId": "01964b05-552a-7c4b-9184-6857e7f3dc5f",
  "runtimeFamily": "java",
  "releaseSet": "java-2026-06",
  "manifest": {},
  "allHosts": false,
  "dryRun": true,
  "mode": "syncProfile"
}
```

Modes:

- `syncProfile`: create or update profile mappings from a manifest; additive
  by default, replacement only with an explicit delete-capable flag
- `linkProfile`: link tenant product versions to profiles
- `inheritProfile`: link a new product version to the previous version's
  profile
- `backfillLinks`: link existing product versions to matching profiles
- `verify`: report missing profiles, links, configs, or properties without
  creating events

Profile delete and replacement operations must respect the
`ON DELETE RESTRICT` link. A command cannot delete a profile while any active
`product_version_config_profile_t` row references it; it must first migrate or
unlink the affected product versions.

Because projections soft-delete rows instead of issuing hard `DELETE`
statements, the command handler must perform this active-link check explicitly
before emitting `ConfigProfileDeletedEvent`. The projection handler should also
defensively skip parent deletion while active links exist and cascade a
successful profile soft-delete to active `config_profile_config_t` and
`config_profile_property_t` rows.

The command handler should not directly update projection tables. It should
emit profile and profile-link events.

For large all-host release sets, the command should avoid one giant synchronous
transaction. It can either:

- emit the profile events first because they are host-neutral, then
- enqueue one profile-link job per host and product

The second step is cheap compared with copying every config property mapping,
but it should still be asynchronous for large tenant counts.

## Importer Option

The event importer should support a generator mode:

```bash
event-importer generate-config-profiles \
  --manifest events/releases/rust-2026-06.json \
  --host 01964b05-552a-7c4b-9184-6857e7f3dc5f \
  --dry-run
```

For deployment bundles, the generator can write normal JSON import files:

```text
events/generated/08-config-profile-properties-rust-2026-06.json
events/generated/09-config-profile-configs-rust-2026-06.json
events/generated/10-product-version-config-profile-links-rust-2026-06.json
```

This is the fastest migration path because it extends the current Rust import
process. It also lets teams review the generated events before importing them.

The importer path is best for bootstrap and local environments. The command API
path is better for live portal operations where the release needs to create
profiles once and link tenant product versions without copying files into each
deployment.

## Release Flow

Recommended release pipeline:

1. Determine the product release set.
2. Classify each product as artifact changed, source changed, config changed,
   or unchanged.
3. Generate or update config/property definitions for products whose config
   contract changed.
4. Create or reuse `ConfigProfile` rows for each config contract.
5. Create new `ProductVersionCreatedEvent` rows for every product whose
   artifact changed.
6. Run profile and profile-link dry-run for all target hosts.
7. Fail the release if dry-run reports unresolved product versions, profiles,
   configs, or properties.
8. Emit profile events and product-version profile-link events.
9. Verify `config_profile_config_t`, `config_profile_property_t`, and
   `product_version_config_profile_t` counts.
10. Smoke-test `getConfigUpdateProperties` for at least one instance, API, app,
   and app-api target for the release.

For patch releases where config does not change, the pipeline can use
`inheritFrom` and verify that the new version links to the same profile as the
previous version.

For Java common-library upgrades, all rebuilt Java products should receive new
product versions even if their own repositories did not change. If
`configChanged=false`, the mapping generator should inherit mappings from each
product's previous version by reusing the previous profile link.

For breaking config releases, the pipeline should require an explicit manifest
and should report added and removed configs/properties in the release note.

## Backfill Existing Product Versions

Backfill is needed for product versions that already exist but have no profile
link or still depend only on legacy direct mappings.

Backfill should support:

- one product version
- all versions of one product
- all products in one runtime family
- all active product versions for all hosts

Backfill must be conservative:

- create only missing active profiles and profile links
- never delete existing direct product-version mappings automatically
- report direct mappings that duplicate profile mappings so operators can
  decide whether to clean them up later
- report conflicting or inactive config/property definitions
- keep generated events deterministic

Backfill output should include counts by host, product, product version,
profile, and direct legacy mappings so operators can confirm why a config
update page was empty before the fix.

Migration from the current tables should be done in three steps:

1. Create profiles from known Java and Rust manifests or from trusted existing
   product-version mappings.
2. Link existing product versions to the correct profile.
3. Leave existing direct mappings in place until query resolution proves the
   profile path covers the same configs/properties.

After migration, release automation should stop generating direct
product-version mapping events for standard mappings. Direct mapping events
remain available for tenant-specific additions.

## Host and Tenant Handling

The profile manifest is host-neutral. The generator resolves global profile
IDs once, then resolves tenant product-version IDs only for profile links.

For `allHosts=true`, the generator should query active hosts that have matching
product versions and create profile-link events per product version. It should
not generate per-host config/property mapping events for standard profile
mappings. If a host does not have the target product version, it should be
reported as skipped, not failed, unless the release request marks that product
version as required for every host.

Host-specific overrides are allowed through optional manifest sections:

```json
{
  "hostOverrides": {
    "01964b05-552a-7c4b-9184-6857e7f3dc5f": {
      "products": [
        {
          "productId": "gtw",
          "directAdd": [
            {
              "configName": "tenant-plugin",
              "properties": ["enabled", "endpoint"]
            }
          ]
        }
      ]
    }
  }
}
```

The default path should be shared profiles. Host overrides should be rare and
visible in dry-run output.

If a tenant needs to remove a standard profile property, assign a different
profile to that product version. Avoid negative host-specific overrides in the
MVP because they make query resolution and audit history harder to reason
about.

## Observability

The generator or command should publish a structured summary:

- release set
- runtime family
- host count
- product count
- generated profile events
- generated profile config events
- generated profile property events
- generated product-version profile-link events
- skipped existing profile links
- duplicate direct mappings
- missing product versions
- missing profiles
- missing configs
- missing properties
- failed hosts

The config update page empty-state message should reference this operational
check: if an instance has no applicable config properties, verify the product
version has a profile link or direct config/config-property mappings.

## Phased Implementation

### Phase 1: Manifest Generator for Importer

- Add Java and Rust mapping manifests.
- Generate JSON import files for `ConfigProfile`, profile config/property
  mappings, and product-version profile links.
- Use direct IDs in generated events.
- Add dry-run validation and count reports.
- Use this path to backfill current local/dev deployments.

### Phase 2: Sync Command

- Add `syncProductVersionConfigProfiles`.
- Support `dryRun`, `syncProfile`, `linkProfile`, `inheritProfile`,
  `backfillLinks`, and `verify`.
- Emit profile and profile-link events instead of direct SQL.
- Add RBAC so only product/release admins can run it.

### Phase 3: Release Pipeline Integration

- Call dry-run during Java and Rust release workflows.
- Fail release on unresolved profiles, product versions, configs, or
  properties.
- Emit profile events and profile-link events after product versions are
  created.
- Record mapping summary in release artifacts.

### Phase 4: Runtime Drift Detection

- Add scheduled or on-demand verification.
- Report active product versions with no profile link and no direct config
  mappings.
- Report config properties referenced by manifests but missing from
  `config_property_t`.
- Add a portal-view diagnostics link from the config update page.

## Open Questions

- Should release manifests live in `event-importer`, each product repository,
  or a dedicated release metadata repository?
- Should `ProductVersionCreatedEvent` optionally carry a `configProfileRef`,
  or should profile linking remain a separate release step?
- Do we need an organization-level policy to prevent inheritance for selected
  regulated products?
- Do we need a profile-clone command for tenant-specific removals, or is manual
  profile creation enough for the MVP?

## Recommendation

Implement the profile schema and Phase 1 importer generator first, then add the
sync command for live all-host operations.

The long-term target is release-time automation:

- product CI generates the profile manifest from source metadata instead of
  relying on hand-maintained JSON
- product release creates product versions
- profile dry-run validates configs/properties once
- profile-link dry-run validates every tenant product version
- profile and profile-link events are emitted or imported
- config update page works for the new release without manual follow-up

For Java, manifest generation should eventually come from a Maven plugin that
introspects the `light-4j` config modules or generated config metadata during
the build. For Rust, the equivalent should be a Cargo build script or release
tool that extracts config structs and their generated metadata. This keeps the
manifest aligned with the code and turns manual manifest editing into an
exception path.

This keeps the config update page simple and keeps product applicability in the
event-sourced product release model without duplicating standard mappings for
every tenant.
