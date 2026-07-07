# Router: softMaxConnectionsPerThread

The `softMaxConnectionsPerThread` property defines the soft limit on concurrent connections per thread before the router starts queuing requests or applying backpressure.

## Configuration Options

```yaml
softMaxConnectionsPerThread: 5
```

* **Default**: `5`.
* This should be less than or equal to `connectionsPerThread`. It helps in load balancing and managing connection bursts gracefully.
