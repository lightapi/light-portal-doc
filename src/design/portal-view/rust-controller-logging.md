# Rust Controller Logging

The controller service dashboard already has a logger page for Java runtimes.
That page is built around Logback concepts: named loggers, per-logger levels,
historical log content, and live streaming through controller-mediated MCP
tools. Rust products need a similar operator workflow, but the underlying
logging model is different. Rust services use `tracing` targets and one runtime
`logging.filter` expression instead of mutable Logback logger objects.

This document proposes a Rust-aware logger page for gateway, agent, API,
deployer, and workflow runtimes:

- `gtw`: `light-gateway`
- `agt`: `light-agent`
- `api`: Rust API services built on `light-axum` or `light-runtime`
- `dpl`: `light-deployer`
- `wf`: `light-workflow`

The goal is to keep the existing controller page entry point while switching
the page behavior based on runtime capabilities.

## Current State

`portal-view` has a unified controller logger page at
`/app/controller/logger`. The page receives a runtime instance from the control
pane dashboard and uses controller MCP tools:

- `get_loggers`
- `set_loggers`
- `get_log_content`
- `start_logs`
- `stop_logs`

Those contracts work for Java services where the runtime can inspect and update
Logback logger levels.

Rust services already expose live logging filter control through the
`light-runtime` MCP handler:

- `get_logging_filter`
- `set_logging_filter`
- `reload_modules` with `modules: ["runtime/logging"]`

The tested config server baseline is:

```yaml
logging.filter: info,light_pingora::security=debug
```

This keeps the process at `info` by default and enables `debug` only for the
gateway security target.

## Goals

- Provide one operator page for Rust log filter control, time-based history,
  and live streaming.
- Reuse the controller-mediated MCP path instead of adding direct browser
  access to runtime instances.
- Preserve the existing Java logger page behavior.
- Use Rust `tracing` vocabulary in the UI: target, level, filter expression,
  and source.
- Let operators build common filters without memorizing module paths.
- Keep an advanced filter input for exact `EnvFilter` expressions.
- Support time-range log lookup from the running process.
- Support live log streaming through `notifications/log`.
- Make reset behavior explicit: live filter changes are temporary unless the
  instance configuration is updated separately.

## Non-Goals

- Do not replace Java Logback logger management.
- Do not make the browser connect directly to pods, services, or container
  runtimes.
- Do not keep historical logs in portal-view or controller memory.
- Do not store full authorization headers, tokens, cookies, request bodies, or
  other secrets in log files, log responses, or live stream payloads.

## Runtime Detection

The logger page should select the Rust experience when either condition is
true:

- the selected runtime instance advertises product type `gtw`, `agt`, `api`,
  `dpl`, or `wf`
- the runtime MCP `tools/list` or controller tool discovery includes
  `get_logging_filter`

If detection is uncertain, portal-view can attempt `get_logging_filter` and
fall back to the Java logger page if the response says logging control is not
available.

The page should show a capability banner when a selected runtime supports only
some features:

| Capability | Required runtime support |
| --- | --- |
| Filter control | `get_logging_filter`, `set_logging_filter`, `reload_modules` |
| History | `get_log_content` backed by a JSON log file or platform log provider |
| Live stream | `start_logs`, `stop_logs`, `notifications/log` |

## Page Layout

Use the current logger page route and high-level structure, but render Rust
content when the selected instance is Rust.

Header:

- service label
- runtime instance ID
- service ID
- product type
- address and port
- connection status
- logging capability status

Tabs:

- `Filter`
- `History`
- `Live Stream`

The Java page can keep `Config`, `History`, and `Live Stream`; the Rust page
uses `Filter` instead of `Config` because the operator edits one `tracing`
filter expression, not a list of Logback logger objects.

## Filter Tab

The filter tab controls the active runtime `logging.filter`.

Controls:

- current effective filter
- filter source, such as `values.yml:logging.filter`, `env:RUST_LOG`, or
  `mcp:set_logging_filter`
- default level selector
- target rows for common Rust modules
- advanced filter text area
- `Apply Live`
- `Reset From Config`

Levels:

- `error`
- `warn`
- `info`
- `debug`
- `trace`
- `off`

Recommended default level is `info`.

Example generated filter:

```text
info,light_pingora::security=debug
```

Apply flow:

```text
operator changes target rows
  -> portal-view builds EnvFilter expression
  -> controller calls runtime set_logging_filter
  -> runtime validates and applies the filter immediately
  -> portal-view refreshes get_logging_filter
```

Reset flow:

```text
operator clicks Reset From Config
  -> controller calls reload_modules with runtime/logging
  -> runtime reloads logging.filter from current resolved values
  -> portal-view refreshes get_logging_filter
```

Baseline changes are handled outside this page. If an operator wants the filter
to survive restart or reset, they should update the selected instance
configuration, for example:

```yaml
logging.filter: info,light_pingora::security=debug
```

## Target Presets

The advanced filter must accept any valid Rust `tracing` target. The module
picker should be backed by reference data so new targets can be added without a
portal-view deployment.

Portal-view should load the dropdown from:

```text
/r/data?name=logging_target
```

Recommended reference table mapping:

| Reference field | Logging target use |
| --- | --- |
| `ref_table_t.table_name` | `logging_target` |
| `ref_value_t.value_code` | exact Rust `tracing` target, such as `light_pingora::security` |
| `value_locale_t.value_desc` | dropdown label and short operator-facing description |
| `ref_value_t.display_order` | stable dropdown order |
| `ref_value_t.active` | retire a target without deleting the row |

The simplest page can load all active targets from `/r/data?name=logging_target`
and group them client-side by product. If product-specific filtering is needed
later, add a reference relation such as `logging-target-product` that links each
target to `common`, `gtw`, `agt`, `api`, `dpl`, or `wf`. Operators can still
type a custom target if the target is not present in the reference table.

Suggested seed data:

Common targets:

| Target | Use |
| --- | --- |
| `light_runtime` | bootstrap, config loading, reload, controller registration |
| `light_client` | outbound HTTP and OAuth client support |
| `portal_registry` | control-plane websocket registration |
| `reqwest` | outbound HTTP client internals |
| `hyper_util` | connection and pooling internals |
| `rustls` | TLS handshakes and certificates |
| `tungstenite` | websocket handshake and frames |

Gateway targets:

| Target | Use |
| --- | --- |
| `light_gateway` | gateway application and proxy glue |
| `light_pingora` | shared Pingora framework code |
| `light_pingora::security` | JWT validation and JWK loading |
| `light_pingora::unified_security` | unified auth routing |
| `light_pingora::mcp` | MCP router and backend MCP calls |
| `light_pingora::handler` | handler duration diagnostics |
| `light_pingora::pii_tokenization` | tokenization runtime warnings |
| `pingora_core` | Pingora server and protocol lifecycle |
| `pingora_proxy` | Pingora proxy request handling |

Agent targets:

| Target | Use |
| --- | --- |
| `light_agent` | agent HTTP server and session handling |
| `model_provider` | model-provider calls and fallback routing |
| `mcp_client` | outbound MCP client requests |

API targets:

| Target | Use |
| --- | --- |
| `light_axum` | HTTP transport and axum integration |
| `light_runtime` | shared runtime modules |
| service crate target | API-specific handlers, using the crate name with hyphens converted to underscores |

Deployer targets:

| Target | Use |
| --- | --- |
| `light_deployer` | deployment workflow and git/Kubernetes operations |
| `light_runtime` | shared runtime modules |

Workflow targets:

| Target | Use |
| --- | --- |
| `light_workflow` | workflow engine, consumers, and task executor |
| `workflow_core` | workflow model and shared core logic |
| `light_rule` | rule execution |
| `model_provider` | model-provider calls |
| `mcp_client` | MCP tool calls |

The UI can also learn targets from returned history and live rows. Any target
seen in logs can become a temporary suggestion for that browser session, but
the authoritative dropdown source is the `logging_target` reference table.

## History Tab

The history tab fetches logs from the running application for a time range.

Controls:

- presets: last 5, 10, 30, and 60 minutes
- required start time
- optional end time
- minimum level
- optional target filter
- text search
- result limit

Request:

```json
{
  "runtimeInstanceId": "019...",
  "startTime": "2026-06-17T21:30:00Z",
  "endTime": "2026-06-17T21:45:00Z",
  "loggerLevel": "debug",
  "loggerName": "light_pingora::security",
  "limit": 1000
}
```

For compatibility, `loggerName` maps to the Rust target and `loggerLevel` maps
to the minimum tracing level. The controller can keep the existing
`get_log_content` tool name.

Recommended normalized row shape:

```json
{
  "timestamp": "2026-06-17T21:37:43.147463Z",
  "level": "DEBUG",
  "logger": "light_pingora::security",
  "target": "light_pingora::security",
  "message": "JWT validation failed after JWKS refresh: InvalidSignature",
  "fields": {
    "error": "InvalidSignature"
  }
}
```

The response can preserve the current grouped shape for compatibility:

```json
{
  "content": {
    "light_pingora::security": {
      "logs": [
        {
          "timestamp": "2026-06-17T21:37:43.147463Z",
          "level": "DEBUG",
          "message": "JWT validation failed after JWKS refresh: InvalidSignature"
        }
      ]
    }
  }
}
```

Portal-view should flatten the grouped response into rows, as the current Java
page already does.

History source selection:

1. If a JSON log file is configured, parse that file first. This should be the
   preferred source because the same file can be collected by Splunk or another
   logging system.
2. If no log file is configured, use Kubernetes pod logs or container logs when
   the controller/runtime environment can access them.
3. If neither source is available, return an explicit unsupported response.

The browser must not read Kubernetes or container logs directly. The controller
or runtime-side tool should own that platform access and return the normalized
row shape above.

When reading a JSON log file, the reader should filter by timestamp, level,
target, and text search. If the file format is line-oriented JSON, each line
should contain at least `timestamp`, `level`, `target`, and `message`.

## Live Stream Tab

The live stream tab starts and stops log streaming for the selected runtime
instance.

Controls:

- full filter expression
- start
- stop
- clear
- auto-scroll toggle
- bounded client buffer
- stream status

Request:

```json
{
  "runtimeInstanceId": "019...",
  "filter": "info,light_pingora::security=debug"
}
```

`start_logs` should accept the full Rust filter expression because this is the
syntax Rust operators already use. For backward compatibility, the controller
can still accept `level` and `loggerName`, then translate them into a filter
expression.

The stream filter controls which events are sent to that stream subscription.
It must not change the process-wide `logging.filter`; process-wide changes
still go through `set_logging_filter`. Because `tracing` filters can suppress
events before stream filtering sees them, the UI should warn when the stream
filter is more verbose than the current active runtime filter.

Notification:

```json
{
  "method": "notifications/log",
  "params": {
    "runtimeInstanceId": "019...",
    "timestamp": "2026-06-17T21:37:43.147463Z",
    "level": "DEBUG",
    "logger": "light_pingora::security",
    "target": "light_pingora::security",
    "message": "JWT validation failed after JWKS refresh: InvalidSignature"
  }
}
```

The portal-view live buffer should remain bounded. The current 1000-row FIFO
buffer is a good default.

Each browser/controller session must have its own stream subscription. Starting
a stream from one operator must not replace another operator's stream for the
same runtime instance.

## Runtime Implementation

Add shared Rust logging support to `light-runtime`, not separately in every
product.

Recommended components:

- `LoggingControl`: existing active `EnvFilter` control.
- `JsonLogWriter`: optional line-oriented JSON file writer for services that
  need historical lookup or Splunk ingestion.
- `LogFileReader`: reads and filters configured JSON log files.
- `PlatformLogProvider`: controller-side or runtime-side abstraction for
  Kubernetes pod logs and container logs when no log file is configured.
- `LogStreamHub`: per-client subscriptions for live streaming.
- `LogRecord`: normalized timestamp, level, target, message, fields, and
  optional span/correlation fields.

Recommended runtime MCP tools:

| Tool | Purpose |
| --- | --- |
| `get_logging_filter` | Return current Rust filter and source. |
| `set_logging_filter` | Validate and apply a live filter expression. |
| `get_log_content` | Return log rows from JSON file or platform log provider by time range, level, and target. |
| `start_logs` | Start live log notifications for one controller client with a full filter expression. |
| `stop_logs` | Stop live log notifications for one controller client. |
| `reload_modules` | Reset `runtime/logging` from resolved config values. |

The JSON log file should be configurable:

```yaml
logging.file.enabled: true
logging.file.path: /var/log/light-gateway/app.log
logging.file.format: json
logging.file.maxBytes: 104857600
logging.file.maxFiles: 10
logging.stream.maxSubscribers: 20
```

Defaults should be conservative. If no JSON log file and no platform log
provider are available, `get_log_content` should return a clear unsupported
response instead of an empty success that looks like there were no logs.

## Controller Changes

The controller should expose Rust logging tools through the same `callTool`
path used by the existing logger page.

Add or pass through these tool names:

- `get_logging_filter`
- `set_logging_filter`
- `reload_modules`
- `get_log_content`
- `start_logs`
- `stop_logs`

For Rust runtimes, `get_loggers` and `set_loggers` are not the primary control
surface. The UI should use `get_logging_filter` and `set_logging_filter`
instead. The controller may keep `get_loggers` and `set_loggers` for Java
compatibility.

The controller should route `notifications/log` back to the portal-view
websocket with the originating `runtimeInstanceId` so the page can ignore logs
from other selected services.

For history, the controller should resolve sources in this order:

1. configured JSON log file
2. Kubernetes or container log provider
3. unsupported response with a clear reason

## Portal-View Implementation

Recommended structure:

- keep `/app/controller/logger` as the route
- keep the existing `Logger` component as the shell
- split Java and Rust behavior into child panels:
  - `JavaLoggerPanel`
  - `RustLoggerPanel`
- reuse the current history and live table rendering where possible
- add a Rust filter builder for `logging.filter`

Rust filter builder state:

```ts
type RustFilterDraft = {
  defaultLevel: "error" | "warn" | "info" | "debug" | "trace" | "off";
  targets: Array<{ target: string; level: string }>;
  advanced: string;
  mode: "builder" | "advanced";
};
```

In builder mode, portal-view generates the expression:

```text
<defaultLevel>,<target>=<level>,<target>=<level>
```

In advanced mode, portal-view sends the text exactly as entered and lets the
runtime validate it.

The page should show a warning when the current source is
`mcp:set_logging_filter`, because that indicates a live override that can be
lost on restart or reset by reloading `runtime/logging`.

## Baseline Configuration

Live debug changes should call `set_logging_filter`; they should not update
config server by default.

To persist a baseline filter, the operator should use the instance
configuration page and update:

```yaml
logging.filter: info,light_pingora::security=debug
```

After saving the instance configuration, the config update flow can call:

```json
{
  "name": "reload_modules",
  "arguments": {
    "modules": ["runtime/logging"]
  }
}
```

This makes the saved config the active baseline. Alternatively, the operator
can return to the logger page and use `Reset From Config` to reload only
`runtime/logging`.

The Rust logger page can link to the selected instance configuration, but it
should not write baseline config itself.

## Security And Safety

- Gate filter changes and log access behind the same controller permissions as
  the Java logger page.
- Treat logs as sensitive operational data.
- Do not render raw ANSI escape sequences as HTML.
- Truncate very large messages and expose an expand action.
- Mask obvious token and secret fields in JSON log output, history responses,
  and live stream payloads.
- Rate-limit live streams per runtime instance and per controller client.
- Show a warning before enabling broad `trace` filters.

## Rollout Plan

1. Add controller pass-through for `get_logging_filter` and
   `set_logging_filter`.
2. Add `RustLoggerPanel` in portal-view with filter control only.
3. Add JSON file logging and a `get_log_content` reader for Rust services.
4. Add Kubernetes/container log fallback when no log file is configured.
5. Add Rust `start_logs` and `stop_logs` backed by per-client stream
   subscriptions.
6. Seed the `logging_target` reference data and load dropdown options from
   `/r/data?name=logging_target`.
7. Enable product-specific target presets for `gtw`, `agt`, `api`, `dpl`, and
   `wf`.

## Resolved Decisions

- Historical logs are not kept in memory. Use a configured JSON log file first;
  if there is no file, fall back to Kubernetes or container logs when they are
  available.
- `start_logs` accepts a full `filter` expression. Compatibility fields such as
  `level` and `loggerName` can be translated by the controller.
- The module dropdown is backed by the `logging_target` reference table exposed
  through `/r/data?name=logging_target`.
- The logger page does not save a baseline. Baseline changes belong in instance
  configuration.
