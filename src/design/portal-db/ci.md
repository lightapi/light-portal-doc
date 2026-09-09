# Portal DB CI Design

Portal DB CI verifies that a fresh installation, the explicitly supported upgrade paths, and the runtime database policies agree. It also verifies that the checked-in installation artifacts can be reproduced from their authoritative sources. A successful schema load alone is insufficient: retained data, migration rejection, replay behavior, documentation, and environment isolation are part of the contract.

This document describes the implementation reviewed on September 9, 2026. Paths beginning with `postgres/` or `.github/` refer to the `portal-db` repository. The implementation and its executable contracts remain authoritative as the schema evolves.

## Qualification status

The completed review independently reproduced a clean run of `postgres/tests/run-ci-schema-gates.sh` against the pinned PostgreSQL 17.10 image: **23/23 gates passed, exit 0**. This includes generation under a different authenticated role, install-time seed attribution, and repeated seed insertion. The four previously failing jobs have been addressed locally.

At that review checkpoint, GitHub Actions had not run the revised implementation. Its composite action, workspace bind mount under `GITHUB_WORKSPACE`, and service-container connectivity still required remote qualification. Local success must not be described as a verified green GitHub run.

Repository ruleset and branch-protection API requests previously returned HTTP 403 with the requirement to upgrade the GitHub plan or make the private repository public. This is a recorded operational constraint, not a continuously verified repository setting. Passing CI does not currently establish enforced merge protection.

## Motivation and failure model

The repair began with four failed jobs in run `34364264434`: `execution-schema-gate`, `llm-control-plane-schema-gate`, `cascade-delete-policy-schema-gate`, and `multi-schema-environment-gate`. Documentation and cascade behavior were steps within one job; they were not two failed jobs.

Several failures had shared structural causes:

| Failure | Design response |
| --- | --- |
| Canonical schema and hand-maintained upgrade chains drifted apart | Declare baseline-specific migration phases and compare the resulting schema with canonical state |
| A dump conversion lost the runtime-section markers expected by a shell script | Generate an explicit repeatable cascade installer from authoritative inputs |
| Documentation and cascade steps attempted to load the standalone DDL into the same database | Give independent installation gates separate disposable databases |
| A bare `psql` invocation authenticated as the runner OS user | Set `PGUSER` explicitly for environment-driven bootstrap calls |
| An earlier failed step hid later independent gates | Continue independent steps after failures while preserving real prerequisite dependencies |
| Generated seed values captured the generating role | Emit install-time defaults for session-owned attribution and test a distinct authenticated role |
| Dump regeneration depended on floating tool versions | Pin database server and clients together and narrowly normalize dump metadata |

The initial observed failures did not define the complete defect set. The workflow-tool gate and shared-grants transaction gate were previously masked by earlier failures. Isolation and failure reporting therefore precede conclusions about how many repairs are necessary.

## Architecture

```mermaid
flowchart TD
    Sources[Authoritative schema inputs] --> Generate[Materialize in an empty pinned database]
    Generate --> Dump[Dump catalog and assemble seeds and runtime]
    Dump --> Artifacts[Checked-in generated SQL]
    Artifacts --> Fresh[Fresh-install gates]
    Sources --> Reproduce[Regenerate and compare]
    Artifacts --> Reproduce
    Baselines[Declared historical baselines] --> Phases[Ordered migration phases and retained-data fixtures]
    Phases --> Compare[Canonical and migrated schema comparison]
    Artifacts --> Compare
    Fresh --> Behavior[Documentation, seed, cascade and isolation assertions]
    Phases --> Safety[Abort, rollback and replay assertions]
    Inventory[Patch inventory and dependency contracts] --> Coverage[Coverage disposition and workflow filter checks]
```

These checks establish complementary properties. A generation comparison detects stale artifacts. A migration comparison detects an incomplete upgrade path. Behavioral fixtures detect defects that identical table definitions cannot expose. Inventory checks make the limits of qualification visible.

## Canonical generation contract

### Sources and outputs

`postgres/bin/generate-ddl.py` materializes these inputs in order:

| Input | Responsibility |
| --- | --- |
| `postgres/schema/base.sql` | Final-state schema and schema-owned seed source, initialized from commit `4d6842a` |
| `postgres/schema/comments.sql` | Explicit table and column documentation introduced by the CI repair |
| `postgres/schema/policies.sql` | Reviewed additions to the cascade relationship inventory |
| `postgres/schema/cascade-finalize.sql` | Policy validation and repeatable trigger installation |
| `postgres/schema/toolchain.env` | Pinned PostgreSQL image and Node version used by the tooling |

`base.sql` is an authoring input. Subsequent generation does not overwrite it. Fresh-install changes belong in these sources, with corresponding upgrade patches where required.

The generator writes five outputs:

- `postgres/ddl.sql`: the complete standalone fresh-install script.
- `postgres/schema/seeds.generated.sql`: the non-cascade schema-owned seed section, also embedded in `ddl.sql`.
- `postgres/schema/cascade-runtime.generated.sql`: the repeatable cascade installer, also embedded in `ddl.sql`.
- `postgres/patch_20260909_02_schema_documentation.sql`: the documentation upgrade wrapped in a transaction.
- `postgres/patch_20260909_03_cascade_install.sql`: the generated cascade upgrade installer.

Do not hand-edit these outputs. Regenerate them after changing their sources. `--check` compares regenerated content with the checked-in artifacts and fails on drift.

The standalone contract includes stored procedures, trigger functions, trigger installation, cascade-policy synchronization, comments, and schema-owned seeds. It introduces no `\i` or `\ir` dependency into `ddl.sql`. Application bootstrap data such as `init-lightapi.sql` remains a separate installation step.

The canonical DDL is a **fresh-install artifact**, not an idempotent upgrade script. Replaying its bare `CREATE TABLE` statements into a populated database is invalid. Replay guarantees apply to the designated seed section, cascade installer, and qualified migration transitions.

### Reproducibility and toolchain

The reviewed toolchain uses PostgreSQL server and client version **17.10**, Node **24.14.0**, and this database image:

```text
pgvector/pgvector@sha256:d2ef61f42ef767baa5a1475393303cc235bcd92febd9d7014eddb48b41f3bad0
```

The generator checks the server version and `pg_dump` version before generation. The comparison normalizes only:

1. The matching random `\restrict` and `\unrestrict` token.
2. The `Dumped from database version` header.
3. The `Dumped by pg_dump version` header.

Missing, mismatched, or multiple restriction-token pairs fail validation. Catalog definitions and seed data are not normalized away. Header normalization does not authorize a version change because the toolchain is checked separately.

The canonical script's restriction commands require a compatible `psql`; the repository README documents 17.6+, 16.10+, 15.14+, or 14.19+. Reproducible generation has the stricter pinned 17.10 requirement. JDBC-only consumers can generate a DBVisualizer copy with the repository converters; that copy is not another maintained canonical artifact.

The composite action `.github/actions/schema-toolchain/action.yml` installs Node, installs ripgrep, pulls the pinned image, and puts wrappers for `psql`, `pg_dump`, `createdb`, and `dropdb` on `GITHUB_PATH`. `postgres/bin/pg-client.sh` executes those clients in the image, forwards PostgreSQL environment variables, uses host networking, and mounts the current working directory at the same path plus `/tmp`.

This pins the schema-sensitive database tools; it does not make the entire runner immutable. Ubuntu, apt-provided utilities, and version-tagged GitHub actions remain separate dependencies. Update the toolchain source, workflow service images, and composite-action version settings together when deliberately upgrading.

### Seed semantics

Seed serialization preserves installation behavior:

| Seed table | Attribution and replay contract |
| --- | --- |
| `scheduler_lock_t` | `last_heartbeat` uses `CURRENT_TIMESTAMP`; conflict on `lock_id` does nothing |
| `log_counter` | Conflict on `id` does nothing |
| `pii_token_scheme_t` | `update_user` uses `DEFAULT`, resolving to installing `SESSION_USER`; conflict on `scheme_id` does nothing |
| `operational_store_profile_t` | Explicit source authors remain intact; conflict on `(profile_id, profile_version)` does nothing |
| `cascade_relationship_policy_t` | Seed attribution uses `DEFAULT`; synchronization updates attribution with `SESSION_USER` |

Runtime seed timestamps use `CURRENT_TIMESTAMP`. Generation-time role names and timestamps must not become installation data. In particular, the operational profile authors `p7-compatibility-closure` and `registration-v2-bootstrap` are intentional source values and remain unchanged.

`run-generated-seed-gate.sh` authenticates as a distinct login role, checks reproducibility, loads canonical DDL, verifies attribution, applies the non-cascade seed section twice, and compares existing seed rows. It also replays cascade installation and checks policy attribution. The profile seed section temporarily disables its legacy-profile write guard inside a transaction and restores it afterward.

## Migration qualification

### Baselines and phase order

There is no universal chronological migration list. `postgres/migrations/workflow_runner.json` and `llm_control_plane.json` declare a baseline, a gate, and named phases containing the target schema and ordered patch sequence. `postgres/bin/migration-path.py` renders patches for the selected schema and produces include files consumed at explicit positions in the SQL gates.

The include positions matter: gates reconstruct historical prerequisites, insert retained-data fixtures, apply transitions, and assert results between phases. Repeated patch entries deliberately exercise replay at the supported transition boundary. Reapplying an old patch after a later transition has removed its prerequisites is not an equivalent test.

The execution path reconstructs the runner and agent foundations. It restores historical prerequisites such as `agent_memory_directive_t.bank_id` before operational decoupling; the later publication transition removes that column again. The LLM paths cover historical reconstruction and a retained-data bridge before endpoint ownership becomes authoritative.

Schema comparisons report the collected differences rather than stopping at the first differing column. Retained-data and behavioral assertions complement those comparisons. A matching final catalog alone cannot prove that a destructive migration preserved user data.

### Endpoint-ownership safety

`postgres/patch_20260909_01_llm_endpoint_ownership.sql` moves transport ownership fully to the endpoint. The migration itself locks endpoint and deployment tables and checks reconciliation before dropping deployment `base_url` and `provider_protocol`. It updates the embedding qualification view to read endpoint-owned protocol before removing those columns.

The reconciliation gate exercises four failure cases:

| Fixture | Required rejection |
| --- | --- |
| Deployment transport differs from its endpoint | Transport reconciliation error |
| Referenced endpoint is absent | Missing-endpoint reconciliation error |
| Only one legacy transport column remains | Partial-migration error |
| Active deployment Bedrock policy disagrees with endpoint protocol | Bedrock-contract error |

Each fixture matches its own expected error message, then verifies that the failed migration retained the data and expected legacy-column count. The successful path checks retained data and applies the patch twice. Row fingerprints use `to_jsonb`, avoiding false differences when dropping and re-adding a column changes its physical order.

These are executable pre-drop protections. A review instruction to reconcile rows outside the patch would not prevent an unsafe invocation from silently losing divergent values.

### Inventory boundaries

`postgres/migrations/inventory.json` requires every discovered patch to have a declared path or an explicit disposition. At the reviewed checkpoint it accounted for **153 patches**, including **41 on the declared execution/LLM paths** and **69 explicitly unqualified**; the remaining entries referenced standalone gates.

A standalone gate reference does not establish that the main CI workflow executes it. The unqualified entries have SHA-256 locks so an edit requires a reviewed disposition update or new qualification. These locks are review tripwires, not execution coverage. Adding manifests must never be reported as qualification of every historical patch.

`postgres/bin/check-schema-contracts.py` rejects missing inventory entries and unexpected changes to locked artifacts. Do not regenerate the inventory merely to make that failure disappear. Select a supported baseline and a meaningful qualification path for each new migration.

## Documentation and cascade gates

The documentation gate loads canonical DDL into its own database and checks table and column comments together. It also revalidates routine bodies after their dependencies exist; `pg_dump` disables those checks during initial loading. Required runtime routines and triggers are asserted explicitly.

The negative documentation fixture uses `pg_description` to discover the targets supplied by `comments.sql`. It clears comments and reapplies the source inside an exploratory transaction, emits target-specific `COMMENT ... IS NULL` statements, and rolls back that exploration. The emitted fixture is then applied to the installed schema. The gate requires a failure reporting missing table and column comments before replaying the documentation patch twice and requiring success.

This makes multiline comments and text containing ` IS ` safe: fixture construction depends on catalog identity, not line-oriented SQL rewriting.

The cascade behavior gate uses a different database. It loads canonical DDL once and uses `cascade-runtime.generated.sql` for repeat installation. There is no runtime-section marker extraction and no second complete DDL load.

The cascade installer runs transactionally. It handles the legacy `enabled` policy shape, restores the canonical view and routines, synchronizes policies, validates relationships, and reinstalls application-schema triggers. Policies owned entirely by the application schema and absent from the authoritative inventory are removed; external-schema policies are preserved. An invalid relationship must roll back the installation. Named application schemas use `postgres/bin/render-schema.sh` to render the installer.

## Workflow topology and failure visibility

The main `ci.yml` runs on pull requests, pushes to `master` or `main`, and manual dispatch. Its six job identifiers remain stable:

| Job | Responsibilities |
| --- | --- |
| `multi-schema-environment-gate` | Deterministic rendering, environment isolation, repository-layout container bootstrap, public-schema leakage checks, shared-grants transaction safety |
| `bootstrap-seed-schema-gate` | Contract unit tests, inventory/dependency contracts, explicit bootstrap seed schema qualification |
| `runtime-instance-operational-metadata-schema-gate` | Canonical and migration equivalence for runtime operational metadata |
| `cascade-delete-policy-schema-gate` | Generation, cross-role seeds, documentation, cascade behavior and atomic installation |
| `execution-schema-gate` | Runner migration equivalence and the separately isolated workflow-tool gate |
| `llm-control-plane-schema-gate` | LLM equivalence followed by dependent endpoint reconciliation |

Independent steps use:

```yaml
if: ${{ !cancelled() && steps.toolchain.outcome == 'success' }}
```

This allows later independent checks to run after a failure without running after cancellation or failed toolchain setup. It does not convert a failed step into success. Dependent operations remain sequential: LLM reconciliation needs a row established by the LLM equivalence gate, and container validation needs successful initialization.

Separate databases prevent earlier installation or failed fixtures from contaminating unrelated gates. Explicit `PGUSER` is necessary for bare environment-driven `psql` calls; the service's `POSTGRES_USER` setting alone does not select the client's login role.

Retain job identifiers when refactoring. Moving jobs into a matrix can change check names and invalidate a future required-check configuration. Service-block deduplication is deferred until that naming and enforcement contract is settled.

### Knowledge workflows and path filters

Three additional schema workflows qualify Knowledge phase 1, phase 2, and the admin API boundary. `sync-auto-pr.yml` is a synchronization workflow and is outside the schema-gate set.

The contract checker follows literal shell and SQL dependencies transitively and validates both push and pull-request path filters. Dynamic dependencies require explicit declarations in `postgres/migrations/workflow-dependencies.json`. Reviewed filter changes can be generated with:

```bash
postgres/bin/check-schema-contracts.py --write-filters
postgres/bin/check-schema-contracts.py
```

For example, the admin API gate reads `postgres/tests/light_knowledge_phase1_schema_fingerprint.sql`; editing that helper must trigger its workflow. That workflow loads `postgres/knowledge/ddl.sql`, so adding the unrelated configuration `postgres/ddl.sql` to its filter is unnecessary. Deriving filters from executable dependencies prevents shared helpers from silently falling outside the trigger set.

## Local qualification procedure

Use a disposable PostgreSQL cluster, not a shared development or production cluster. These gates create databases and cluster roles and exercise intentionally invalid data. The generated-seed gate creates a temporary login superuser with a test password equal to its generated role name. Its exit trap cannot clean up after `SIGKILL`; destroying the disposable cluster is the final cleanup boundary. Its `REASSIGN OWNED` cleanup can also fail independently of successful assertions, so inspect cleanup errors when interpreting a nonzero exit.

The following example assumes Linux host networking, Docker, Python 3, Node 24.14.0, and ripgrep. Run it from the `portal-db` root. The wrappers reproduce the pinned client boundary used by CI.

```bash
source postgres/schema/toolchain.env

docker run -d --name portal-db-ci-local \
  -p 127.0.0.1:55439:5432 \
  -e POSTGRES_PASSWORD=postgres \
  "$PORTAL_DB_IMAGE"

client_bin="$(mktemp -d /tmp/portal-db-clients.XXXXXX)"
for tool in psql pg_dump createdb dropdb; do
  printf '#!/usr/bin/env bash\nexec "%s/postgres/bin/pg-client.sh" "%s" "$@"\n' \
    "$PWD" "$tool" > "$client_bin/$tool"
  chmod +x "$client_bin/$tool"
done
export PATH="$client_bin:$PATH"

# Continue when PostgreSQL reports that it is accepting connections.
docker exec portal-db-ci-local pg_isready -U postgres
psql --version
pg_dump --version
node --version

postgres/tests/run-ci-schema-gates.sh \
  postgresql://postgres:postgres@localhost:55439/postgres \
  /tmp/portal-db-ci-results
```

Use a fresh log directory for each qualification run and avoid concurrent runs writing to the same logs. The driver writes per-gate logs and `results.txt`, continues independent gates after failures, and returns a nonzero result if a gate fails. Provisioning failures can still terminate the driver; do not infer complete coverage from a partial results file. At this checkpoint a complete successful run has 23 named results, including `generated_seeds` and all three Knowledge gates.

After collecting results, remove the disposable cluster and client wrappers:

```bash
docker stop portal-db-ci-local
docker rm portal-db-ci-local
rm -r -- "$client_bin"
```

For a source change, regenerate before checking using two separately created empty databases:

```bash
postgres/bin/generate-ddl.py postgresql://.../empty_generation_database
postgres/bin/generate-ddl.py postgresql://.../empty_verification_database --check
```

Run the affected behavioral gates after regeneration, then the full qualification driver when the change spans shared schema contracts. SQL syntax checks or skipped PostgreSQL tests cannot replace a live migration and replay test.

## Change and release acceptance

A schema change should carry its authoritative source edit, generated outputs, applicable migration path, retained-data or behavior assertions, and inventory/dependency updates together. Reviewers should be able to identify the baseline being upgraded and the exact state protected by each rejection test.

Before declaring this repair remotely qualified:

1. Run the revised workflows on GitHub Actions for the exact reviewed commit.
2. Confirm all six main jobs ran and passed, including the formerly masked independent steps.
3. Run the three Knowledge boundary workflows when qualifying the complete schema suite; a path-filtered workflow that did not execute provides no evidence for that commit.
4. Verify the composite action's client versions, workspace mounts, and connectivity to PostgreSQL service containers.
5. Record the commit and run results separately from any decision about merge enforcement.

Enforced merge protection requires a repository plan or visibility decision, or an explicitly designed alternative mechanism. A local pre-push hook is bypassable. Gating the synchronization PR flow would only protect that route unless other write routes were also controlled. Neither alternative is implemented or implied by a passing test suite.

## Implementation references

The main reference points in `portal-db` are:

- `postgres/schema/README.md` and `postgres/bin/generate-ddl.py` for generation and seed contracts.
- `postgres/migrations/README.md`, the two path manifests, and `postgres/bin/migration-path.py` for historical qualification.
- `postgres/bin/check-schema-contracts.py` for inventory and transitive workflow dependencies.
- `.github/workflows/ci.yml` and `.github/actions/schema-toolchain/action.yml` for remote execution.
- `postgres/tests/run-ci-schema-gates.sh` for local orchestration and its complete result set.
- `postgres/tests/run-generated-seed-gate.sh`, `run-llm-endpoint-reconciliation-gate.sh`, `documentation_negative_fixture.sql`, and `run-cascade-delete-policy-schema-gate.sh` for the regression contracts discussed here.

Related Portal design documents describe [operational storage and database topology](../light-portal/development-database-topology.md) and [snapshot-derived database bootstrap](../light-portal/database-recreation-event-bootstrap.md).
