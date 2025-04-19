# Tag

Let's design a tagging system for your light-portal entities. Tags are typically non-hierarchical keywords or labels that you can assign to entities for flexible organization and discovery, complementing categories.

**1. Database Design (PostgreSQL)**

For a flexible and efficient tagging system, we'll use two main tables: a central `tags` table and a join table `entity_tags` to create a many-to-many relationship between entities and tags.

**a) `tag` Table:**
Stores the definitions of the tags themselves.

```sql
CREATE TABLE tag_t (
    tag_id        VARCHAR(22) NOT NULL,         -- Unique ID for the tag
    host_id       VARCHAR(22),                  -- null means global tag 
    tag_name      VARCHAR(100) UNIQUE NOT NULL, -- Tag name (e.g., "featured", "urgent", "api", "documentation") - Enforce uniqueness
    tag_desc      VARCHAR(1024),                -- Optional description of the tag
    update_user   VARCHAR(255) DEFAULT SESSION_USER NOT NULL,
    update_ts     TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    PRIMARY KEY (tag_id)
);

-- Index for efficient lookup by tag_name (common search/filter)
CREATE INDEX idx_tags_tag_name ON tags_t (tag_name);
```

*   **`tag_id`**: Unique identifier for each tag.
*   **`tag_name`**: The actual tag value (e.g., "featured").  `UNIQUE NOT NULL` constraint ensures tag names are unique across the system (global tags in this design).
*   **`tag_desc`**: Optional description for the tag.
*   **`update_user`, `update_ts`**: Standard audit columns.
*   **`UNIQUE (tag_name)`**: Important constraint to ensure tag names are unique. This makes tag management simpler and consistent.

**b) `entity_tags_t` Join Table (Many-to-Many Relationship):**
Links entities to tags.

```sql
CREATE TABLE entity_tags_t (
    entity_id   VARCHAR(22) NOT NULL,      -- ID of the entity (schema, product, document, etc.)
    entity_type VARCHAR(50) NOT NULL,     -- Type of the entity ('schema', 'product', 'document', etc.)
    tag_id      VARCHAR(22) NOT NULL REFERENCES tags_t(tag_id) ON DELETE CASCADE, -- Foreign key to tags_t

    PRIMARY KEY (entity_id, entity_type, tag_id) -- Composite primary key to prevent duplicate tag assignments to the same entity
);

-- Indexes for efficient queries
CREATE INDEX idx_entity_tags_tag_id ON entity_tags_t (tag_id);        -- Find entities by tag
CREATE INDEX idx_entity_tags_entity ON entity_tags_t (entity_id, entity_type); -- Find tags for an entity
```

*   **`entity_id`**:  ID of the entity being tagged.
*   **`entity_type`**: Type of the entity (must match the types you use for categories and other entity-related tables).
*   **`tag_id`**: Foreign key referencing the `tags_t` table.
*   **Composite Primary Key (`entity_id`, `entity_type`, `tag_id`)**: Ensures that an entity of a specific type cannot be associated with the same tag multiple times.
*   **`ON DELETE CASCADE`**: If a tag is deleted from `tags_t`, all associations in `entity_tags_t` are automatically removed. Consider `ON DELETE RESTRICT` if you want to prevent tag deletion if it's still in use.

**2. Service Endpoints**

You'll need service endpoints to manage tags themselves and to manage the associations between tags and entities.

**a) Tag Management Endpoints (Likely in a `TagService` or Admin-Specific Service):**

*   **POST /tags** - Create a new tag
    *   Request Body (JSON):
        ```json
        {
          "tagId": "uniqueTagId123",  // Optional - let backend generate if not provided
          "tagName": "featured",      // Required - unique tag name
          "tagDesc": "Items that are highlighted or promoted" // Optional
        }
        ```
    *   Response: 201 Created, with Location header (URL of the new tag) and response body (created tag JSON).
*   **GET /tags** - List all tags (with pagination, filtering, sorting - similar to `getCategory` endpoint)
    *   Query Parameters: `offset`, `limit`, `tagName`, `tagDesc`, etc.
    *   Response: 200 OK, JSON array of tag objects (with `total` count).
*   **GET /tags/{tagId}** - Get a specific tag by ID
    *   Path Parameter: `tagId`
    *   Response: 200 OK, tag object in JSON. 404 Not Found if not exists.
*   **PUT /tags/{tagId}** - Update an existing tag
    *   Path Parameter: `tagId`
    *   Request Body (JSON):  (Same structure as POST, but `tagId` in the path is used for identification)
    *   Response: 200 OK, updated tag object in JSON. 404 Not Found if tag not found.
*   **DELETE /tags/{tagId}** - Delete a tag
    *   Path Parameter: `tagId`
    *   Response: 204 No Content. 404 Not Found if tag not found.

**b) Entity Tag Association Endpoints (Likely within Entity-Specific Services like `SchemaService`, `ProductService`):**

*   **(Within POST /schemas, PUT /schemas/{schemaId}, etc. entity creation/update endpoints):**
    *   Request Body for creating or updating an entity should include a field (e.g., `tagIds`: `["tagId1", "tagId2"]`) to specify the tags to associate with the entity.
    *   Service logic (like in the updated `createSchema` and `updateSchema` methods) will handle updating the `entity_tags_t` table (deleting old links and inserting new ones) within the same transaction as the entity creation/update.
*   **GET /schemas/{schemaId}/tags** (or `/products/{productId}/tags`, etc.) - Get tags associated with a specific entity
    *   Path Parameter: `schemaId` (or `productId`, etc.)
    *   Response: 200 OK, JSON array of tag objects associated with the entity.
*   **PUT /schemas/{schemaId}/tags** (or similar) -  Replace tags associated with an entity (Less common, often handled within the entity update endpoint directly)
    *   Path Parameter: `schemaId`
    *   Request Body (JSON):  `{ "tagIds": ["tagIdA", "tagIdB"] }` - list of tag IDs to associate.
    *   Response: 200 OK, updated entity object (or just 204 No Content).

**c) Entity Filtering/Search Endpoints:**

*   **GET /schemas** (or `/products`, `/documents`, etc.) - List entities, now with tag filtering:
    *   Query Parameter: `tagNames` (or `tagIds`, or `tags` - choose one and be consistent), e.g., `tagNames=featured,api&tagNames=urgent` (multiple tags to filter by).
    *   Backend logic: Modify the `getSchema` (or `getProduct`, `getDocument`, etc.) service methods to:
        1.  Parse the `tagNames` parameter (could be comma-separated, multiple parameters, etc.).
        2.  Modify the SQL query to include a `JOIN` with `entity_tags_t` and `tags_t` and add a `WHERE` clause to filter by the provided tag names.  You might need to use `EXISTS` or `IN` subqueries for efficient filtering by multiple tags.

**Example Query for Filtering Schemas by Tags (using PostgreSQL `EXISTS`):**

```sql
SELECT schema_t.*, ... -- Select schema columns
FROM schema_t
WHERE EXISTS (
    SELECT 1
    FROM entity_tags_t et
    INNER JOIN tags_t t ON et.tag_id = t.tag_id
    WHERE et.entity_id = schema_t.schema_id
      AND et.entity_type = 'schema'
      AND t.tag_name IN (?, ?, ?) -- Parameterized tag names list
);
```

**UI Considerations:**

*   **Tag Management UI:** Similar to category management, likely an admin section to create, edit, delete tags.
*   **Tag Assignment UI:**
    *   Entity creation/edit forms should include a tag selection component (e.g., tag input with autocomplete, checkboxes, tag pills).
    *   Allow users to search/browse existing tags and assign them.
*   **Tag Filtering/Browsing UI:**
    *   Display tags prominently (tag cloud, list, filters).
    *   Clicking/selecting a tag should filter the entity lists to show only entities associated with that tag.

**Benefits of this Tagging System:**

*   **Flexible Organization:** Tags are free-form and non-hierarchical, allowing for more flexible and ad-hoc categorization than categories alone.
*   **Discoverability:** Improves search and filtering capabilities, making it easier for users to find relevant entities.
*   **Metadata Enrichment:** Tags add valuable metadata to entities.
*   **Scalability:** The database design is efficient for querying and managing tags and associations even with a large number of entities and tags.

This design provides a solid foundation for a tagging system. You can further refine it based on your specific requirements, such as adding tag groups, permissions for tag management, or more advanced search capabilities.
