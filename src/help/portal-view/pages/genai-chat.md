# GenAI Chat

Open **GenAI Chat** at `/app/genai/chat`, select an agent in the current Host,
and click **Connect**. The connected session determines the available turn types.
Tech Support normally offers Chat. A published coding-only policy shows a fixed
**Coding implementation** label and opens the repository form automatically.
An agent with both types shows a selector. Reconnect with a new session after
changing the published policy.

## Repository input for coding

The current coding implementation accepts one immutable **Git bundle** per
request. **Repository bundle URI is not a GitHub HTTPS URL**, a repository
directory, or a ZIP download. It must be an absolute `file:///...` URI for a
regular bundle file on the **workflow runner host**, under the repository URI
prefix allowed by the published coding profile. The runner must be able to read
the file and traverse its parent directories. Symlink inputs are rejected.

If the repository is on GitHub, clone it yourself on the runner host using your
normal Git credentials, then create a bundle. The current request does not ask
the worker to clone GitHub or pass it Git credentials. A bundle contains committed
Git objects; uncommitted and untracked working-tree changes are not included.

## Prepare and fill the form

Run these commands on the runner host. Replace both paths. `bundle_dir` must be
the approved repository spool directory from the published profile, not an
arbitrary temporary directory. Use a complete clone and a new bundle filename.

```bash
repo=/absolute/path/to/your/repository
bundle_dir=/absolute/path/to/approved/repositories
bundle="$bundle_dir/my-repository-$(date +%Y%m%d-%H%M%S).bundle"
base_revision=$(git -C "$repo" rev-parse HEAD)
git -C "$repo" bundle create "$bundle" --all
git -C "$repo" bundle verify "$bundle"
chmod 400 "$bundle"
python3 - "$bundle" "$base_revision" <<'PY'
import hashlib
from pathlib import Path
import sys

path = Path(sys.argv[1]).resolve()
with path.open('rb') as source:
    digest = hashlib.file_digest(source, 'sha256').hexdigest()
print('Repository bundle URI:', path.as_uri())
print('Bundle SHA-256: sha256:' + digest)
print('Bundle size (bytes):', path.stat().st_size)
print('Base commit:', sys.argv[2])
PY
```

Python 3.11 or later is required for this example. Run as the runner's user, or
arrange read access for that user before submitting. Keep the bundle unchanged
and available while the request runs.

| Form field | Value |
| --- | --- |
| Repository bundle URI | Printed `file:///...` URI on the runner host |
| Bundle SHA-256 | Printed `sha256:` prefix plus 64 lowercase hex digits |
| Bundle size (bytes) | Printed size of the bundle file, not the checkout |
| Base commit | Full commit hash printed above, contained in the bundle |
| Worker workspace root | `/workspace/repository`, the logical worker path rather than your host checkout |
| Maximum patch bytes | Positive output limit; start with `65536` for a small task |
| Maximum changed files | Positive output limit; start with `1` for a one-file task |

Enter the implementation instruction in the message box and send it after the
session initializes. The worker reconstructs a checkout from the bundle and
returns a patch for review; this does not directly modify your original checkout
or push changes to GitHub. Request acceptance is not completion.

**Import coding request JSON** is an alternative to typing the fields. It imports
a typed request with `profile: "coding"`, prompt `text`, and a `coding` object;
it does not upload the bundle. See the
[Codex personal tutorial](../../../tutorial/light-agent/codex-personal.md#9-submit-one-small-coding-turn-after-the-runner-gate-passes)
for the request-generation helper and a complete smoke test.

## Multiple repositories

Each request currently carries one repository bundle, one base commit, and one
worker workspace root. Multiple independent repositories in a single turn are
not supported. Submit a separate request for each repository. A monorepo can
contain multiple projects in one bundle, but submodules are separate repositories
and their contents are not automatically included by bundling the parent.

## Troubleshooting

- **Two turn options for codex-personal:** setting the authoring policy alone is
  insufficient. Publish its Agent policy, refresh/activate the configuration
  snapshot, restart the agent, and establish a new session.
- **Invalid repository URI:** use the runner-local bundle URI, not a GitHub URL
  or a path on the browser's computer.
- **Repository staging rejected:** check the approved URI prefix, file ownership
  and permissions, and exact bundle hash and size.
- **Base commit unavailable:** recreate the bundle from a complete clone that
  contains the requested commit.
- **Output limit exceeded:** choose limits appropriate to the task within the
  published policy's constraints, or split the task into smaller changes.
