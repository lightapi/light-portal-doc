# Router: preResolveFQDN2IP

The `preResolveFQDN2IP` property determines whether the router should pre-resolve Fully Qualified Domain Names (FQDNs) to IP addresses when parsing target addresses.

## Configuration Options

```yaml
preResolveFQDN2IP: false
```

* **`true`**: FQDNs are resolved to IPs on startup or when the configuration loads. This saves DNS lookup time during request routing.
* **`false`** (Default): DNS resolution occurs dynamically during routing.
