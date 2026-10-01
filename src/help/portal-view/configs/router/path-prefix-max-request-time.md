# Router: pathPrefixMaxRequestTime

Override the ordinary deadline by literal request-path prefix.

**Type:** Map of integer (ms). **Default:** `{}`.

## Meaning

A map from **literal incoming request-path prefixes** to ordinary request deadlines in milliseconds. Unmatched paths use `maxRequestTime`. Streaming requests use their streaming policy instead.

```yaml
maxRequestTime: 1000
pathPrefixMaxRequestTime:
  /v1/address: 5000
  /v2/address: 10000
  /v3/address: 30000
  /v1/pets/: 5000
```

| Request | Ordinary deadline | Explanation |
| --- | --- | --- |
| `/v1/address` or `/v1/address/42` | 5 seconds | Starts with `/v1/address`. |
| `/v2/address` | 10 seconds | Matches the second prefix. |
| `/v3/address` | 30 seconds | Gives the third API a longer budget. |
| `/v1/pets/123` | 5 seconds | Uses a literal prefix covering pet identifiers. |
| `/v1/contact` | 1 second | No override; uses the global setting. |

The source and Portal descriptions also contain this example:

```yaml
pathPrefixMaxRequestTime:
  /v1/pets/{petId}: 5000
```

Here `{petId}` is **literal text**, not a path parameter. It will not match `/v1/pets/123`. Use `/v1/pets/` for the timeout override. Endpoint patterns in method/query/header rewrite rules have different matching semantics.

The original JSON example is:

```json
{"/v1/address":5000,"/v2/address":10000,"/v3/address":30000,"/v1/pets/{petId}":5000}
```

It expresses the same map, including the literal-braces limitation. Replace the last key with `/v1/pets/` for identifier-bearing requests. In `values.yml`, use:

```yaml
router.pathPrefixMaxRequestTime: {"/v1/address":5000,"/v2/address":10000,"/v3/address":30000,"/v1/pets/":5000}
```

The Java test fixture also stores this map as JSON text:

```yaml
router.pathPrefixMaxRequestTime: '{"/v1/address":5000,"/v2/address":10000,"/v3/address":30000,"/v1/pets/":5000}'
```

Both represent a map rather than four separate properties. Prefer the native map when the editor supports it.

Another example from the existing help is:

```yaml
pathPrefixMaxRequestTime:
  /v1/long-polling: 5000
  /v2/upload: 10000
```

This gives ordinary long-polling requests five seconds and uploads ten seconds. Actual event streams should use the streaming properties.

Matching uses `startsWith`, so `/v1/address` also matches `/v1/addresses`. Use a trailing slash when you need a child-path boundary. Rust chooses the longest matching nonempty prefix. Java stops at the first matching map entry. Avoid overlapping prefixes for portable behavior. A value of `0` disables this deadline for matching ordinary requests.

See [Router configuration](./index.md) for Portal/`values.yml` syntax, runtime compatibility, and source references.
