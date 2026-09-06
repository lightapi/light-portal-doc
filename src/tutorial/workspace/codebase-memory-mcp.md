# Index the Multi-Repo Workspace with codebase-memory-mcp

This tutorial sets up [`codebase-memory-mcp`](https://github.com/DeusData/codebase-memory-mcp),
a third-party MCP server that builds a persistent code-structure graph so an
agent can query call chains, routes, and architecture instead of repeatedly
re-reading files. It covers installing the server, indexing a workspace that
holds many `light-4j`-style repos (for example `light-portal`, the
`*-command`/`*-query` service pairs, and shared libraries), and keeping two
separate index databases when the same repos are checked out in more than one
place — for example a private workspace under `$HOME` and a Linux-desktop
workspace shared with other users, such as `/data/ai-workspace`.

> [!IMPORTANT]
> The download/verification wrapper (`install.sh`, and the PyPI package's
> `_cli.py`) is open source and checksum-verifies every release against a
> published SHA-256 manifest before running it. The actual indexing engine is
> a closed-source, statically linked native binary. Its README claims the
> tool runs "100% locally" with no telemetry; that claim is not independently
> verifiable from what is public. Do not point it at a repository whose
> contents must never leave the local machine without first sourcing that
> guarantee from something you can audit.

## Why two databases

A single install of `codebase-memory-mcp` derives each indexed project's name
from the repository's **full absolute path** (slugified), not just the
directory's basename, so `/home/<user>/workspace/light-portal` and
`/data/ai-workspace/light-portal` never collide on name even inside one
shared store. That said, keeping them in one store is still the wrong
default here:

- The private workspace and the shared desktop workspace are expected to hold
  the *same* repos at *different* commits. Mixing both into one graph makes
  `cross-repo-intelligence` mode (route/channel matching across projects)
  match a service against the wrong commit of its counterpart.
- The shared workspace is writable by more than one Linux user. The graph
  store is SQLite-backed and not designed for concurrent multi-process
  writers from different OS accounts; pointing several accounts' live agents
  at one store risks lock contention or corruption, especially if the
  filesystem is network-mounted.
- Wiping or rebuilding one workspace's index should never require touching
  the other's.

The tool exposes exactly the knob needed for this: the `CBM_CACHE_DIR`
environment variable, documented as controlling where "all project indexes
and config are stored." Give each workspace its own value and the databases
never interact.

| Workspace | Example root | `CBM_CACHE_DIR` |
| --- | --- | --- |
| Private | `$HOME/workspace` | `$HOME/workspace/.codebase-memory-db` |
| Shared desktop | `/data/ai-workspace` | `/data/ai-workspace/.codebase-memory-db` |

Putting the cache directory at the workspace root (a sibling of the cloned
repos, not inside any one of them) also means it is outside every individual
repo's Git tree — nothing to add to `.gitignore` for it.

> [!IMPORTANT]
> `codebase-memory-mcp` runs a single daemon **per Linux account**, exclusive
> to whichever `CBM_CACHE_DIR` started it — not one daemon per cache
> directory. Verified directly: with a live MCP server connected to the
> private workspace, starting a second one against the shared workspace fails
> immediately with `CBM could not start because the active account daemon
> uses a different cache directory ... Close all CBM sessions and commands,
> then retry with one consistent CBM_CACHE_DIR`. In practice this means **you
> cannot have Claude Code or Codex connected to both workspaces at the same
> time** under this account. Fully close one (exit the client so no MCP
> server process remains) before opening the other. This is a limitation of
> the closed-source daemon, not of the per-workspace registration set up
> below — separate `CBM_CACHE_DIR`s make the two workspaces' *data* isolated,
> not concurrently *usable*.

## Before you begin

You need:

- `python3` and `pip`, **or** a POSIX shell and `curl`/`wget`, to run the
  installer;
- write access to the two workspace roots above;
- for the shared workspace, confirmation of which Linux group actually has
  access — check with `stat -c '%U %G %a' /data/ai-workspace`. A shared
  workspace that is `rwxrwx---` owned by a single user's own group is not
  actually shared with anyone else yet; the group needs to include every
  intended user (or the directory needs a shared group) before this
  separation buys you anything.

## 1. Install the server

Prefer the PyPI package over piping the install script directly into `bash`
so you can inspect what you're running first:

```bash
pip install --user codebase-memory-mcp
# or, if the system Python is externally managed:
python3 -m venv ~/.local/share/codebase-memory-mcp/venv
~/.local/share/codebase-memory-mcp/venv/bin/pip install codebase-memory-mcp
```

Running it once (`codebase-memory-mcp --version`) downloads the native
runtime for your platform from GitHub Releases and verifies its SHA-256
checksum against the published `checksums.txt` before executing it.

Avoid `codebase-memory-mcp install` (and the `curl | bash` one-liner, which
ends by invoking the same subcommand) unless you want it: it auto-detects
and rewrites configuration for dozens of coding tools system-wide (Claude
Code, Codex CLI, Cursor, VS Code, Windsurf, and more), which is a much wider
blast radius than "register one MCP server." This tutorial registers the
server explicitly and narrowly instead.

## 2. Create a cache directory per workspace

```bash
mkdir -p "$HOME/workspace/.codebase-memory-db"
mkdir -p /data/ai-workspace/.codebase-memory-db
```

## 3. Register Claude Code per workspace

Register a **project-scoped** server in each workspace root — not a
user-scoped one — so the correct `CBM_CACHE_DIR` is picked automatically from
whichever workspace Claude Code is started in:

```bash
cd "$HOME/workspace"
claude mcp add --scope project codebase-memory-mcp \
  -e CBM_CACHE_DIR="$HOME/workspace/.codebase-memory-db" \
  -- codebase-memory-mcp

cd /data/ai-workspace
claude mcp add --scope project codebase-memory-mcp \
  -e CBM_CACHE_DIR=/data/ai-workspace/.codebase-memory-db \
  -- codebase-memory-mcp
```

This writes a `.mcp.json` in each workspace root. The first time you start
`claude` in either directory afterward, approve the pending server when
prompted (`claude mcp list` shows it as "⏸ Pending approval" until then).

Do **not** also register a user-scoped copy of this server — it would apply
in both workspaces and reintroduce the exact ambiguity this setup avoids.

## 4. Make Codex CLI workspace-aware

Codex CLI's own MCP registration (`~/.codex/config.toml`) can declare which
environment variables to forward from the invoking shell into the server
subprocess:

```toml
[mcp_servers.codebase-memory-mcp]
command = "codebase-memory-mcp"
args = []
env_vars = ["CBM_CACHE_DIR", "CBM_RUNTIME_DIR"]
```

That only helps if `CBM_CACHE_DIR` is already correct in the shell Codex was
started from. Add a directory-based hook to `~/.bashrc` so it is:

```bash
# codebase-memory-mcp: select the per-workspace index database by cwd.
_cbm_set_workspace_cache() {
    case "$PWD" in
        "$HOME"/workspace|"$HOME"/workspace/*)
            export CBM_CACHE_DIR="$HOME/workspace/.codebase-memory-db"
            ;;
        /data/ai-workspace|/data/ai-workspace/*)
            export CBM_CACHE_DIR="/data/ai-workspace/.codebase-memory-db"
            ;;
        *)
            unset CBM_CACHE_DIR
            ;;
    esac
}
PROMPT_COMMAND="_cbm_set_workspace_cache${PROMPT_COMMAND:+; $PROMPT_COMMAND}"
```

> [!IMPORTANT]
> This only fires in an **interactive** shell that sources `~/.bashrc` (bash
> exits early for non-interactive shells). It covers the normal case —
> `cd` into a workspace in a terminal, then run `claude` or `codex` from
> there — but not a client launched by something that doesn't source your
> shell rc file (a service manager, an IDE's own process launcher, and so
> on). Reload with `source ~/.bashrc` or open a new terminal after adding it.

## 5. Index every repo in a workspace

Every repo is indexed independently; they all land in whichever
`CBM_CACHE_DIR` is active. `devops/workspace/reindex-codebase-memory.sh`
does this for a whole workspace — a copy lives at the root of each
workspace so it needs no flags at all (it defaults to scanning its own
directory and to `<its own directory>/.codebase-memory-db`):

```bash
cd "$HOME/workspace"   # or /data/ai-workspace
./reindex-codebase-memory.sh            # index every repo, then link them
./reindex-codebase-memory.sh --dry-run  # preview without indexing
./reindex-codebase-memory.sh --help     # all options (mode, cache dir, etc.)
```

The equivalent by hand, run from inside the target workspace root (so the
shell hook above sets the right cache directory):

```bash
# 1. Structural pass over every repo
for repo in */; do
  [ -d "$repo/.git" ] || continue
  codebase-memory-mcp cli index_repository --repo-path "$repo" --mode full
done

# 2. Cross-repo linking (HTTP routes / Kafka channels between services)
for repo in */; do
  [ -d "$repo/.git" ] || continue
  codebase-memory-mcp cli index_repository --repo-path "$repo" \
    --mode cross-repo-intelligence --target-projects '*'
done

# 3. Confirm
codebase-memory-mcp cli list_projects --include-details true
```

Notes:

- `index_repository --help` documents `--target-projects` as taking a JSON
  array such as `["*"]`. In this build (0.10.8) that form fails validation
  (`target_projects must contain valid project names or '*'`), and a
  multi-element array silently scans only one project instead of erroring.
  Pass one bare value — `*` for every project, or a single exact name from
  `list_projects` — not a JSON array.
- `--mode full` also builds similarity/semantic edges; use `--mode fast` for
  a quicker structural-only first pass across a large workspace and upgrade
  specific repos to `full` later if you need those edges.
- Do **not** pass `--persistence true` for repos in the shared workspace. It
  writes a compressed `.codebase-memory/graph.db.zst` into the repo itself,
  intended for teammates to `git`-commit and bootstrap from — a different,
  opt-in sharing mechanism from the live shared cache directory this
  tutorial sets up. Mixing the two adds a second, easily-stale copy of the
  same data. `reindex-codebase-memory.sh` leaves this off unless you pass
  `--persistence`.

## 6. Verify the separation

Index the same repo from both workspaces and confirm they produce distinct
projects in distinct stores:

```bash
codebase-memory-mcp cli list_projects --include-details true   # run in each workspace
```

Each workspace's `list_projects` should show only that workspace's repos,
with project names derived from that workspace's absolute paths (for
example `home-<user>-workspace-light-portal` versus
`data-ai-workspace-light-portal`).

## 7. Schedule automatic reindexing

The index does **not** stay current on its own for a workspace this size.
`auto_watch` (default `true`) only registers an **already-indexed** project
with a background git watcher when a live MCP session actually connects to
it — it does not proactively watch every repo in the cache directory, it
requires the daemon/session to keep running, and (per the one-daemon-per-
account limit above) it can only ever be watching one workspace at a time.
`auto_index` (default **false**) only covers indexing a project the first
time it's seen; it does not refresh existing ones. Treat both as a
best-effort bonus for repos you're actively querying in a live session, not
as the source of truth for the rest of the workspace.

Instead, reindex on a schedule with
`devops/workspace/reindex-all-workspaces.sh`, which reindexes each workspace
in turn — never concurrently, and calling `codebase-memory-mcp daemon stop`
between them — so a scheduled run can't hit the same daemon conflict
described above:

```bash
devops/workspace/reindex-all-workspaces.sh --help
devops/workspace/reindex-all-workspaces.sh --dry-run
```

It defaults to `$HOME/workspace` and `/data/ai-workspace`; pass `--workspace
DIR` (repeatable) to reindex a different set instead of editing the script.

Install it as a daily cron job:

```bash
SCRIPT="/home/agent/workspace/devops/workspace/reindex-all-workspaces.sh"
LOG="$HOME/.local/state/codebase-memory-mcp/reindex-all-workspaces.log"
mkdir -p "$(dirname "$LOG")"
(crontab -l 2>/dev/null; echo "0 2 * * * $SCRIPT --mode full >> $LOG 2>&1") | crontab -
crontab -l
```

This runs a full reindex of both workspaces at 02:00 daily, logging to
`$LOG`. A full pass across a workspace this size takes real wall-clock time
(minutes, not seconds) and CPU — pick an off-peak hour, and switch the first
pass to `--mode fast` (`--mode fast` on `reindex-all-workspaces.sh`) if daily
full reindexing costs more than the freshness is worth; the cross-repo-
intelligence linking pass always runs regardless of `--mode`. The log file
is not rotated by this setup; truncate or logrotate it if it grows large
over time.

Between scheduled runs, check one repo's freshness on demand instead of
trusting the whole workspace is current:

```bash
codebase-memory-mcp cli index_status --project <name-from-list_projects>
```

## Troubleshooting

| Symptom | Likely cause and correction |
| --- | --- |
| Claude Code shows the server as "⏸ Pending approval" forever | Approval happens interactively on `claude` startup, not via `claude mcp list`. Start `claude` in that workspace root and approve when prompted. |
| Same repo shows up once instead of twice across workspaces | You are running both workspaces against the same `CBM_CACHE_DIR`. Check `claude mcp get codebase-memory-mcp` in each directory and the exported `$CBM_CACHE_DIR` in the shell. |
| Codex still hits the wrong database | The shell that started Codex never sourced the `~/.bashrc` hook (non-interactive launch), or `~/.codex/config.toml` is missing `CBM_CACHE_DIR` from `env_vars`. |
| `.codebase-memory/graph.db.zst` appears inside a repo you didn't expect | Something passed `--persistence true` for that `index_repository` call. Delete the artifact and re-index without the flag if it wasn't intentional. |
| Two Linux users on the shared workspace still can't see each other's index | `/data/ai-workspace` (or whatever shared root you used) isn't actually group-shared. Check `stat -c '%U %G %a'` and fix group membership/permissions before assuming the databases are the only isolation boundary. |
| Cross-repo-intelligence pass fails with `target_projects must contain valid project names or '*'` | You passed `--target-projects` as a JSON array (`["*"]`), matching `index_repository --help` — but this build rejects that form. Pass a bare value instead: `--target-projects '*'` or one exact name from `list_projects`. |
| `codebase-memory-mcp: CBM could not start because the active account daemon uses a different cache directory ...` | Something else (a live Claude Code/Codex session, another `cli` command, or an overlapping cron run) is already using a different workspace's `CBM_CACHE_DIR` under this account. Close it first — this account can only have one workspace's daemon active at a time; see the callout above. |

## Source

- [DeusData/codebase-memory-mcp](https://github.com/DeusData/codebase-memory-mcp)
