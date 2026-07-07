# Router: hostWhitelist

The `hostWhitelist` property restricts the set of downstream hosts the router is allowed to forward requests to.

## Configuration Options

```yaml
hostWhitelist: []
```

* **Default**: `[]` (Empty list).
* When empty, no whitelist filtering is applied.
* If defined, the router will deny requests (with `403 Forbidden`) if the dynamically resolved target host (e.g., from `service_url`) does not match one of the regular expressions in this list.
