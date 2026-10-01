# Router: streamPathPrefixes

Declare streaming request paths before response headers arrive.

**Type:** List of string. **Default:** `[]`.

## Meaning

Literal incoming request-path prefixes that declare an expected stream before downstream headers arrive. This is useful when a client cannot set `Accept`, or when the backend takes time to send its first response headers.

```yaml
streamPathPrefixes:
  - /events/
  - /v1/chat/stream
```

`/events/orders` and `/v1/chat/stream` use the streaming request deadline from the start. `/v1/chat/completions` does not match. Both runtimes check these prefixes without regex or `{parameter}` expansion.

The second prefix also matches `/v1/chat/streaming` because matching is a string-prefix test. Choose prefixes deliberately. A path declaration takes precedence over Accept classification in Rust.

```yaml
streamPathPrefixes: []
```

No paths are declared streaming; the proxy can still classify by `Accept` or downstream `Content-Type`. A path match does not force the backend to emit SSE or change its Content-Type.

See [Router configuration](./index.md) for Portal/`values.yml` syntax, runtime compatibility, and source references.
