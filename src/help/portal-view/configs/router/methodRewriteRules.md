# Router: methodRewriteRules

The `methodRewriteRules` property allows rewriting the HTTP method of a request before it is forwarded.

## Configuration Options

```yaml
methodRewriteRules:
  - "/v1/graphql POST GET"
```

* **Default**: `[]` (Empty list).
* Each rule is a string with three parts separated by whitespace: the request path prefix, the source HTTP method, and the target HTTP method.
* This is commonly used to adapt APIs (e.g., converting a `POST` request into a `GET` request for specific legacy systems).
