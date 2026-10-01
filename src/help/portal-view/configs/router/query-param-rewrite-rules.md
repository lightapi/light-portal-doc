# Router: queryParamRewriteRules

Rename existing query keys and conditionally replace values.

**Type:** Map of rule lists. **Default:** `{}`.

## Meaning

A map from endpoint patterns to lists of rules that modify **existing** query parameters. Rules do not create a missing parameter, and there is no documented add/delete operation in this rule format.

| Field | Meaning |
| --- | --- |
| `oldK` | Existing query key to find; required for a useful rule. |
| `newK` | Optional replacement key; omitted means keep the original key. |
| `oldV` | Optional exact value to replace, used together with `newV`. |
| `newV` | Replacement value, applied only when `oldV` is also present and matches. |

A key rename occurs even when `oldV` does not match. `newV` alone does **not** unconditionally set a value. Values are literal strings, not regexes; `oldK: oldV` in the database's abbreviated example means the field `oldK` has the string value `oldV`, not an arbitrary parameter/value pair.

## Complete Java fixture example

```yaml
queryParamRewriteRules:
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

| Incoming request | Result | Explanation |
| --- | --- | --- |
| `/v1/address?business-query=value1&module=billing&app-id=esb` | `/v1/address?request-query=value2&mod=billing&app-id=emb` | Renames and replaces the first pair, renames `module` preserving its value, and replaces `app-id`'s value preserving its key. |
| `/v1/address?business-query=other` | `/v1/address?request-query=other` | The key is renamed; the value does not equal `value1`. |
| `/v2/address?key1=old` | `/v2/address?key1=new` | Value-only replacement. |
| `/v2/address?key1=other` | Unchanged pair | `oldV` does not match. |
| `/v3/address?path=main` | `/v3/address?route=main` | Key-only rename. |
| `/v1/pets/123?path=main` | `/v1/pets/123?route=main` | Endpoint placeholder matches identifier `123`. |
| `/v2/address?country=CA` | Same pair | No `key1` exists to rewrite. |

The displayed pair order is explanatory; query serialization/order and percent encoding can differ without changing the meaning.

Equivalent JSON:

```json
{"/v1/address":[{"oldK":"business-query","newK":"request-query","oldV":"value1","newV":"value2"},{"oldK":"module","newK":"mod"},{"oldK":"app-id","oldV":"esb","newV":"emb"}],"/v2/address":[{"oldK":"key1","oldV":"old","newV":"new"}],"/v3/address":[{"oldK":"path","newK":"route"}],"/v1/pets/{petId}":[{"oldK":"path","newK":"route"}]}
```

In `values.yml`, put this map under `router.queryParamRewriteRules`. The source template's abbreviated YAML omits some colons after endpoint keys; the complete example above supplies them.

The template/database also show two rules under one pet endpoint:

```yaml
queryParamRewriteRules:
  /v1/pets/{petId}:
    - oldK: oldV
      newK: newV
    - oldK: oldV2
      newK: newV2
```

`/v1/pets/123?oldV=a&oldV2=b` becomes the same path with `newV=a&newV2=b`. The strings `oldV` and `newV` here are parameter **names**, because they are values of `oldK` and `newK`; no query-value replacement fields are supplied.

Another help example:

```yaml
queryParamRewriteRules:
  /v1/search:
    - oldK: q
      newK: query
    - oldK: version
      oldV: '1'
      newV: '2'
```

`/v1/search?q=router&version=1` becomes `/v1/search?query=router&version=2`. Quote numeric-looking values so they remain strings.

## Matching and portability

Both implementations accept endpoint placeholders. Rust selects the longest matching rule-map key and also accepts literal prefix matches. Java selects the first endpoint match using its path-segment matcher. Avoid overlapping keys for portable behavior.

Rust preserves query pairs when no endpoint rule matches. Java's current query builder, when the configured map is nonempty but no endpoint matches, does not append the original query. Test unrelated endpoints before enabling a global Java rewrite map.

Repeated values and destination-key collisions also differ: Java replaces matching repeated values with one new value and can overwrite an existing destination key; Rust rewrites each pair and preserves duplicate pairs. Prefer unique source/destination keys and single values when the same configuration must behave identically.

See [Router configuration](./index.md) for Portal/`values.yml` syntax, runtime compatibility, and source references.
