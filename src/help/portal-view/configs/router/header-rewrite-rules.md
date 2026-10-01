# Router: headerRewriteRules

Rename existing headers and conditionally replace values.

**Type:** Map of rule lists. **Default:** `{}`.

## Meaning

A map from endpoint patterns to lists of rules for **existing** HTTP headers. The fields have the same structure as query rules:

| Field | Meaning |
| --- | --- |
| `oldK` | Existing header name to look up. |
| `newK` | Optional replacement header name. |
| `oldV` | Optional exact header value to match. |
| `newV` | Replacement value; requires a matching `oldV`. |

A name change does not require a value match. Supplying `newV` without `oldV` does not set the value unconditionally. The rules do not supply a general add/delete-header language; use the appropriate header handler for those operations.

## Complete fixture example

```yaml
headerRewriteRules:
  /v1/address:
    - oldK: business-query
      newK: request-query
      oldV: value1
      newV: value2
    - oldK: module
      newK: mod
    - oldK: app-id
      oldV: esb
      newV: emb
  /v2/address:
    - oldK: key1
      oldV: old
      newV: new
  /v3/address:
    - oldK: path
      newK: route
  /v1/pets/{petId}:
    - oldK: path
      newK: route
```

| Endpoint and incoming header | Result | Meaning |
| --- | --- | --- |
| `/v1/address`, `business-query: value1` | `request-query: value2` | Rename and conditional value replacement. |
| `/v1/address`, `business-query: other` | `request-query: other` | Rename still applies; value does not match. |
| `/v1/address`, `module: billing` | `mod: billing` | Rename only. |
| `/v1/address`, `app-id: esb` | `app-id: emb` | Replace value only. |
| `/v2/address`, `key1: old` | `key1: new` | Replace value on the second endpoint. |
| `/v3/address`, `path: main` | `route: main` | Rename on the third endpoint. |
| `/v1/pets/123`, `path: main` | `route: main` | Placeholder selects the pet endpoint. |

Equivalent JSON:

```json
{"/v1/address":[{"oldK":"business-query","newK":"request-query","oldV":"value1","newV":"value2"},{"oldK":"module","newK":"mod"},{"oldK":"app-id","oldV":"esb","newV":"emb"}],"/v2/address":[{"oldK":"key1","oldV":"old","newV":"new"}],"/v3/address":[{"oldK":"path","newK":"route"}],"/v1/pets/{petId}":[{"oldK":"path","newK":"route"}]}
```

Put the map under `router.headerRewriteRules` in `values.yml`.

The abbreviated template/database example is also valid when written as a complete map:

```yaml
headerRewriteRules:
  /v1/address:
    - oldK: oldV
      newK: newV
  /v1/pets/{petId}:
    - oldK: oldV
      newK: newV
    - oldK: oldV2
      newK: newV2
```

This renames headers named `oldV` and `oldV2` to `newV` and `newV2`, preserving their values. Those strings are header names, not values being replaced.

The previous help contains a legacy-auth adaptation:

```yaml
headerRewriteRules:
  /v1/api:
    - oldK: X-Legacy-Token
      newK: Authorization
```

An existing `X-Legacy-Token: Bearer example-token` becomes `Authorization: Bearer example-token`; the rule does not add `Bearer ` to a raw token. This runs at proxy forwarding time and does not authenticate the caller or change the credentials seen by earlier security handlers.

## Runtime differences to check

Rust applies these rules to the upstream request, preserves unrelated headers, and uses HTTP header-name lookup. Its current rewrite path reads a single header value; do not assume multivalue preservation.

Java uses the same `copyHeaders` helper for both upstream request headers and downstream response headers. With a nonempty endpoint rule list, the current helper only copies headers whose names equal an `oldK`; unrelated headers can be omitted. Its `oldK` comparison is a case-sensitive string comparison even though HTTP names are normally case-insensitive. Check actual header spelling and every required header, including authentication and stream Content-Type, before enabling this map in Java.

Endpoint-map selection also differs: Rust uses the longest match (including literal prefix matches), whereas Java takes the first utility-matcher result. These are concrete implementation differences; a shared rule format alone does not ensure identical request/response behavior.

See [Router configuration](./index.md) for Portal/`values.yml` syntax, runtime compatibility, and source references.
