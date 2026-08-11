# Knowledge Bases

Use `/app/genai/KnowledgeBases` to create tenant Knowledge Bases, manage bounded
ingestion policies, attach immutable Git/Markdown sources, and inspect indexing
and access-control evidence.

## Ownership and ingestion policies

An ingestion policy is a reusable set of hard ceilings for a source build. The
policy controls document, chunk, source-byte, stored-byte, embedding-token,
spend, elapsed-time, and concurrency limits.

The platform supports more than one policy:

- A **global policy** is owned by the light-portal installation and is visible
  to every tenant. A platform administrator creates and maintains it.
- A **tenant policy** is owned by one Portal host and is visible only to that
  tenant. Create one when that tenant needs limits different from the global
  choices.

A tenant does not need to create its own policy when a suitable global policy
exists. A typical installation publishes a small set of named global policies,
such as standard documentation and large documentation, and adds tenant
policies only for exceptions. The model is therefore not a single bootstrap
singleton. Bootstrap may create a safe starter global policy, but the UI and
services remain the source of truth for managing multiple policies.

Do not generate or type a random ingestion policy UUID. Create the policy on
the Knowledge Bases page; the service generates its UUID. The Add source dialog
then lists the active global and current-tenant policies by name.

Deactivating a policy prevents new source selections. Portal refuses to
deactivate it while a non-deleted source still refers to it; migrate or remove
those sources first. Inactive policies remain visible in the management list
and can be reviewed and reactivated with an update.

## Add a Git/Markdown source

Open a Knowledge Base, select **Sources**, and choose **Add Git/Markdown
source**.

Fill the form as follows:

- **Display name:** a short label such as `light-fabric documentation`.
- **Approved repository URI:** the public HTTPS clone URI. For light-fabric,
  use `https://github.com/networknt/light-fabric.git`.
- **Immutable commit:** the complete 40- or 64-character commit SHA that was
  reviewed. Do not enter `main`, `master`, a tag, or another movable ref.
- **Ingestion policy:** select an existing global or current-tenant policy.

The light-fabric repository may be used even though it contains both source
code and documents. The Phase 1a connector ignores non-Markdown files and
symlinks, does not execute repository hooks, and rejects repositories containing
Git submodules. In the current pilot it
scans every Markdown file in the checked-out commit, not only `docs/`.
Repository include/exclude controls are not yet enforced by the worker, so
README files and other Markdown outside `docs/` may also be indexed. Use a
documentation-only repository or reviewed commit when that broader Markdown
set is not acceptable.

### Why branches are rejected

A branch name can point to different content between approval and ingestion.
Pinning the source to a full commit makes the checkout reproducible, gives the
worker an exact content identity, and prevents an unreviewed branch update from
silently entering the index. To ingest a newer revision, update the source to a
new reviewed commit and start another sync.

## Runtime enforcement boundary

Portal stores the selected policy and validates that it is either global or
owned by the Knowledge Base tenant. The Phase 1a worker still obtains its
effective source limits from the deployed worker configuration. Until the
worker resolves the selected policy at job start, administrators must keep the
worker limits at least as restrictive as the selected Portal policy. A stored
policy must not be treated as runtime-enforced merely because its UUID appears
on a source.

## Authentication and error messages

Knowledge query actions require `portal.r`; mutation actions require `portal.w`.
The light-portal contract does not use `portal.knowledge.r` or
`portal.knowledge.w`.

JWT security runs before the query or command handler. When a valid token lacks
the action scope, security returns a structured `403` response such as
`AUTH_TOKEN_SCOPE_MISMATCH`. Portal displays the backend message so an
administrator can distinguish insufficient scope from a failed Knowledge Base
operation. This does not expose the token or its claims.

If the page shows **Knowledge Base operation failed**, inspect the gateway and
service response. Common causes are a missing access-control route, a token
without `portal.r` or `portal.w`, an unavailable GenAI query/command service, or
an object that is not visible to the selected tenant.

## Recommended setup

1. A platform administrator creates at least one conservative global ingestion
   policy, or the installation bootstraps a starter global policy.
2. A tenant administrator creates a tenant Knowledge Base.
3. Create a tenant policy only when the global choices are unsuitable.
4. Add an HTTPS Git source pinned to a reviewed full commit SHA.
5. Select the policy by name and create the source.
6. Confirm the deployed worker configuration enforces equal or tighter limits.
7. Run the source sync and review documents, generations, access evidence, and
   quality evidence before promotion.
