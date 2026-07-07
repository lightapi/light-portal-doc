# Router: rewriteHostHeader

The `rewriteHostHeader` property determines whether the gateway should rewrite the HTTP `Host` header to match the destination target's host before forwarding the request.

## Configuration Options

```yaml
rewriteHostHeader: true
```

* **`true`** (Default): The `Host` header is replaced with the downstream service's address.
* **`false`**: The original `Host` header provided by the client is preserved.
