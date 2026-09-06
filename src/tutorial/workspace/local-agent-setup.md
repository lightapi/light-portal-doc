# Setup a Local Workspace User for Advanced Coding Agents on Ubuntu 24.04

This tutorial helps you run terminal agents like OpenAI Codex CLI and Claude Code from an isolated Linux account so they cannot directly read your personal data in the normal desktop profile.

## Why isolate by user first

A dedicated user is usually the best tradeoff: easier than carrying a second laptop, safer than using your primary account, and easier to maintain than nested per-command sandboxes.

| Approach | Security | Maintenance | Verdict |
|---|---|---|---|
| Primary user + built-in sandbox | 🟡 Moderate | 🟢 Very easy | Convenient, but OS permissions still expose personal keys, cookies, `.env`, and SSH material if a policy is too broad. |
| Dedicated Linux user | 🟢 High | 🟢 Easy | **Recommended.** A separate account isolates your normal profile with standard Unix permissions. |
| Separate laptop | 🟢 High | 🔴 Tedious | Adds hardware/ops overhead and complicates coding workflow. |

For Ubuntu 24.04 specifically, this setup keeps each agent session scoped to one workspace and reduces blast radius from destructive commands.

## What this tutorial creates

- A non-privileged `agent` account
- A shared agent workspace at `/data/ai-workspace`
- A launch flow that keeps your main account separate while still giving access to shared code
- Optional hardening guidance for Codex CLI and Claude Code sandbox settings

## Step 1 — Create the dedicated agent user

Create a non-admin user that will run terminal coding agents.

```bash
sudo adduser agent
```

- Do not add `agent` to `sudo`.
- Use a strong password when prompted, or a non-interactive password strategy if your policy requires one.

## Step 2 — Create a shared workspace

Create one workspace that both your main user and `agent` can access.

```bash
sudo mkdir -p /data/ai-workspace
sudo chown -R agent:agent /data/ai-workspace
sudo chmod 770 /data/ai-workspace
sudo usermod -aG agent your_primary_username
```

The last command lets your primary account read/write the same workspace without using `sudo` each time.

After this change, log out and log back in so the group update takes effect.

## Step 3 — Create and use the agent session

When you want to run coding agents, switch into the dedicated account:

```bash
su - agent
cd /data/ai-workspace
```

Install Java, Node and Rust

```
curl -s "https://get.sdkman.io" | bash
source "$HOME/.sdkman/bin/sdkman-init.sh"
sdk version

sdk list java
sdk install java 25.0.4-amzn
sdk list maven
sdk insstall maven 3.9.16

curl -fsSL https://bun.sh/install | bash
bun --version
ln -s $(which bun) $HOME/.bun/bin/node
bun upgrade

curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
source "$HOME/.cargo/env"
rustc --version
cargo --version


```



Run agent tooling in this account only. If you need a GUI app for files, do not launch it from the agent account unless you have a strict reason.

When finished:

```bash
exit
```

Then return to your normal user context.

## Step 4 — Configure Git and GitHub access for each agent

For unattended agents with auto-approved execution, split Git transport from GitHub API access:

- **Blast-radius control:** scoped PATs can only touch the selected repo(s), so a leaked token cannot affect your entire account.
- **Auditability:** distinct token names and optional per-agent accounts make it easy to trace changes and revoke only one actor.
- **Separation of concerns:** use SSH for Git transport and PATs for API actions (issues, PRs, Actions).
- Use separate keys/tokens per agent identity so permissions, audit trail, and revocation are isolated.

### 4.1 SSH identity for Git transport

Create a dedicated SSH key inside `agent` and add the public key to GitHub:

```bash
su - agent
mkdir -p ~/.ssh
chmod 700 ~/.ssh
ssh-keygen -t ed25519 -C "agent@ubuntu-local"
cat ~/.ssh/id_ed25519.pub
```

Copy the printed public key to **GitHub → Settings → SSH and GPG keys** (or use a repository Deploy Key if you want a single-repo limit).

Test:

```bash
ssh -T git@github.com
```

For a deploy-only repo setup, add only a Deploy Key for that repository instead of a user key.

### 4.2 Fine-grained PATs for API actions

Create one token per agent in **GitHub → Settings → Developer settings → Personal access tokens → Fine-grained tokens** with:

- **Repository access:** select only the workspace repository the agent needs
- **Permissions (minimum):**
  - `Contents`: Read and write
  - `Issues`: Read and write
  - `Pull requests`: Read and write
  - `Actions`: Read and write (only if the agent must trigger/cancel workflows)
- Short expiry (30 or 90 days), then rotate regularly.

Create two tokens (for example `agent-codex` and `agent-claude`) so a single credential leak or compromise stays contained.

### 4.3 Safe token wiring in the agent user shell

Store tokens in a dedicated file with strict permissions and load it when `agent` starts:

```bash
mkdir -p ~/.config/agent
cat > ~/.config/agent/github-env.sh <<'EOF'
export GITHUB_TOKEN="github_pat_your_default_agent_token_here"
export CLAUDE_GITHUB_TOKEN="github_pat_your_claude_token_here"
export CODEX_GITHUB_TOKEN="github_pat_your_codex_token_here"
EOF
chmod 600 ~/.config/agent/github-env.sh
```

Load tokens in `~/.bashrc`:

```bash
if [ -f ~/.config/agent/github-env.sh ]; then
  . ~/.config/agent/github-env.sh
fi
```

Use a shell wrapper or explicit env per tool when needed:

```bash
env CODEX_GITHUB_TOKEN="$CODEX_GITHUB_TOKEN" GITHUB_TOKEN="$CODEX_GITHUB_TOKEN" codex
env GITHUB_TOKEN="$CLAUDE_GITHUB_TOKEN" claude
```

If you want to keep one default credential for both agents, use only `GITHUB_TOKEN` in
`github-env.sh` and run both tools with `GITHUB_TOKEN`:

```bash
env GITHUB_TOKEN="$GITHUB_TOKEN" codex
env GITHUB_TOKEN="$GITHUB_TOKEN" claude
```

> [!IMPORTANT]
> Keep credentials outside repositories and never commit them. This file should stay on disk only under `agent` with mode `600`.

### 4.4 Commit author identity

Set agent-specific Git identity so commit history stays attributable:

```bash
git config --global user.name "Codex Agent Workspace"
git config --global user.email "agent-workspace@local"
```

Use separate names/emails for each dedicated agent if you want a clearer commit audit trail.

## Step 5 — Configure safer agent sandboxes

Keep the OS-level isolation and still enable built-in agent sandboxes.

### Codex CLI

Install bubblewrap and set a restrictive sandbox config in `~/.codex/config.toml`:

```toml
approval_policy = "on-request"
sandbox_mode = "workspace-write"
```

Use a workspace-owned path and keep your workspace directory owner-only where possible.

### Claude Code

On Ubuntu, install required helper tools:

```bash
sudo apt install -y bubblewrap socat
```

This helps avoid sandbox launch failures caused by missing utilities.

### Ubuntu 24.04 namespace exception

If a sandbox launch fails with user-namespace errors, enable unprivileged user namespaces:

```bash
sudo sysctl -w kernel.unprivileged_userns_clone=1
```

For permanent behavior, persist it in `/etc/sysctl.d/99-userns.conf`:

```bash
printf 'kernel.unprivileged_userns_clone=1\n' | sudo tee /etc/sysctl.d/99-userns.conf
sudo sysctl --system
```

## Step 6 — Quick verification checklist

Run this after setup:

```bash
# 1) Verify isolation account can access the shared workspace
id -nG
ls -ld /data/ai-workspace

# 2) Verify key agents still run under the correct account context
whoami
pwd

# 3) Verify sandbox helper binaries exist
command -v bwrap
command -v socat

# 4) Verify GitHub API credentials for each tool
env | grep GITHUB_TOKEN
env | grep CODEX_GITHUB_TOKEN
env | grep CLAUDE_GITHUB_TOKEN
```

If any command fails, fix that dependency first before enabling agent workflows.

## Alternative: container-based isolation

If you do not want to manage additional local users, you can run agents from Docker-based sandboxes (for example, `sbx` wrappers). This keeps workspaces mounted explicitly and avoids sharing Linux UID state, at the cost of more tooling to maintain.

A common pattern:

```bash
# Example shape only
sbx run codex
sbx run claude
```

Use whichever model of container isolation your team already uses so updates and secrets are consistent.

## Security notes

- Never store API keys, cookies, SSH private keys, or `.env` files in the shared workspace.
- Never run this agent user as `sudo`.
- Keep `.codex` and `.claude` folders inside the agent home when possible.
- Keep the primary profile and production credentials outside `/data/ai-workspace` and inject only required references when needed.

## Sources

- https://nimbalyst.com/blog/orchestrating-claude-code-and-codex-together/
- https://mikemcquaid.com/sandboxed-agent-worktrees-my-coding-and-ai-setup-in-2026/
- https://learn.chatgpt.com/docs/sandboxing
- https://yeet.cx/topical-takes/sandbox-ai-coding-agent-linux
- https://www.reddit.com/r/ClaudeAI/comments/1qvwtye/i_reviewed_claudes_sandboxing_codexs_approach_and/
- https://prince-arora-aws.medium.com/how-to-create-a-secure-sandbox-environment-for-claude-code-on-ubuntu-2b8a80872fa5
- https://github.com/openai/codex/issues/29908
- https://community.openai.com/t/codex-in-chatgpt-desktop-app-for-linux-is-now-in-preview/1390027?page=2
- https://www.youtube.com/watch?v=b7ThC0eE29E&t=687
- https://www.youtube.com/watch?v=zb2LyMro77M
- https://meridianlabs-ai.github.io/inspect_swe/codex_cli.html
