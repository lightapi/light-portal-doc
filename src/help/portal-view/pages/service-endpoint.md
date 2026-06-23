# Service Endpoint

The Service Endpoint page lists the endpoints generated for an API version. Use it to review endpoint metadata and configure endpoint-level access control.

## Endpoint-Level Access Control

Access rules, permissions, row filters, and column filters are stored against individual endpoints. Bulk operations on this page write the same endpoint-level records used by the existing per-endpoint pages.

The page does not define API-version-level inherited defaults. After a bulk update, each affected endpoint has its own materialized access-control records.

## Bulk Access

Select one or more endpoint rows and choose **Bulk Access** to apply one access-control operation to all selected endpoints.

Supported operation groups include:

- endpoint rule assignment
- role, group, position, and attribute permissions
- role, group, position, and attribute row filters
- role, group, position, and attribute column filters

The default conflict mode is **Skip Existing**, which avoids changing matching records that already exist. Use **Overwrite Existing** only when the selected endpoints should receive the submitted configuration.

## Access Overview

Choose **Access Overview** to review the final endpoint-level configuration for the current API version.

The overview shows:

- endpoint rule assignments grouped by rule type
- permissions by principal type
- row filters by principal type
- column filters by principal type
- summary counts for endpoints with missing configuration, permissions, row filters, and column filters

Use the missing-only filter to find endpoints that still have no access configuration after a bulk update.

## Per-Endpoint Adjustments

Use the row action icons when one endpoint needs a specific exception. The per-endpoint pages remain the detailed editors for rule lists, permissions, row filters, and column filters.
