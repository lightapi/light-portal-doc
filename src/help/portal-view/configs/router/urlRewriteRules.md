# Router: urlRewriteRules

The `urlRewriteRules` property defines regex-based rules to rewrite the request URL path before routing it to the downstream target.

## Configuration Options

```yaml
urlRewriteRules:
  - "/v1/api/(.*) /api/$1"
  - "/old-path /new-path"
```

* **Default**: `[]` (Empty list).
* Each rule is a string containing two parts separated by whitespace: a regex pattern to match the incoming path, and a replacement string.
* The router applies the first matching rule and stops evaluating subsequent rules.
