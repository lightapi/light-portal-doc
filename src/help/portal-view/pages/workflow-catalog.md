# Workflow Catalog

Use Workflow Catalog to browse workflow definitions that can be discovered or
started from Marketplace.

Visible records include workflow definitions published to the catalog and
workflow definitions you can already access through ownership or position scope.
Workflow administrators can see all workflow definitions for the current host.

Common filters:

- search text for namespace, name, and version
- workflow categories
- grouped workflow tags
- active or inactive status
- sort and card/list view options

Catalog cards show workflow metadata, publication state, categories, tags, and a
short definition preview. Use the details drawer to inspect the workflow id,
owner metadata, taxonomy, and read-only YAML preview without leaving the catalog.

Common actions:

- start a workflow from the selected definition
- open the details drawer
- edit workflow definitions you own or administer
- create a new workflow definition
- open Workflow Admin for table-based management

Publishing a workflow to the catalog is controlled by the workflow definition's
`catalogVisible` setting. Publishing makes the workflow discoverable in
Marketplace, but editing and deleting remain restricted to owners, owner
positions, workflow administrators, and administrators.
