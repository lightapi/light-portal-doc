# Router: streamIdleTimeout

Maximum silence between downstream streaming bytes; 0 disables it.

**Type:** Integer (ms). **Default:** `0`.

## Meaning

Maximum silence between downstream streaming bytes, in milliseconds, once a streaming response is confirmed. This is an upstream stream-read timeout, not an overall request duration, and does not govern ordinary buffered responses.

```yaml
streamIdleTimeout: 0
```

Disables the router's streaming idle timer.

```yaml
streamIdleTimeout: 30000
```

If no downstream streaming bytes arrive for thirty seconds, the proxy closes the stalled stream. An SSE heartbeat every fifteen seconds should keep this timer alive. The measurement concerns arriving bytes, not complete SSE events or application-level messages.

Choose a value longer than the backend's expected heartbeat interval plus network delay. A quiet but healthy subscription can otherwise be disconnected. Once response headers have been sent, timeout handling usually closes the stream rather than replacing it with a new `504` response.

See [Router configuration](./index.md) for Portal/`values.yml` syntax, runtime compatibility, and source references.
