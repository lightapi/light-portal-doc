# HttpClient Retry

Since the JDK HttpClient supports proxy configuration, we use it to connect to external services through NetSkope or McAfee gateways within an enterprise environment. When comparing it with the light-4j Http2Client, we identified several important behavioral differences and usage considerations.

### Unresolved InetSocketAddress

When configuring a proxy for the JDK HttpClient, it is important to use an unresolved socket address for the proxy host.

```
        if (config.getProxyHost() != null && !config.getProxyHost().isEmpty()) {
            clientBuilder.proxy(ProxySelector.of(
                    InetSocketAddress.createUnresolved(
                            config.getProxyHost(),
                            config.getProxyPort() == 0 ? 443 : config.getProxyPort()
                    )
            ));
        }

``` 

Using InetSocketAddress.createUnresolved() ensures that DNS resolution occurs when a new connection is established, rather than at client creation time. This allows DNS lookups to respect TTL values and return updated IP addresses when DNS records change.

### Retry with Temporary HttpClient

The JDK HttpClient is a heavyweight, long-lived object and should not be created frequently. It also does not expose APIs to directly manage connections (for example, closing an existing connection and retrying with a fresh one).

A naive retry strategy is to create a new HttpClient instance for retries. Below is an implementation we used for testing purposes:

```
                    /*
                    A new client is created from the second attempt onwards as there is no way we can create new connections. Since this handler
                    is a singleton, it would be a bad idea to repeatedly abandon HttpClient instances in a singleton handler. It will cause leak
                    of resource. We need a clean connection without abandoning the shared resource. The solution is to create a temporary fresh
                    client from the second attempt and discard it immediately to minimize resource footprint.
                    */
                    int maxRetries = config.getMaxConnectionRetries();
                    HttpResponse<byte[]> response = null;

                    for (int attempt = 0; attempt < maxRetries; attempt++) {

                        try {
                            if (attempt == 0) {
                                // First attempt: Use the long-lived, shared client
                                response = this.client.send(request, HttpResponse.BodyHandlers.ofByteArray());
                            } else {
                                // Subsequent attempts: Create a fresh, temporary client inside a try-with-resources
                                logger.info("Attempt {} failed. Creating fresh client for retry.", attempt);

                                try (HttpClient temporaryClient = createJavaHttpClient()) {
                                    response = temporaryClient.send(request, HttpResponse.BodyHandlers.ofByteArray());
                                } // temporaryClient.close() called here if inner block exits normally/exceptionally
                            }
                            break; // Success! Exit the loop.
                        } catch (IOException | InterruptedException e) {
                            // Note: The exception could be from .send() OR from createJavaHttpClient() (if attempt > 0)
                            if (attempt >= maxRetries - 1) {
                                throw e; // Rethrow exception on final attempt failure
                            }
                            logger.warn("Attempt {} failed ({}). Retrying...", attempt + 1, e.getMessage());
                            // Loop continues to next attempt
                        }
                    }

```

#### Load Test Findings


We created a test project under light-example-4j/instance-variable consisting of a caller service and a callee service. The caller created a new HttpClient per request.

During load testing, we observed:

* Extremely high thread and memory utilization

* Very poor throughput

* Sustained 100% CPU usage for several minutes after traffic stopped, as the JVM attempted to clean up HttpClient resources

This behavior exposes several serious problems.

#### Identified Problems

The following is the problems: 

1.  **Resource Exhaustion (Threads & Native Memory)**
    The `java.net.http.HttpClient` is designed to be a long-lived, heavy object. When you create an instance, it spins up a background thread pool (specifically a `SelectorManager` thread) to handle async I/O.
    If you create a new client for **every** HTTP request, you are spawning thousands of threads. Even though the `client` reference is overwritten and eventually Garbage Collected, the background threads may not shut down immediately, leading to `OutOfMemoryError: unable to create new native thread` or high CPU usage.

2.  **Loss of Connection Pooling (Performance Killer)**
    The `HttpClient` maintains an internal connection pool to reuse TCP connections (Keep-Alive) to the downstream service (`localhost:7002`). By recreating the client every time, you force a new TCP handshake (and SSL handshake if using HTTPS) for every single request. This drastically increases latency.

3.  **Thread Safety (Race Condition)**
    Your handler is a singleton, meaning one instance of `DataGetHandler` serves all requests.
    You have defined `private HttpClient client;` as an instance variable.
    *   **Scenario:** Request A comes in, creates a client, and assigns it to `this.client`. Immediately after, Request B comes in and overwrites `this.client` with a *new* client.
    *   Because `handleRequest` is called concurrently by multiple Undertow worker threads, having a mutable instance variable shared across requests is unsafe. While it might not crash immediately, it is poor design to share state this way without synchronization (though in this specific logic, you don't actually *need* to share the state, which makes it even worse).


### Connection: close Header

Given the above findings, creating temporary HttpClient instances for retries is too risky. Further investigation revealed a safer and more efficient approach: forcing a new connection using the Connection: close header.

By disabling persistent connections for a retry request, the existing HttpClient can be reused while ensuring the next request establishes a fresh TCP connection.

#### Why this is better than creating a new HttpClient

* Lower Resource Overhead: Recreating HttpClient creates a new SelectorManager thread and internal infrastructure, which is a heavy operation.

* Prevents Thread Leaks: Repeatedly creating and discarding clients can lead to "SelectorManager" thread buildup if not closed properly.

* Clean Socket Management: The Connection: close header handles the lifecycle at the protocol level, allowing the existing client’s thread pool to remain stable. 

#### How does the header work

The Connection: close header instructs both the client and the server (or load balancer) to terminate the TCP connection immediately after the current request/response exchange is finished. When you use this header on a retry, the following happens:

* Current Request: The client established a connection (or reused one) to send the request.

* After Response: Once the response is received (or the request fails), the client's internal pool will not return that connection to the pool; it will close the socket.

* Next Attempt: Any subsequent request made by that same HttpClient instance will be forced to open a brand-new connection. This fresh connection will hit your load balancer again, which can then route it to a different, healthy node. 

#### Recommended Retry Strategy (Three Attempts)

In most high-availability scenarios, retrying a third time (or using a "3-strikes" policy) is recommended. Here is the optimal sequence:

* 1st Attempt (Normal): Use the default persistent connection. This is fast and efficient.

* 2nd Attempt (The "Fresh Connection" Retry): Use the Connection: close header. This forces the load balancer to re-evaluate the target node if the first one was dead or hanging.

* 3rd Attempt (Final Safeguard): If the second attempt fails, it is often worth one final try with a small exponential backoff (e.g., 500ms–1s). This helps in cases of transient network congestion or when the load balancer hasn't yet updated its health checks to exclude the failing node. 


```
                    /*
                     * 1st Attempt (Normal): Use the default persistent connection. This is fast and efficient.

                     * 2nd Attempt (The "Fresh Connection" Retry): Use the Connection: close header. This forces
                     *  the load balancer to re-evaluate the target node if the first one was dead or hanging.

                     * 3rd Attempt (Final Safeguard): It will use a new connection to send the request.
                     */
                    int maxRetries = config.getMaxConnectionRetries();
                    HttpResponse<byte[]> response = null;

                    for (int attempt = 0; attempt < maxRetries; attempt++) {
                        try {
                            HttpRequest finalRequest;

                            if (attempt == 0) {
                                // First attempt: Use original request (Keep-Alive enabled by default)
                                finalRequest = request;
                            } else {
                                // Subsequent attempts: Force a fresh connection by adding the 'Connection: close' header.
                                // This ensures the load balancer sees a new TCP handshake and can route to a new node.
                                logger.info("Attempt {} failed. Retrying with 'Connection: close' to force fresh connection.", attempt);

                                finalRequest = HttpRequest.newBuilder(request, (name, value) -> true)
                                        .header("Connection", "close")
                                        .build();
                            }

                            // Always use the same shared, long-lived client
                            response = this.client.send(finalRequest, HttpResponse.BodyHandlers.ofByteArray());
                            break; // Success! Exit the loop.

                        } catch (IOException | InterruptedException e) {
                            if (attempt >= maxRetries - 1) {
                                throw e; // Rethrow on final attempt
                            }
                            logger.warn("Attempt {} failed ({}). Retrying...", attempt + 1, e.getMessage());

                            // Optional: Add a small sleep/backoff here to allow LB health checks to update
                        }
                    }

```

#### Header Restriction

Header Restriction: Ensure your JVM is started with -Djdk.httpclient.allowRestrictedHeaders=connection to allow the HttpClient to modify the Connection header.

