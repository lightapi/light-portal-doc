# Config Server

### Default Config Properties

For each config class in light-4j modules, we use annotations to generate schemas for the config files with default values, comments and validation rules.

As one time step, we also generate events to input all the properties into the light-portal. These events will create a base-line of the config properties with default values. All events in this first time population doesn't have a version. 

For each version release, we will create and attach an event.json file with the change to the properties. Most likely, we will add some properties with default values for each release. All events in the is file will have a version associated. Once played on the portal, updates for the version will be populated. 

On the portal ui, we load all properties and default values from database with a union of the base-line properties and all versions below and equal to the current version. 


### Instance Config Snapshot

Once a logical instance is created on the light-portal, we need to provide the product_version_id which will map to a specific product version. We also need to provide runtime configuration and deployment configuration for the instance to start the server and deploy it to a target environment. During the configuration updates, it might be a process of discovery and may take several revisit to complete. If a user makes a mistake, he/she might want to rollback the previous changes to a snapshot version to start it over again. During the deployment, we also need to save and tag the snapshot version so that we can rollback to the previous deployment configuration snapshot in case of deployment failure. 

The above requirements force us to create a table that is record all the commit for the config updates at instance level. It is like a GitHub commit to group several updates together. The user needs to explicitly click the commit button on the UI to allow the server to run the query to populate the snapshot table to create a new snapshot id. 

Durng the deployment, the deployment serivce will invoke the config server to force a commit and also link that commit to a deployment id just like a tag in GitHub. 


To meet the requirement above, we need to design tables to store immutable snapshots associated with a commitId/snapshotId to proivde reliable rollback points. 


### Snapshot tables

```
CREATE TABLE config_snapshot_t (
    snapshot_id                 UUID NOT NULL, -- Primary Key, maybe UUIDv7 for time ordering
    snapshot_ts                 TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    snapshot_type               VARCHAR(32) NOT NULL, -- e.g., 'DEPLOYMENT', 'USER_SAVE', 'SCHEDULED_BACKUP'
    description                 TEXT,                 -- User-provided description or system-generated info
    user_id                     UUID,                 -- User who triggered it (if applicable)
    deployment_id               UUID,                 -- FK to deployment_t if snapshot_type is 'DEPLOYMENT'
    -- Scope columns define WHAT this snapshot represents:
    scope_host_id               UUID NOT NULL,      -- Host context (always needed)
    scope_config_phase          CHAR(1) NOT NULL,   -- config phase context(required)
    scope_environment           VARCHAR(16),        -- Environment context (if snapshot is env-specific)
    scope_product_id            VARCHAR(8)          -- Product id context
    scope_product_version       VARCHAR(12)         -- Product version context
    scope_service_id            VARCHAR(512)        -- Service id context
    scope_api_id                VARCHAR(16)         -- Api id context
    scope_api_version           VARCHAR(16)         -- Api version context
    PRIMARY KEY(snapshot_id),
    FOREIGN KEY(deployment_id) REFERENCES deployment_t(deployment_id) ON DELETE SET NULL,
    FOREIGN KEY(user_id) REFERENCES user_t(user_id) ON DELETE SET NULL,
    FOREIGN KEY(scope_host_id) REFERENCES host_t(host_id) ON DELETE CASCADE
);

-- Index for finding snapshots by type or scope
CREATE INDEX idx_config_snapshot_scope ON config_snapshot_t (scope_host_id, scope_config_phase, scope_environment, 
    scope_product_id, scope_product_version, scope_service_id, scope_api_id, scope_api_version, snapshot_type, snapshot_ts);
CREATE INDEX idx_config_snapshot_deployment ON config_snapshot_t (deployment_id);


CREATE TABLE config_snapshot_property_t (
    snapshot_property_id        UUID NOT NULL,         -- Surrogate primary key for easier referencing/updates if needed
    snapshot_id                 UUID NOT NULL,         -- FK to config_snapshot_t
    config_id                   UUID NOT NULL,         -- The config id
    property_id                 UUID NOT NULL,         -- The final property id 
    property_name               VARCHAR(64) NOT NULL,  -- The final property name
    property_type               VARCHAR(32) NOT NULL,  -- The property type
    property_value              TEXT,                  -- The effective property value at snapshot time
    value_type                  VARCHAR(32),           -- Optional: Store the type (string, int, bool...) for easier parsing later
    source_level                VARCHAR(32),           -- e.g., 'instance', 'product_version', 'environment', 'default'
    PRIMARY KEY(snapshot_property_id),
    FOREIGN KEY(snapshot_id) REFERENCES config_snapshot_t(snapshot_id) ON DELETE CASCADE
);

-- Unique constraint to ensure one value per key within a snapshot
ALTER TABLE config_snapshot_property_t
    ADD CONSTRAINT config_snapshot_property_uk UNIQUE (snapshot_id, config_id, property_id);

-- Index for quickly retrieving all properties for a snapshot
CREATE INDEX idx_config_snapshot_property_snapid ON config_snapshot_property_t (snapshot_id);


-- Snapshot of Instance API Overrides
CREATE TABLE snapshot_instance_api_property_t (
    snapshot_id         UUID NOT NULL,
    host_id             UUID NOT NULL,
    instance_api_id     UUID NOT NULL,
    property_id         UUID NOT NULL,
    property_value      TEXT,
    update_user         VARCHAR (255) NOT NULL,
    update_ts           TIMESTAMP WITH TIME ZONE NOT NULL,
    PRIMARY KEY(snapshot_id, host_id, instance_api_id, property_id), -- Composite PK matches original structure + snapshot_id
    FOREIGN KEY(snapshot_id) REFERENCES config_snapshot_t(snapshot_id) ON DELETE CASCADE
);
CREATE INDEX idx_snap_iapi_prop ON snapshot_instance_api_property_t (snapshot_id);


-- Snapshot of Instance App Overrides
CREATE TABLE snapshot_instance_app_property_t (
    snapshot_id         UUID NOT NULL,
    host_id             UUID NOT NULL,
    instance_app_id     UUID NOT NULL,
    property_id         UUID NOT NULL,
    property_value      TEXT,
    update_user         VARCHAR (255) NOT NULL,
    update_ts           TIMESTAMP WITH TIME ZONE NOT NULL,
    PRIMARY KEY(snapshot_id, host_id, instance_app_id, property_id),
    FOREIGN KEY(snapshot_id) REFERENCES config_snapshot_t(snapshot_id) ON DELETE CASCADE
);
CREATE INDEX idx_snap_iapp_prop ON snapshot_instance_app_property_t (snapshot_id);

-- Snapshot of Instance App API Overrides
CREATE TABLE snapshot_instance_app_api_property_t (
    snapshot_id         UUID NOT NULL,
    host_id             UUID NOT NULL,
    instance_app_id     UUID NOT NULL,
    instance_api_id     UUID NOT NULL,
    property_id         UUID NOT NULL,
    property_value      TEXT,
    update_user         VARCHAR (255) NOT NULL,
    update_ts           TIMESTAMP WITH TIME ZONE NOT NULL,
    PRIMARY KEY(snapshot_id, host_id, instance_app_id, instance_api_id, property_id),
    FOREIGN KEY(snapshot_id) REFERENCES config_snapshot_t(snapshot_id) ON DELETE CASCADE
);
CREATE INDEX idx_snap_iaappi_prop ON snapshot_instance_app_api_property_t (snapshot_id);


-- Snapshot of Instance Overrides
CREATE TABLE snapshot_instance_property_t (
    snapshot_id         UUID NOT NULL,
    host_id             UUID NOT NULL,
    instance_id         UUID NOT NULL,
    property_id         UUID NOT NULL,
    property_value      TEXT,
    update_user         VARCHAR (255) NOT NULL,
    update_ts           TIMESTAMP WITH TIME ZONE NOT NULL,
    PRIMARY KEY(snapshot_id, host_id, instance_id, property_id),
    FOREIGN KEY(snapshot_id) REFERENCES config_snapshot_t(snapshot_id) ON DELETE CASCADE
);
CREATE INDEX idx_snap_inst_prop ON snapshot_instance_property_t (snapshot_id);


-- Snapshot of Environment Overrides (If needed for rollback)
CREATE TABLE snapshot_environment_property_t (
    snapshot_id         UUID NOT NULL,
    host_id             UUID NOT NULL,
    environment         VARCHAR(16) NOT NULL,
    property_id         UUID NOT NULL,
    property_value      TEXT,
    update_user         VARCHAR (255) NOT NULL,
    update_ts           TIMESTAMP WITH TIME ZONE NOT NULL,
    PRIMARY KEY(snapshot_id, host_id, environment, property_id),
    FOREIGN KEY(snapshot_id) REFERENCES config_snapshot_t(snapshot_id) ON DELETE CASCADE
);
CREATE INDEX idx_snap_env_prop ON snapshot_environment_property_t (snapshot_id);

CREATE TABLE snapshot_product_property_t (
    snapshot_id         UUID NOT NULL,
    product_id          VARCHAR(8) NOT NULL,
    property_id         UUID NOT NULL,
    property_value      TEXT,
    update_user         VARCHAR (255) NOT NULL,
    update_ts           TIMESTAMP WITH TIME ZONE NOT NULL,
    PRIMARY KEY(snapshot_id, product_id, property_id),
    FOREIGN KEY(snapshot_id) REFERENCES config_snapshot_t(snapshot_id) ON DELETE CASCADE
);
CREATE INDEX idx_snap_prd_prop ON snapshot_product_property_t (snapshot_id);

CREATE TABLE snapshot_product_version_property_t (
    snapshot_id         UUID NOT NULL,
    host_id             UUID NOT NULL,
    product_version_id  UUID NOT NULL,
    property_id         UUID NOT NULL,
    property_value      TEXT,
    update_user         VARCHAR (255) NOT NULL,
    update_ts           TIMESTAMP WITH TIME ZONE NOT NULL,
    PRIMARY KEY(snapshot_id, host_id, product_version_id, property_id),
    FOREIGN KEY(snapshot_id) REFERENCES config_snapshot_t(snapshot_id) ON DELETE CASCADE
);
CREATE INDEX idx_snap_pv_prop ON snapshot_product_version_property_t (snapshot_id);

```


### How to generate rollback events

There are two options to generate rollback events or compensate events. 

Option 1. With historical events. 

1.  **Identify Target State:** You have a `snapshot_id` representing the desired historical state.
2.  **Find Snapshot Timestamp:** Get the `snapshot_ts` from `config_snapshot_t` for the target `snapshot_id`.
3.  **Query Events:** Find all configuration events in your event store that:
    *   Occurred *after* the `snapshot_ts`.
    *   Relate to the specific scope (host, instance, environment, etc.) being rolled back.
4.  **Generate Compensating Events:** For each event found in step 3, create its logical inverse (a "compensating event"). For example:
    *   `InstancePropertyUpdated { propertyId: X, newValue: B, oldValue: A }` -> `InstancePropertyUpdated { propertyId: X, newValue: A, oldValue: B }` (Requires storing `oldValue` in the original event).
    *   `InstancePropertyCreated { propertyId: X, value: A }` -> `InstancePropertyDeleted { propertyId: X, value: A }` (Requires storing the value in the delete event for potential future rollback).
    *   `InstancePropertyDeleted { propertyId: X, value: A }` -> `InstancePropertyCreated { propertyId: X, value: A }` (Requires storing the value in the delete event).
5.  **Order Compensating Events:** Sort the generated compensating events in the **reverse chronological order** of the original events they are compensating for.
6.  **Replay Compensating Events:** Apply these ordered compensating events through your event handling system.


Conceptually, this is a valid approach often used in event sourcing patterns (related to compensating transactions). However, it comes with significant challenges and complexities:

**Challenges & Considerations:**

1.  **Generating Perfect Inverse Events:** This is the hardest part.
    *   **Requires Rich Events:** Your original events *must* contain enough information to construct their inverse. For updates, you need the `oldValue`. For creations, the delete needs the key. For deletions, the create needs the deleted value. If your current events don't store this, you cannot reliably generate compensating events this way.
    *   **Complexity:** For multi-step or complex operations, determining the exact inverse sequence can be non-trivial.
2.  **Order of Operations:** Compensating events MUST be applied in strict reverse order. Getting this wrong can lead to incorrect states.
3.  **State Dependencies:** Event handlers sometimes make assumptions about the state *before* the event is applied. Replaying compensating events might encounter unexpected states if other unrelated changes have occurred or if the reverse logic isn't perfect, potentially causing handler errors.
4.  **Performance:** Querying potentially thousands of events, generating inverses, and replaying them might be slow, especially if the time gap between the snapshot and the present is large.
5.  **Snapshot Data Not Used:** This approach doesn't directly leverage the *known good state* stored in `config_snapshot_property_t`. It relies solely on the ability to perfectly reverse subsequent events.
6.  **Idempotency:** Compensating event handlers should ideally be idempotent (applying them multiple times has the same effect as applying them once), although this is hard to guarantee for inverse operations.


Option 2: Diff-based event generation.

1.  **Get Target State:** Fetch key-values from `config_snapshot_property_t` for `snapshot_id`. (`TargetState`)
2.  **Get Current State:** Run aggregation query for the current configuration. (`CurrentState`)
3.  **Calculate Diff:** Find differences between `TargetState` and `CurrentState`.
4.  **Generate Corrective Events:** Create events to *transform* `CurrentState` *into* `TargetState`.
    *   If `key` is in `TargetState` but different/missing in `CurrentState` -> Generate `Upsert[Level]Property` event with the value from `TargetState` (applied at the highest relevant override level for the scope).
    *   If `key` is in `CurrentState` but missing in `TargetState` -> Generate `Delete[Level]Property` event for the override that's currently providing the value (likely the highest relevant override level).
5.  **Apply Events:** Apply these *corrective* events.

**Why the Diff-Based Approach is Often Preferred for Snapshot Rollback:**

*   **Uses Known Good State:** It directly uses the guaranteed state from the snapshot table.
*   **Less Reliant on Event Reversibility:** It doesn't matter if the original events are perfectly reversible or store old values. It focuses on achieving the target state from the current state.
*   **Potentially Fewer Events:** Might generate fewer events than reversing a long history, focusing only on the net changes needed.
*   **More Direct:** The generated events directly aim to establish the target state, which can feel less fragile than relying on reversing history.

**Conclusion:**

While method of reversing events since the snapshot *is* a recognized event sourcing pattern, it's often **more complex and potentially fragile** for the specific task of rolling back to a *known snapshot state* compared to the **diff-based corrective event generation method**.

The diff-based method leverages the snapshot data directly and focuses on achieving the target state, making it generally more robust and often easier to implement correctly, as it doesn't require perfectly reversible events.


### How to create the snapshot


Let's clarify how the `scope_*` columns in `config_snapshot_t` relate to the query that generates the snapshot and the override tables (`*_property_t`).

**The Purpose of `scope_*` Columns:**

The `scope_*` columns in `config_snapshot_t` serve one primary purpose: **To record the specific context for which the snapshot was generated.** They define *what* set of effective configuration values are stored in the associated `config_snapshot_property_t` rows.

Think of them as the **input parameters** that were used to run the aggregation query when the snapshot was created.

**How They Are Used in the Snapshot Generation Query:**

You **do not** need one `scope_*` column for every `*_property_t` table. Instead, the values you store in the `scope_*` columns are the **parameters** you pass into your aggregation query's `WHERE` clauses to filter the rows from the relevant override tables according to the desired context.

Let's refine the query strategy using the `scope_*` concept and aim for a more efficient query than repeated `NOT EXISTS` clauses (using `ROW_NUMBER()` or `DISTINCT ON`).

**Example Scenario: Snapshotting for a specific Instance**

Let's say you want to create a snapshot for a specific `instance_id` on a specific `host_id`.

1.  **Input Parameters:**
    *   `p_host_id` (UUID)
    *   `p_instance_id` (UUID)

2.  **Derive Related IDs (Inside your snapshot creation logic/service):**
    *   You'll need to query `instance_t` to get the associated `product_version_id`, `environment`, etc., for this instance.
    *   Query `product_version_t` to get `product_id`.
    *   Let's call these derived values `v_product_version_id`, `v_environment`, `v_product_id`.

3.  **`config_snapshot_t` Record:**
    *   Generate a `snapshot_id` (e.g., UUIDv7).
    *   `snapshot_ts`: `CURRENT_TIMESTAMP`
    *   `snapshot_type`: e.g., 'DEPLOYMENT'
    *   `scope_host_id`: `p_host_id`
    *   `scope_instance_id`: `p_instance_id`
    *   `scope_environment`: `v_environment` (Store the derived environment for clarity, even though it came from the instance)
    *   `scope_product_version_id`: `v_product_version_id` (Store for clarity)
    *   `scope_product_id`: `v_product_id` (Store for clarity)
    *   *(Other `scope_*` columns like `scope_instance_api_id` would be NULL for this instance-level snapshot)*

4.  **Aggregation Query (Using `ROW_NUMBER()`):**
    This query uses the *input parameters* (`p_host_id`, `p_instance_id`) and the *derived values* (`v_product_version_id`, `v_environment`, `v_product_id`) to find the highest priority value for each `property_id`.

    ```sql
WITH
-- Parameters derived *before* running this query:
-- p_host_id UUID
-- p_instance_id UUID
-- v_product_version_id UUID (derived from p_instance_id)
-- v_environment VARCHAR(16) (derived from p_instance_id)
-- v_product_id VARCHAR(8) (derived from v_product_version_id)

-- Find relevant instance_api_ids and instance_app_ids for the target instance
RelevantInstanceApis AS (
    SELECT instance_api_id
    FROM instance_api_t
    WHERE host_id = ? -- p_host_id
      AND instance_id = ? -- p_instance_id
),
RelevantInstanceApps AS (
    SELECT instance_app_id
    FROM instance_app_t
    WHERE host_id = ? -- p_host_id
      AND instance_id = ? -- p_instance_id
),

-- Pre-process Instance App API properties with merging logic
Merged_Instance_App_Api_Properties AS (
    SELECT
        iaap.property_id,
        CASE cp.value_type
            WHEN 'map' THEN COALESCE(jsonb_merge_agg(iaap.property_value::jsonb), '{}'::jsonb)::text
            WHEN 'list' THEN COALESCE((SELECT jsonb_agg(elem ORDER BY iaa.update_ts) -- Order elements based on when they were added via the link table? Or property update_ts? Assuming property update_ts. Check data model if linking time matters more.
                                        FROM jsonb_array_elements(sub.property_value::jsonb) elem
                                        WHERE jsonb_typeof(sub.property_value::jsonb) = 'array'
                                      ), '[]'::jsonb)::text -- Requires subquery if ordering elements
             -- Subquery approach for ordering list elements by property timestamp:
             /*
              COALESCE(
                 (SELECT jsonb_agg(elem ORDER BY prop.update_ts)
                  FROM instance_app_api_property_t prop,
                       jsonb_array_elements(prop.property_value::jsonb) elem
                  WHERE prop.host_id = iaap.host_id
                    AND prop.instance_app_id = iaap.instance_app_id
                    AND prop.instance_api_id = iaap.instance_api_id
                    AND prop.property_id = iaap.property_id
                    AND jsonb_typeof(prop.property_value::jsonb) = 'array'
                 ), '[]'::jsonb
              )::text
             */
            ELSE MAX(iaap.property_value) -- For simple types, MAX can work if only one entry expected, otherwise need timestamp logic
            -- More robust for simple types: Pick latest based on timestamp
            /*
             (SELECT property_value
              FROM instance_app_api_property_t latest
              WHERE latest.host_id = iaap.host_id
                AND latest.instance_app_id = iaap.instance_app_id
                AND latest.instance_api_id = iaap.instance_api_id
                AND latest.property_id = iaap.property_id
              ORDER BY latest.update_ts DESC LIMIT 1)
            */
        END AS effective_value
    FROM instance_app_api_property_t iaap
    JOIN config_property_t cp ON iaap.property_id = cp.property_id
    JOIN instance_app_api_t iaa ON iaa.host_id = iaap.host_id AND iaa.instance_app_id = iaap.instance_app_id AND iaa.instance_api_id = iaap.instance_api_id -- Join to potentially use its timestamp for ordering lists
    WHERE iaap.host_id = ? -- p_host_id
      AND iaap.instance_app_id IN (SELECT instance_app_id FROM RelevantInstanceApps)
      AND iaap.instance_api_id IN (SELECT instance_api_id FROM RelevantInstanceApis)
    GROUP BY iaap.host_id, iaap.instance_app_id, iaap.instance_api_id, iaap.property_id, cp.value_type -- Group to aggregate/merge
),

-- Pre-process Instance API properties
Merged_Instance_Api_Properties AS (
    SELECT
        iap.property_id,
        CASE cp.value_type
            WHEN 'map' THEN COALESCE(jsonb_merge_agg(iap.property_value::jsonb), '{}'::jsonb)::text
            WHEN 'list' THEN COALESCE((SELECT jsonb_agg(elem ORDER BY prop.update_ts) FROM instance_api_property_t prop, jsonb_array_elements(prop.property_value::jsonb) elem WHERE prop.host_id = iap.host_id AND prop.instance_api_id = iap.instance_api_id AND prop.property_id = iap.property_id AND jsonb_typeof(prop.property_value::jsonb) = 'array'), '[]'::jsonb)::text
            ELSE (SELECT property_value FROM instance_api_property_t latest WHERE latest.host_id = iap.host_id AND latest.instance_api_id = iap.instance_api_id AND latest.property_id = iap.property_id ORDER BY latest.update_ts DESC LIMIT 1)
        END AS effective_value
    FROM instance_api_property_t iap
    JOIN config_property_t cp ON iap.property_id = cp.property_id
    WHERE iap.host_id = ? -- p_host_id
      AND iap.instance_api_id IN (SELECT instance_api_id FROM RelevantInstanceApis)
    GROUP BY iap.host_id, iap.instance_api_id, iap.property_id, cp.value_type
),

-- Pre-process Instance App properties
Merged_Instance_App_Properties AS (
     SELECT
        iapp.property_id,
        CASE cp.value_type
            WHEN 'map' THEN COALESCE(jsonb_merge_agg(iapp.property_value::jsonb), '{}'::jsonb)::text
            WHEN 'list' THEN COALESCE((SELECT jsonb_agg(elem ORDER BY prop.update_ts) FROM instance_app_property_t prop, jsonb_array_elements(prop.property_value::jsonb) elem WHERE prop.host_id = iapp.host_id AND prop.instance_app_id = iapp.instance_app_id AND prop.property_id = iapp.property_id AND jsonb_typeof(prop.property_value::jsonb) = 'array'), '[]'::jsonb)::text
            ELSE (SELECT property_value FROM instance_app_property_t latest WHERE latest.host_id = iapp.host_id AND latest.instance_app_id = iapp.instance_app_id AND latest.property_id = iapp.property_id ORDER BY latest.update_ts DESC LIMIT 1)
        END AS effective_value
    FROM instance_app_property_t iapp
    JOIN config_property_t cp ON iapp.property_id = cp.property_id
    WHERE iapp.host_id = ? -- p_host_id
      AND iapp.instance_app_id IN (SELECT instance_app_id FROM RelevantInstanceApps)
    GROUP BY iapp.host_id, iapp.instance_app_id, iapp.property_id, cp.value_type
),

-- Combine all levels with priority
AllOverrides AS (
    -- Priority 10: Instance App API (highest) - Requires aggregating the merged results if multiple app/api combos apply to the instance
    SELECT
        m_iaap.property_id,
        -- Need final merge/latest logic here if multiple app/api combos apply to the SAME instance_id and define the SAME property_id
        -- Assuming for now we take the first one found or need more complex logic if merge is needed *again* at this stage
        -- For simplicity, let's assume we just take MAX effective value if multiple rows exist per property_id for the instance
        MAX(m_iaap.effective_value) as property_value, -- This MAX might not be right for JSON, need specific logic if merging across app/api combos is needed here
        10 AS priority_level
    FROM Merged_Instance_App_Api_Properties m_iaap
    -- No additional instance filter needed if CTEs were already filtered by RelevantInstanceApps/Apis linked to p_instance_id
    GROUP BY m_iaap.property_id -- Group to handle multiple app/api links potentially setting the same property for the instance

    UNION ALL

    -- Priority 20: Instance API
    SELECT
        m_iap.property_id,
        MAX(m_iap.effective_value) as property_value, -- Similar merge concern as above
        20 AS priority_level
    FROM Merged_Instance_Api_Properties m_iap
    GROUP BY m_iap.property_id

    UNION ALL

    -- Priority 30: Instance App
    SELECT
        m_iapp.property_id,
        MAX(m_iapp.effective_value) as property_value, -- Similar merge concern
        30 AS priority_level
    FROM Merged_Instance_App_Properties m_iapp
    GROUP BY m_iapp.property_id

    UNION ALL

    -- Priority 40: Instance
    SELECT
        ip.property_id,
        ip.property_value,
        40 AS priority_level
    FROM instance_property_t ip
    WHERE ip.host_id = ? -- p_host_id
      AND ip.instance_id = ? -- p_instance_id

    UNION ALL

    -- Priority 50: Product Version
    SELECT
        pvp.property_id,
        pvp.property_value,
        50 AS priority_level
    FROM product_version_property_t pvp
    WHERE pvp.host_id = ? -- p_host_id
      AND pvp.product_version_id = ? -- v_product_version_id

    UNION ALL

    -- Priority 60: Environment
    SELECT
        ep.property_id,
        ep.property_value,
        60 AS priority_level
    FROM environment_property_t ep
    WHERE ep.host_id = ? -- p_host_id
      AND ep.environment = ? -- v_environment

    UNION ALL

    -- Priority 70: Product (Host independent)
    SELECT
        pp.property_id,
        pp.property_value,
        70 AS priority_level
    FROM product_property_t pp
    WHERE pp.product_id = ? -- v_product_id

    UNION ALL

    -- Priority 100: Default values
    SELECT
        cp.property_id,
        cp.property_value, -- Default value
        100 AS priority_level
    FROM config_property_t cp
    -- Optimization: Filter defaults to only those applicable to the product version?
    -- JOIN product_version_config_property_t pvcp ON cp.property_id = pvcp.property_id
    -- WHERE pvcp.host_id = ? AND pvcp.product_version_id = ?
),
RankedOverrides AS (
    SELECT
        ao.property_id,
        ao.property_value,
        ao.priority_level,
        ROW_NUMBER() OVER (PARTITION BY ao.property_id ORDER BY ao.priority_level ASC) as rn
    FROM AllOverrides ao
    WHERE ao.property_value IS NOT NULL -- Exclude levels where the value was NULL (unless NULL is a valid override)
)
-- Final Selection for Snapshot Table
SELECT
    -- snapshot_id needs to be added here or during INSERT
    cfg.config_name || '.' || cp.property_name AS property_key,
    ro.property_value,
    cp.property_type,
    cp.value_type
    -- Include ro.priority_level AS source_priority if storing provenance
FROM RankedOverrides ro
JOIN config_property_t cp ON ro.property_id = cp.property_id
JOIN config_t cfg ON cp.config_id = cfg.config_id
WHERE ro.rn = 1;

```

5.  **Populate `config_snapshot_property_t`:** Insert the results of this query into `config_snapshot_property_t`, using the `snapshot_id` generated in step 3.

**Key Takeaways:**

*   The `scope_*` columns define the *context* of the snapshot.
*   The values for these `scope_*` columns are used as *parameters* within the `WHERE` clauses of the aggregation query that *generates* the snapshot data.
*   You don't need a `scope_*` column per override table. You need columns representing the different *dimensions* or *levels* by which you might want to define a snapshot's context (host, instance, environment, product version, etc.).
*   The aggregation query uses these parameters to filter the relevant rows from each override table and then determines the highest priority value using `UNION ALL` and a ranking mechanism (`ROW_NUMBER()` or `DISTINCT ON`).

This approach keeps the `config_snapshot_t` table focused on metadata and context, while the query handles the complex logic of applying that context to the various override tables to produce the effective configuration for `config_snapshot_property_t`.

### Config Phase

In the config_t table, there is a config_phase column to separate different stages of api/app life cycles. For example, config for codegen, config for runtime, config for deployment. 

Given your two main use cases:

1.  **Service Startup:** Needs the *runtime* (`'R'`) configuration.
2.  **Deployment Rollback:** Needs to potentially restore the state required for *deployment* (`'D'`) and the resulting *runtime* (`'R'`) configuration from that point in time. (Generator `'G'` configs are usually less relevant for deployment/runtime rollbacks).

Here are the options and the recommended approach:

**Option 1: Phase-Specific Snapshots (Separate Records)**

*   **How:** Add `scope_config_phase CHAR(1)` to `config_snapshot_t`.
*   **Snapshot Creation:** When a snapshot event occurs (e.g., pre-deployment):
    *   Generate a `snapshot_id_D` (e.g., using UUIDv7).
    *   Run the aggregation query with `config_phase = 'D'`.
    *   Store results in `config_snapshot_property_t` linked to `snapshot_id_D`.
    *   Create metadata in `config_snapshot_t` for `snapshot_id_D` with `scope_config_phase = 'D'`.
    *   Generate *another* `snapshot_id_R`.
    *   Run the aggregation query with `config_phase = 'R'`.
    *   Store results in `config_snapshot_property_t` linked to `snapshot_id_R`.
    *   Create metadata in `config_snapshot_t` for `snapshot_id_R` with `scope_config_phase = 'R'`.
    *   You'd need a way to link `snapshot_id_D` and `snapshot_id_R` to the same logical event (e.g., same `related_deployment_id`).
*   **Pros:** Very explicit separation. Querying for a specific phase's snapshot is straightforward.
*   **Cons:** Requires multiple runs of the aggregation query. Doubles the metadata rows in `config_snapshot_t`. Complicates linking phases related to the same event. Less efficient.

**Option 2: Single Snapshot, Phase Included in Properties (Recommended)**

*   **How:** Do **not** add `scope_config_phase` to `config_snapshot_t`. Instead, add `config_phase CHAR(1)` to `config_snapshot_property_t`.
*   **Snapshot Creation:**
    *   Generate a single `snapshot_id`.
    *   Create one metadata row in `config_snapshot_t` representing the overall scope and time (without phase).
    *   **Modify the Aggregation Query:**
        *   **Remove** the `WHERE c.config_phase = ?` filter entirely.
        *   **SELECT** the `c.config_phase` value in the final `SELECT` statement.
    *   Run this modified query *once*. It will calculate the effective properties across *all* phases applicable to the scope.
    *   Store the results in `config_snapshot_property_t`, populating the new `config_phase` column for each property based on the phase of the `config_t` record from which it originated.
*   **`config_snapshot_property_t` Structure:**
    ```sql
    CREATE TABLE config_snapshot_property_t (
        -- ... other columns ...
        config_phase        CHAR(1) NOT NULL, -- Phase this property belongs to
        property_key        TEXT NOT NULL,
        property_value      TEXT,
        property_type       VARCHAR(32),
        value_type          VARCHAR(32),
        -- ...
        PRIMARY KEY(snapshot_property_id), -- Or PK(snapshot_id, config_phase, property_key)? Needs thought.
        FOREIGN KEY(snapshot_id) REFERENCES config_snapshot_t(snapshot_id) ON DELETE CASCADE
    );
    -- Ensure uniqueness within a snapshot for a given key *and phase*
    ALTER TABLE config_snapshot_property_t
        ADD CONSTRAINT config_snapshot_property_uk UNIQUE (snapshot_id, config_phase, property_key);
    -- Index for lookup by snapshot and phase
    CREATE INDEX idx_config_snapshot_property_snap_phase ON config_snapshot_property_t (snapshot_id, config_phase);
    ```
*   **Pros:**### commitConfigInstance

Let's outline the structure of your `commitConfigInstance` service method and the necessary SQL INSERT statements using JDBC.

This involves several steps within a single database transaction:

1.  **Generate Snapshot ID:** Create a new UUID for the snapshot.
2.  **Derive Scope IDs:** Query live tables (`instance_t`, `product_version_t`, etc.) based on the input `hostId` and `instanceId` to get other relevant scope identifiers (`environment`, `productId`, `productVersionId`, `serviceId`, etc.).
3.  **Insert Metadata:** Insert a record into `config_snapshot_t`.
4.  **Aggregate Effective Config:** Run the complex aggregation query (using `ROW_NUMBER()` or similar) to get the final effective properties.
5.  **Insert Effective Config:** Insert the results from step 4 into `config_snapshot_property_t`.
6.  **Snapshot Override Tables:** For each relevant live override table (`instance_property_t`, `instance_api_property_t`, etc.), select its current state (filtered by scope) and insert it into the corresponding `snapshot_*_property_t` table.
7.  **Commit/Rollback:** Commit the transaction if all steps succeed, otherwise roll back.

**Java Service Method Structure (Conceptual)**

```java
import com.github.f4b6a3.uuid.UuidCreator; // For UUIDv7 generation
import javax.sql.DataSource; // Assuming you have a DataSource injected
import java.sql.*;
import java.time.OffsetDateTime;
import java.util.*;

public class ConfigSnapshotService {

    private final DataSource ds;
    // Inject DataSource via constructor

    // Pre-compile your complex aggregation query (modify based on previous examples)
    private static final String AGGREGATE_EFFECTIVE_CONFIG_SQL = """
        WITH AllOverrides AS (
            -- Priority 10: Instance App API (merged) ...
            -- Priority 20: Instance API (merged) ...
            -- Priority 30: Instance App (merged) ...
            -- Priority 40: Instance ...
            -- Priority 50: Product Version ...
            -- Priority 60: Environment ...
            -- Priority 70: Product ...
            -- Priority 100: Default ...
        ),
        RankedOverrides AS (
           SELECT ..., ROW_NUMBER() OVER (PARTITION BY ao.property_id ORDER BY ao.priority_level ASC) as rn
           FROM AllOverrides ao WHERE ao.property_value IS NOT NULL
        )
        SELECT
            c.config_phase,   -- Phase from config_t
            cfg.config_id,    -- Added config_id
            cp.property_id,   -- Added property_id
            cp.property_name, -- Added property_name
            cp.property_type,
            cp.value_type,
            cfg.config_name || '.' || cp.property_name AS property_key, -- Keep for logging/debug? Not needed in snapshot table itself
            ro.property_value,
            ro.priority_level -- To determine source_level
        FROM RankedOverrides ro
        JOIN config_property_t cp ON ro.property_id = cp.property_id
        JOIN config_t cfg ON cp.config_id = cfg.config_id
        WHERE ro.rn = 1;
    """; // NOTE: Add parameters (?) for host_id, instance_id, derived IDs etc.

    public Result<String> commitConfigInstance(Map<String, Object> event) {
        // 1. Extract Input Parameters
        UUID hostId = (UUID) event.get("hostId");
        UUID instanceId = (UUID) event.get("instanceId");
        String snapshotType = (String) event.getOrDefault("snapshotType", "USER_SAVE"); // Default type
        String description = (String) event.get("description");
        UUID userId = (UUID) event.get("userId"); // May be null
        UUID deploymentId = (UUID) event.get("deploymentId"); // May be null

        if (hostId == null || instanceId == null) {
            return Failure.of(new Status(INVALID_PARAMETER, "hostId and instanceId are required."));
        }

        UUID snapshotId = UuidCreator.getTimeOrderedEpoch(); // Generate Snapshot ID (e.g., V7)

        Connection connection = null;
        try {
            connection = ds.getConnection();
            connection.setAutoCommit(false); // Start Transaction

            // 2. Derive Scope IDs
            // Query instance_t and potentially product_version_t based on hostId, instanceId
            DerivedScope scope = deriveScopeInfo(connection, hostId, instanceId);
            if (scope == null) {
                connection.rollback(); // Rollback if instance not found
                return Failure.of(new Status(OBJECT_NOT_FOUND, "Instance not found for hostId/instanceId."));
            }

            // 3. Insert Snapshot Metadata
            insertSnapshotMetadata(connection, snapshotId, snapshotType, description, userId, deploymentId, hostId, scope);

            // 4 & 5. Aggregate and Insert Effective Config
            insertEffectiveConfigSnapshot(connection, snapshotId, hostId, instanceId, scope);

            // 6. Snapshot Individual Override Tables
            // Use INSERT ... SELECT ... for efficiency
            snapshotInstanceProperties(connection, snapshotId, hostId, instanceId);
            snapshotInstanceApiProperties(connection, snapshotId, hostId, instanceId);
            snapshotInstanceAppProperties(connection, snapshotId, hostId, instanceId);
            snapshotInstanceAppApiProperties(connection, snapshotId, hostId, instanceId); // Requires finding relevant App/API IDs first
            snapshotEnvironmentProperties(connection, snapshotId, hostId, scope.environment());
            snapshotProductVersionProperties(connection, snapshotId, hostId, scope.productVersionId());
            snapshotProductProperties(connection, snapshotId, scope.productId());
            // Add others as needed

            // 7. Commit Transaction
            connection.commit();
            logger.info("Successfully created config snapshot: {}", snapshotId);
            return Success.of(snapshotId.toString());

        } catch (SQLException e) {
            logger.error("SQLException during snapshot creation for instance {}: {}", instanceId, e.getMessage(), e);
            if (connection != null) {
                try {
                    connection.rollback();
                } catch (SQLException ex) {
                    logger.error("Error rolling back transaction:", ex);
                }
            }
            return Failure.of(new Status(SQL_EXCEPTION, "Database error during snapshot creation."));
        } catch (Exception e) { // Catch other potential errors (e.g., during scope derivation)
             logger.error("Exception during snapshot creation for instance {}: {}", instanceId, e.getMessage(), e);
             if (connection != null) {
                 try { connection.rollback(); } catch (SQLException ex) { logger.error("Error rolling back transaction:", ex); }
             }
            return Failure.of(new Status(GENERIC_EXCEPTION, "Unexpected error during snapshot creation."));
        } finally {
            if (connection != null) {
                try {
                    connection.setAutoCommit(true); // Restore default behavior
                    connection.close();
                } catch (SQLException e) {
                    logger.error("Error closing connection:", e);
                }
            }
        }
    }

    // --- Helper Methods ---

    // Placeholder for derived scope data structure
    private record DerivedScope(String environment, String productId, String productVersion, UUID productVersionId, String serviceId /*, add API details if needed */) {}

    private DerivedScope deriveScopeInfo(Connection conn, UUID hostId, UUID instanceId) throws SQLException {
        // Query instance_t LEFT JOIN product_version_t ... WHERE i.host_id = ? AND i.instance_id = ?
        // Extract environment, service_id from instance_t
        // Extract product_id, product_version from product_version_t (via product_version_id in instance_t)
        // Return new DerivedScope(...) or null if not found
        String sql = """
            SELECT i.environment, i.service_id, pv.product_id, pv.product_version, i.product_version_id
            FROM instance_t i
            LEFT JOIN product_version_t pv ON i.host_id = pv.host_id AND i.product_version_id = pv.product_version_id
            WHERE i.host_id = ? AND i.instance_id = ?
        """;
        try (PreparedStatement ps = conn.prepareStatement(sql)) {
            ps.setObject(1, hostId);
            ps.setObject(2, instanceId);
            try (ResultSet rs = ps.executeQuery()) {
                if (rs.next()) {
                    return new DerivedScope(
                        rs.getString("environment"),
                        rs.getString("product_id"),
                        rs.getString("product_version"),
                        rs.getObject("product_version_id", UUID.class),
                        rs.getString("service_id")
                    );
                } else {
                    return null; // Instance not found
                }
            }
        }
    }

    private void insertSnapshotMetadata(Connection conn, UUID snapshotId, String snapshotType, String description,
                                        UUID userId, UUID deploymentId, UUID hostId, DerivedScope scope) throws SQLException {
        String sql = """
            INSERT INTO config_snapshot_t
            (snapshot_id, snapshot_ts, snapshot_type, description, user_id, deployment_id,
             scope_host_id, scope_environment, scope_product_id, scope_product_version_id, -- Changed col name
             scope_service_id /*, scope_api_id, scope_api_version - Add if applicable */)
            VALUES (?, CURRENT_TIMESTAMP, ?, ?, ?, ?, ?, ?, ?, ?, ? /*, ?, ? */)
            """;
        try (PreparedStatement ps = conn.prepareStatement(sql)) {
            ps.setObject(1, snapshotId);
            ps.setString(2, snapshotType);
            ps.setString(3, description);
            ps.setObject(4, userId);         // setObject handles null correctly
            ps.setObject(5, deploymentId);   // setObject handles null correctly
            ps.setObject(6, hostId);
            ps.setString(7, scope.environment());
            ps.setString(8, scope.productId());
            ps.setObject(9, scope.productVersionId()); // Store the ID
            ps.setString(10, scope.serviceId());
            // Set API scope if needed ps.setObject(11, ...); ps.setString(12, ...);
            ps.executeUpdate();
        }
    }


    private void insertEffectiveConfigSnapshot(Connection conn, UUID snapshotId, UUID hostId, UUID instanceId, DerivedScope scope) throws SQLException {
         String insertSql = """
            INSERT INTO config_snapshot_property_t
            (snapshot_property_id, snapshot_id, config_phase, config_id, property_id, property_name,
             property_type, property_value, value_type, source_level)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """;
        // Prepare the aggregation query
        try (PreparedStatement selectStmt = conn.prepareStatement(AGGREGATE_EFFECTIVE_CONFIG_SQL);
             PreparedStatement insertStmt = conn.prepareStatement(insertSql)) {

             // Set ALL parameters for the AGGREGATE_EFFECTIVE_CONFIG_SQL query
             int paramIndex = 1;
             // Example: set parameters based on how AGGREGATE_EFFECTIVE_CONFIG_SQL is structured
             // selectStmt.setObject(paramIndex++, hostId);
             // selectStmt.setObject(paramIndex++, instanceId);
             // ... set derived scope IDs (productVersionId, environment, productId) ...
             // ... set parameters for all UNION branches and potential subqueries ...

             try (ResultSet rs = selectStmt.executeQuery()) {
                int batchCount = 0;
                while (rs.next()) {
                    insertStmt.setObject(1, UuidCreator.getTimeOrderedEpoch()); // snapshot_property_id
                    insertStmt.setObject(2, snapshotId);
                    insertStmt.setString(3, rs.getString("config_phase"));
                    insertStmt.setObject(4, rs.getObject("config_id", UUID.class));
                    insertStmt.setObject(5, rs.getObject("property_id", UUID.class));
                    insertStmt.setString(6, rs.getString("property_name"));
                    insertStmt.setString(7, rs.getString("property_type"));
                    insertStmt.setString(8, rs.getString("property_value"));
                    insertStmt.setString(9, rs.getString("value_type"));
                    insertStmt.setString(10, mapPriorityToSourceLevel(rs.getInt("priority_level"))); // Map numeric priority back to level name

                    insertStmt.addBatch();
                    batchCount++;

                    if (batchCount % 100 == 0) { // Execute batch periodically
                        insertStmt.executeBatch();
                    }
                }
                 if (batchCount % 100 != 0) { // Execute remaining batch
                     insertStmt.executeBatch();
                 }
             }
         }
    }

    // Helper to map priority back to source level name
    private String mapPriorityToSourceLevel(int priority) {
        return switch (priority) {
            case 10 -> "instance_app_api"; // Adjust priorities as used in your query
            case 20 -> "instance_api";
            case 30 -> "instance_app";
            case 40 -> "instance";
            case 50 -> "product_version";
            case 60 -> "environment";
            case 70 -> "product";
            case 100 -> "default";
            default -> "unknown";
        };
    }


    // --- Methods for Snapshotting Individual Override Tables ---

    private void snapshotInstanceProperties(Connection conn, UUID snapshotId, UUID hostId, UUID instanceId) throws SQLException {
        String sql = """
            INSERT INTO snapshot_instance_property_t
            (snapshot_id, host_id, instance_id, property_id, property_value, update_user, update_ts)
            SELECT ?, host_id, instance_id, property_id, property_value, update_user, update_ts
            FROM instance_property_t
            WHERE host_id = ? AND instance_id = ?
            """;
        try (PreparedStatement ps = conn.prepareStatement(sql)) {
            ps.setObject(1, snapshotId);
            ps.setObject(2, hostId);
            ps.setObject(3, instanceId);
            ps.executeUpdate();
        }
    }

    private void snapshotInstanceApiProperties(Connection conn, UUID snapshotId, UUID hostId, UUID instanceId) throws SQLException {
         // Find relevant instance_api_ids first
        List<UUID> apiIds = findRelevantInstanceApiIds(conn, hostId, instanceId);
        if (apiIds.isEmpty()) return; // No API overrides for this instance

        String sql = """
            INSERT INTO snapshot_instance_api_property_t
            (snapshot_id, host_id, instance_api_id, property_id, property_value, update_user, update_ts)
            SELECT ?, host_id, instance_api_id, property_id, property_value, update_user, update_ts
            FROM instance_api_property_t
            WHERE host_id = ? AND instance_api_id = ANY(?) -- Use ANY with array for multiple IDs
            """;
        try (PreparedStatement ps = conn.prepareStatement(sql)) {
            ps.setObject(1, snapshotId);
            ps.setObject(2, hostId);
            // Create a SQL Array from the List of UUIDs
            Array sqlArray = conn.createArrayOf("UUID", apiIds.toArray());
            ps.setArray(3, sqlArray);
            ps.executeUpdate();
            sqlArray.free(); // Release array resources
        }
    }

    // Similar methods for snapshotInstanceAppProperties, snapshotInstanceAppApiProperties...
    // These will need helper methods like findRelevantInstanceApiIds/findRelevantInstanceAppIds

    private void snapshotEnvironmentProperties(Connection conn, UUID snapshotId, UUID hostId, String environment) throws SQLException {
        if (environment == null || environment.isEmpty()) return; // No environment scope
        String sql = """
             INSERT INTO snapshot_environment_property_t
             (snapshot_id, host_id, environment, property_id, property_value, update_user, update_ts)
             SELECT ?, host_id, environment, property_id, property_value, update_user, update_ts
             FROM environment_property_t
             WHERE host_id = ? AND environment = ?
             """;
         try (PreparedStatement ps = conn.prepareStatement(sql)) {
             ps.setObject(1, snapshotId);
             ps.setObject(2, hostId);
             ps.setString(3, environment);
             ps.executeUpdate();
         }
    }

     private void snapshotProductVersionProperties(Connection conn, UUID snapshotId, UUID hostId, UUID productVersionId) throws SQLException {
         if (productVersionId == null) return;
         String sql = """
              INSERT INTO snapshot_product_version_property_t
              (snapshot_id, host_id, product_version_id, property_id, property_value, update_user, update_ts)
              SELECT ?, host_id, product_version_id, property_id, property_value, update_user, update_ts
              FROM product_version_property_t
              WHERE host_id = ? AND product_version_id = ?
              """;
          try (PreparedStatement ps = conn.prepareStatement(sql)) {
              ps.setObject(1, snapshotId);
              ps.setObject(2, hostId);
              ps.setObject(3, productVersionId);
              ps.executeUpdate();
          }
     }

     private void snapshotProductProperties(Connection conn, UUID snapshotId, String productId) throws SQLException {
         if (productId == null || productId.isEmpty()) return;
         String sql = """
               INSERT INTO snapshot_product_property_t
               (snapshot_id, product_id, property_id, property_value, update_user, update_ts)
               SELECT ?, product_id, property_id, property_value, update_user, update_ts
               FROM product_property_t
               WHERE product_id = ?
               """;
           try (PreparedStatement ps = conn.prepareStatement(sql)) {
               ps.setObject(1, snapshotId);
               ps.setString(2, productId);
               ps.executeUpdate();
           }
     }

    // --- Helper method to find associated instance_api_ids ---
    private List<UUID> findRelevantInstanceApiIds(Connection conn, UUID hostId, UUID instanceId) throws SQLException {
        List<UUID> ids = new ArrayList<>();
        String sql = "SELECT instance_api_id FROM instance_api_t WHERE host_id = ? AND instance_id = ?";
        try (PreparedStatement ps = conn.prepareStatement(sql)) {
            ps.setObject(1, hostId);
            ps.setObject(2, instanceId);
            try (ResultSet rs = ps.executeQuery()) {
                while(rs.next()) {
                    ids.add(rs.getObject("instance_api_id", UUID.class));
                }
            }
        }
        return ids;
    }
     // --- Add similar helper for findRelevantInstanceAppIds ---
     // --- Add similar helper for findRelevantInstanceAppApiIds (if needed) ---

}
```

**SQL INSERT Statements:**

1.  **`config_snapshot_t`:**
    ```sql
    INSERT INTO config_snapshot_t
    (snapshot_id, snapshot_ts, snapshot_type, description, user_id, deployment_id,
     scope_host_id, scope_environment, scope_product_id, scope_product_version_id, scope_service_id /*, ... other scope cols */)
    VALUES (?, CURRENT_TIMESTAMP, ?, ?, ?, ?, ?, ?, ?, ?, ? /*, ... */)
    ```
    *(Parameters: snapshotId, snapshotType, description, userId, deploymentId, hostId, environment, productId, productVersionId, serviceId, ...)*

2.  **`config_snapshot_property_t`:** (Executed in a loop/batch)
    ```sql
    INSERT INTO config_snapshot_property_t
    (snapshot_property_id, snapshot_id, config_phase, config_id, property_id, property_name,
     property_type, property_value, value_type, source_level)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ```
    *(Parameters: new UUID, snapshotId, phase, configId, propertyId, propName, propType, propValue, valType, sourceLevelString)*

3.  **`snapshot_instance_property_t`:**
    ```sql
    INSERT INTO snapshot_instance_property_t
    (snapshot_id, host_id, instance_id, property_id, property_value, update_user, update_ts)
    SELECT ?, host_id, instance_id, property_id, property_value, update_user, update_ts
    FROM instance_property_t
    WHERE host_id = ? AND instance_id = ?
    ```
    *(Parameters: snapshotId, hostId, instanceId)*

4.  **`snapshot_instance_api_property_t`:**
    ```sql
    INSERT INTO snapshot_instance_api_property_t
    (snapshot_id, host_id, instance_api_id, property_id, property_value, update_user, update_ts)
    SELECT ?, host_id, instance_api_id, property_id, property_value, update_user, update_ts
    FROM instance_api_property_t
    WHERE host_id = ? AND instance_api_id = ANY(?) -- Parameter is a SQL Array of relevant instance_api_ids
    ```
    *(Parameters: snapshotId, hostId, SQL Array of instance_api_ids)*

5.  **`snapshot_instance_app_property_t`:**
    ```sql
    INSERT INTO snapshot_instance_app_property_t
    (snapshot_id, host_id, instance_app_id, property_id, property_value, update_user, update_ts)
    SELECT ?, host_id, instance_app_id, property_id, property_value, update_user, update_ts
    FROM instance_app_property_t
    WHERE host_id = ? AND instance_app_id = ANY(?) -- Parameter is a SQL Array of relevant instance_app_ids
    ```
    *(Parameters: snapshotId, hostId, SQL Array of instance_app_ids)*

6.  **`snapshot_instance_app_api_property_t`:**
    ```sql
    INSERT INTO snapshot_instance_app_api_property_t
    (snapshot_id, host_id, instance_app_id, instance_api_id, property_id, property_value, update_user, update_ts)
    SELECT ?, host_id, instance_app_id, instance_api_id, property_id, property_value, update_user, update_ts
    FROM instance_app_api_property_t
    WHERE host_id = ?
      AND instance_app_id = ANY(?) -- SQL Array of relevant instance_app_ids
      AND instance_api_id = ANY(?) -- SQL Array of relevant instance_api_ids
    ```
    *(Parameters: snapshotId, hostId, SQL Array of instance_app_ids, SQL Array of instance_api_ids)*

7.  **`snapshot_environment_property_t`:**
    ```sql
    INSERT INTO snapshot_environment_property_t
    (snapshot_id, host_id, environment, property_id, property_value, update_user, update_ts)
    SELECT ?, host_id, environment, property_id, property_value, update_user, update_ts
    FROM environment_property_t
    WHERE host_id = ? AND environment = ?
    ```
    *(Parameters: snapshotId, hostId, environment)*

8.  **`snapshot_product_version_property_t`:**
    ```sql
    INSERT INTO snapshot_product_version_property_t
    (snapshot_id, host_id, product_version_id, property_id, property_value, update_user, update_ts)
    SELECT ?, host_id, product_version_id, property_id, property_value, update_user, update_ts
    FROM product_version_property_t
    WHERE host_id = ? AND product_version_id = ?
    ```
    *(Parameters: snapshotId, hostId, productVersionId)*

9.  **`snapshot_product_property_t`:**
    ```sql
    INSERT INTO snapshot_product_property_t
    (snapshot_id, product_id, property_id, property_value, update_user, update_ts)
    SELECT ?, product_id, property_id, property_value, update_user, update_ts
    FROM product_property_t
    WHERE product_id = ?
    ```
    *(Parameters: snapshotId, productId)*

**Important Considerations:**

*   **Transaction Management:** Ensure all these inserts happen within a single atomic transaction.
*   **Error Handling:** Robust error handling and rollback are critical.
*   **Performance:** The aggregation query can be heavy. Consider its performance impact. The `INSERT ... SELECT` statements should be reasonably efficient if the source tables are properly indexed on their scope columns.
*   **Parameterization:** Use `PreparedStatement` for all queries to prevent SQL injection and improve performance.
*   **Scope Derivation Logic:** Ensure the logic in `deriveScopeInfo` and the helpers like `findRelevantInstanceApiIds` is correct and handles cases where relationships might not exist (e.g., an instance with no associated APIs).
*   **UUID Generation:** Use a suitable UUID generator (like UUIDv7 via `uuid-creator`).
*   **Logging:** Add clear logging for snapshot creation success/failure.
*   **Refinement:** You'll need to adapt the `AGGREGATE_EFFECTIVE_CONFIG_SQL` query based on the final version using `ROW_NUMBER` and correctly incorporate parameters.
    *   Only one aggregation query run per snapshot event.
    *   Captures the complete multi-phase state at that point under one `snapshot_id`.
    *   Simpler `config_snapshot_t` metadata.
    *   Facilitates rollbacks that might need to restore both 'D' and 'R' phase configurations.
*   **Cons:**
    *   Requires modifying the aggregation query.
    *   Consuming services (like startup) need to add `AND config_phase = 'R'` when querying `config_snapshot_property_t`.

**Conclusion:**

**Option 2 is the better approach.** Create a single snapshot representing the point-in-time state for the defined scope, but modify your aggregation query to:

1.  **Remove the `config_phase = ?` filter.**
2.  **Select `c.config_phase` in the final output.**
3.  Store this `config_phase` along with the effective `property_key` and `property_value` in the `config_snapshot_property_t` table.

This is more efficient for snapshot creation and provides a complete view for rollbacks. Consumers simply need to add a phase filter when reading the specific configuration they need (e.g., `'R'` for runtime).

**Modified Aggregation Query Snippet (Final SELECT):**

```sql
-- (Inside the final SELECT statement of the modified aggregation query)
SELECT
    -- snapshot_id needs to be added here or during INSERT
    c.config_phase,   -- <-- Select the phase
    cfg.config_name || '.' || cp.property_name AS property_key,
    ro.property_value,
    cp.property_type,
    cp.value_type
    -- Include ro.priority_level AS source_priority if storing provenance
FROM RankedOverrides ro
JOIN config_property_t cp ON ro.property_id = cp.property_id
JOIN config_t cfg ON cp.config_id = cfg.config_id
-- Make sure the join to config_t (aliased as c or cfg) is available here to get the phase
-- This join likely happened earlier to get config_name anyway.
WHERE ro.rn = 1;
```

### commitConfigInstance

Okay, let's outline the structure of your `commitConfigInstance` service method and the necessary SQL INSERT statements using JDBC.

This involves several steps within a single database transaction:

1.  **Generate Snapshot ID:** Create a new UUID for the snapshot.
2.  **Derive Scope IDs:** Query live tables (`instance_t`, `product_version_t`, etc.) based on the input `hostId` and `instanceId` to get other relevant scope identifiers (`environment`, `productId`, `productVersionId`, `serviceId`, etc.).
3.  **Insert Metadata:** Insert a record into `config_snapshot_t`.
4.  **Aggregate Effective Config:** Run the complex aggregation query (using `ROW_NUMBER()` or similar) to get the final effective properties.
5.  **Insert Effective Config:** Insert the results from step 4 into `config_snapshot_property_t`.
6.  **Snapshot Override Tables:** For each relevant live override table (`instance_property_t`, `instance_api_property_t`, etc.), select its current state (filtered by scope) and insert it into the corresponding `snapshot_*_property_t` table.
7.  **Commit/Rollback:** Commit the transaction if all steps succeed, otherwise roll back.

**Java Service Method Structure (Conceptual)**

```java
import com.github.f4b6a3.uuid.UuidCreator; // For UUIDv7 generation
import javax.sql.DataSource; // Assuming you have a DataSource injected
import java.sql.*;
import java.time.OffsetDateTime;
import java.util.*;

public class ConfigSnapshotService {

    private final DataSource ds;
    // Inject DataSource via constructor

    // Pre-compile your complex aggregation query (modify based on previous examples)
    private static final String AGGREGATE_EFFECTIVE_CONFIG_SQL = """
        WITH AllOverrides AS (
            -- Priority 10: Instance App API (merged) ...
            -- Priority 20: Instance API (merged) ...
            -- Priority 30: Instance App (merged) ...
            -- Priority 40: Instance ...
            -- Priority 50: Product Version ...
            -- Priority 60: Environment ...
            -- Priority 70: Product ...
            -- Priority 100: Default ...
        ),
        RankedOverrides AS (
           SELECT ..., ROW_NUMBER() OVER (PARTITION BY ao.property_id ORDER BY ao.priority_level ASC) as rn
           FROM AllOverrides ao WHERE ao.property_value IS NOT NULL
        )
        SELECT
            c.config_phase,   -- Phase from config_t
            cfg.config_id,    -- Added config_id
            cp.property_id,   -- Added property_id
            cp.property_name, -- Added property_name
            cp.property_type,
            cp.value_type,
            cfg.config_name || '.' || cp.property_name AS property_key, -- Keep for logging/debug? Not needed in snapshot table itself
            ro.property_value,
            ro.priority_level -- To determine source_level
        FROM RankedOverrides ro
        JOIN config_property_t cp ON ro.property_id = cp.property_id
        JOIN config_t cfg ON cp.config_id = cfg.config_id
        WHERE ro.rn = 1;
    """; // NOTE: Add parameters (?) for host_id, instance_id, derived IDs etc.

    public Result<String> commitConfigInstance(Map<String, Object> event) {
        // 1. Extract Input Parameters
        UUID hostId = (UUID) event.get("hostId");
        UUID instanceId = (UUID) event.get("instanceId");
        String snapshotType = (String) event.getOrDefault("snapshotType", "USER_SAVE"); // Default type
        String description = (String) event.get("description");
        UUID userId = (UUID) event.get("userId"); // May be null
        UUID deploymentId = (UUID) event.get("deploymentId"); // May be null

        if (hostId == null || instanceId == null) {
            return Failure.of(new Status(INVALID_PARAMETER, "hostId and instanceId are required."));
        }

        UUID snapshotId = UuidCreator.getTimeOrderedEpoch(); // Generate Snapshot ID (e.g., V7)

        Connection connection = null;
        try {
            connection = ds.getConnection();
            connection.setAutoCommit(false); // Start Transaction

            // 2. Derive Scope IDs
            // Query instance_t and potentially product_version_t based on hostId, instanceId
            DerivedScope scope = deriveScopeInfo(connection, hostId, instanceId);
            if (scope == null) {
                connection.rollback(); // Rollback if instance not found
                return Failure.of(new Status(OBJECT_NOT_FOUND, "Instance not found for hostId/instanceId."));
            }

            // 3. Insert Snapshot Metadata
            insertSnapshotMetadata(connection, snapshotId, snapshotType, description, userId, deploymentId, hostId, scope);

            // 4 & 5. Aggregate and Insert Effective Config
            insertEffectiveConfigSnapshot(connection, snapshotId, hostId, instanceId, scope);

            // 6. Snapshot Individual Override Tables
            // Use INSERT ... SELECT ... for efficiency
            snapshotInstanceProperties(connection, snapshotId, hostId, instanceId);
            snapshotInstanceApiProperties(connection, snapshotId, hostId, instanceId);
            snapshotInstanceAppProperties(connection, snapshotId, hostId, instanceId);
            snapshotInstanceAppApiProperties(connection, snapshotId, hostId, instanceId); // Requires finding relevant App/API IDs first
            snapshotEnvironmentProperties(connection, snapshotId, hostId, scope.environment());
            snapshotProductVersionProperties(connection, snapshotId, hostId, scope.productVersionId());
            snapshotProductProperties(connection, snapshotId, scope.productId());
            // Add others as needed

            // 7. Commit Transaction
            connection.commit();
            logger.info("Successfully created config snapshot: {}", snapshotId);
            return Success.of(snapshotId.toString());

        } catch (SQLException e) {
            logger.error("SQLException during snapshot creation for instance {}: {}", instanceId, e.getMessage(), e);
            if (connection != null) {
                try {
                    connection.rollback();
                } catch (SQLException ex) {
                    logger.error("Error rolling back transaction:", ex);
                }
            }
            return Failure.of(new Status(SQL_EXCEPTION, "Database error during snapshot creation."));
        } catch (Exception e) { // Catch other potential errors (e.g., during scope derivation)
             logger.error("Exception during snapshot creation for instance {}: {}", instanceId, e.getMessage(), e);
             if (connection != null) {
                 try { connection.rollback(); } catch (SQLException ex) { logger.error("Error rolling back transaction:", ex); }
             }
            return Failure.of(new Status(GENERIC_EXCEPTION, "Unexpected error during snapshot creation."));
        } finally {
            if (connection != null) {
                try {
                    connection.setAutoCommit(true); // Restore default behavior
                    connection.close();
                } catch (SQLException e) {
                    logger.error("Error closing connection:", e);
                }
            }
        }
    }

    // --- Helper Methods ---

    // Placeholder for derived scope data structure
    private record DerivedScope(String environment, String productId, String productVersion, UUID productVersionId, String serviceId /*, add API details if needed */) {}

    private DerivedScope deriveScopeInfo(Connection conn, UUID hostId, UUID instanceId) throws SQLException {
        // Query instance_t LEFT JOIN product_version_t ... WHERE i.host_id = ? AND i.instance_id = ?
        // Extract environment, service_id from instance_t
        // Extract product_id, product_version from product_version_t (via product_version_id in instance_t)
        // Return new DerivedScope(...) or null if not found
        String sql = """
            SELECT i.environment, i.service_id, pv.product_id, pv.product_version, i.product_version_id
            FROM instance_t i
            LEFT JOIN product_version_t pv ON i.host_id = pv.host_id AND i.product_version_id = pv.product_version_id
            WHERE i.host_id = ? AND i.instance_id = ?
        """;
        try (PreparedStatement ps = conn.prepareStatement(sql)) {
            ps.setObject(1, hostId);
            ps.setObject(2, instanceId);
            try (ResultSet rs = ps.executeQuery()) {
                if (rs.next()) {
                    return new DerivedScope(
                        rs.getString("environment"),
                        rs.getString("product_id"),
                        rs.getString("product_version"),
                        rs.getObject("product_version_id", UUID.class),
                        rs.getString("service_id")
                    );
                } else {
                    return null; // Instance not found
                }
            }
        }
    }

    private void insertSnapshotMetadata(Connection conn, UUID snapshotId, String snapshotType, String description,
                                        UUID userId, UUID deploymentId, UUID hostId, DerivedScope scope) throws SQLException {
        String sql = """
            INSERT INTO config_snapshot_t
            (snapshot_id, snapshot_ts, snapshot_type, description, user_id, deployment_id,
             scope_host_id, scope_environment, scope_product_id, scope_product_version_id, -- Changed col name
             scope_service_id /*, scope_api_id, scope_api_version - Add if applicable */)
            VALUES (?, CURRENT_TIMESTAMP, ?, ?, ?, ?, ?, ?, ?, ?, ? /*, ?, ? */)
            """;
        try (PreparedStatement ps = conn.prepareStatement(sql)) {
            ps.setObject(1, snapshotId);
            ps.setString(2, snapshotType);
            ps.setString(3, description);
            ps.setObject(4, userId);         // setObject handles null correctly
            ps.setObject(5, deploymentId);   // setObject handles null correctly
            ps.setObject(6, hostId);
            ps.setString(7, scope.environment());
            ps.setString(8, scope.productId());
            ps.setObject(9, scope.productVersionId()); // Store the ID
            ps.setString(10, scope.serviceId());
            // Set API scope if needed ps.setObject(11, ...); ps.setString(12, ...);
            ps.executeUpdate();
        }
    }


    private void insertEffectiveConfigSnapshot(Connection conn, UUID snapshotId, UUID hostId, UUID instanceId, DerivedScope scope) throws SQLException {
         String insertSql = """
            INSERT INTO config_snapshot_property_t
            (snapshot_property_id, snapshot_id, config_phase, config_id, property_id, property_name,
             property_type, property_value, value_type, source_level)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """;
        // Prepare the aggregation query
        try (PreparedStatement selectStmt = conn.prepareStatement(AGGREGATE_EFFECTIVE_CONFIG_SQL);
             PreparedStatement insertStmt = conn.prepareStatement(insertSql)) {

             // Set ALL parameters for the AGGREGATE_EFFECTIVE_CONFIG_SQL query
             int paramIndex = 1;
             // Example: set parameters based on how AGGREGATE_EFFECTIVE_CONFIG_SQL is structured
             // selectStmt.setObject(paramIndex++, hostId);
             // selectStmt.setObject(paramIndex++, instanceId);
             // ... set derived scope IDs (productVersionId, environment, productId) ...
             // ... set parameters for all UNION branches and potential subqueries ...

             try (ResultSet rs = selectStmt.executeQuery()) {
                int batchCount = 0;
                while (rs.next()) {
                    insertStmt.setObject(1, UuidCreator.getTimeOrderedEpoch()); // snapshot_property_id
                    insertStmt.setObject(2, snapshotId);
                    insertStmt.setString(3, rs.getString("config_phase"));
                    insertStmt.setObject(4, rs.getObject("config_id", UUID.class));
                    insertStmt.setObject(5, rs.getObject("property_id", UUID.class));
                    insertStmt.setString(6, rs.getString("property_name"));
                    insertStmt.setString(7, rs.getString("property_type"));
                    insertStmt.setString(8, rs.getString("property_value"));
                    insertStmt.setString(9, rs.getString("value_type"));
                    insertStmt.setString(10, mapPriorityToSourceLevel(rs.getInt("priority_level"))); // Map numeric priority back to level name

                    insertStmt.addBatch();
                    batchCount++;

                    if (batchCount % 100 == 0) { // Execute batch periodically
                        insertStmt.executeBatch();
                    }
                }
                 if (batchCount % 100 != 0) { // Execute remaining batch
                     insertStmt.executeBatch();
                 }
             }
         }
    }

    // Helper to map priority back to source level name
    private String mapPriorityToSourceLevel(int priority) {
        return switch (priority) {
            case 10 -> "instance_app_api"; // Adjust priorities as used in your query
            case 20 -> "instance_api";
            case 30 -> "instance_app";
            case 40 -> "instance";
            case 50 -> "product_version";
            case 60 -> "environment";
            case 70 -> "product";
            case 100 -> "default";
            default -> "unknown";
        };
    }


    // --- Methods for Snapshotting Individual Override Tables ---

    private void snapshotInstanceProperties(Connection conn, UUID snapshotId, UUID hostId, UUID instanceId) throws SQLException {
        String sql = """
            INSERT INTO snapshot_instance_property_t
            (snapshot_id, host_id, instance_id, property_id, property_value, update_user, update_ts)
            SELECT ?, host_id, instance_id, property_id, property_value, update_user, update_ts
            FROM instance_property_t
            WHERE host_id = ? AND instance_id = ?
            """;
        try (PreparedStatement ps = conn.prepareStatement(sql)) {
            ps.setObject(1, snapshotId);
            ps.setObject(2, hostId);
            ps.setObject(3, instanceId);
            ps.executeUpdate();
        }
    }

    private void snapshotInstanceApiProperties(Connection conn, UUID snapshotId, UUID hostId, UUID instanceId) throws SQLException {
         // Find relevant instance_api_ids first
        List<UUID> apiIds = findRelevantInstanceApiIds(conn, hostId, instanceId);
        if (apiIds.isEmpty()) return; // No API overrides for this instance

        String sql = """
            INSERT INTO snapshot_instance_api_property_t
            (snapshot_id, host_id, instance_api_id, property_id, property_value, update_user, update_ts)
            SELECT ?, host_id, instance_api_id, property_id, property_value, update_user, update_ts
            FROM instance_api_property_t
            WHERE host_id = ? AND instance_api_id = ANY(?) -- Use ANY with array for multiple IDs
            """;
        try (PreparedStatement ps = conn.prepareStatement(sql)) {
            ps.setObject(1, snapshotId);
            ps.setObject(2, hostId);
            // Create a SQL Array from the List of UUIDs
            Array sqlArray = conn.createArrayOf("UUID", apiIds.toArray());
            ps.setArray(3, sqlArray);
            ps.executeUpdate();
            sqlArray.free(); // Release array resources
        }
    }

    // Similar methods for snapshotInstanceAppProperties, snapshotInstanceAppApiProperties...
    // These will need helper methods like findRelevantInstanceApiIds/findRelevantInstanceAppIds

    private void snapshotEnvironmentProperties(Connection conn, UUID snapshotId, UUID hostId, String environment) throws SQLException {
        if (environment == null || environment.isEmpty()) return; // No environment scope
        String sql = """
             INSERT INTO snapshot_environment_property_t
             (snapshot_id, host_id, environment, property_id, property_value, update_user, update_ts)
             SELECT ?, host_id, environment, property_id, property_value, update_user, update_ts
             FROM environment_property_t
             WHERE host_id = ? AND environment = ?
             """;
         try (PreparedStatement ps = conn.prepareStatement(sql)) {
             ps.setObject(1, snapshotId);
             ps.setObject(2, hostId);
             ps.setString(3, environment);
             ps.executeUpdate();
         }
    }

     private void snapshotProductVersionProperties(Connection conn, UUID snapshotId, UUID hostId, UUID productVersionId) throws SQLException {
         if (productVersionId == null) return;
         String sql = """
              INSERT INTO snapshot_product_version_property_t
              (snapshot_id, host_id, product_version_id, property_id, property_value, update_user, update_ts)
              SELECT ?, host_id, product_version_id, property_id, property_value, update_user, update_ts
              FROM product_version_property_t
              WHERE host_id = ? AND product_version_id = ?
              """;
          try (PreparedStatement ps = conn.prepareStatement(sql)) {
              ps.setObject(1, snapshotId);
              ps.setObject(2, hostId);
              ps.setObject(3, productVersionId);
              ps.executeUpdate();
          }
     }

     private void snapshotProductProperties(Connection conn, UUID snapshotId, String productId) throws SQLException {
         if (productId == null || productId.isEmpty()) return;
         String sql = """
               INSERT INTO snapshot_product_property_t
               (snapshot_id, product_id, property_id, property_value, update_user, update_ts)
               SELECT ?, product_id, property_id, property_value, update_user, update_ts
               FROM product_property_t
               WHERE product_id = ?
               """;
           try (PreparedStatement ps = conn.prepareStatement(sql)) {
               ps.setObject(1, snapshotId);
               ps.setString(2, productId);
               ps.executeUpdate();
           }
     }

    // --- Helper method to find associated instance_api_ids ---
    private List<UUID> findRelevantInstanceApiIds(Connection conn, UUID hostId, UUID instanceId) throws SQLException {
        List<UUID> ids = new ArrayList<>();
        String sql = "SELECT instance_api_id FROM instance_api_t WHERE host_id = ? AND instance_id = ?";
        try (PreparedStatement ps = conn.prepareStatement(sql)) {
            ps.setObject(1, hostId);
            ps.setObject(2, instanceId);
            try (ResultSet rs = ps.executeQuery()) {
                while(rs.next()) {
                    ids.add(rs.getObject("instance_api_id", UUID.class));
                }
            }
        }
        return ids;
    }
     // --- Add similar helper for findRelevantInstanceAppIds ---
     // --- Add similar helper for findRelevantInstanceAppApiIds (if needed) ---

}
```

**SQL INSERT Statements:**

1.  **`config_snapshot_t`:**
    ```sql
    INSERT INTO config_snapshot_t
    (snapshot_id, snapshot_ts, snapshot_type, description, user_id, deployment_id,
     scope_host_id, scope_environment, scope_product_id, scope_product_version_id, scope_service_id /*, ... other scope cols */)
    VALUES (?, CURRENT_TIMESTAMP, ?, ?, ?, ?, ?, ?, ?, ?, ? /*, ... */)
    ```
    *(Parameters: snapshotId, snapshotType, description, userId, deploymentId, hostId, environment, productId, productVersionId, serviceId, ...)*

2.  **`config_snapshot_property_t`:** (Executed in a loop/batch)
    ```sql
    INSERT INTO config_snapshot_property_t
    (snapshot_property_id, snapshot_id, config_phase, config_id, property_id, property_name,
     property_type, property_value, value_type, source_level)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ```
    *(Parameters: new UUID, snapshotId, phase, configId, propertyId, propName, propType, propValue, valType, sourceLevelString)*

3.  **`snapshot_instance_property_t`:**
    ```sql
    INSERT INTO snapshot_instance_property_t
    (snapshot_id, host_id, instance_id, property_id, property_value, update_user, update_ts)
    SELECT ?, host_id, instance_id, property_id, property_value, update_user, update_ts
    FROM instance_property_t
    WHERE host_id = ? AND instance_id = ?
    ```
    *(Parameters: snapshotId, hostId, instanceId)*

4.  **`snapshot_instance_api_property_t`:**
    ```sql
    INSERT INTO snapshot_instance_api_property_t
    (snapshot_id, host_id, instance_api_id, property_id, property_value, update_user, update_ts)
    SELECT ?, host_id, instance_api_id, property_id, property_value, update_user, update_ts
    FROM instance_api_property_t
    WHERE host_id = ? AND instance_api_id = ANY(?) -- Parameter is a SQL Array of relevant instance_api_ids
    ```
    *(Parameters: snapshotId, hostId, SQL Array of instance_api_ids)*

5.  **`snapshot_instance_app_property_t`:**
    ```sql
    INSERT INTO snapshot_instance_app_property_t
    (snapshot_id, host_id, instance_app_id, property_id, property_value, update_user, update_ts)
    SELECT ?, host_id, instance_app_id, property_id, property_value, update_user, update_ts
    FROM instance_app_property_t
    WHERE host_id = ? AND instance_app_id = ANY(?) -- Parameter is a SQL Array of relevant instance_app_ids
    ```
    *(Parameters: snapshotId, hostId, SQL Array of instance_app_ids)*

6.  **`snapshot_instance_app_api_property_t`:**
    ```sql
    INSERT INTO snapshot_instance_app_api_property_t
    (snapshot_id, host_id, instance_app_id, instance_api_id, property_id, property_value, update_user, update_ts)
    SELECT ?, host_id, instance_app_id, instance_api_id, property_id, property_value, update_user, update_ts
    FROM instance_app_api_property_t
    WHERE host_id = ?
      AND instance_app_id = ANY(?) -- SQL Array of relevant instance_app_ids
      AND instance_api_id = ANY(?) -- SQL Array of relevant instance_api_ids
    ```
    *(Parameters: snapshotId, hostId, SQL Array of instance_app_ids, SQL Array of instance_api_ids)*

7.  **`snapshot_environment_property_t`:**
    ```sql
    INSERT INTO snapshot_environment_property_t
    (snapshot_id, host_id, environment, property_id, property_value, update_user, update_ts)
    SELECT ?, host_id, environment, property_id, property_value, update_user, update_ts
    FROM environment_property_t
    WHERE host_id = ? AND environment = ?
    ```
    *(Parameters: snapshotId, hostId, environment)*

8.  **`snapshot_product_version_property_t`:**
    ```sql
    INSERT INTO snapshot_product_version_property_t
    (snapshot_id, host_id, product_version_id, property_id, property_value, update_user, update_ts)
    SELECT ?, host_id, product_version_id, property_id, property_value, update_user, update_ts
    FROM product_version_property_t
    WHERE host_id = ? AND product_version_id = ?
    ```
    *(Parameters: snapshotId, hostId, productVersionId)*

9.  **`snapshot_product_property_t`:**
    ```sql
    INSERT INTO snapshot_product_property_t
    (snapshot_id, product_id, property_id, property_value, update_user, update_ts)
    SELECT ?, product_id, property_id, property_value, update_user, update_ts
    FROM product_property_t
    WHERE product_id = ?
    ```
    *(Parameters: snapshotId, productId)*

**Important Considerations:**

*   **Transaction Management:** Ensure all these inserts happen within a single atomic transaction.
*   **Error Handling:** Robust error handling and rollback are critical.
*   **Performance:** The aggregation query can be heavy. Consider its performance impact. The `INSERT ... SELECT` statements should be reasonably efficient if the source tables are properly indexed on their scope columns.
*   **Parameterization:** Use `PreparedStatement` for all queries to prevent SQL injection and improve performance.
*   **Scope Derivation Logic:** Ensure the logic in `deriveScopeInfo` and the helpers like `findRelevantInstanceApiIds` is correct and handles cases where relationships might not exist (e.g., an instance with no associated APIs).
*   **UUID Generation:** Use a suitable UUID generator (like UUIDv7 via `uuid-creator`).
*   **Logging:** Add clear logging for snapshot creation success/failure.
*   **Refinement:** You'll need to adapt the `AGGREGATE_EFFECTIVE_CONFIG_SQL` query based on the final version using `ROW_NUMBER` and correctly incorporate parameters.

### rollbackConfigInstance

Okay, here's the `rollbackConfigInstance` method implementing the DELETE/INSERT strategy to restore the state of instance-level and related sub-level overrides from a snapshot.

**Assumptions:**

*   "Rolling back an instance" means restoring the overrides defined specifically for that instance and its associated APIs, Apps, and App-API combinations. It *does not* modify higher-level overrides (Environment, Product Version, Product).
*   The `snapshot_*_property_t` tables accurately store the state of the corresponding live tables *at the time the snapshot was taken*.
*   The necessary helper methods like `findRelevantInstanceApiIds`, `findRelevantInstanceAppIds` exist (examples provided).

```java
import com.github.f4b6a3.uuid.UuidCreator; // If needed for audit logging ID
import javax.sql.DataSource;
import java.sql.*;
import java.util.*;

public class ConfigRollbackService {

    private final DataSource ds;
    // Inject DataSource via constructor

    // --- SQL Templates ---

    // DELETE Statements (Targeting LIVE tables)
    private static final String DELETE_INSTANCE_PROPS_SQL = "DELETE FROM instance_property_t WHERE host_id = ? AND instance_id = ?";
    private static final String DELETE_INSTANCE_API_PROPS_SQL = "DELETE FROM instance_api_property_t WHERE host_id = ? AND instance_api_id = ANY(?)";
    private static final String DELETE_INSTANCE_APP_PROPS_SQL = "DELETE FROM instance_app_property_t WHERE host_id = ? AND instance_app_id = ANY(?)";
    private static final String DELETE_INSTANCE_APP_API_PROPS_SQL = "DELETE FROM instance_app_api_property_t WHERE host_id = ? AND instance_app_id = ANY(?) AND instance_api_id = ANY(?)";

    // INSERT ... SELECT Statements (From SNAPSHOT tables to LIVE tables)
    private static final String INSERT_INSTANCE_PROPS_SQL = """
        INSERT INTO instance_property_t
        (host_id, instance_id, property_id, property_value, update_user, update_ts)
        SELECT host_id, instance_id, property_id, property_value, update_user, update_ts
        FROM snapshot_instance_property_t
        WHERE snapshot_id = ? AND host_id = ? AND instance_id = ?
        """;
    private static final String INSERT_INSTANCE_API_PROPS_SQL = """
        INSERT INTO instance_api_property_t
        (host_id, instance_api_id, property_id, property_value, update_user, update_ts)
        SELECT host_id, instance_api_id, property_id, property_value, update_user, update_ts
        FROM snapshot_instance_api_property_t
        WHERE snapshot_id = ? AND host_id = ? AND instance_api_id = ANY(?)
        """;
     private static final String INSERT_INSTANCE_APP_PROPS_SQL = """
        INSERT INTO instance_app_property_t
        (host_id, instance_app_id, property_id, property_value, update_user, update_ts)
        SELECT host_id, instance_app_id, property_id, property_value, update_user, update_ts
        FROM snapshot_instance_app_property_t
        WHERE snapshot_id = ? AND host_id = ? AND instance_app_id = ANY(?)
        """;
    private static final String INSERT_INSTANCE_APP_API_PROPS_SQL = """
        INSERT INTO instance_app_api_property_t
        (host_id, instance_app_id, instance_api_id, property_id, property_value, update_user, update_ts)
        SELECT host_id, instance_app_id, instance_api_id, property_id, property_value, update_user, update_ts
        FROM snapshot_instance_app_api_property_t
        WHERE snapshot_id = ? AND host_id = ? AND instance_app_id = ANY(?) AND instance_api_id = ANY(?)
        """;

    public Result<String> rollbackConfigInstance(Map<String, Object> event) {
        // 1. Extract Input Parameters
        UUID snapshotId = (UUID) event.get("snapshotId");
        UUID hostId = (UUID) event.get("hostId");
        UUID instanceId = (UUID) event.get("instanceId");
        UUID userId = (UUID) event.get("userId"); // For potential auditing
        String description = (String) event.get("rollbackDescription"); // Optional reason

        if (snapshotId == null || hostId == null || instanceId == null) {
            return Failure.of(new Status(INVALID_PARAMETER, "snapshotId, hostId, and instanceId are required."));
        }

        Connection connection = null;
        List<UUID> currentApiIds = null;
        List<UUID> currentAppIds = null;

        try {
            connection = ds.getConnection();
            connection.setAutoCommit(false); // Start Transaction

            // --- Pre-computation: Find CURRENT associated IDs for DELETE scope ---
            // It's generally safer to delete based on current relationships and then
            // insert based on snapshot relationships if they could have diverged.
            currentApiIds = findRelevantInstanceApiIds(connection, hostId, instanceId);
            currentAppIds = findRelevantInstanceAppIds(connection, hostId, instanceId);
            // Note: InstanceAppApi requires both lists.

            logger.info("Starting rollback for instance {} (host {}) to snapshot {}", instanceId, hostId, snapshotId);

            // --- Execute Deletes from LIVE tables ---
            executeDelete(connection, DELETE_INSTANCE_PROPS_SQL, hostId, instanceId);

            if (!currentApiIds.isEmpty()) {
                executeDeleteWithArray(connection, DELETE_INSTANCE_API_PROPS_SQL, hostId, currentApiIds);
                // Also delete AppApi props related to these APIs if apps also exist
                if (!currentAppIds.isEmpty()) {
                     executeDeleteWithTwoArrays(connection, DELETE_INSTANCE_APP_API_PROPS_SQL, hostId, currentAppIds, currentApiIds);
                }
            }

            if (!currentAppIds.isEmpty()) {
                executeDeleteWithArray(connection, DELETE_INSTANCE_APP_PROPS_SQL, hostId, currentAppIds);
                 // AppApi props deletion might have already happened above if APIs existed.
                 // If only apps existed but no APIs, delete AppApi here (redundant if handled above)
                 // Generally safe to run the AppApi delete again if needed, targeting only appIds.
                 // For simplicity, we assume the AppApi delete targeting both arrays covers necessary cases.
            }


            // --- Execute Inserts from SNAPSHOT tables ---
            executeInsertSelect(connection, INSERT_INSTANCE_PROPS_SQL, snapshotId, hostId, instanceId);

            // For array-based inserts, we need the IDs *from the snapshot time*
            // However, the SELECT inside the INSERT query implicitly filters by snapshot_id AND the array condition,
            // so it should correctly only insert relationships that existed in the snapshot.
            // We still use the *current* IDs to DEFINE the overall scope of instance being affected,
            // but the INSERT...SELECT filters correctly based on snapshot content.
            if (!currentApiIds.isEmpty()) { // Use currentApiIds to decide IF we run the insert query
                executeInsertSelectWithArray(connection, INSERT_INSTANCE_API_PROPS_SQL, snapshotId, hostId, currentApiIds);
                 if (!currentAppIds.isEmpty()) {
                    executeInsertSelectWithTwoArrays(connection, INSERT_INSTANCE_APP_API_PROPS_SQL, snapshotId, hostId, currentAppIds, currentApiIds);
                }
            }
            if (!currentAppIds.isEmpty()) { // Use currentAppIds to decide IF we run the insert query
                executeInsertSelectWithArray(connection, INSERT_INSTANCE_APP_PROPS_SQL, snapshotId, hostId, currentAppIds);
                // Redundant AppApi insert if handled above? No, the INSERT uses the AppId filter.
                // If only apps existed at snapshot time, this covers it.
            }

            // --- Optional: Audit Logging ---
            // logRollbackActivity(connection, snapshotId, hostId, instanceId, userId, description);


            // --- Commit Transaction ---
            connection.commit();
            logger.info("Successfully rolled back instance {} (host {}) to snapshot {}", instanceId, hostId, snapshotId);
            return Success.of("Rollback successful to snapshot " + snapshotId);

        } catch (SQLException e) {
            logger.error("SQLException during rollback for instance {} to snapshot {}: {}", instanceId, snapshotId, e.getMessage(), e);
            if (connection != null) {
                try {
                    connection.rollback();
                     logger.warn("Transaction rolled back for instance {} snapshot {}", instanceId, snapshotId);
                } catch (SQLException ex) {
                    logger.error("Error rolling back transaction:", ex);
                }
            }
            return Failure.of(new Status(SQL_EXCEPTION, "Database error during rollback operation."));
        } catch (Exception e) { // Catch other potential errors
             logger.error("Exception during rollback for instance {} to snapshot {}: {}", instanceId, snapshotId, e.getMessage(), e);
             if (connection != null) {
                 try { connection.rollback(); } catch (SQLException ex) { logger.error("Error rolling back transaction:", ex); }
             }
            return Failure.of(new Status(GENERIC_EXCEPTION, "Unexpected error during rollback operation."));
        } finally {
            if (connection != null) {
                try {
                    connection.setAutoCommit(true); // Restore default behavior
                    connection.close();
                } catch (SQLException e) {
                    logger.error("Error closing connection:", e);
                }
            }
        }
    }

    // --- Helper Methods for Execution ---

    private void executeDelete(Connection conn, String sql, UUID hostId, UUID instanceId) throws SQLException {
         try (PreparedStatement ps = conn.prepareStatement(sql)) {
             ps.setObject(1, hostId);
             ps.setObject(2, instanceId);
             int rowsAffected = ps.executeUpdate();
             logger.debug("Deleted {} rows from {} for instance {}", rowsAffected, getTableNameFromDeleteSql(sql), instanceId);
         }
    }

    private void executeDeleteWithArray(Connection conn, String sql, UUID hostId, List<UUID> idList) throws SQLException {
        if (idList == null || idList.isEmpty()) return; // Nothing to delete if list is empty
        try (PreparedStatement ps = conn.prepareStatement(sql)) {
            ps.setObject(1, hostId);
            Array sqlArray = conn.createArrayOf("UUID", idList.toArray());
            ps.setArray(2, sqlArray);
            int rowsAffected = ps.executeUpdate();
            logger.debug("Deleted {} rows from {} for {} IDs", rowsAffected, getTableNameFromDeleteSql(sql), idList.size());
            sqlArray.free();
        }
    }

    private void executeDeleteWithTwoArrays(Connection conn, String sql, UUID hostId, List<UUID> idList1, List<UUID> idList2) throws SQLException {
        if (idList1 == null || idList1.isEmpty() || idList2 == null || idList2.isEmpty()) return;
         try (PreparedStatement ps = conn.prepareStatement(sql)) {
             ps.setObject(1, hostId);
             Array sqlArray1 = conn.createArrayOf("UUID", idList1.toArray());
             Array sqlArray2 = conn.createArrayOf("UUID", idList2.toArray());
             ps.setArray(2, sqlArray1);
             ps.setArray(3, sqlArray2);
             int rowsAffected = ps.executeUpdate();
             logger.debug("Deleted {} rows from {} for {}x{} IDs", rowsAffected, getTableNameFromDeleteSql(sql), idList1.size(), idList2.size());
             sqlArray1.free();
             sqlArray2.free();
         }
    }


    private void executeInsertSelect(Connection conn, String sql, UUID snapshotId, UUID hostId, UUID instanceId) throws SQLException {
         try (PreparedStatement ps = conn.prepareStatement(sql)) {
             ps.setObject(1, snapshotId);
             ps.setObject(2, hostId);
             ps.setObject(3, instanceId);
             int rowsAffected = ps.executeUpdate();
              logger.debug("Inserted {} rows into {} from snapshot {}", rowsAffected, getTableNameFromInsertSql(sql), snapshotId);
         }
    }

     private void executeInsertSelectWithArray(Connection conn, String sql, UUID snapshotId, UUID hostId, List<UUID> idList) throws SQLException {
         if (idList == null || idList.isEmpty()) return; // No scope to insert for
         try (PreparedStatement ps = conn.prepareStatement(sql)) {
             ps.setObject(1, snapshotId);
             ps.setObject(2, hostId);
             Array sqlArray = conn.createArrayOf("UUID", idList.toArray());
             ps.setArray(3, sqlArray);
             int rowsAffected = ps.executeUpdate();
             logger.debug("Inserted {} rows into {} from snapshot {} for {} IDs", rowsAffected, getTableNameFromInsertSql(sql), snapshotId, idList.size());
             sqlArray.free();
         }
     }

     private void executeInsertSelectWithTwoArrays(Connection conn, String sql, UUID snapshotId, UUID hostId, List<UUID> idList1, List<UUID> idList2) throws SQLException {
         if (idList1 == null || idList1.isEmpty() || idList2 == null || idList2.isEmpty()) return;
         try (PreparedStatement ps = conn.prepareStatement(sql)) {
             ps.setObject(1, snapshotId);
             ps.setObject(2, hostId);
             Array sqlArray1 = conn.createArrayOf("UUID", idList1.toArray());
             Array sqlArray2 = conn.createArrayOf("UUID", idList2.toArray());
             ps.setArray(3, sqlArray1);
             ps.setArray(4, sqlArray2);
             int rowsAffected = ps.executeUpdate();
              logger.debug("Inserted {} rows into {} from snapshot {} for {}x{} IDs", rowsAffected, getTableNameFromInsertSql(sql), snapshotId, idList1.size(), idList2.size());
             sqlArray1.free();
             sqlArray2.free();
         }
     }


    // --- Helper methods to find associated IDs (same as before) ---
    private List<UUID> findRelevantInstanceApiIds(Connection conn, UUID hostId, UUID instanceId) throws SQLException {
        // ... implementation ...
    }
    private List<UUID> findRelevantInstanceAppIds(Connection conn, UUID hostId, UUID instanceId) throws SQLException {
        // ... implementation ...
    }

    // --- Optional: Helper to get table name from SQL for logging ---
    private String getTableNameFromDeleteSql(String sql) {
        // Simple parsing, might need adjustment
        try { return sql.split("FROM ")[1].split(" ")[0]; } catch (Exception e) { return "[unknown table]"; }
    }
    private String getTableNameFromInsertSql(String sql) {
        try { return sql.split("INTO ")[1].split(" ")[0]; } catch (Exception e) { return "[unknown table]"; }
    }

     // --- Optional: Audit Logging Method ---
    // private void logRollbackActivity(Connection conn, UUID snapshotId, ...) throws SQLException { ... }

}
```

**Explanation:**

1.  **Parameter Extraction:** Gets `snapshotId`, `hostId`, `instanceId`.
2.  **Transaction Control:** Sets `setAutoCommit(false)` at the start and uses `commit()` or `rollback()`.
3.  **Find Current Related IDs:** Queries `instance_api_t` and `instance_app_t` to find the *currently* associated APIs and Apps for the target instance. This is needed to define the scope for the `DELETE` operations.
4.  **Execute Deletes:** Uses helper methods to execute `DELETE` statements against the *live* override tables (`instance_property_t`, `instance_api_property_t`, etc.), filtering by `hostId`, `instanceId`, and the arrays of `currentApiIds` / `currentAppIds` where applicable. This clears the current overrides within the specific scope.
5.  **Execute Inserts:** Uses helper methods to execute `INSERT INTO [live_table] SELECT ... FROM [snapshot_table]` statements.
    *   These statements select data from the `snapshot_*_property_t` tables.
    *   They are filtered by the target `snapshotId`.
    *   Crucially, they are also filtered by `hostId`, `instanceId`, and the relevant `instance_api_id` / `instance_app_id` arrays. This ensures only the overrides relevant to this instance *within that snapshot* are inserted.
6.  **SQL Arrays:** Uses `connection.createArrayOf("UUID", ...)` to pass lists of IDs efficiently to PostgreSQL's `ANY(?)` operator. Remember to `free()` the array resources.
7.  **Helpers:** Includes helper methods for executing the different types of DELETE/INSERT statements and for finding the related API/App IDs.
8.  **Error Handling:** Uses `try-catch-finally` to manage the transaction and connection state.
9.  **Logging:** Added basic logging for start, success, errors, and rows affected.
10. **Scope Focus:** This implementation focuses the rollback on the instance and its direct sub-levels (API, App, App-API). It assumes rolling back an instance doesn't automatically mean rolling back shared Environment or Product Version overrides.

This approach provides a clean and relatively robust way to restore the specific override state from your snapshots using the DELETE/INSERT strategy. Remember to test thoroughly!

