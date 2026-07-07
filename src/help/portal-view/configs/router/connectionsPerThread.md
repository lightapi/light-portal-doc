# Router: connectionsPerThread

The `connectionsPerThread` property defines the hard limit on the number of concurrent connections the router will maintain per worker thread.

## Configuration Options

```yaml
connectionsPerThread: 10
```

* **Default**: `10`.
* This controls the maximum capacity of Pingora connection pools. If the number of concurrent requests to a target exceeds this limit multiplied by the number of worker threads, new requests will fail or be queued depending on `maxQueueSize`.
