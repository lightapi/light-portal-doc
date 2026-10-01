# Router: streamResponseHeaderOverwrite

Give downstream streaming headers precedence over existing response headers.

**Type:** List of string. **Default:** `Six headers; see property page`.

## Meaning

Names of response headers whose existing gateway values should give way to the actual downstream streaming response. This prevents a header already set by another handler from masking the stream's Content-Type, cache policy, or framing.

```yaml
streamResponseHeaderOverwrite:
  - Content-Type
  - Cache-Control
  - Connection
  - Transfer-Encoding
  - Content-Encoding
  - Content-Length
```

This is the complete default list:

| Header | Reason for including it |
| --- | --- |
| `Content-Type` | Preserve the backend's streaming media type, such as `text/event-stream`. |
| `Cache-Control` | Preserve the backend's stream-specific caching policy. |
| `Connection` | Avoid retaining a conflicting connection policy; protocol handling still applies. |
| `Transfer-Encoding` | Avoid retaining incompatible transfer framing. |
| `Content-Encoding` | Prevent stale encoding metadata from describing the wrong body. |
| `Content-Length` | Avoid an ordinary response length being applied to an open-ended stream. |

The list contains **header names**, not `name: value` assignments. It neither invents `Cache-Control: no-cache` nor requests gzip. In Java, these existing outbound headers are removed before downstream headers are copied, and Content-Length is removed from a confirmed stream. Rust captures the backend's values for these names and restores them after response handlers, with separate protocol/framing handling.

```yaml
streamResponseHeaderOverwrite: []
```

Disables the configured overwrite list. Other mandatory framing cleanup still applies. This is usually unsuitable when another response handler sets ordinary-content headers. If customizing the list, retain the default entries unless you have checked the complete response chain.

See [Router configuration](./index.md) for Portal/`values.yml` syntax, runtime compatibility, and source references.
