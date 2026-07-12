# Clone an Instance

Instance Clone creates a new instance from the active, projected configuration
of an existing instance. Open **Instance Admin** and select the **Clone** action
on an instance you own. Administrators may clone any visible instance. A
read-only source cannot be cloned.

The page reloads and authorizes the source on the server. Values passed from
the Instance Admin row are navigation hints only and are not trusted as the
clone source.

## What is cloned

The plan can copy the following active instance graph:

- the instance definition, tags, and categories;
- instance APIs, path prefixes, apps, and app/API links;
- overridden configuration properties at instance, API, app, app/API, and
  deployment-instance scope;
- selected instance files;
- selected deployment definitions and their overridden properties;
- an optional current configuration snapshot.

Runtime instances, OAuth clients, authorization sessions/tokens, deployment
jobs and operational status, audit history, notifications, and other transient
records are not cloned. Create the target OAuth client after the clone reaches
a successful terminal status.

## Target identity

Enter a unique target instance name and environment tag. Environment defaults
to the environment tag. Service and product version default to the source when
left blank. The preview shows the resolved `(host, service, environment)`
snapshot lookup tuple.

For the portal BFF workflow, use separate environment tags and instances:

| Environment tag | Configuration source | Typical instance |
|---|---|---|
| `loc` | `portal-config-loc` | local portal BFF |
| `dev` | `portal-config-dev` | development portal BFF |
| `demo` | `light-portal-install` | install/demo portal BFF |

Keeping these instances separate prevents one environment's gateway redirect,
cookie, host, or service configuration from being reused by another.

## Masked configuration values

Every overridden property is masked initially. Choose one action per stable
scope/property selector:

- **COPY** copies the source value server-side without revealing it;
- **REPLACE** validates and stores the replacement entered on the page;
- **OMIT** leaves the target override absent so effective lower-precedence
  configuration can apply.

**Reveal** returns one property value through a separate audited request. It
never reveals file or certificate content. Revealed values are cleared when a
selector changes or the plan is refreshed, and they are not included in the
plan fingerprint.

COPY and REPLACE are checked against the current property schema. OMIT is
checked against the resulting effective target configuration. If a source
value no longer satisfies the current schema, replace or omit it and plan
again.

## Optional resources

Files and deployment definitions are excluded by default. Enable them and
select individual IDs explicitly. Confirm certificate copying before planning
any selected certificate/file set. File content remains server-side and is not
returned in the preview.

Creating a current snapshot is also optional. When selected, the snapshot
event is written last and successful completion is reported as
`SNAPSHOT_READY`.

## Plan and execute

Select **Plan Clone** to validate authorization, target uniqueness, current
schemas, selected resources, limits, and source projection parity. The preview
shows warnings plus exact event and serialized-byte counts.

Any target, property, file, deployment, certificate-confirmation, or snapshot
change invalidates the preview and disables **Clone** until planning succeeds
again. **Clone** submits the complete plan once. A browser timeout does not
mean the clone failed and must not be followed by another submission; use
**Refresh status** with the original request instead.

## Status and recovery

The status values are:

- `ACCEPTED`: the atomic event/outbox transaction committed and is waiting for
  projection;
- `PROJECTED`: the target projected successfully without a requested snapshot;
- `SNAPSHOT_READY`: the target and requested snapshot projected successfully;
- `FAILED_DLQ`: projection rolled back and the transaction was moved to the
  dead-letter queue.

While accepted, the page polls one request at a time with capped backoff and
pauses when the tab is hidden or the browser is offline. A transient status
failure displays **Still processing** and offers a manual refresh; it does not
resubmit the clone.

For `FAILED_DLQ`, record the clone request ID and safe error code and contact an
administrator. Do not create another clone request until the original DLQ
transaction is diagnosed. A repaired replay must use the original transaction
metadata.

After `PROJECTED` or `SNAPSHOT_READY`, use **Open Instance**, **Open
Configuration**, or **Create OAuth Client** to continue setup.

