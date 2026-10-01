# Router: streamRequestAcceptTypes

Recognize expected streams by Accept.

**Type:** List of string. **Default:** `[text/event-stream]`.

## Meaning

The request `Accept` media types that indicate an expected streaming response before downstream response headers arrive. Matching is case-insensitive, splits comma-separated values, and ignores parameters. It is a classification check, not full HTTP content negotiation: `q` weights are not used, so even a matching media type with `q=0` is recognized.

```yaml
streamRequestAcceptTypes:
  - text/event-stream
```

A request with `Accept: application/json, text/event-stream; charset=utf-8` is recognized as expecting a stream. `Accept: */*` is not a match for this list.

```yaml
streamRequestAcceptTypes: []
streamPathPrefixes:
  - /events/
```

Disables client-controlled Accept classification and declares `/events/` through operator-controlled path matching instead.

**Runtime difference:** Java uses `streamMaxRequestTime` as soon as Accept matches. Rust retains the ordinary request deadline for an Accept-only match until the backend confirms a configured streaming `Content-Type`; if it returns ordinary content, Rust clears the Accept-only classification. Configure an appropriate ordinary setup budget as well as a streaming budget.

See [Router configuration](./index.md) for Portal/`values.yml` syntax, runtime compatibility, and source references.
