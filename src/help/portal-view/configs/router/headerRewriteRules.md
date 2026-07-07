# Router: headerRewriteRules

The `headerRewriteRules` property defines rules to add, remove, or modify HTTP headers before forwarding the request.

## Configuration Options

```yaml
headerRewriteRules:
  /v1/api:
    - oldK: "X-Legacy-Token"
      newK: "Authorization"
```

* **Default**: `{}` (Empty map).
* The structure is identical to `queryParamRewriteRules`, mapping path prefixes to header rewrite rules.
* If `newK` is provided but `newV` is not, the header name is changed while preserving the value. If `newV` is provided, the value is updated.
