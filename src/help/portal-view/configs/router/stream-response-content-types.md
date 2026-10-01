# Router: streamResponseContentTypes

Recognize streaming responses by Content-Type.

**Type:** List of string. **Default:** `[text/event-stream]`.

## Meaning

The response `Content-Type` values that identify a streaming passthrough response. Matching is case-insensitive, ignores media-type parameters, and compares configured media types rather than doing wildcard matching.

```yaml
streamResponseContentTypes:
  - text/event-stream
```

`Content-Type: text/event-stream; charset=utf-8` identifies an SSE stream. `Content-Type: application/json` does not. The proxy transfers response bytes incrementally and applies streaming header/idle-timeout handling.

```yaml
streamResponseContentTypes:
  - text/event-stream
  - application/x-ndjson
```

This also recognizes newline-delimited JSON streams. Add a type only when the backend actually uses it for incremental responses; adding `application/json` would classify ordinary JSON responses as streams too.

```yaml
streamResponseContentTypes: []
```

Disables response-media-type recognition. It does not remove request classification through `Accept` or path prefixes. See `streamMaxRequestTime` for what happens when a stream is discovered only after response headers arrive.

See [Router configuration](./index.md) for Portal/`values.yml` syntax, runtime compatibility, and source references.
