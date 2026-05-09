# Instance File Config Phase

## Overview

`instance_file_t` stores instance-specific files that are not modeled as standard `config_property_t` rows. Examples include API specifications such as `openapi.yaml` and custom certificates or supporting files.

The config snapshot model currently separates two kinds of file data:

- Standard files are flattened into `config_snapshot_property_t`.
- Non-standard instance files are copied into `snapshot_instance_file_t`.

The `/config-server/files` endpoint must return both sets. It already filters standard files by `config_phase` through `config_snapshot_property_t.config_phase`, but `instance_file_t` and `snapshot_instance_file_t` do not currently carry `config_phase`. That makes it impossible to union the two sources while preserving runtime, deployment, and generator phase semantics.

## Problem

When a service starts through `DefaultConfigLoader`, it calls `/config-server/files` with `host`, `serviceId`, and `envTag`. The endpoint resolves the current snapshot and returns the files that should be written into `/config`.

For the sidecar case, `openapi.yaml` exists in both `instance_file_t` and `snapshot_instance_file_t`, but it does not exist in `config_snapshot_property_t`. Since the current `/files` query reads only `config_snapshot_property_t`, the response does not include `openapi.yaml`, and the sidecar cannot write it to `/config`.

The correct endpoint behavior is:

1. Read standard files from `config_snapshot_property_t`.
2. Read non-standard files from `snapshot_instance_file_t`.
3. Filter both sources by the requested config phase.
4. Return one filename-to-base64-content map.

## Decision

Add `config_phase` to both runtime and snapshot instance file tables:

- `instance_file_t.config_phase`
- `snapshot_instance_file_t.config_phase`

The allowed values should match `config_t.config_phase`:

- `G`: generator
- `D`: deployment
- `R`: runtime

The default value for existing and new rows should be `R`, because current instance files are consumed by runtime startup unless explicitly marked otherwise.

## Schema Changes

### Runtime Table

```sql
ALTER TABLE instance_file_t
  ADD COLUMN config_phase CHAR(1) NOT NULL DEFAULT 'R';

ALTER TABLE instance_file_t
  ADD CHECK (config_phase IN ('G', 'D', 'R'));

ALTER TABLE instance_file_t
  DROP CONSTRAINT IF EXISTS instance_file_uk;

ALTER TABLE instance_file_t
  ADD CONSTRAINT instance_file_uk
    UNIQUE (host_id, instance_id, config_phase, v_file_name);
```

The unique constraint must include `config_phase` so the same filename can exist separately for runtime and deployment if needed.

### Snapshot Table

```sql
ALTER TABLE snapshot_instance_file_t
  ADD COLUMN config_phase CHAR(1) NOT NULL DEFAULT 'R';

ALTER TABLE snapshot_instance_file_t
  ADD CHECK (config_phase IN ('G', 'D', 'R'));

CREATE INDEX idx_snap_inst_file_phase
  ON snapshot_instance_file_t (snapshot_id, config_phase, file_type, active);
```

The primary key can remain `(snapshot_id, host_id, instance_file_id)` because `instance_file_id` identifies the copied runtime row. The phase-aware index supports config-server lookups.

## Migration

Existing rows should be backfilled to runtime:

```sql
UPDATE instance_file_t
SET config_phase = 'R'
WHERE config_phase IS NULL;

UPDATE snapshot_instance_file_t
SET config_phase = 'R'
WHERE config_phase IS NULL;
```

If a historical custom file was actually intended for deployment or generator use, it must be corrected explicitly after migration. There is no reliable way to infer that from the current schema.

## Snapshot Creation

`create_snapshot` must copy `config_phase` from `instance_file_t` into `snapshot_instance_file_t`.

Current copy shape:

```sql
INSERT INTO snapshot_instance_file_t (
    snapshot_id, host_id, instance_file_id, instance_id, file_type,
    file_name, file_value, file_desc, expiration_ts,
    aggregate_version, active, update_user, update_ts
)
SELECT
    p_snapshot_id, t.host_id, t.instance_file_id, t.instance_id, t.file_type,
    t.file_name, t.file_value, t.file_desc, t.expiration_ts,
    t.aggregate_version, t.active, t.update_user, t.update_ts
FROM instance_file_t t
WHERE t.host_id = p_host_id
  AND t.instance_id = p_instance_id
  AND t.active = TRUE;
```

Target copy shape:

```sql
INSERT INTO snapshot_instance_file_t (
    snapshot_id, host_id, instance_file_id, instance_id, config_phase,
    file_type, file_name, file_value, file_desc, expiration_ts,
    aggregate_version, active, update_user, update_ts
)
SELECT
    p_snapshot_id, t.host_id, t.instance_file_id, t.instance_id, t.config_phase,
    t.file_type, t.file_name, t.file_value, t.file_desc, t.expiration_ts,
    t.aggregate_version, t.active, t.update_user, t.update_ts
FROM instance_file_t t
WHERE t.host_id = p_host_id
  AND t.instance_id = p_instance_id
  AND t.active = TRUE;
```

Snapshot creation should continue copying all active instance files for the instance. Consumers filter by phase when reading.

## Config Server Query

The `/files` endpoint should union standard files and non-standard instance files for the current snapshot.

Standard files:

```sql
SELECT
    p.source_level AS source,
    c.config_name,
    p.property_name,
    p.value_type,
    p.property_value,
    10 AS source_rank
FROM config_snapshot_property_t p
JOIN config_snapshot_t cs ON cs.snapshot_id = p.snapshot_id
JOIN config_t c ON c.config_id = p.config_id
JOIN host_t h ON cs.host_id = h.host_id
WHERE h.sub_domain || '.' || h.domain = ?
  AND cs.current = TRUE
  AND p.config_phase = ?
  AND p.property_type = 'File'
  AND cs.service_id = ?
  AND cs.environment = ?
```

Non-standard instance files:

```sql
SELECT
    'instance_file' AS source,
    'files' AS config_name,
    f.file_name AS property_name,
    'string' AS value_type,
    f.file_value AS property_value,
    100 AS source_rank
FROM snapshot_instance_file_t f
JOIN config_snapshot_t cs
  ON cs.snapshot_id = f.snapshot_id
 AND cs.host_id = f.host_id
 AND cs.instance_id = f.instance_id
JOIN host_t h ON h.host_id = cs.host_id
WHERE h.sub_domain || '.' || h.domain = ?
  AND cs.current = TRUE
  AND f.config_phase = ?
  AND f.file_type = 'File'
  AND f.active = TRUE
  AND cs.service_id = ?
  AND cs.environment = ?
```

The implementation can combine these with `UNION ALL`. If the same filename appears in both sources, the instance file should win because it is the instance-specific override. Java can enforce this by inserting standard rows first and custom rows second into the response map. SQL can enforce it with `source_rank` and `DISTINCT ON (property_name)` if the response is assembled directly from a result set.

The same model should be applied to `/certs` with `property_type = 'Cert'` and `file_type = 'Cert'`, because `instance_file_t.file_type` already supports certificates.

## API and Event Changes

All create, update, query, and replay paths for instance files should include `configPhase`.

Required behavior:

- New create/update requests accept `configPhase`.
- Missing `configPhase` defaults to `R` for backward compatibility.
- Created and updated events include `configPhase`.
- Replay of historical events defaults missing `configPhase` to `R`.
- Query responses expose `configPhase`.
- UI forms and grids allow the operator to choose or filter by phase.

## Code Impact

Expected implementation surfaces:

- `portal-db/postgres/ddl.sql`
- `portal-db/postgres/ddl-dbvis.sql`
- New `portal-db/postgres/patch_*.sql`
- `portal-db/postgres/sp_tr_fn.sql`
- `light-portal/db-provider` persistence for create, update, query, snapshot, clone, and replay flows
- `light-config-server` snapshot `/files` and `/certs` query behavior through `ConfigServerQueryPersistenceImpl`
- `portal-service/crates/portal-core` snapshot file and cert queries
- `portal-service/apps/config-server` response assembly if duplicate precedence is handled outside SQL
- `portal-view` schemas/forms/pages for instance files

## Validation

Minimum checks:

1. Create or migrate an instance file named `openapi.yaml` with `config_phase = 'R'`.
2. Create a snapshot for the instance.
3. Verify `snapshot_instance_file_t` has the same `config_phase`.
4. Call `/config-server/files?host=dev.lightapi.net&serviceId=...&envTag=dev`.
5. Confirm the response contains both standard files such as `logback.xml` and non-standard files such as `openapi.yaml`.
6. Start a sidecar with `DefaultConfigLoader` and confirm `/config/openapi.yaml` is written.

Regression tests should cover:

- Existing instance files default to runtime.
- Same filename can exist in different phases.
- `/files` filters out non-matching phases.
- Custom instance files override standard files with the same filename.
- Java and Rust config-server implementations return the same file keys.

## Out of Scope

This change does not move non-standard files into `config_snapshot_property_t`. Keeping them in `snapshot_instance_file_t` preserves the distinction between modeled config properties and instance-specific file artifacts.
