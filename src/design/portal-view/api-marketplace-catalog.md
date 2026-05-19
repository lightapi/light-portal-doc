# API Marketplace Catalog

## Context

The portal already has a Marketplace navigation group and an `api-marketplace`
page registry entry. The current API administration page is table-oriented and
is useful for owners, but it is not a consumer catalog. A Marketplace API
catalog should let users discover APIs by business category, capability,
protocol, lifecycle status, and governance metadata.

API create and update forms already use the standardized taxonomy fields:

- `categoryIds` for selected category identifiers.
- `tagIds` for selected tag identifiers.
- `getCategoryLabelByType` with `entityType = "api"` for category options.
- `getTagLabelByType` with `entityType = "api"` for tag options.

The service query layer also returns `categoryIds`, `categories`, `tagIds`, and
`tags` for API rows. The catalog should use those fields for display and
filtering instead of reintroducing the legacy `apiTags` string field.

## Goals

- Add a Marketplace menu entry for an API catalog.
- Use database-backed categories and tags, not hard-coded UI lists.
- Keep categories and tags reusable across future catalog pages.
- Keep API create/update forms as the source of truth for taxonomy assignment.
- Give consumers a browse-first experience instead of an admin table.
- Support deep links from a catalog listing to API detail, versions, endpoints,
  runtime bindings, and owner actions.
- Preserve host scope and ownership rules already used by API administration.

## Non-Goals

- Do not replace API administration pages with the catalog.
- Do not store display names in API rows when they can be resolved from
  `category_t`, `tag_t`, `entity_category_t`, and `entity_tag_t`.
- Do not use the old `apiTags` field for catalog filtering.
- Do not make taxonomy values static frontend constants.
- Do not expose private tenant APIs through a public catalog without an
  explicit visibility and authorization decision.

## Current Building Blocks

| Area | Current shape | Catalog use |
| --- | --- | --- |
| Portal navigation | Marketplace group already exists in the sidebar | Add an API Catalog child item under Marketplace |
| Page registry | `api-marketplace` points to `/app/marketplace`, while the app route still needs a real catalog page | Keep a registry entry for search, task links, and help links |
| API admin page | `Service.tsx` calls `service/getApi` and displays `categories` and `tags` | Reuse its query contract but present catalog cards/list views |
| API detail page | `ApiDetail.tsx` shows API versions and action links | Catalog detail can deep-link to this page |
| Forms | `createApi` and `updateApi` submit `categoryIds` and `tagIds` | Catalog reads the same assignments |
| Category labels | `category/getCategoryLabelByType` returns `id` and `label` | Use for category tabs, filters, and chips |
| Tag labels | `tag/getTagLabelByType` returns id, label, value, group code, group label, group sort order, and tag sort order | Use for grouped tag filters and grouped multi-select controls |
| Database | `category_t`, `tag_t`, `entity_category_t`, and `entity_tag_t` are entity-type scoped | Use `entity_type = 'api'` for API catalog taxonomy |

## User Experience

The first screen under Marketplace should be the usable catalog, not a landing
page. The recommended route is:

```text
/app/marketplace/api
```

The sidebar can keep the existing Marketplace group, but its children should
move from API-type-only links to intent-based entries:

- API Catalog
- API Clients
- JSON Schema
- YAML Rule
- Schema Form

The API Catalog page should provide:

- Search across API id, name, description, business group, line of business,
  capability, platform, git repository, categories, and tags.
- Category tabs or a category rail based on `getCategoryLabelByType`.
- Grouped tag filters based on `getTagLabelByType`.
- Filter chips for active category and tag selections.
- A compact card or list row per API with name, description, status,
  categories, tags, owner, business group, and latest version summary.
- Actions to view details, review versions, create a new version, update the
  API metadata, and open related runtime or access-control pages when the user
  has permission.

The catalog should support an `Uncategorized` bucket for active APIs without
category assignments. This avoids hiding incomplete data and gives admins an
easy cleanup target.

## Categories And Tags

Categories should be stable browse buckets. Tags should be flexible facets.
Both are stored with `entityType = "api"` so the same tag names can be reused
for other entity types without forcing cross-catalog semantics.

Recommended initial API categories:

| Category value | Label | Purpose |
| --- | --- | --- |
| `public-api` | Public API | External developer-facing APIs |
| `partner-api` | Partner API | APIs shared with business partners |
| `internal-api` | Internal API | Organization-internal service APIs |
| `platform-service` | Platform Service | Shared platform or infrastructure APIs |
| `data-api` | Data API | Data access, analytics, reporting, and query APIs |
| `ai-automation-api` | AI / Automation API | Agent, workflow, automation, or AI-facing APIs |
| `security-compliance-api` | Security / Compliance API | Identity, audit, policy, compliance, and control APIs |
| `developer-tooling-api` | Developer Tooling API | Build, test, deployment, and developer-experience APIs |
| `legacy-modernization-api` | Legacy / Modernization API | Legacy integration and modernization APIs |

The stored `category_name` must stay lower-case and URL-friendly. The display
labels above are UI labels derived from those values.

Recommended initial API tag groups:

| Group code | Group label | Example tag values |
| --- | --- | --- |
| `protocol` | Protocol | `openapi`, `graphql`, `hybrid`, `mcp`, `rest`, `event-driven` |
| `lifecycle` | Lifecycle | `draft`, `review`, `implemented`, `deprecated`, `beta`, `ga` |
| `security` | Security | `oauth2`, `jwt`, `mtls`, `pii`, `hipaa`, `pci`, `read-only` |
| `runtime` | Runtime | `gateway`, `sidecar`, `kubernetes`, `serverless`, `multi-region` |
| `domain` | Domain | `customer`, `order`, `payment`, `inventory`, `tax`, `billing` |
| `consumer` | Consumer | `public`, `partner`, `internal`, `agent-facing`, `mobile`, `web` |
| `operations` | Operations | `high-traffic`, `low-latency`, `batch`, `streaming`, `critical` |
| `integration` | Integration | `database`, `kafka`, `s3`, `third-party`, `mainframe`, `saas` |

Stored tag names must stay lower-case and URL-friendly. If a display label needs
capitalization, the UI should format it or the label endpoint should provide a
separate display field later.

Tags without `tag_group_code` or `tag_group_label` should be shown under a
`General` filter group in the catalog UI. Configured groups should appear first
by `group_sort_order`; the `General` group should appear after configured
groups, matching the current label query behavior where null group sort values
sort last.

## Data Flow

Catalog filter option loading:

```text
portal-view
  -> category/getCategoryLabelByType(hostId, entityType = "api")
  -> tag/getTagLabelByType(hostId, entityType = "api")
```

Catalog result loading:

```text
portal-view
  -> service/getApi(hostId, offset, limit, active, filters, globalFilter, sorting)
  -> api rows with categoryIds, categories, tagIds, tags
```

The catalog should prefer server-side pagination and filtering. Client-side
filtering is acceptable only for a small first pass because it breaks as soon as
the API count exceeds one fetched page.

## Query Contract

The existing `getApi` contract already supports `filters`, `globalFilter`,
`sorting`, `offset`, `limit`, `hostId`, and `active`. To make the catalog work
well at scale, add first-class filter support for taxonomy fields:

```json
{
  "hostId": "01964b05-552a-7c4b-9184-6857e7f3dc5f",
  "offset": 0,
  "limit": 20,
  "active": true,
  "categoryIds": ["..."],
  "tagIds": ["..."],
  "tagMatch": "all",
  "globalFilter": "payment"
}
```

Recommended semantics:

- `categoryIds` uses OR semantics by default. An API in any selected category
  is returned.
- `tagIds` should support `tagMatch = "all"` and `tagMatch = "any"`.
- Category and tag filters should use `EXISTS` against `entity_category_t` and
  `entity_tag_t` with `entity_type = 'api'` and `active = TRUE`.
- Display arrays should continue to be returned as `categories` and `tags`.
- Form update payloads should continue to submit identifiers only through
  `categoryIds` and `tagIds`.

## Page Design

The API Catalog page can be implemented as a dedicated page rather than trying
to stretch the current API admin table.

Proposed files:

```text
src/pages/marketplace/ApiCatalog.tsx
src/pages/marketplace/components/ApiCatalogFilters.tsx
src/pages/marketplace/components/ApiCatalogCard.tsx
src/pages/marketplace/hooks/useApiCatalog.ts
```

Page state:

- search text
- selected category ids
- selected tag ids
- tag match mode
- active status
- pagination
- sorting
- view mode, either compact list or card grid

Catalog state should be URL-driven from Phase 1. Search text, selected
categories, selected tags, tag match mode, active status, sorting, and
pagination should be encoded in the query string so users can refresh the page,
use browser navigation, and share filtered catalog URLs. Example:

```text
/app/marketplace/api?q=payment&category=public-api&tag=oauth2&tag=mtls&tagMatch=all&page=1
```

The page should still reuse existing infrastructure:

- `fetchClient` for portal query calls.
- `useUserState` for host and user context.
- `buildTaskAwareRoute` for deep links.
- ownership utilities for update/delete action visibility.
- `TaskActionPanel` for publisher/admin next actions.
- `pageRegistry` and contextual help metadata.

## Routing And Navigation

Add or update these portal-view entries:

| Location | Change |
| --- | --- |
| `Sidebar.tsx` | Add `API Catalog` under Marketplace with route `/app/marketplace/api` |
| `App.tsx` | Route `/app/marketplace/api` to `ApiCatalog` |
| `pageRegistry.ts` | Add or update API Catalog metadata, keywords, and help path |
| `taskRegistry.ts` | Update publish/review steps to point to `/app/marketplace/api` |
| Help docs | Add a user-facing help page after the UI settles |

The existing `/app/marketplace` route can redirect to `/app/marketplace/api` or
remain a broader Marketplace landing page later. For the first API catalog
implementation, redirecting keeps the behavior simple.

## Backend Changes

The backend already persists API category and tag relationships. The main
backend change is query filtering:

1. Extend `service-query` spec for optional `categoryIds`, `tagIds`, and
   `tagMatch`.
2. Update `GetApi` to pass those optional fields to the DB provider.
3. Update `PortalDbProvider#getApi` and `ApiServicePersistenceImpl#getApi`.
4. Add SQL predicates over `entity_category_t` and `entity_tag_t`.
5. Verify or add compound indexes for taxonomy filtering.
6. Add tests for category-only, tag-any, tag-all, combined taxonomy filters,
   and APIs with no taxonomy assignments.

The existing join-table indexes are useful for entity lookups and label
resolution, but catalog filtering also needs indexes that start with filter
fields. Before implementing Phase 2, verify the query plan and add indexes if
needed:

```sql
CREATE INDEX idx_entity_tag_filter
ON entity_tag_t (entity_type, tag_id, entity_id)
WHERE active = TRUE;

CREATE INDEX idx_entity_category_filter
ON entity_category_t (entity_type, category_id, entity_id)
WHERE active = TRUE;
```

For `tagMatch = "all"`, prefer a single grouped subquery over generating one
`EXISTS` predicate per selected tag when the selected tag set can grow. A common
shape is to filter `entity_tag_t` by selected tag ids, group by `entity_id`, and
require `COUNT(DISTINCT tag_id) = selectedTagCount`.

The query response should continue to include both identifiers and labels:

```json
{
  "apiId": "0001",
  "apiName": "Petstore",
  "categoryIds": ["..."],
  "categories": ["public-api"],
  "tagIds": ["..."],
  "tags": ["openapi", "oauth2"]
}
```

## Implementation Phases

### Phase 1: Catalog Page

- Add the API Catalog route and Marketplace menu entry.
- Load category and tag options from the existing label endpoints.
- Load APIs with `service/getApi`.
- Render search, category filter, grouped tag filter, and API list/card results.
- Store catalog filters, search text, sorting, and pagination in the URL query
  string.
- Use current query response labels for display.
- Deep-link to existing API detail and update forms.

### Phase 2: Server-Side Taxonomy Filters

- Add `categoryIds`, `tagIds`, and `tagMatch` to `service-query`.
- Implement SQL filtering in `ApiServicePersistenceImpl`.
- Keep current table filtering support for admin use.
- Add DB provider and handler tests.

### Phase 3: Catalog Polish

- Add API detail summary panels with versions, endpoint count, runtime exposure,
  and access-control hints.
- Add help docs and task links.
- Add optional counts per category and tag if the catalog needs faceted counts.

## Open Questions

- Should Marketplace API Catalog show only active APIs by default? The
  recommendation is yes, with an admin-visible inactive filter.
- Should unauthenticated users ever see catalog data? The recommendation is no
  until a separate public visibility model is designed.
- Should category selection be single-select or multi-select? The
  recommendation is multi-select OR semantics for flexibility.
- Should tags use all-match or any-match by default? The recommendation is
  `all` for precision, with a visible toggle if users need broader searches.
- Should OpenAPI tags imported from specs automatically create API catalog
  tags? The recommendation is no for the first pass. Spec tags are often
  endpoint-level groupings and should not automatically become curated catalog
  taxonomy.
