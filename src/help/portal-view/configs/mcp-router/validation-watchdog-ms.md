# MCP Router: schema.validationWatchdogMs

`schema.validationWatchdogMs` is an observational threshold for a schema
validation job.

- **Type:** Positive integer, in milliseconds
- **Default:** `50`
- **Alias accepted by the Rust loader:** `validationTimeoutMs`

When validation takes longer, the worker logs a warning with elapsed and
configured milliseconds. It does not interrupt or cancel the validator; the
name “watchdog” is intentional. Use `maxConcurrentValidations` to bound
admission and concurrency.

