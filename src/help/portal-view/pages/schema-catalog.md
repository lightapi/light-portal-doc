# Schema Catalog

Use Schema Catalog to browse reusable schema contracts from Marketplace.

The catalog is backed by schema registry records, categories, and tags. It is
intended for discovery and inspection, not bulk schema administration.

Visible records include published global schemas, published schemas for the
current host, and draft or retired schemas that you own or can administer.

Common filters:

- search text for schema id, name, description, source, and owner metadata
- schema type, starting with JSON Schema
- schema status, such as draft, published, and retired
- schema categories
- grouped schema tags
- active or inactive status
- sort and card/list view options

Catalog cards show a compact contract summary:

- schema id, name, latest published version, and type
- spec version, source, status, and scope
- schema alias and external URL when external access is enabled
- categories and tags
- whether the schema body is available for preview
- whether the schema can drive config-backed form generation

Common actions:

- open the schema details drawer
- preview JSON Schema source
- copy a schema reference
- copy an external schema URL when available
- create a new schema version when you have permission
- edit draft metadata and taxonomy when you own or administer the schema
- open Schema Admin for table-based management
