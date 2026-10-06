# Using with Cursor cloud agents

Cursor cloud / Project agents run on a remote VM. They cannot see `~/Developer/agent-definition` or `~/.cursor/skills` on your Mac.

## What to do

1. Open this repo as the workspace, **or** add it to the Cursor Environment / Project, **or** submodule it into the project the cloud agent uses.
2. Repo: https://github.com/jarushannaidoo-Stitch/agent-definition
3. In a normal Agent chat on that workspace, say **run onboarding** (or `/onboard-models`).
4. Do **not** use Cursor's `/onboard` Environments flow.
5. Do **not** ask the agent to search GitHub, the web, or plugins for `onboard-models` / `agent-definition`.

## Pack discovery order

The `onboard-models` skill and `./adapters/onboard-models.sh` resolve the pack as:

1. Current workspace (cwd, a parent, or `./agent-definition` under cwd)
2. `$AGENTPACK_ROOT`, then `$PACK_ROOT`
3. `~/Developer/agent-definition`
4. `~/agent-definition`

On a cloud VM only (1) and (2) usually apply. Opening this repo as the workspace is enough.

## Local Cursor Agent

On your laptop, skills already install under `~/.cursor/skills` via `./adapters/export-cursor.sh`. Say **run onboarding** in a local Agent chat (not a cloud/Project VM). Prefer `/onboard-models` over `/onboard`.
