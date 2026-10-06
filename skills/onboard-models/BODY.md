# Onboard models

Agent-led setup. The user says "run onboarding" (or "set up models", "onboard", "run onboard-models"); you do everything else. Never ask the user to type a shell command, a flag or a pack path. Shipping profiles (`profiles/codex.yaml`, `profiles/claude.yaml`, ...) are never edited; you write `profiles/personal-<harness>.yaml`.

## Triggers
"run onboarding", "run onboard-models", "onboard", "onboard this pack", "set up models", "set up my models", "pick my models", "change my models", "switch models", "reset my models".

## Flow
Run every step yourself. Use `run_command` for the helper and `ask_user` for every question. If `ask_user` has no structured widget in this harness, fall back to a numbered list in a chat message and accept a number, several numbers, or a typed model id as the reply.

### 1. Find the pack (ask at most once)
Use the first that exists and contains `adapters/onboard-models.sh`:
1. `$AGENTPACK_ROOT`
2. `~/Developer/agent-definition`
3. A search of the home directory (depth 4) for `adapters/onboard-models.sh` next to `manifest.yaml`

Only if all fail, `ask_user` once: "Where is your agent-definition folder?" Run every later command from that root (`cd <root> && ...`).

### 2. Pick the harness
Decide which harness you are running in from your own tool set (see Harness notes), not from environment variables (a bridge can inherit another harness's env). Run `./adapters/onboard-models.sh --list-harnesses`. Then `ask_user` one question: "Set up models for which harness?" with every registered harness as an option, the one you are in listed first and marked "(this one)". Skip the question when the user already named a harness ("set up models for Claude").

### 3. Discover models
Run `./adapters/onboard-models.sh --harness <h> --list-models --json`. The JSON gives `models` (id, name, efforts, service_tiers, source), `current` (bindings already in the personal or shipping profile), `slots`, `main_required`, `profile`, `profile_env` and `notes`. Show the notes if any (for example "Pi not installed, static suggestions only").

### 4. Ask the user
First `ask_user` one quick-path question:
- "Keep current" (only if `current` has bindings): skip to step 5 with `current` as the answers.
- "One model for everything": ask a single model question and apply it to every slot.
- "Pick per capability" (default).

For "Pick per capability", ask one question per slot, in this order, batching all of them into a single `ask_user` call when the harness supports several questions at once:

| Slot | What it is for (show this to the user) |
|------|----------------------------------------|
| `main` | Your root chat session (skip when `main_required` is false and the user does not care) |
| `orchestrator` | Plans and coordinates delivery |
| `implement` | Writes code |
| `adversarial_audit` | Hostile review of changes |
| `taste` | Design, naming and UX judgement |
| `verify` | Runs and checks evidence |
| `fast_narrow` | Small, cheap, quick lookups |

Each question: options are the discovered model ids (label `name (id)`), the slot's current model first and marked "(current)", then `inherit-parent` ("use whatever this harness is set to") and "Other - type a model id". Accept a free-text id; the script warns but allows ids outside the list. If the question tool caps the number of options, offer the current model, the top two or three discovered ids and "Other", and print the full catalog as a numbered list in the same message so any id can be picked by number.

Then ask reasoning effort once for all slots (options: the efforts the chosen models share, plus "harness default"), and offer per-slot overrides only if the user asks. Ask service tier only when a chosen model lists one (`fast`), default "harness default".

### 5. Write, activate, export
1. Write the answers to a temp file (JSON):
   `{"main": {"model": "<id>", "reasoning": "<effort>"}, "capabilities": {"orchestrator": {"model": "<id>", "reasoning": "<effort>", "service_tier": "fast"}, ...}}`
   Omit `reasoning` / `service_tier` for "harness default". Omit `main` when skipped.
2. Preview: `./adapters/onboard-models.sh --harness <h> --answers <file> --dry-run`. Fix any `error:` by re-asking only the slot it names.
3. Show the user the preview as a short slot -> model table and `ask_user` "Write and activate this?" (yes / change a slot / cancel). For Codex, say that export rewrites the installed agents and the owned `~/.codex/config.toml` keys (a config backup is written first).
4. On yes: `./adapters/onboard-models.sh --harness <h> --answers <file> --activate --export`. Always go through the script, never hand-edit the profile, so validation stays in one place. `--activate` writes `profiles/.active/<h>`, so later exports and `./adapters/check.sh` use the personal profile without env vars.
5. Run `./adapters/check.sh` and report anything that is not clean.

### 6. Confirm
Tell the user, in plain words:
- the file written (`profiles/personal-<h>.yaml`) and each slot -> model
- that it is active for `<h>` and was exported (plus any install step from Harness notes, for example copying a portable skills folder)
- how to change it: say "run onboarding" again (answers are pre-filled from the current profile)
- how to undo: say "reset my models", which runs `./adapters/onboard-models.sh --harness <h> --deactivate` and re-exports, returning to the shipping profile

## Rules
- One personal profile per harness (`personal-<harness>`); the script refuses to overwrite a profile bound to another harness.
- Stitch-strict delivery stays on the shipping Codex profile (no Anthropic there). Personal profiles may mix any vendors.
- `inherit-parent` means the harness picks the model (Grok Bot settings, Pi default, Hermes config). Codex needs concrete ids.
- A new harness is registered by copying `harnesses/_template.yaml`; then this flow works for it unchanged.
- Do not edit shipping profiles, and do not skip the preview confirmation before export.

## Tools
- `ask_user`: harness choice, quick path, one question per slot, effort, final confirmation. Numbered list in chat when no widget exists.
- `run_command`: every helper call (`--list-harnesses`, `--list-models --json`, `--dry-run`, `--activate --export`, `--deactivate`, `check.sh`).
- `edit_file`: only the temp answers file.

## Harness notes: codex
- You are in Codex when you have `exec_command` and `request_user_input_async`. User says: "run onboarding" or "$onboard-models".
- `ask_user` -> `request_user_input_async` with one question per slot (options from the JSON). `run_command` -> `exec_command` with `workdir` set to the pack root.
- Discovery reads `~/.codex/models_cache.json`. Export writes `~/.codex/agents`, `~/.agents/skills`, `~/.codex/AGENTS.md` and owned `config.toml` keys; restart Codex to pick up the new main model.

## Harness notes: cursor
- You are in Cursor when you have Shell, Read and AskQuestion. User says: "run onboarding" or "/onboard-models".
- `ask_user` -> AskQuestion: one single-select question per slot in one call, plus an "Other - type a model id" option (the user can also reply in chat). `run_command` -> Shell with the pack root as working directory.
- Discovery: `~/.cursor/rules/pstack-models.mdc` ids plus the Codex cache. Cursor export does not apply model profiles yet; the profile is recorded and per-chat models still come from the Cursor model picker and pstack-models.mdc. Say so in the confirmation.

## Harness notes: claude
- You are in Claude Code when you have Bash and AskUserQuestion. User says: "run onboarding" or "/onboard-models".
- `ask_user` -> AskUserQuestion: up to 4 questions per call and 2-4 options each, so ask the slots in two calls with the current model plus top picks as options (it adds an "Other" free-text choice itself) and print the full catalog as a numbered list alongside. `run_command` -> Bash.
- Discovery: `~/.claude/cache/model-catalog/*.json`. Export writes `~/agents/claude-skills`; finish with `rsync -a ~/agents/claude-skills/ ~/.claude/skills/` after asking the user, then tell them to restart Claude Code.

## Harness notes: grokbot
- You are in Grok Bot when you have SendToUser, Shell and ListMachines. User says: "run onboarding" (or "set up models").
- The pack lives on the user's laptop, not the box: call ListMachines, use the laptop's machineId on every Shell call, and run from `~/Developer/agent-definition` there.
- `ask_user` -> SendToUser question widget, one question per slot (the turn ends; the answer resumes you). A subagent cannot ask; it returns the questions to its parent. `run_command` -> Shell with machineId.
- Grok Bot models come from its agent settings, so discovery offers `inherit-parent`; also offer "Other" for an id seen in the Grok Bot model picker. To set up Codex or Claude from Grok Bot, pick that harness in step 2. Export writes `~/agents/grokbot-skills` on the laptop; copying it into the box workflows folder is a separate step to offer.

## Harness notes: pi
- User says: "run onboarding" or "/skill:onboard-models".
- `ask_user`: no confirmed widget; use the numbered-list fallback. `run_command` -> bash tool.
- Discovery: `~/.pi/agent/models.json` + `settings.json` when installed, else static suggestions. Export writes `~/agents/pi-skills`; install with `rsync -a ~/agents/pi-skills/ ~/.pi/agent/skills/` after asking.

## Harness notes: hermes
- User says: "run onboarding" or "/onboard-models".
- `ask_user`: no confirmed widget; use the numbered-list fallback. `run_command` -> the Hermes terminal tool.
- Discovery: `~/.hermes/config.yaml` when installed, else inherit plus static suggestions. Export writes `~/agents/hermes-skills`; install under `~/.hermes/skills/agentpack/` after asking.
