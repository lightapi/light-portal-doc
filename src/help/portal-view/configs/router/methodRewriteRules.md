# Router: methodRewriteRules

Rewrite the method for an endpoint pattern.

**Type:** List of string. **Default:** `[]`.

## Meaning

A list of `endpoint-pattern source-method target-method` strings. Endpoint patterns can contain a single-segment placeholder such as `{petId}`; this is not regex syntax or the literal-prefix timeout syntax.

```yaml
methodRewriteRules:
  - '/v2/address POST PUT'
  - '/v1/address POST PATCH'
  - '/v1/address GET DELETE'
  - '/v1/pets/{petId} GET DELETE'
  - '/v1/pets/{petId}/address GET DELETE'
```

| Client request | Downstream method | Meaning |
| --- | --- | --- |
| `POST /v2/address` | `PUT` | Legacy POST performs the backend's replacement/update operation. |
| `POST /v1/address` | `PATCH` | Legacy POST performs a partial update. |
| `GET /v1/address` | `DELETE` | Legacy GET invokes a bodyless delete operation. |
| `GET /v1/pets/123` | `DELETE` | `{petId}` matches identifier `123`. |
| `GET /v1/pets/123/address` | `DELETE` | The longer pattern targets the pet's address resource. |

Equivalent JSON from the source fixture, with the additional nested-address example:

```json
["/v2/address POST PUT","/v1/address POST PATCH","/v1/address GET DELETE","/v1/pets/{petId} GET DELETE","/v1/pets/{petId}/address GET DELETE"]
```

Use uppercase method names and keep endpoint patterns unambiguous. Rust applies the first matching rule and matches the complete endpoint shape. Java continues evaluating rules and its utility matcher can match a longer path by its leading segments; short incoming paths can also expose its unchecked segment indexing. Do not rely on identical behavior for overlapping endpoint patterns or chained rewrites.

## Body and security implications

The rule changes the method, not the payload. The source specifically cautions against changing a method with a body into one without a body, or vice versa. POST-to-PUT/PATCH examples preserve the update body. GET-to-DELETE assumes the backend delete requires no body.

The earlier help contained:

```yaml
methodRewriteRules:
  - '/v1/graphql POST GET'
```

This illustrates the syntax but is unsuitable for a typical body-carrying GraphQL POST: the router does not convert its JSON payload into GET query parameters. Use a body-compatible adaptation instead.

GET-to-DELETE makes a conventionally safe method perform a destructive action downstream. Limit it to an explicitly authorized legacy endpoint and review caching, prefetching, and CSRF behavior. Authentication, authorization, and API validation handlers preceding the router see the incoming method, not the rewritten one.

See [Router configuration](./index.md) for Portal/`values.yml` syntax, runtime compatibility, and source references.
