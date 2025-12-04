# Cascade Soft Delete

With the recent refactor, relying on `ON DELETE CASCADE` is no longer suitable after implementing **soft deletes**, because soft delete is an `UPDATE` operation (`SET active = FALSE`) and not a true `DELETE` from the database.

The pattern we should follow in an **Event Sourcing / Event-Driven Architecture** with soft deletes is:

### 1. The Principle of Causality (or Domain Consistency)

When a parent entity (e.g., `role_t`) is soft-deleted, all its dependent children entities (e.g., `role_user_t`, `role_permission_t`, etc.) must also be soft-deleted to maintain domain consistency. This cascade logic must be implemented **in the application layer** (the projection service or command handler or database).

### 2. Implementation in the Command/Event Handler/Database

#### Strategy A: Event Amplification

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
-- create a view to simplify the foreign key relationship. 

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
    -- Check for required columns
    EXISTS (
        SELECT 1 FROM pg_attribute a
        WHERE a.attrelid = fd.parent_table_oid
          AND a.attname = 'delete_ts'
          AND NOT a.attisdropped
    ) AS parent_has_delete_ts,
    EXISTS (
        SELECT 1 FROM pg_attribute a
        WHERE a.attrelid = fd.child_table_oid
          AND a.attname = 'delete_ts'
          AND NOT a.attisdropped
    ) AS child_has_delete_ts,
    EXISTS (
        SELECT 1 FROM pg_attribute a
        WHERE a.attrelid = fd.parent_table_oid
          AND a.attname = 'delete_user'
          AND NOT a.attisdropped
    ) AS parent_has_delete_user,
    EXISTS (
        SELECT 1 FROM pg_attribute a
        WHERE a.attrelid = fd.child_table_oid
          AND a.attname = 'delete_user'
          AND NOT a.attisdropped
    ) AS child_has_delete_user
FROM fk_details fd
-- Only include relationships where both tables have deletion tracking
WHERE EXISTS (
    SELECT 1 FROM pg_attribute a
    WHERE a.attrelid = fd.parent_table_oid
      AND a.attname = 'delete_ts'
      AND NOT a.attisdropped
) AND EXISTS (
    SELECT 1 FROM pg_attribute a
    WHERE a.attrelid = fd.child_table_oid
      AND a.attname = 'delete_ts'
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
parent_schema parent_table child_schema child_table   constraint_name                   foreign_key_mapping                foreign_key_json                           parent_columns       child_columns        column_count child_table_oid parent_table_oid parent_has_delete_ts child_has_delete_ts parent_has_delete_user child_has_delete_user 
------------- ------------ ------------ ------------- --------------------------------- ---------------------------------- ------------------------------------------ -------------------- -------------------- ------------ --------------- ---------------- -------------------- ------------------- ---------------------- --------------------- 
public        api_t        public       api_version_t api_version_t_host_id_api_id_fkey host_id → host_id, api_id → api_id {"api_id": "api_id", "host_id": "host_id"} ["host_id","api_id"] ["host_id","api_id"] 2            360279          360268           true                 true                true                   true                  

```


Create a function for update active to true and false. 

```
CREATE OR REPLACE FUNCTION smart_cascade_soft_delete()
RETURNS TRIGGER AS $$
DECLARE
    fk_record RECORD;
    where_clause TEXT;
    query_text TEXT;
    column_index INT;
    current_user_name TEXT;
    deletion_context TEXT;
    deletion_context_pattern TEXT;
    delete_timestamp TIMESTAMP;
BEGIN
    -- Get current user
    current_user_name := current_user;
    
    -- Handle SOFT DELETE (active = false)
    IF NEW.active = FALSE AND OLD.active = TRUE THEN
        -- Generate deletion timestamp
        delete_timestamp := CURRENT_TIMESTAMP;
        
        -- Set deletion context
        deletion_context := format('PARENT_CASCADE_%s_%s', 
            TG_TABLE_NAME, 
            to_char(delete_timestamp, 'YYYYMMDD_HH24MISSMS')
        );
        
        -- Update parent with deletion context if columns exist
        IF EXISTS (
            SELECT 1 FROM information_schema.columns 
            WHERE table_schema = TG_TABLE_SCHEMA 
              AND table_name = TG_TABLE_NAME 
              AND column_name = 'delete_user'
        ) THEN
            NEW.delete_user := deletion_context;
        END IF;
        
        IF EXISTS (
            SELECT 1 FROM information_schema.columns 
            WHERE table_schema = TG_TABLE_SCHEMA 
              AND table_name = TG_TABLE_NAME 
              AND column_name = 'delete_ts'
        ) THEN
            NEW.delete_ts := delete_timestamp;
        END IF;
        
        -- Update parent's update columns
        NEW.update_ts := delete_timestamp;
        NEW.update_user := current_user_name;
        
        FOR fk_record IN
            SELECT *
            FROM cascade_relationships_v
            WHERE parent_schema = TG_TABLE_SCHEMA
              AND parent_table = TG_TABLE_NAME
        LOOP
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
            
            -- Add condition to only update currently active records
            where_clause := where_clause || ' AND active = TRUE';
            
            -- Cascade the soft delete with context
            query_text := format(
                'UPDATE %I.%I 
                 SET active = FALSE,
                     delete_ts = $2, 
                     delete_user = $3,
                     update_ts = $2,
                     update_user = $4
                 WHERE %s',
                fk_record.child_schema,
                fk_record.child_table,
                where_clause
            );
            
            EXECUTE query_text USING OLD, delete_timestamp, deletion_context, current_user_name;
        END LOOP;
        
    -- Handle RESTORE (active = true)
    ELSIF NEW.active = TRUE AND OLD.active = FALSE THEN
        -- Only restore children that were deleted by parent cascade
        
        FOR fk_record IN
            SELECT *
            FROM cascade_relationships_v
            WHERE parent_schema = TG_TABLE_SCHEMA
              AND parent_table = TG_TABLE_NAME
        LOOP
            -- Pattern to match cascade deletions
            deletion_context_pattern := format('PARENT_CASCADE_%s_%%', TG_TABLE_NAME);
            
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
            
            -- Only restore cascade-deleted records
            where_clause := where_clause || 
                ' AND delete_user LIKE $2 AND active = FALSE';
            
            -- Restore the records
            query_text := format(
                'UPDATE %I.%I 
                 SET active = TRUE,
                     delete_ts = NULL, 
                     delete_user = NULL,
                     update_ts = CURRENT_TIMESTAMP,
                     update_user = $3
                 WHERE %s',
                fk_record.child_schema,
                fk_record.child_table,
                where_clause
            );
            
            EXECUTE query_text USING OLD, deletion_context_pattern, current_user_name;
        END LOOP;
        
        -- Clear parent's deletion context
        IF EXISTS (
            SELECT 1 FROM information_schema.columns 
            WHERE table_schema = TG_TABLE_SCHEMA 
              AND table_name = TG_TABLE_NAME 
              AND column_name = 'delete_user'
        ) THEN
            NEW.delete_user := NULL;
        END IF;
        
        IF EXISTS (
            SELECT 1 FROM information_schema.columns 
            WHERE table_schema = TG_TABLE_SCHEMA 
              AND table_name = TG_TABLE_NAME 
              AND column_name = 'delete_ts'
        ) THEN
            NEW.delete_ts := NULL;
        END IF;
        
        -- Update parent's update columns
        NEW.update_ts := CURRENT_TIMESTAMP;
        NEW.update_user := current_user_name;
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
```


Install the trigger.

```
-- Apply cascade triggers only to tables that have BOTH active AND delete_ts columns
DO $$
DECLARE
    table_record RECORD;
    has_active_column BOOLEAN;
    has_delete_ts_column BOOLEAN;
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
              SELECT 1 FROM pg_constraint con
              JOIN pg_class ref ON con.confrelid = ref.oid
              WHERE con.contype = 'f'
                AND ref.oid = c.oid
          )
    LOOP
        -- Check if table has required columns
        SELECT EXISTS (
            SELECT 1 FROM pg_attribute a
            WHERE a.attrelid = table_record.table_oid
              AND a.attname = 'active'
              AND NOT a.attisdropped
        ) INTO has_active_column;
        
        SELECT EXISTS (
            SELECT 1 FROM pg_attribute a
            WHERE a.attrelid = table_record.table_oid
              AND a.attname = 'delete_ts'
              AND NOT a.attisdropped
        ) INTO has_delete_ts_column;
        
        IF NOT (has_active_column AND has_delete_ts_column) THEN
            RAISE NOTICE 'Skipping %.% - missing required columns (active: %, delete_ts: %)', 
                table_record.schema_name, table_record.table_name,
                has_active_column, has_delete_ts_column;
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
             EXECUTE FUNCTION smart_cascade_soft_delete()',
            table_record.schema_name, table_record.table_name
        );
        
        RAISE NOTICE 'Created cascade trigger on %.%', 
            table_record.schema_name, table_record.table_name;
    END LOOP;
END $$;
```

The above appoach has the following benefits.

* Clean separation: delete_ts/delete_user are dedicated to soft delete tracking

* Clear semantics: Easy to understand and query

* No interference: Doesn't conflict with update_ts/update_user for normal updates

* Intelligent restoration: Can restore only cascade-deleted records

* Audit trail: Complete history of who deleted what and when


This approach ensures you only restore child entities that were cascade-deleted, maintaining data integrity while providing a clear audit trail.


### 3. Special Handler for deletion of Host and Org 

Due to the significant tables that needs to be updated when deleting a host or an org, we need to rely on the cascade delete of the database. So deletion of host or org will be implemented as hard delete and it should be warned to users on the UI interface. 

### 4. Add delete_ts column to reverse cascade soft delete

After cascade soft delete for role_t, all children entities will be marked as active = false. When add back the same role again, we need to mark all the cascade delete children entities to active = true. However, we need to avoid updating the rows that were soft deleted individually. By adding a delete_ts, we can use it to find out all related children entities that are cascade deleted. 

### 5. Update queries to add active = true condition

We need to update some queries in the db provider to add conditions for each joining table with active = true so that only active rows will be returned. 


**Conclusion:**

Based on our team discussion, we are going to: 

* Adopt the third option that use db trigger to do that same like the hard cascade delete. 
* Change the org and host delete to hard delete. 
* Update some queries to add condition to check the active = true. 
