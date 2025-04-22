# Composit key vs Surrogate UUID key

### Composite key with 5 or more columns

User the following three tables as examples. We have composite key with 5 columns and some of them are varchar types in product version_property_t table. Is is a good idea to create UUID keys for config_property_t and product_version_t? 

```
-- each config file will have a config_id reference and this table contains all the properties including default. 
CREATE TABLE config_property_t (
    config_id                 UUID NOT NULL,
    property_name             VARCHAR(64) NOT NULL,
    property_type             VARCHAR(32) DEFAULT 'Config' NOT NULL,
    light4j_version           VARCHAR(12), -- only newly introduced property has a version.
    display_order             INTEGER,
    required                  BOOLEAN DEFAULT false NOT NULL,
    property_desc             VARCHAR(4096),
    property_value            TEXT,
    value_type                VARCHAR(32),
    property_file             TEXT,
    resource_type             VARCHAR(30) DEFAULT 'none',
    update_user               VARCHAR(255) DEFAULT SESSION_USER NOT NULL,
    update_ts                 TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

ALTER TABLE config_property_t
    ADD CHECK ( property_type IN ( 'Cert', 'Config', 'File') );


COMMENT ON COLUMN config_property_t.property_value IS
    'Property Default Value';

COMMENT ON COLUMN config_property_t.value_type IS
    'One of string, boolean, integer, float, map, list';

COMMENT ON COLUMN config_property_t.resource_type IS
  'One of none, api, app, app_api, api|app_api, app|app_api, all';

ALTER TABLE config_property_t ADD CONSTRAINT config_property_pk PRIMARY KEY ( config_id, property_name );



CREATE TABLE product_version_t (
    host_id                     UUID NOT NULL,
    product_id                  VARCHAR(8) NOT NULL,
    product_version             VARCHAR(12) NOT NULL, -- internal product version 
    light4j_version             VARCHAR(12) NOT NULL, -- open source release version
    break_code                  BOOLEAN DEFAULT false, -- breaking code change to upgrade to this version.
    break_config                BOOLEAN DEFAULT false, -- config server need this to decide if clone is allowed for this version. 
    release_note                TEXT,
    version_desc                VARCHAR(1024),
    release_type                VARCHAR(24) NOT NULL, -- Alpha Version, Beta Version, Release Candidate, General Availability, Production Release
    current                     BOOLEAN DEFAULT false,
    version_status              VARCHAR(16) NOT NULL, 
    update_user                 VARCHAR (255) DEFAULT SESSION_USER NOT NULL,
    update_ts                   TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    PRIMARY KEY(host_id, product_id, product_version)
);


-- customized property for product version within the host.
CREATE TABLE product_version_property_t (
    host_id          UUID NOT NULL,
    product_id       VARCHAR(8) NOT NULL,
    product_version  VARCHAR(12) NOT NULL,
    config_id        UUID NOT NULL,
    property_name    VARCHAR(64) NOT NULL,
    property_value   TEXT,
    property_file    TEXT,
    update_user      VARCHAR (126) DEFAULT SESSION_USER NOT NULL,
    update_ts        TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

ALTER TABLE product_version_property_t
    ADD CONSTRAINT product_version_property_pk PRIMARY KEY ( host_id, 
                                                             product_id,
                                                             product_version,
                                                             config_id,
                                                             property_name);
```

Replacing the wide, multi-column composite primary key in `product_version_property_t` with one based on surrogate UUID keys from the parent tables is **generally a very good idea** for several reasons, primarily related to performance and maintainability.

Let's break down the pros and cons:

**Current Situation (Composite Keys):**

*   **`config_property_t` PK:** (`config_id` UUID, `property_name` VARCHAR(64)) - Size: 16 + (up to 64 + overhead) bytes. Reasonably sized.
*   **`product_version_t` PK:** (`host_id` UUID, `product_id` VARCHAR(8), `product_version` VARCHAR(12)) - Size: 16 + (8 + overhead) + (12 + overhead) bytes. Getting wider.
*   **`product_version_property_t` PK:** (`host_id` UUID, `product_id` VARCHAR(8), `product_version` VARCHAR(12), `config_id` UUID, `property_name` VARCHAR(64)) - Size: 16 + (8+oh) + (12+oh) + 16 + (64+oh) bytes. **This is quite wide.**

**Problems with the Wide Composite Key in `product_version_property_t`:**

1.  **Large Primary Key Index:** The B-tree index for this 5-column PK will be large. Larger indexes consume more disk space, more memory (reducing cache efficiency), and take longer to scan during queries, updates, and deletes.
2.  **Large Foreign Keys (Implicit):** If any other table were to reference `product_version_property_t` (unlikely given its nature, but possible), the foreign key would also need all 5 columns.
3.  **Larger Secondary Indexes:** Any *other* indexes you create on `product_version_property_t` will typically include the primary key columns implicitly (in PostgreSQL leaf nodes). A wide PK bloats *all* other indexes on the table, magnifying the performance impact.
4.  **Update Overhead:** Updating any of the PK columns (though generally discouraged) is very expensive. More importantly, index maintenance during INSERTs and DELETEs is heavier with wider keys.
5.  **Join Complexity:** Joining on 5 columns is syntactically more verbose.

**Proposed Solution (Surrogate UUID Keys):**

1.  **Add Surrogate Key to `config_property_t`:**
    *   Add a new column: `cp_id UUID PRIMARY KEY DEFAULT gen_random_uuid()` (or use UUIDv7 generator).
    *   Add a `UNIQUE` constraint on the *original* natural key: `ALTER TABLE config_property_t ADD CONSTRAINT config_property_nat_key UNIQUE (config_id, property_name);` (This is CRITICAL to maintain data integrity).
    *   Size of new PK: 16 bytes.

2.  **Add Surrogate Key to `product_version_t`:**
    *   Add a new column: `pv_id UUID PRIMARY KEY DEFAULT gen_random_uuid()` (or UUIDv7).
    *   Add a `UNIQUE` constraint on the original natural key: `ALTER TABLE product_version_t ADD CONSTRAINT product_version_nat_key UNIQUE (host_id, product_id, product_version);` (CRITICAL).
    *   Size of new PK: 16 bytes.

3.  **Modify `product_version_property_t`:**
    *   Remove the existing 5-column PK.
    *   Replace the 5 individual columns used for the PK/FK relationship with two new columns: `pv_id UUID` and `cp_id UUID`.
    *   Create the new Primary Key: `ALTER TABLE product_version_property_t ADD CONSTRAINT product_version_property_pk PRIMARY KEY (pv_id, cp_id);`
    *   Add Foreign Key constraints:
        ```sql
        ALTER TABLE product_version_property_t
            ADD CONSTRAINT product_version_property_fk_pv
            FOREIGN KEY (pv_id) REFERENCES product_version_t(pv_id) ON DELETE CASCADE; -- Or appropriate action

        ALTER TABLE product_version_property_t
            ADD CONSTRAINT product_version_property_fk_cp
            FOREIGN KEY (cp_id) REFERENCES config_property_t(cp_id) ON DELETE CASCADE; -- Or appropriate action
        ```
    *   Size of new PK: 16 + 16 = 32 bytes.

**Advantages of the Proposed Solution:**

1.  **Significantly Smaller PK Index:** The PK index on `product_version_property_t` shrinks from potentially >100 bytes wide to just 32 bytes. This is the biggest win.
2.  **Smaller Secondary Indexes:** All other indexes on `product_version_property_t` will also be smaller.
3.  **Improved Query Performance:** Smaller indexes mean faster scans, better cache utilization, and quicker lookups, updates, and deletes involving the PK or indexes on `product_version_property_t`.
4.  **Simpler Joins:** Joining `product_version_property_t` to its parent tables now only requires joining on the single `pv_id` or `cp_id` columns.
5.  **Simpler Foreign Keys:** The FK definitions are simpler.

**Disadvantages/Considerations:**

1.  **Need for `UNIQUE` Constraints:** You *absolutely must* add the `UNIQUE` constraints on the original natural keys in the parent tables (`config_property_t`, `product_version_t`) to prevent duplicate entries based on business logic. This adds two new indexes.
2.  **Storage Overhead (Parent Tables):** You add 16 bytes per row to `config_property_t` and `product_version_t` for the new UUID PKs.
3.  **Migration Effort:** You need to:
    *   Add the new UUID columns to the parent tables.
    *   Populate them with unique UUIDs for all existing rows.
    *   Add the new FK columns (`pv_id`, `cp_id`) to `product_version_property_t`.
    *   Update `product_version_property_t` to populate these new columns by joining back to the parent tables based on the *original* composite keys.
    *   Drop the old PK and FK constraints (or the old columns if they are no longer needed besides the value overrides).
    *   Add the new PK and FK constraints.
    *   Add the `UNIQUE` constraints on the parent tables.
4.  **Lookups by Natural Key:** Queries that previously used the composite PK directly on the parent tables (e.g., `SELECT ... FROM product_version_t WHERE host_id = ? AND product_id = ? AND product_version = ?`) will now use the new `UNIQUE` index instead of the PK index. Performance should still be very good, but it's technically hitting a different index.

**Conclusion:**

**Yes, it is a good idea.** The performance benefits gained from dramatically reducing the size of the primary (and consequently, secondary) indexes on the frequently accessed `product_version_property_t` table likely outweigh the disadvantages (extra storage on parent tables, migration effort, extra unique indexes). The simplification of joins and foreign keys is also a significant maintainability improvement.

**Recommendation:**

Proceed with the plan to introduce surrogate UUID keys (preferably UUIDv7 for generation if using a library) on `config_property_t` and `product_version_t`, and change `product_version_property_t` to use these two UUIDs as its composite primary key. **Do not forget to add the `UNIQUE` constraints on the original natural keys in the parent tables.**

### Composite key with 3 or 4 columns

If a composite key with 3 or 4 columns, it is less definitive than the 5-column case. It moves into a "it depends" territory, requiring weighing the pros and cons more carefully based on specifics.

Here's a breakdown of factors to consider for 3 or 4 column composite primary keys:

**Arguments for Sticking with the Composite Natural Key (CNK):**

1.  **Simplicity (Potentially):** No need for an extra surrogate key column and an extra `UNIQUE` index on the natural key columns. The schema might feel slightly less cluttered *if* the natural key is intuitive and stable.
2.  **Reduced Storage (Parent Table):** Avoids adding 16 bytes per row for the UUID PK in the table itself.
3.  **Meaningful Key:** The PK components have inherent business meaning, which can sometimes be useful for direct queries or understanding relationships without extra joins (though the `UNIQUE` index on the SUK approach provides this lookup too).
4.  **Migration Cost:** Avoids the effort of adding columns, backfilling data, and changing referencing tables.

**Arguments for Refactoring to a Surrogate UUID Key (SUK):**

1.  **Index Size (Still Relevant):** This is the biggest factor.
    *   **Calculate the Width:** Add up the *maximum* potential size of the 3 or 4 columns in the CNK.
        *   `UUID`: 16 bytes
        *   `INT`: 4 bytes
        *   `BIGINT`: 8 bytes
        *   `VARCHAR(N)`: N bytes + 1 or 4 bytes overhead (depending on length)
        *   `TIMESTAMP`: 8 bytes
        *   `BOOLEAN`: 1 byte
    *   **Compare:** Compare the calculated width to the typical width of a surrogate key reference (16 bytes for one UUID, or 32 bytes if the child table needs two UUIDs like in your `product_version_property_t` example).
    *   **Threshold:** If the CNK width starts exceeding ~32-40 bytes, the performance benefits of a narrower SUK (especially for secondary indexes and joins) become increasingly attractive. Even a 3-column key like `(UUID, VARCHAR(8), VARCHAR(12))` is already `16 + (8+1) + (12+1) = 38` bytes. A 4-column key is almost certainly wider.
2.  **Secondary Index Bloat:** Remember, *all* other indexes on the table implicitly include the PK columns. A wide CNK makes *every* index larger, impacting cache efficiency and scan speed across the board. This effect is magnified if you have many secondary indexes.
3.  **Join Performance/Simplicity:** Joining on a single UUID column is generally faster and syntactically simpler than joining on 3 or 4 columns, especially if some are strings.
4.  **Foreign Key Simplicity:** Tables referencing this table only need to store a single UUID column as the foreign key, rather than 3 or 4 columns. This significantly reduces storage and complexity in child tables.
5.  **Immutability/Stability:** Surrogate keys are inherently stable. If there's *any* chance the values in the natural key columns might need to change (which is generally bad practice for PKs but sometimes unavoidable), using a SUK provides crucial insulation.

**Decision Rubric (Heuristics):**

*   **Scenario 1: Key is mostly small, fixed-width types (e.g., 3 INTs, 2 INTs + UUID). Total width < ~32 bytes.**
    *   *Lean towards:* Keeping the CNK might be acceptable, especially if the table isn't heavily referenced or doesn't have many secondary indexes. The benefits of SUK are less pronounced.
*   **Scenario 2: Key includes even one moderately sized VARCHAR (e.g., VARCHAR(20+)) or multiple smaller VARCHARs. Total width > ~32-40 bytes.**
    *   *Lean towards:* Refactoring to SUK. The performance benefits from reduced index sizes (primary and secondary) and simpler joins/FKs likely start to outweigh the costs.
*   **Scenario 3: Key includes wide VARCHARs (VARCHAR(50+)).**
    *   *Lean towards:* Strongly consider refactoring to SUK. Benefits are significant.
*   **Scenario 4: The table is frequently referenced by other tables via FK.**
    *   *Lean towards:* Refactoring to SUK to simplify the child tables.
*   **Scenario 5: The table has many secondary indexes.**
    *   *Lean towards:* Refactoring to SUK to keep those indexes smaller.
*   **Scenario 6: Any component of the natural key is potentially volatile.**
    *   *Lean towards:* Refactoring to SUK for stability.

**Conclusion:**

For 3 or 4 columns, it's less of a slam dunk than for 5 columns, but **refactoring to a surrogate UUID key is still often beneficial, especially if VARCHARs are involved or the total key width exceeds roughly 32-40 bytes.** The key drivers are the reduction in primary and secondary index size and the simplification of foreign keys and joins.

Carefully calculate the width of your specific 3 or 4 column composite keys and consider the usage patterns of the table before deciding.

