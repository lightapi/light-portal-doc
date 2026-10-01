# Router: maxConnectionRetries

Java proxy connection retry limit.

**Type:** Integer. **Default:** `3`.

## Meaning

In Java, the configured proxy retry limit when acquiring a backend connection. The proxy can try alternate hosts, and the target can supply its own retry count; the effective limit uses the larger value. The initial attempt is separate from retries.

```yaml
maxConnectionRetries: 3
```

Allows up to three configured retries after the initial connection attempt, subject to the target's policy and the request deadline. For example, a failed connection to one discovered address can be followed by an attempt against another address.

```yaml
maxConnectionRetries: 0
```

Disables the router-configured retries; target-specific behavior can still affect the effective limit. This setting is not a policy to replay every backend `500` response, and it should not be treated as permission to replay an already transmitted non-idempotent request. The proxy's send/error and idempotency handling also apply.

**Rust support:** the property is accepted, but the current gateway does not feed it into Pingora's retry policy. Changing it does not establish a Rust retry count.

See [Router configuration](./index.md) for Portal/`values.yml` syntax, runtime compatibility, and source references.
