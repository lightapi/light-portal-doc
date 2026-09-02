# Operational Storage

> **Implementation status:** P0 through P7 are complete. Clean installs and
> retained-volume upgrades import the same canonical registration and API
> closure deltas.

The Operational Storage page registers the existing database used by a Host's
runtime services. It does not create or provision a database.

Open **Host Admin**, find the Host, and select its **Operational Storage** row
action. The heading shows the selected Host's fully qualified name, such as
`dev.networknt.com`.

## Access

Users with the `host-viewer` or `host-admin` role can inspect the page. A
`host-admin` can register, update, deactivate, or unregister storage. These
actions change the Config Server binding; they never create, alter, or delete
the customer's database.

## Host scope

The selected Host is the storage scope. There is no separate Environment field.

When you open this page from `dev.networknt.com`, the registration belongs to
`dev.networknt.com`. It cannot be used to register storage for
`test.networknt.com`; return to Host Admin and open that Host instead.

## Before registration

The database must already exist. The customer or deployment owner is responsible
for:

- creating and operating the PostgreSQL database;
- installing the required schemas and migrations;
- creating least-privilege runtime roles;
- configuring network and TLS access; and
- storing the runtime credential in an approved secret mechanism.

## Register storage

Enter the PostgreSQL server, port, database name, TLS mode, mounted credential
file path, and required schema and credential generations.
Then select **Register storage**.

The credential reference must be an absolute path visible to each runtime
service. Portal publishes that exact path as `databaseUrlFile`; arbitrary secret
provider identifiers are not accepted until runtime secret-provider resolution
is implemented. Registration requests use an idempotency key so a retry cannot
create a second binding.

Runtime usernames are intentionally not registered at Host scope. Agent,
Workflow, Gateway, A2A, Execution, and Deployer use separate least-privilege
roles supplied by their own deployment secrets while sharing this endpoint
policy.

Portal stores the Host binding in its control-plane database and publishes the
connection contract through Config Server. Customer runtime services load their
Host-specific configuration, resolve the credential from their deployment, and
connect directly to the operational database. Light Portal does not connect to
it.

Passwords and password-bearing database URLs must not be entered into fields
that are documented as non-secret. Put the URL in the mounted credential file.

## Registration details

The registration card shows:

- lifecycle and publication state;
- engine, server, port, and expected database identity;
- minimum schema and credential generations;
- mounted credential-file path;
- binding version and digest; and
- optional runtime validation information when available.

The page does not show provisioning jobs, attempts, provider containers, or
database-decommission controls.

## Lifecycle actions

- **Update registration** publishes a new version of an active connection contract.
- **Reactivate registration** is shown for a deactivated registration and asks
  for confirmation before republishing it.
- **Deactivate** revokes runtime publication while retaining the registration
  history and all customer data.
- **Unregister** removes the active binding from future Config Server
  publication.

Neither Deactivate nor Unregister drops the database. Database backup, retention,
credential rotation, and deletion remain customer or deployment operations.

Version-1 provisioning records, if present from an older deployment, appear as
read-only history. The page cannot retry or resume those provisioning jobs.

## Local demonstration databases

The standard local, development, bootstrap, and installer profiles use one
PostgreSQL container and register these defaults:

| Host | Database |
| --- | --- |
| `dev.lightapi.net` | `operations` |
| `dev.networknt.com` | `operations_networknt` |
| `dev.taiji.io` | `operations_taiji` |

These databases are created by deployment initialization, not by this page.
