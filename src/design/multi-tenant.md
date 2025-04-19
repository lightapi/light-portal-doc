# Multi-Tenant

## Database Schema

Adding a host_id to every table is one approach, but it does lead to composite primary keys and can impact performance. Using UUIDs as primary keys, even in a multi-tenant environment, is another viable option with its own set of trade-offs. Let's examine both strategies:

1. Host ID on Every Table (Composite Primary Keys)

Schema: Each table would have a host_id column, and the primary key would be a combination of host_id and another unique identifier (e.g., user_id, endpoint_id).

```
CREATE TABLE user_t (
    host_id UUID NOT NULL,  -- References hosts table
    user_id INT NOT NULL, 
    -- ... other columns
    PRIMARY KEY (host_id, user_id),
    FOREIGN KEY (host_id) REFERENCES hosts_t(host_id)
);
```

Pros:

* Data Isolation: Clear separation of data at the database level. Easy to query data for a specific tenant.

* Backup/Restore: Simplified backup and restore procedures for individual tenants.

Cons:

* Composite Primary Keys: Can lead to more complex queries, especially joins, as you always need to include the host_id. Can affect query optimizer performance.

* Storage Overhead: host_id is repeated in every row of every table, adding storage overhead.

* Index Impact: Composite indexes can sometimes be less efficient than single-column indexes.

2. UUIDs as Primary Keys (Shared Tables)

Schema: Tables use UUIDs as primary keys. A separate table (tenant_resources_t) maps UUIDs to tenants.

```
CREATE TABLE user_t (
    user_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    -- ... other columns
);


CREATE TABLE tenant_resource_t(
    host_id UUID NOT NULL,
    resource_type varchar(255) NOT NULL, --e.g., 'user', 'api_endpoint'
    resource_id UUID NOT NULL,
    PRIMARY KEY(host_id, resource_type, resource_id),
    FOREIGN KEY (host_id) REFERENCES hosts_t(host_id)
);
```

Pros:

* Simplified Primary Keys: Easier to manage single-column UUID primary keys. Simpler joins.

* Reduced Storage Overhead: No need to repeat host_id in every table.

* Application Logic: Multi-tenancy is handled mostly in the application logic by querying tenant_resources_t to ensure a user belongs to the correct tenant, adding a layer of flexibility. (This is also a con if not carefully implemented.)

Cons:

* Data Isolation (slightly reduced): Data is logically separated but resides in shared tables. Robust application logic is essential to prevent data leakage between tenants.

* Backup/Restore (more complex): Backing up/restoring for a single tenant requires filtering based on the tenant_resources_t table.

* Query Performance (potential issue): Queries might require joining with tenant_resources_t table which will add a bit overhead. Proper indexing and query optimization become crucial.

3. Hybrid Approach (Recommended in many cases)

* Combine the strengths of both approaches.

* Use UUIDs as primary keys for most tables for simplicity.

* Add host_id to tables where data isolation is paramount (e.g., tables containing sensitive financial or personal data) or where frequent tenant-specific queries are performed. This provides a more granular level of control and allows for optimized queries when needed.

* Use the tenant_resources_t table to maintain an overview of which resources belong to which tenant, supporting the application logic's multi-tenancy enforcement.

Choosing the Right Strategy:

* Small Number of Tenants, Low Data Volume: UUIDs might be sufficient.

* Strict Data Isolation Requirements, Frequent Tenant-Specific Queries, High Data Volume: host_id on every relevant table or a hybrid approach is often preferable.

* Flexibility in Multi-Tenancy Implementation: Favors the UUID approach or Hybrid approach, with logic predominantly handled in the application layer.

Additional Considerations:

* Database Support: Check if database (PostgreSQL) has specific features for multi-tenancy.

* Indexing: Carefully plan indexes for optimal performance in any multi-tenant scenario.

* Schema Design: Consider creating views for tenant-specific data access to simplify queries in the application layer.

* Security: Implement robust security measures to prevent data leakage between tenants, regardless of the chosen approach.

The hybrid approach usually provides the best balance between performance, data isolation, and development complexity in real-world multi-tenant applications. You have more direct control where strict isolation is required and can maintain the simplicity of UUIDs where it's beneficial. Using tenant_resources_t for application logic enforcement offers flexibility and a central point of management for tenant resource association. This approach also prepares the application for potential future expansion and different multi-tenancy demands as the application grows.

## Citus PostgreSQL Extension

Citus, now fully integrated into PostgreSQL as a distributed database extension, can be very helpful in scaling your multi-tenant application, especially if you anticipate significant data growth and high query loads. Here's how Citus can fit into your use case and the factors to consider:

#### How Citus Helps:

* Horizontal Scalability: Citus allows you to distribute the data across multiple PostgreSQL nodes (servers), enabling horizontal scaling. This is crucial for handling increasing data volumes and query loads in a multi-tenant environment.

* Improved Query Performance: By distributing data and queries, Citus can significantly improve the performance of many types of queries, especially analytical queries that operate on large datasets. This is particularly beneficial if we have tenants with substantially different data volumes or query patterns.

* Shard Placement by Tenant: One of the most effective ways to use Citus for multi-tenancy is to shard the data by host_id (or a tenant ID). This means that all data for a given tenant resides on the same shard (a subset of the distributed database). This allows for efficient tenant isolation and simplifies queries for tenant-specific data.

* Simplified Multi-Tenant Queries: When sharding by tenant, queries that filter by host_id become very efficient because Citus can route them directly to the appropriate shard. This eliminates the need for expensive scans across the entire database.

* Flexibility: Citus supports various sharding strategies, allowing you to choose the best approach for the data and query patterns. You can even use a hybrid approach, distributing some tables while keeping others replicated across all nodes for faster access to shared data.

Example (Sharding by Tenant):

Create a distributed table: When creating tables (e.g., user_t, api_endpoint_t, etc.), we would declare them as distributed tables in Citus, using the host_id as the distribution column:

```
CREATE TABLE user_t (
    host_id UUID NOT NULL,
    user_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    -- ... other columns
) DISTRIBUTE BY HASH (host_id);
```

Querying: When querying data for a specific tenant, include the host_id in the WHERE clause:

```
SELECT * FROM users_t WHERE host_id = 'your-tenant-id';
```

Citus will automatically route this query to the shard containing the data for that tenant, resulting in much faster query execution.

#### Citus Cost:

* Citus Open Source: The Citus open-source extension is free to use and is included in the PostgreSQL distribution. We can self-host and manage it.

* Azure CosmosDB for PostgreSQL (Managed Citus): Microsoft offers a fully managed cloud service called Azure CosmosDB for PostgreSQL, which is built on Citus. This service has usage-based pricing, and the cost depends on factors like the number of nodes, storage, and compute resources used. This managed option reduces the operational overhead of managing Citus yourself.

#### Recommendation:

Don't automatically add host_id to every table just because we are using Citus. Carefully analyze the data model, query patterns, and multi-tenancy requirements.

* Distribute tables by host_id (tenant ID) when data locality and isolation are paramount, and we want to optimize tenant-specific queries.

* Consider replicating smaller, frequently joined tables to avoid unnecessary joins and host_id overhead.

* Use a central mapping table (tenant_resources_t) to manage tenant-resource associations and enforce multi-tenancy rules in the application logic where appropriate.

This more nuanced approach provides a balance between the benefits of distributed data with Citus and avoiding unnecessary complexity or performance overhead from overusing host_id. Choose the Citus deployment model (self-hosted open source or managed cloud service) that best suits our needs and budget.

#### Primary Key Considerations in a Distributed Citus Environment

When a table includes `host_id` (due to sharding requirements), it is important to include `host_id` as part of the primary key. This ensures proper functioning and optimization within the Citus distributed database.

1. **Distribution Column Requirement**  
   In Citus, the distribution column (e.g., `host_id`) must be part of the primary key. This is essential for routing queries and distributing data correctly across shards.

2. **Uniqueness Enforcement**  
   - The primary key enforces uniqueness across the entire distributed database.  
   - For example, if `user_id` is unique only within a tenant (host), then `(host_id, user_id)` is required as the primary key to ensure uniqueness across all shards.

3. **Data Locality and Co-location**  
   Including `host_id` in the primary key ensures that all rows for the same tenant (identified by the same `host_id`) are stored together on a single shard. This provides:  
   - **Efficient Joins**: Joins between tables related to the same tenant can be performed locally on a single shard, avoiding expensive cross-shard data transfers.  
   - **Optimized Queries**: Queries filtering by `host_id` are efficiently routed to the appropriate shard.

4. **Referential Integrity**  
   If other tables reference the `users_t` table and are also distributed by `host_id`, including `host_id` in the primary key of `users_t` is essential to maintain referential integrity across shards.


## Multi-Host User Session Management

In a multi-host environment where multiple hosts reside on the same server, users must associate with one host at a time. The session management is handled as follows:

1. **Host Association on Login**:  
   - Once a user logs in, a **host cookie** is returned, derived from the JWT token.  
   - The user's session defaults to the associated host in the cookie.

2. **Switching Hosts**:  
   - If a user wishes to switch to another host, they can:
     - Access the **User Menu** to select a different host.
     - Log out of the current session.
   - During the next login, the session will be tied to the newly selected host.

3. **Host in API Requests**:  
   - For all API requests sent to the server, the host is typically included as part of the request payload.
   - For login users, the host is in the JWT token as a custom claim.
   - For guest users, the default host is used until the user is signed in.
   - This ensures proper routing and handling of requests in a multi-host environment.

By associating users to a specific host for each session, this approach ensures clear separation of data and responsibilities across hosts, while providing users the flexibility to switch hosts as needed.


## Event Header

As the portal is based on the event sorucing, all events will be responsible for populating the database. So, they need to be separated by host_id as well. In the event header, we have one unique id which is generated when event is created. Also, it has host_id and user_id in the EventId which is included in every events. 

## Reference and Shared Tables

In an application there are some data that is shared by all tenants. For example, the dropdown options on the UI and business validation. We call them reference data and have defined several tables to manage them centrally. For each reference data type, there is a logical table defined in the ref_table_t and marked as common or not. Common means the table can be shared with other tenants. Otherwise, it is only private for the owner tenant. 

Some other entities are very similar but they cannot be fit into the reference tables. For example, category_t table contains all the category definitions for different entities. These tables are designed with an optional host_id. Here is an exmaple. 

```
CREATE TABLE category_t (
    category_id          VARCHAR(22) NOT NULL,   -- unique id to identify the category
    host_id              VARCHAR(22),            -- null mean global category
    entity_type          VARCHAR(50) NOT NULL,   -- the version of the schema
    category_name        VARCHAR(126) NOT NULL,  -- category name, must be url friendly.
    category_desc        VARCHAR(1024) NOT NULL, -- decription
    parent_category_id   VARCHAR(22) REFERENCES category_t(category_id) ON DELETE SET NULL, -- parent category id, null if there is no parent.
    sort_order           INT DEFAULT 0,          -- sort order on the UI
    update_user          VARCHAR (255) DEFAULT SESSION_USER NOT NULL,
    update_ts            TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    PRIMARY KEY (category_id)
);

-- 1. Unique index for GLOBAL categories (where host_id IS NULL)
-- Ensures uniqueness of (entity_type, category_name, parent_category_id) ONLY when host_id is NULL
CREATE UNIQUE INDEX idx_category_unique_global
ON category_t (entity_type, category_name, parent_category_id)
NULLS NOT DISTINCT -- Handles NULLs in parent_category_id correctly
WHERE host_id IS NULL;

-- 2. Unique index for TENANT-SPECIFIC categories (where host_id IS NOT NULL)
-- Ensures uniqueness of (host_id, entity_type, category_name, parent_category_id)
-- for rows that belong to a specific host.
CREATE UNIQUE INDEX idx_category_unique_tenant
ON category_t (host_id, entity_type, category_name, parent_category_id)
NULLS NOT DISTINCT -- Handles NULLs in parent_category_id correctly
WHERE host_id IS NOT NULL;


CREATE INDEX idx_category_entity_type ON category_t (entity_type);
CREATE INDEX idx_category_parent ON category_t (parent_category_id);
CREATE INDEX idx_category_name ON category_t (category_name);
CREATE INDEX idx_category_host_id ON category_t (host_id);

```

On the UI, the host_id will be auto populated according to the associated host_id by the user in readonly mode. There is a checkbox "Is Global Category" in the form. If checked, the backend service will have an FGA rule to ensure that the user is admin and the host_id will be removed in the event. This works for both create and update. 

When viewing categories, the super admin might see all categories by default, possibly with a column or indicator showing the host_id (or "Global"). Filters should allow viewing global only, or a specific tenant's categories.

Tenant Admin / Host Owner:

When a tenant admin accesses the category management UI, their context is fixed to their own host_id.

They should only be able to create/edit categories associated with their specific host_id.

The UI should not offer them the option to create/edit global categories or categories for other hosts. The host_id is implicitly set or displayed as read-only based on their logged-in context.

When viewing categories, they should see their own tenant-specific categories plus all applicable global categories. The UI should clearly differentiate between these (e.g., using grouping, labels, icons).







