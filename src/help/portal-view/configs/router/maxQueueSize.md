# Router: maxQueueSize

The `maxQueueSize` property specifies the maximum number of requests that can be queued when all connections are busy.

## Configuration Options

```yaml
maxQueueSize: 0
```

* **Default**: `0`.
* A value of `0` means requests will immediately fail if the `connectionsPerThread` limit is reached.
* Setting a higher value allows the router to temporarily hold requests in a queue until a connection becomes available.
