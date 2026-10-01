# Router: hostWhitelist

Allow explicit service_url hosts; an empty list denies them.

**Type:** List of regex string. **Default:** `[]`.

## Meaning

An allowlist of regular expressions matched against the **hostname** in an explicit `service_url`. Matching covers the whole hostname, without the scheme, port, or path. This is the control for caller-supplied URLs; it is not a global allowlist applied to every discovery/direct-registry target.

```yaml
hostWhitelist: []
```

An empty list **denies explicit `service_url` routing**. Java throws a configuration/routing error; Rust returns a forbidden rejection. Ordinary registered `service_id` routing can still work. Do not interpret this as "allow every host" or assume identical error status handling in the two runtimes.

```yaml
hostWhitelist:
  - 'api\.example\.com'
  - 'api\d+\.example\.com'
  - '192\.168\.0\.[0-9]{1,3}'
  - '10\.1\.2\.[0-9]{1,3}'
```

| Target URL | Result | Reason |
| --- | --- | --- |
| `https://api.example.com:8443/v1` | Allowed | First pattern matches the hostname. |
| `https://api1.example.com/v1` | Allowed | `\d+` matches one or more digits. |
| `http://192.168.0.25:8080/v1` | Allowed | Matches the private-address pattern. |
| `http://10.1.2.8:8080/v1` | Allowed | Matches the second private subnet pattern. |
| `https://evil.example.com/v1` | Denied | No pattern matches. |
| `https://xapi1.example.com.evil/v1` | Denied | A substring match is insufficient. |

The expressions above limit hostname text, not protocol or port. The numeric patterns are illustrative and do not validate all IPv4 octet ranges. Single-quoted YAML keeps backslashes literal.

The Java source test fixture contains this historical example:

```yaml
router.hostWhitelist:
  - 192.168.0.*
  - 10.1.2.*
```

These are regexes, **not shell wildcards or CIDR subnets**. `.` means any character; `0.*` means a literal zero followed by arbitrary characters. They can therefore match hostnames outside the intended subnet. Prefer the escaped expressions above. The historical JSON representation is:

```yaml
router.hostWhitelist: '["192.168.0.*","10.1.2.*"]'
```

It has exactly the same permissive regex meaning. A more precise JSON representation is:

```json
["192\\.168\\.0\\.[0-9]{1,3}","10\\.1\\.2\\.[0-9]{1,3}"]
```

Use regex constructs supported by both Java and Rust; Rust regex does not support Java look-around or backreferences. Allowing a hostname is not the same as restricting every IP it can resolve to.

See [Router configuration](./index.md) for Portal/`values.yml` syntax, runtime compatibility, and source references.
