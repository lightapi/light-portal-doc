# Shared task workspaces with local Codex and Claude agents

This tutorial connects terminal agents to `light-workspace`, the owner-local
workspace manager in `light-fabric`. You will register repositories, connect
Codex CLI, create a task, and let Claude Code review the same uncommitted files.

**This is a local terminal workflow.** It does not enable workspace selection in
Portal's `/app/genai/chat`, change the Docker `codex-personal` service, or replace
the repository bundle field. Controller/runner and Portal integration remain
unfinished. No `portal-config-loc` Compose change is needed for this walkthrough.

If you already have `/home/steve/.local/share/light-workspace/personal/workspace.json`,
skip to [Connect a local agent](#connect-a-local-agent). Do not repeat discovery
or registration just to connect a client.

## Paths and identities

| Item | Value in this walkthrough |
|---|---|
| Existing source repositories | `/home/steve/workspace` |
| Executable | `/home/steve/workspace/light-fabric/target/release/light-workspace` |
| Persistent private store | `/home/steve/.local/share/light-workspace` |
| Workspace ID | `personal` |
| First task ID | `workspace-smoke-1` |
| Codex identity | `com.networknt.agent.codex-personal-1.0.0` |
| Claude identity | `com.networknt.agent.claude-personal-1.0.0` |

These two agent identities are entries in one workspace grant. They do not create
Linux accounts or configure model subscriptions. Both clients run as `steve` and
use the same store. The [dedicated-user tutorial](./local-agent-setup.md) describes
a different host isolation setup; its `/data/ai-workspace` paths are not required
here. If you choose a dedicated account, substitute that account's paths throughout.

The source directory is used for discovery. Task branches and worktrees live in
the private store; agents do not switch branches in your existing checkouts.
Creating another task creates another worktree per repository, allowing parallel
workflows. A task always includes the workspace's full repository membership.

## Build and register

Run these commands in a Linux terminal as the user that will launch the agents.
The examples use Steve's host paths. Prerequisites are Rust/Cargo, Git, `jq`,
bubblewrap (`/usr/bin/bwrap`) for `execute`, and authenticated `gh` for GitHub
operations. Git must be able to read each registered origin without interactive
credential prompts. Index providers are optional and must be configured before
registration if you intend to use them.

```bash
cd /home/steve/workspace/light-fabric
cargo build --release -p light-workspace
umask 077
# Replace HOST_ID with the Portal Host ID that owns this workspace.
# Discovery reads origins and local refs without changing source checkouts.
target/release/light-workspace discover /home/steve/workspace personal HOST_ID \
  com.networknt.agent.codex-personal-1.0.0 \
  com.networknt.agent.claude-personal-1.0.0 > discovery.json

# Set grants BEFORE the first registration. Do not redirect onto discovery.json.
jq '.workspace | .operations = ["edit", "execute", "review", "commit", "push", "issue", "pull-request"]' \
  discovery.json > workspace.json
jq '{id, hostId, agents, operations, indexers, repositoryCount: (.repositories | length)}' workspace.json
```

If you already registered successfully, skip discovery and registration and go to
[Connect a local agent](#connect-a-local-agent). Use the persisted registration
when checking IDs and grants; changing the input file does not update it.

The result has `workspace`, `integrationBranchNotKnownLocally`, and
`skippedRepositories` with directory/reason diagnostics for unsuitable names or
unreadable origins. A skipped child does not stop discovery. Extract the
`workspace` object into a private registration file. Select its operation grants
explicitly; discovery grants none. Each agent grant covers all repositories.
Example (replace paths and identities):

```json
{
  "schemaVersion": 1,
  "id": "personal",
  "hostId": "HOST_ID",
  "agents": ["com.networknt.agent.codex-personal-1.0.0", "com.networknt.agent.claude-personal-1.0.0"],
  "operations": ["edit", "execute", "review", "commit", "push", "issue", "pull-request"],
  "repositories": [
    {
      "name": "service",
      "source": "git@github.com:OWNER/SERVICE.git",
      "integrationBranch": "develop",
      "releaseBranch": "master"
    }
  ],
  "indexers": {
    "gitnexus": {
      "executable": "/absolute/path/to/gitnexus",
      "args": ["analyze", "--force"],
      "timeoutSeconds": 300
    },
    "codebase-memory-mcp": {
      "executable": "/absolute/path/to/codebase-memory-mcp",
      "args": [],
      "timeoutSeconds": 300
    }
  }
}
```

Register the extracted `workspace.json`, not the discovery wrapper. Keep the
persistent store outside the source tree:

```bash
install -d -m 700 /home/steve/.local/share/light-workspace
target/release/light-workspace \
  /home/steve/.local/share/light-workspace register workspace.json
```

Expected output: `{"registered":"personal"}`. The private directory stores managed
repositories, task worktrees, checkpoints, and indexes. Both agents use this path.

Registration is metadata-only and idempotent for identical input. It rejects
changes to an existing registration. The current implementation does not yet
provide membership migration or live grant revocation. Do not edit registration
files while tasks or clients are active. Credentials stay in host-managed Git
and GitHub authentication, not this JSON or the model's tool arguments.

## Connect a local agent

Here, **local agent** means the Codex CLI or Claude Code application running as
`steve` on this Linux host. Open an ordinary terminal to run the commands below.
These steps do not configure the `codex-personal` service in Portal Chat or require
a Compose restart. The MCP client starts `light-workspace` as a child process and
exchanges JSON over stdin/stdout; there is no URL or port to enter, and you do not
start `serve` manually in another terminal.

### Check the registered identities

```bash
jq '{id, agents, operations}' \
  /home/steve/.local/share/light-workspace/personal/workspace.json
```

The examples below assume the full agent IDs produced by the discovery command.
Every launch identity must match an entry in `agents` exactly. The MCP server name
`personal-workspace` is only a client-side label; the workspace ID is `personal`.
Both clients use the same private store, with a different agent identity. This is
an owner-local launch setting, not network authentication or isolation between
host administrators. Do not run the clients as different Linux users against this
0700 store without designing an authenticated shared service first.

### Add the server to Codex CLI

Run this once in your Linux terminal, using your existing Codex installation and
login. It updates your local Codex configuration, not `workspace.json`:

```bash
codex mcp add personal-workspace -- \
  /home/steve/workspace/light-fabric/target/release/light-workspace \
  /home/steve/.local/share/light-workspace serve personal \
  com.networknt.agent.codex-personal-1.0.0

codex mcp list
```

The list should contain `personal-workspace` and the command above. Start a new
Codex CLI session by running `codex`; in its interactive prompt enter `/mcp`.
Check that `personal-workspace` connects and exposes `task_workspace`.
An existing session may need to be restarted to pick up the new configuration.

Codex stores this entry in `~/.codex/config.toml`. Do not paste an `mcpServers`
JSON object into that TOML file. For long workspace operations you can add
`tool_timeout_sec = 600` inside the existing `[mcp_servers.personal-workspace]`
table. That is a client timeout, not a guarantee that indexing all repositories
will finish in ten minutes. Prefer the direct CLI for the initial clone and large
index builds. See the [official Codex MCP documentation](https://developers.openai.com/codex/mcp/).

### Add the server to Claude Code (optional second agent)

In your Linux terminal, with Claude Code installed and signed in:

```bash
claude mcp add --transport stdio --scope user personal-workspace -- \
  /home/steve/workspace/light-fabric/target/release/light-workspace \
  /home/steve/.local/share/light-workspace serve personal \
  com.networknt.agent.claude-personal-1.0.0

claude mcp get personal-workspace
```

Start a new session with `claude`, then use `/mcp` to inspect the connection.
`--scope user` keeps this setting in your user configuration instead of creating
a repository `.mcp.json`. See the [Claude Code MCP documentation](https://code.claude.com/docs/en/mcp).
You can connect Codex first and add Claude later; two separate processes share
persistent tasks through the same store and task locks.

### Create the first task outside the model session

Run this in your Linux terminal after checking Git access to the registered
origins. The first creation clones **every registered repository** and fetches its
integration branch. For a 129-repository workspace this can take time and disk
space; registration itself did not download these repositories. The managed copies
come from the recorded origins, so uncommitted edits in `/home/steve/workspace`
are not imported.

```bash
printf '%s\n' '{"operation":"create","task":"workspace-smoke-1"}' | \
  /home/steve/workspace/light-fabric/target/release/light-workspace \
  /home/steve/.local/share/light-workspace call personal \
  com.networknt.agent.codex-personal-1.0.0
```

Expected output includes `"state": "ready"` and `checkouts` with one managed path
per repository, each on `agent/workspace-smoke-1`. Retrying the same task ID resumes
provisioning or returns the existing task. Do not invent a new task ID on every
retry. Missing `develop` branches must be resolved explicitly; there is no fallback
to `master`. Task creation makes no commits, pushes, issues, or PRs.

### Ask the connected agent to use it

In the **Codex conversation**, enter:

> Use the personal-workspace MCP server's task_workspace tool. Call status for
> task workspace-smoke-1 and report its state and repository names. Use only the
> workspace tools for this task; do not access its files through host shell or
> native file tools. Do not edit, commit, push, or create GitHub resources.

The tool arguments for that first call are:

```json
{"operation":"status","task":"workspace-smoke-1"}
```

Then ask it to read a specific file, for example:

> For workspace-smoke-1, use task_workspace read to read README.md in repository
> light-fabric and summarize the project. Do not change files.

Use a repository name returned by `status` if `light-fabric` is not registered.
This confirms the model can use the tool rather than merely seeing its name.
The model client handles its own model login; the workspace server does not log
in to Codex/Claude on your behalf.

The manager must remain the only agent write path. Instructions to use MCP are
workflow guidance, not a security boundary: an agent with unrestricted host file
or shell access can bypass the freeze. This tutorial does not configure a hardened
native-agent sandbox. Workspace `execute` does sandbox the commands it launches.

## Make a small change and hand it to the reviewer

After the read-only connection check succeeds, choose a small real change and
name the task and repository in your Codex conversation. For example:

> In task workspace-smoke-1, read README.md in light-fabric through task_workspace.
> Propose a clearer sentence and show me the proposed change before editing.

After you accept the wording, tell Codex to use `edit` with the digest returned by
`read`. The tool expects this shape (the agent supplies the real content/digest):

```json
{
  "operation": "edit",
  "task": "workspace-smoke-1",
  "edit": {
    "repository": "light-fabric",
    "path": "README.md",
    "content": "COMPLETE_UPDATED_FILE_CONTENT",
    "expectedDigest": "DIGEST_FROM_READ"
  }
}
```

`content` replaces the whole file. For a new file `expectedDigest` is `null`; to
delete a file `content` is `null` and the current digest is still required.
Do not use the literal placeholder strings above as a real edit.

When the changes are ready, ask Codex:

> Freeze workspace-smoke-1 using task_workspace and report the checkpoint digest.
> Do not commit or push yet.

Expected result: state `frozen` and a `checkpoint.digest`. In the **Claude Code
conversation**, after connecting its server, ask:

> Use only personal-workspace task_workspace tools. Inspect task workspace-smoke-1
> using status, files, and read. Review the proposed README.md change in light-fabric
> against the frozen checkpoint. Do not modify files or use native shell/file tools.
> Submit review with that exact checkpoint digest, approved true only if acceptable,
> and concrete findings. Do not commit or push.

Claude sees the same managed files; no bundle, copy, commit, or push is needed
for the handoff. Successful approval sets state `approved`. An agent that made
edits cannot approve its own task. If changes are requested, ask Codex to call
`remediate`, make corrections, freeze again, and ask Claude to review the new digest.
Remediation invalidates the previous approval.

You can verify state independently from the terminal:

```bash
printf '%s\n' '{"operation":"status","task":"workspace-smoke-1"}' | \
  /home/steve/workspace/light-fabric/target/release/light-workspace \
  /home/steve/.local/share/light-workspace call personal \
  com.networknt.agent.codex-personal-1.0.0
```

## Commit and publish when ready

This section performs real Git/GitHub writes only when you request them. Configure
Git committer identity and GitHub authentication for the host user before delivery.
An existing host `git config --global user.name` and `user.email` can supply the
identity. `gh auth status` checks the CLI account; Git clone/push authentication
must also work for the configured origin URLs.

1. Tell the implementer to call `commit` for the approved task with your intended
   message. It commits changed repositories on `agent/workspace-smoke-1`.
2. Tell it to call `push`. The manager creates absent task refs or accepts refs
   already at the reviewed commit; it does not overwrite unrelated remote changes.
3. For each changed repository, request `github` with `action: "pull-request"`,
   the repository name, title, and body. Include an existing issue reference in the
   body when appropriate. PRs target the configured integration branch (`develop`).

The command to create an issue instead uses `action: "issue"`. Existing issue
editing, PR merging, CI tracking, and release promotion are not implemented by
this service. Merging `develop` into `master` before a release remains your normal
release process. Retrying delivery requires the same original inputs.

## Optional indexing and command execution

Start with the read/edit/review workflow. Discovery produces `indexers: {}`;
installing GitNexus or codebase-memory-mcp alone does not enable `index` in this
workspace. Use the provider registration example above **before registering** if
indexing is required. The current service cannot update an existing registration;
with existing tasks, use a separate registration until migration is implemented.
Do not alter stored metadata to add providers.

For a configured provider, freeze the task first, then call from a terminal:

```bash
printf '%s\n' '{"operation":"index","task":"workspace-smoke-1","provider":"gitnexus"}' | \
  /home/steve/workspace/light-fabric/target/release/light-workspace \
  /home/steve/.local/share/light-workspace call personal \
  com.networknt.agent.codex-personal-1.0.0
```

Indexing runs sequentially across all repositories and may exceed a model client's
tool timeout. It uses independent checkpoint copies. A successful index for the
same checkpoint is reused; a failed replacement retains the previous index.
Use `index-status` to check freshness and `index-query` with a repository and query.
Direct indexer MCP servers configured elsewhere do not automatically point at this
task's checkpoint copies.

The workspace `execute` operation launches Linux bubblewrap commands under `/usr`,
with no network, host home, or credential access. Review execution is read-only.
It is suitable for available inspection/build tools, but it does not mount your
host SDK installations or provide online dependency installation. A native client
with unrestricted host tools can bypass workspace freezes; this local walkthrough
is not a complete security configuration for that client.

## Checkpoint reached

You should now have a connected local MCP client, a managed task containing all
registered repositories, and an explicit implementer/reviewer handoff. You can
stop after the read-only connection check; GitHub writes are not required to
verify the setup. Portal Chat can also use this registration when the native
runner is configured and the agent's published coding policy includes a matching
workspace binding. In Chat choose **Shared workspace**, `personal`, **Understand
code**, and **Existing task**, then enter `workspace-smoke-1`. Start with a small
read-only request. See [GenAI Chat help](../../help/portal-view/pages/genai-chat.md)
for the form and current tool limitations. Local MCP registration alone does not
configure the Portal runner or publish the binding.

## Setup troubleshooting

| Symptom | Check or next step |
|---|---|
| `No such file or directory` from registration | Run from the directory containing `workspace.json`, or give its absolute path. Extract `.workspace` from discovery first. |
| Shell says the binary does not exist | Build with `--release` and use `target/release/light-workspace` consistently. |
| `workspace already registered with different membership or grants` | Registrations are immutable. Before any tasks or active clients exist, back up the unused workspace directory and register the corrected input. With existing tasks, retain the registration and use a new workspace ID/store until migration is implemented. Never overwrite stored metadata to bypass the guard. |
| `agent has no workspace grant` | Match the full agent ID in the stored `agents` array; a shortened name is a different identity. |
| `serve` appears to hang in a terminal | It is waiting for MCP JSON. Let the client launch it; use `call` for a direct JSON operation. |
| `/mcp` does not show the server | Check the client registration and absolute binary path, then start a new client session. |
| Tool timeout during first task creation | Use the terminal `call` command above and retry the same task ID; check Git authentication and integration branches. |
| `index provider is not configured by host` | Discovery leaves `indexers` empty. Add provider configuration before registration; merely installing an indexer does not register it. Existing registrations have no update command. |
| Review command cannot write | Review mounts source files read-only. Writable build/test copies are not yet implemented. |
| Portal Chat still requests a repository bundle | Publish a coding profile with the matching workspace binding, deploy the workspace-capable agent and native runner, then reconnect with a new session. Local MCP registration alone is insufficient. |
