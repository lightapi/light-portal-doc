# Cascade Soft Delete

With the recent refactor, relying on `ON DELETE CASCADE` is no longer suitable after implementing **soft deletes**, because soft delete is an `UPDATE` operation (`SET active = FALSE`) and not a true `DELETE` from the database.

The pattern we should follow in an **Event Sourcing / Event-Driven Architecture** with soft deletes is:

### 1. The Principle of Causality (or Domain Consistency)

When a parent entity (e.g., `role_t`) is soft-deleted, all its dependent children entities (e.g., `role_user_t`, `role_permission_t`, etc.) must also be soft-deleted to maintain domain consistency. This cascade logic must be implemented **in the application layer** (the projection service or command handler or database).

### 2. Implementation in the Command/Event Handler/Database

#### Strategy A: Event Amplification (Recommended for True EDA/Event Sourcing)

The command handler that received the initial command/event (e.g., `DeleteRoleCommand` -> `RoleDeletedEvent`) should not directly perform the cascading *database* updates. Instead, it should be responsible for **emitting new cascading events** for each child entity.

1.  **Incoming Command:** Generate a `RoleDeletedEvent` (for a specific `role_id`).
2.  **Emitting Child Events:** It then emits an event for each dependent child, such as `RoleUserRemovedEvent(role_id, user_id)` and `RolePermissionRemovedEvent(role_id, permission_id)`.
3.  **Event Store:** Push an array of events to event_store_t and outbox_message_t tables in a transaction.
4.  **Event Processor:** All events will be processed in the same transaction to update parent table and child tables together. 

**Pro:** Decoupled, explicit, audit trail for every change.
**Con:** More complex event processing, increased event volume; Need to refactor all delete command handlers to emit more events and it is significant code change and long term maintenance work.

#### Strategy B: Direct Application-Level Cascade

In a service that primarily acts as a projection (CQRS read model) and is tightly coupled with its projection logic, the simplest approach is to bundle the cascading logic directly into the parent handler's processing.

1.  **Incoming Event:** `RoleDeletedEvent`.
2.  **Event Processor:** The `deleteRole(conn, event)` method would execute the parent soft delete (`UPDATE role_t SET active=FALSE`).
3.  **Cascading Updates:** Immediately after, within the same transaction, it would execute multiple cascading `UPDATE` statements on the child tables. Make sure that only the active flag is updated based on the primary key for child tables. 

```java
// Inside deleteRole(Connection conn, Map<String, Object> event)
// 1. Soft delete the parent
// UPDATE role_t SET active = FALSE WHERE ...
// 2. Soft delete the children in the same transaction
// UPDATE role_user_t SET active = FALSE, update_user = ?, update_ts = ? WHERE host_id = ? AND role_id = ?
// UPDATE role_permission_t SET active = FALSE, update_user = ?, update_ts = ? WHERE host_id = ? AND role_id = ?
```

**Pro:** Simple, fast, maintains transactional integrity easily.
**Con:** Tightly couples the projection logic; no explicit events for child deletion in the event store; Many db provider update and long term maintenace work. 


#### Strategy C: Direct Database-Level Cascade

Create a trigger in database to manage the cascade soft delete for child tables. This can be individual trigger on each table or a centralized trigger to apply on all tables. 


**Pro:** Simple, fast, maintains transactional integrity easily. Minimum code change in app logic and easy to implement and maintain. 
**Con:** Need to make sure that the project team is aware of the logic to void confusions.

Create a cascade_relationships_v view based on the foreign keys. 

```
DROP VIEW IF EXISTS cascade_relationships_v;

CREATE VIEW cascade_relationships_v AS
WITH fk_details AS (
    SELECT 
        pn.nspname::text AS parent_schema,
        pc.relname::text AS parent_table,
        cn.nspname::text AS child_schema,
        cc.relname::text AS child_table,
        c.conname::text AS constraint_name,
        c.oid AS constraint_id,
        cc.oid AS child_table_oid,
        pc.oid AS parent_table_oid,
        unnest.parent_col,
        unnest.child_col,
        unnest.ord
    FROM pg_constraint c
    JOIN pg_class pc ON c.confrelid = pc.oid
    JOIN pg_namespace pn ON pc.relnamespace = pn.oid
    JOIN pg_class cc ON c.conrelid = cc.oid
    JOIN pg_namespace cn ON cc.relnamespace = cn.oid
    CROSS JOIN LATERAL (
        SELECT 
            unnest(c.confkey) AS parent_col,
            unnest(c.conkey) AS child_col,
            generate_series(1, array_length(c.conkey, 1)) AS ord
    ) unnest
    WHERE c.contype = 'f'
)
SELECT
    fd.parent_schema,
    fd.parent_table,
    fd.child_schema,
    fd.child_table,
    fd.constraint_name,
    -- Human readable mapping
    string_agg(
        format('%I → %I', 
            (SELECT attname FROM pg_attribute 
             WHERE attrelid = fd.parent_table_oid
               AND attnum = fd.parent_col),
            (SELECT attname FROM pg_attribute 
             WHERE attrelid = fd.child_table_oid
               AND attnum = fd.child_col)
        ), 
        ', ' ORDER BY fd.ord
    ) AS foreign_key_mapping,
    -- Structured data for trigger
    jsonb_object_agg(
        (SELECT attname FROM pg_attribute 
         WHERE attrelid = fd.parent_table_oid
           AND attnum = fd.parent_col),
        (SELECT attname FROM pg_attribute 
         WHERE attrelid = fd.child_table_oid
           AND attnum = fd.child_col)
    ) AS foreign_key_json,
    -- Arrays for easier processing
    array_agg(
        (SELECT attname FROM pg_attribute 
         WHERE attrelid = fd.parent_table_oid
           AND attnum = fd.parent_col)
        ORDER BY fd.ord
    ) AS parent_columns,
    array_agg(
        (SELECT attname FROM pg_attribute 
         WHERE attrelid = fd.child_table_oid
           AND attnum = fd.child_col)
        ORDER BY fd.ord
    ) AS child_columns,
    COUNT(*) AS column_count,
    fd.child_table_oid,
    fd.parent_table_oid,
    -- Check for active column in BOTH tables
    EXISTS (
        SELECT 1 FROM pg_attribute a
        WHERE a.attrelid = fd.parent_table_oid
          AND a.attname = 'active'
          AND NOT a.attisdropped
    ) AS parent_has_active,
    EXISTS (
        SELECT 1 FROM pg_attribute a
        WHERE a.attrelid = fd.child_table_oid
          AND a.attname = 'active'
          AND NOT a.attisdropped
    ) AS child_has_active
FROM fk_details fd
-- Only include relationships where BOTH tables have active column
WHERE EXISTS (
    SELECT 1 FROM pg_attribute a
    WHERE a.attrelid = fd.parent_table_oid
      AND a.attname = 'active'
      AND NOT a.attisdropped
) AND EXISTS (
    SELECT 1 FROM pg_attribute a
    WHERE a.attrelid = fd.child_table_oid
      AND a.attname = 'active'
      AND NOT a.attisdropped
)
GROUP BY 
    fd.parent_schema, fd.parent_table,
    fd.child_schema, fd.child_table,
    fd.constraint_name, fd.constraint_id, 
    fd.child_table_oid, fd.parent_table_oid
ORDER BY fd.parent_schema, fd.parent_table, fd.child_schema, fd.child_table;
```

To test the view above.

```
SELECT * FROM cascade_relationships_v 
WHERE parent_table = 'api_t' AND child_table = 'api_version_t';
```

And the result. 

```
parent_schema	parent_table	child_schema	child_table	constraint_name	foreign_key_mapping	foreign_key_json	parent_columns	child_columns	column_count	child_table_oid	parent_table_oid	parent_has_active	child_has_active
public	api_t	public	api_version_t	api_fkv2	host_id → host_id, api_id → api_id	{"api_id": "api_id", "host_id": "host_id"}	["host_id","api_id"]	["host_id","api_id"]	2	348265	348254	true	true

```


Create a function for update active to true and false. 

```
CREATE OR REPLACE FUNCTION dynamic_cascade_soft_operations()
RETURNS TRIGGER AS $$
DECLARE
    fk_record RECORD;
    where_clause TEXT;
    query_text TEXT;
    column_index INT;
    child_has_active BOOLEAN;
BEGIN
    -- Handle SOFT DELETE (active = false)
    IF NEW.active = FALSE AND OLD.active = TRUE THEN
        FOR fk_record IN
            SELECT *
            FROM cascade_relationships_v
            WHERE parent_schema = TG_TABLE_SCHEMA
              AND parent_table = TG_TABLE_NAME
        LOOP
            -- Double-check that child table has active column
            SELECT EXISTS (
                SELECT 1 FROM pg_attribute a
                WHERE a.attrelid = (
                    SELECT oid FROM pg_class 
                    WHERE relname = fk_record.child_table 
                      AND relnamespace = (SELECT oid FROM pg_namespace 
                                         WHERE nspname = fk_record.child_schema)
                )
                AND a.attname = 'active'
                AND NOT a.attisdropped
            ) INTO child_has_active;
            
            IF NOT child_has_active THEN
                CONTINUE;
            END IF;
            
            -- Build WHERE clause
            where_clause := '';
            FOR column_index IN 1..fk_record.column_count LOOP
                IF column_index > 1 THEN
                    where_clause := where_clause || ' AND ';
                END IF;
                where_clause := where_clause || format(
                    '%I = $1.%I',
                    fk_record.child_columns[column_index],
                    fk_record.parent_columns[column_index]
                );
            END LOOP;
            
            query_text := format(
                'UPDATE %I.%I SET active = FALSE 
                 WHERE %s AND active = TRUE',
                fk_record.child_schema,
                fk_record.child_table,
                where_clause
            );
            
            EXECUTE query_text USING OLD;
        END LOOP;
        
    -- Handle RESTORE (active = true)
    ELSIF NEW.active = TRUE AND OLD.active = FALSE THEN
        FOR fk_record IN
            SELECT *
            FROM cascade_relationships_v
            WHERE parent_schema = TG_TABLE_SCHEMA
              AND parent_table = TG_TABLE_NAME
        LOOP
            -- Double-check that child table has active column
            SELECT EXISTS (
                SELECT 1 FROM pg_attribute a
                WHERE a.attrelid = (
                    SELECT oid FROM pg_class 
                    WHERE relname = fk_record.child_table 
                      AND relnamespace = (SELECT oid FROM pg_namespace 
                                         WHERE nspname = fk_record.child_schema)
                )
                AND a.attname = 'active'
                AND NOT a.attisdropped
            ) INTO child_has_active;
            
            IF NOT child_has_active THEN
                CONTINUE;
            END IF;
            
            -- Build WHERE clause
            where_clause := '';
            FOR column_index IN 1..fk_record.column_count LOOP
                IF column_index > 1 THEN
                    where_clause := where_clause || ' AND ';
                END IF;
                where_clause := where_clause || format(
                    '%I = $1.%I',
                    fk_record.child_columns[column_index],
                    fk_record.parent_columns[column_index]
                );
            END LOOP;
            
            query_text := format(
                'UPDATE %I.%I SET active = TRUE 
                 WHERE %s AND active = FALSE',
                fk_record.child_schema,
                fk_record.child_table,
                where_clause
            );
            
            EXECUTE query_text USING OLD;
        END LOOP;
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
```


Install the trigger.

```
-- Apply cascade triggers only to tables that have active column
DO $$
DECLARE
    table_record RECORD;
    has_active_column BOOLEAN;
BEGIN
    FOR table_record IN
        SELECT 
            n.nspname AS schema_name,
            c.relname AS table_name,
            c.oid AS table_oid
        FROM pg_class c
        JOIN pg_namespace n ON c.relnamespace = n.oid
        WHERE c.relkind = 'r'  -- Regular tables only
          AND n.nspname NOT IN ('pg_catalog', 'information_schema')
          AND EXISTS (
              -- Has at least one foreign key constraint where it's the referenced table
              SELECT 1 FROM pg_constraint con
              JOIN pg_class ref ON con.confrelid = ref.oid
              WHERE con.contype = 'f'
                AND ref.oid = c.oid
          )
    LOOP
        -- Check if table has active column
        SELECT EXISTS (
            SELECT 1 FROM pg_attribute a
            WHERE a.attrelid = table_record.table_oid
              AND a.attname = 'active'
              AND NOT a.attisdropped
        ) INTO has_active_column;
        
        IF NOT has_active_column THEN
            RAISE NOTICE 'Skipping %.% - no active column', 
                table_record.schema_name, table_record.table_name;
            CONTINUE;
        END IF;
        
        -- Drop existing trigger if it exists
        EXECUTE format(
            'DROP TRIGGER IF EXISTS trg_cascade_soft_ops ON %I.%I',
            table_record.schema_name, table_record.table_name
        );
        
        -- Create new trigger
        EXECUTE format(
            'CREATE TRIGGER trg_cascade_soft_ops
             AFTER UPDATE OF active ON %I.%I
             FOR EACH ROW
             EXECUTE FUNCTION dynamic_cascade_soft_operations()',
            table_record.schema_name, table_record.table_name
        );
        
        RAISE NOTICE 'Created cascade trigger on %.%', 
            table_record.schema_name, table_record.table_name;
    END LOOP;
END $$;
```

And here is the result.

```
NOTICE:  trigger "trg_cascade_soft_ops" for relation "public.tag_t" does not exist, skipping
NOTICE:  Created cascade trigger on public.tag_t
NOTICE:  trigger "trg_cascade_soft_ops" for relation "public.category_t" does not exist, skipping
NOTICE:  Created cascade trigger on public.category_t
NOTICE:  trigger "trg_cascade_soft_ops" for relation "public.api_t" does not exist, skipping
NOTICE:  Created cascade trigger on public.api_t
NOTICE:  trigger "trg_cascade_soft_ops" for relation "public.api_version_t" does not exist, skipping
NOTICE:  Created cascade trigger on public.api_version_t
NOTICE:  trigger "trg_cascade_soft_ops" for relation "public.api_endpoint_t" does not exist, skipping
NOTICE:  Created cascade trigger on public.api_endpoint_t
NOTICE:  trigger "trg_cascade_soft_ops" for relation "public.api_endpoint_scope_t" does not exist, skipping
NOTICE:  Created cascade trigger on public.api_endpoint_scope_t
NOTICE:  trigger "trg_cascade_soft_ops" for relation "public.config_property_t" does not exist, skipping
NOTICE:  Created cascade trigger on public.config_property_t
NOTICE:  trigger "trg_cascade_soft_ops" for relation "public.platform_t" does not exist, skipping
NOTICE:  Created cascade trigger on public.platform_t
NOTICE:  trigger "trg_cascade_soft_ops" for relation "public.pipeline_t" does not exist, skipping
NOTICE:  Created cascade trigger on public.pipeline_t
NOTICE:  trigger "trg_cascade_soft_ops" for relation "public.instance_t" does not exist, skipping
NOTICE:  Created cascade trigger on public.instance_t
NOTICE:  trigger "trg_cascade_soft_ops" for relation "public.deployment_instance_t" does not exist, skipping
NOTICE:  Created cascade trigger on public.deployment_instance_t
NOTICE:  trigger "trg_cascade_soft_ops" for relation "public.instance_api_t" does not exist, skipping
NOTICE:  Created cascade trigger on public.instance_api_t
NOTICE:  trigger "trg_cascade_soft_ops" for relation "public.instance_app_t" does not exist, skipping
NOTICE:  Created cascade trigger on public.instance_app_t
NOTICE:  trigger "trg_cascade_soft_ops" for relation "public.app_t" does not exist, skipping
NOTICE:  Created cascade trigger on public.app_t
NOTICE:  trigger "trg_cascade_soft_ops" for relation "public.instance_app_api_t" does not exist, skipping
NOTICE:  Created cascade trigger on public.instance_app_api_t
NOTICE:  trigger "trg_cascade_soft_ops" for relation "public.product_version_t" does not exist, skipping
NOTICE:  Created cascade trigger on public.product_version_t
NOTICE:  trigger "trg_cascade_soft_ops" for relation "public.config_t" does not exist, skipping
NOTICE:  Created cascade trigger on public.config_t
NOTICE:  trigger "trg_cascade_soft_ops" for relation "public.deployment_t" does not exist, skipping
NOTICE:  Created cascade trigger on public.deployment_t
NOTICE:  trigger "trg_cascade_soft_ops" for relation "public.org_t" does not exist, skipping
NOTICE:  Created cascade trigger on public.org_t
NOTICE:  trigger "trg_cascade_soft_ops" for relation "public.host_t" does not exist, skipping
NOTICE:  Created cascade trigger on public.host_t
NOTICE:  trigger "trg_cascade_soft_ops" for relation "public.ref_table_t" does not exist, skipping
NOTICE:  Created cascade trigger on public.ref_table_t
NOTICE:  trigger "trg_cascade_soft_ops" for relation "public.ref_value_t" does not exist, skipping
NOTICE:  Created cascade trigger on public.ref_value_t
NOTICE:  trigger "trg_cascade_soft_ops" for relation "public.relation_type_t" does not exist, skipping
NOTICE:  Created cascade trigger on public.relation_type_t
NOTICE:  trigger "trg_cascade_soft_ops" for relation "public.user_t" does not exist, skipping
NOTICE:  Created cascade trigger on public.user_t
NOTICE:  trigger "trg_cascade_soft_ops" for relation "public.user_host_t" does not exist, skipping
NOTICE:  Created cascade trigger on public.user_host_t
NOTICE:  Skipping public.customer_t - no active column
NOTICE:  Skipping public.employee_t - no active column
NOTICE:  trigger "trg_cascade_soft_ops" for relation "public.position_t" does not exist, skipping
NOTICE:  Created cascade trigger on public.position_t
NOTICE:  trigger "trg_cascade_soft_ops" for relation "public.role_t" does not exist, skipping
NOTICE:  Created cascade trigger on public.role_t
NOTICE:  trigger "trg_cascade_soft_ops" for relation "public.group_t" does not exist, skipping
NOTICE:  Created cascade trigger on public.group_t
NOTICE:  trigger "trg_cascade_soft_ops" for relation "public.attribute_t" does not exist, skipping
NOTICE:  Created cascade trigger on public.attribute_t
NOTICE:  trigger "trg_cascade_soft_ops" for relation "public.auth_provider_t" does not exist, skipping
NOTICE:  Created cascade trigger on public.auth_provider_t
NOTICE:  trigger "trg_cascade_soft_ops" for relation "public.auth_client_t" does not exist, skipping
NOTICE:  Created cascade trigger on public.auth_client_t
NOTICE:  Skipping public.config_snapshot_t - no active column
NOTICE:  trigger "trg_cascade_soft_ops" for relation "public.worklist_t" does not exist, skipping
NOTICE:  Created cascade trigger on public.worklist_t
NOTICE:  Skipping public.process_info_t - no active column
NOTICE:  Skipping public.task_info_t - no active column
NOTICE:  trigger "trg_cascade_soft_ops" for relation "public.rule_t" does not exist, skipping
NOTICE:  Created cascade trigger on public.rule_t
```



### 3. Special Handler for deletion of Host and Org 

Due to the significant tables that needs to be updated when deleting a host or an org, we need to rely on the cascade delete of the database. So deletion of host or org will be implemented as hard delete and it should be warned to users on the UI interface. 

### 4. Add delete_at column to reverse cascade soft delete

After cascade soft delete for role_t, all children entities will be marked as active = false. When add back the same role again, we need to mark all the cascade delete children entities to active = true. However, we need to avoid updating the rows that were soft deleted individually. By adding a delete_ts, we can use it to find out all related children entities that are cascade deleted. 

### 5. Update queries to add active = true condition

We need to update some queries in the db provider to add conditions for each joining table with active = true so that only active rows will be returned. 


**Conclusion:**

