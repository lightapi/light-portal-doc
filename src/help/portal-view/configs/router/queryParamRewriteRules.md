# Router: queryParamRewriteRules

The `queryParamRewriteRules` property defines rules to add, remove, or modify URL query parameters before forwarding the request.

## Configuration Options

```yaml
queryParamRewriteRules:
  /v1/search:
    - oldK: "q"
      newK: "query"
    - oldK: "version"
      oldV: "1"
      newV: "2"
```

* **Default**: `{}` (Empty map).
* The map is keyed by endpoint path prefixes.
* Each rule can specify:
  * `oldK`: The query parameter key to match.
  * `oldV` (Optional): The expected value to match.
  * `newK` (Optional): The new key to rename the parameter to.
  * `newV` (Optional): The new value to assign.
