# Agent definition pack schema (v1)

Harness-agnostic source of truth. Any harness adapter reads this tree and emits its native skills / agents / subagents.

## Layout

```
agent-definition/
  AGENTS.md              # canonical standing rules, copied to the harness instruction path
  manifest.yaml          # index + pack metadata
  SCHEMA.md              # this file
  README.md              # human contract
  skills/<id>/
    skill.yaml           # required metadata
    BODY.md              # required recipe (markdown)
  agents/<id>/
    agent.yaml           # required metadata (capability, never a model id)
    INSTRUCTIONS.md      # required system / developer instructions
  profiles/<name>.yaml   # binds capabilities to concrete models for one harness
  harnesses/<name>.yaml  # registers a harness (skills out dir, discovery, builtin vs generic)
  harnesses/_template.yaml  # copy to add pi/hermes-like hosts
  adapters/              # optional reference exporters (not required to consume)
  adapters/tool-map.yaml # neutral tool verbs -> each harness's tools, plus the leak lint
  adapters/onboard-models.sh  # pick models -> profiles/personal-<harness>.yaml (agent: "run onboarding")
```

The complete pack is also preserved in `../agent-definition-backups/latest`. Update both locations for every standing-rule, agent, subagent, or skill change, preserving older snapshots. The reference Codex adapter also installs `AGENTS.md` and its owned `config.toml` keys; every reference adapter supports `--check` to verify installed copies.

## skill.yaml

| Field | Type | Required | Meaning |
|-------|------|----------|---------|
| `id` | string | yes | Stable slug (`feature-loop`). Folder name must match. |
| `name` | string | yes | Display name |
| `description` | string | yes | When to use (one line / short paragraph) |
| `version` | string | no | Semver for the skill content |
| `tags` | string[] | no | Freeform |
| `when` | string | no | Longer trigger guidance if description is short |
| `related` | string[] | no | Other skill ids |

`BODY.md` is the recipe. No harness paths (`~/.codex/...`, Cursor plugin paths) in the body unless under a clearly labeled "Harness notes" section. Prefer role names and relative references to `agents/<id>`.

### Harness notes sections

- `## Harness notes: <harness>[, <harness>]` holds steps, paths and tool parameters that only one harness understands (for example Codex `fork_turns`, Cursor `~/.cursor/...` paths). Known harness names come from `harnesses/*.yaml` (today: `codex`, `cursor`, `grokbot`, `claude`, `pi`, `hermes`); adapters reject any other name so a typo cannot silently drop a section. Copy `harnesses/_template.yaml` to register another host.
- A section runs from its heading to the next level-1 or level-2 heading outside a code fence. Put these sections at the end of `BODY.md`.
- Adapters keep only the sections naming their harness: Codex (`~/.agents/skills`), Cursor (`~/.cursor/skills`), and each skills-only export (`~/agents/grokbot-skills`, `~/agents/claude-skills`, `~/agents/pi-skills`, `~/agents/hermes-skills`, or `$OUT_ENV`) keep their own notes; the portable Cursor copy (`~/agents/skills`) keeps every section.
- A plain `## Harness notes` heading (no harness named) applies to every harness and is always kept. Prefer the targeted form.
- Companion files are copied verbatim; filtering applies only to `BODY.md`.

### Model references in skills

Skill bodies and `skill.yaml` descriptions never name a concrete model or vendor model id. Use one of:

- **A role** (`csa`, `styla`, `cos`, ...): the role runs on the active profile's binding for its capability. Say so and do not override it.
- **A capability binding** for an unnamed launch: "the active profile's `adversarial_audit` binding". If the harness has no binding for that capability, the skill asks which model to use; it never silently substitutes. Stitch delivery skills use only roles and capability bindings.
- **A panel** for exploratory fan-out (multi-model review, races): a named slot such as `how-critics`. A panel is one model or an ordered list (one subagent per entry). An entry of `inherit-parent` or `auto` means the parent session model. If a panel is not configured, the skill asks once which models to use, and if the user defers it runs every slot on the parent session model and says the panel was single-model. Mixing vendors is optional diversity, never a requirement. Inside Stitch delivery, the delivery model rules override any panel.

Each skill that uses panels carries a short `## Model panels` section (skills are read standalone, so the rule is repeated) and per-harness notes saying where panels come from.

Panel registry (ids used in skill bodies; Cursor maps each to a line in `~/.cursor/rules/pstack-models.mdc`):

| Panel | Used by | Cursor pstack line |
|-------|---------|--------------------|
| `how-explorer`, `how-explainer`, `how-critics` | how | `how explorer`, `how explainer`, `how critics` |
| `why-investigators`, `why-synthesizer` | why | `why investigators`, `why synthesizer` |
| `arena-runners`, `arena-cross-judge` | arena | `arena runners`, `arena cross-judge pool` |
| `swarm-workers` | swarm, poteto-mode | `swarm workers` |
| `interrogate-reviewers` | interrogate | `interrogate reviewers` |
| `feature`, `refactoring`, `bug-fix`, `perf-issue`, `hillclimb`, `judgment-and-prose`, `hardest-tasks` | poteto-mode | `feature, refactoring`, `bug-fix`, `perf-issue`, `hillclimb`, `judgment and prose`, `hardest tasks` |

Profiles reserve an optional `panels:` map (panel id -> model or list) for a future adapter that installs panel bindings; no adapter reads or writes it yet, so Codex follows the unconfigured-panel rule today.

### Tool references in skills

Skill bodies name harness-neutral tool verbs, never a harness's tool names or parameters (`Task`, `subagent_type`, `run_in_background`, `readonly`, Glob/Grep, `AskQuestion`, `spawn_agent`, `fork_turns`, `wait_agent`, ...). The verbs and each harness's concrete tool live in `adapters/tool-map.yaml`. Keep the list small; add a verb only when a skill needs one that no existing verb covers.

| Verb | Meaning |
|------|---------|
| `spawn_subagent` | Start a fresh subagent from a standalone brief. The step names what it needs: role (a pack agent id, a named harness role, or general-purpose), model (role binding, capability binding or panel entry), access (read-only or write), background, and environment (local or cloud) where it matters. |
| `await_subagents` | Collect spawned subagents' results as each finishes. |
| `message_subagent` | Send a follow-up, correction or resume to an existing subagent. |
| `ask_user` | Ask the human a structured question and wait for the answer. |
| `search_files` | Find files by name pattern or search file contents. |
| `read_file` | Read a file's contents. |
| `edit_file` | Create or change a file. |
| `run_command` | Run a shell command. |

Rules:

- Write the verb in backticks and its options in plain words ("`spawn_subagent`, role general-purpose, access read-only"). Skills are read standalone, so a skill that uses verbs carries a short `## Tools` section (one line per verb it uses) and `## Harness notes: codex` / `cursor` / `grokbot` sections that give the real tool names and parameters. Those notes must agree with `adapters/tool-map.yaml`.
- A capability a harness lacks is stated in its notes (for example Codex `spawn_agent` has no read-only flag and no cloud environment), never papered over or silently substituted.
- Prompt templates in companion files (text pasted into a subagent's brief) use plain English ("search file contents for the symbol, read the implementation"), not verbs or tool names: the subagent never sees the parent's harness notes, and companions are copied verbatim with no harness filtering.
- The reference adapter lints on every export and `--check`: each `BODY.md` (outside targeted harness notes) and each companion `.md` is scanned for the `leaks` patterns in `adapters/tool-map.yaml`. A leak in a skill listed under `lint.pending` is reported as pending; a path under `lint.exempt` (archived workflows) is skipped; any other leak is drift (`--check` exits 1). A pending skill that is already clean is also drift, so the list cannot go stale.

`adapters/tool-map.yaml` fields: `schema_version` (1), `verbs` (verb -> `meaning`, `codex`, `cursor`, `grokbot`; every known harness is required; write TBD in the text where a harness capability is unconfirmed), `leaks` (harness -> list of Python regexes, unquoted), `lint.pending` (skill ids) and `lint.exempt` (paths relative to `skills/`).

## agent.yaml

| Field | Type | Required | Meaning |
|-------|------|----------|---------|
| `id` | string | yes | Stable slug (`reviewer`). Folder name must match. |
| `name` | string | yes | Spawn / reference name (may equal id) |
| `description` | string | yes | When a parent should spawn this agent |
| `kind` | string | yes | One of: `subagent`, `orchestrator`, `standing` |
| `model` | object | yes | See below |
| `sandbox` | string | no | `read-only` \| `workspace-write` \| `full` (semantic; harness maps) |
| `tags` | string[] | no | Freeform |
| `skills` | string[] | no | skill ids this agent may load |

### model object

| Field | Type | Required | Meaning |
|-------|------|----------|---------|
| `capability` | string | yes | Semantic tier: `orchestrator` \| `implement` \| `fast_narrow` \| `adversarial_audit` \| `taste` \| `verify` |

Roles describe what they need, never which vendor provides it. `model.preferred`, `reasoning`, `service_tier` and `fallbacks` moved to profiles (Phase 2, 2026-10-06); the reference adapter rejects them in `agent.yaml` so there is one source of truth.

## profiles/<name>.yaml

A profile binds capabilities to concrete models for one harness. The reference Codex adapter uses `profiles/codex.yaml` unless `--profile NAME` or `AGENTPACK_PROFILE=NAME` selects another. Switching profiles changes models without touching any role or skill.

| Field | Type | Required | Meaning |
|-------|------|----------|---------|
| `profile` | string | yes | Must equal the file name |
| `harness` | string | yes | Harness this profile targets (`codex`, `grokbot`); adapters reject a mismatch |
| `description` | string | no | Human note |
| `strict` | bool | no (default `true`) | Fail closed: every capability used by a role must be mapped; `default` is forbidden; never remap silently |
| `main` | binding | no | Root-session defaults (Codex: `model`, `model_reasoning_effort`, `service_tier`, `[features].fast_mode` in `config.toml`) |
| `capabilities` | map capability -> binding | yes | One binding per capability the roles use |
| `roles` | map agent id -> partial binding | no | Per-role override of any binding field; use only where a role genuinely differs from its capability |
| `default` | binding | no | Non-strict profiles only: used for capabilities without a binding |

A binding is `model` (required except in `roles` overrides; the value `inherit-parent` means the harness chooses, from the parent session or its own agent settings, and is accepted only by skills-only adapters such as `grokbot`, never by Codex), optional `reasoning` (`low` \| `medium` \| `high` \| `xhigh` \| `max` \| `ultra`), optional `service_tier` (such as `fast`; Codex maps `fast` to priority processing plus `features.fast_mode = true`; omit to inherit the harness default) and optional `fallbacks` (ordered alternates, never used by a strict profile).

Resolution: `roles.<id>` fields override `capabilities.<capability>`; a non-strict profile may fall back to `default`. A strict profile with an unmapped capability is an adapter error, not a remap. Never bind a model the harness cannot run. Follow explicit workflow/captain pins first; fallbacks apply only when the consuming workflow and a non-strict profile both permit it.

The Codex adapter records the resolution in `~/.codex/agents/.agentpack-resolved` (a dotfile Codex does not load as an agent) so `--check` also catches a profile switch. Generated `.toml` files carry no extra comments, keeping them byte-identical to pre-profile installs.

### Grok Bot profile and export

`profiles/grokbot.yaml` is strict and binds every capability to `inherit-parent`: Grok Bot picks models in its own agent settings, so the pack records intent without pinning ids it cannot install. Replace a binding with a concrete id only when the live Grok Bot model picker shows it. `adapters/export-grokbot.sh` is skills-only: it writes `SKILL.md` folders (frontmatter `name` + `description`, the same shape as Grok Bot sand-workflow skills) plus a `.agentpack-resolved` sidecar to `$GROKBOT_SKILLS_OUT` (default `~/agents/grokbot-skills`). `$GROKBOT_PROFILE` or `--profile` selects another profile; `AGENTPACK_PROFILE` stays Codex-only so one variable cannot cross harnesses. The exporter never writes to a Grok Bot box; syncing the out dir into the box workflows folder is a separate, manual step.

### Claude Code, Pi, and Hermes exports

`profiles/claude.yaml` ships concrete Claude catalog ids (Fable/Opus/Haiku-style) as a stub; `profiles/pi.yaml` and `profiles/hermes.yaml` ship `inherit-parent` until onboarding writes personal bindings. Each has `adapters/export-<name>.sh` (skills-only, portable out dir under `~/agents/<name>-skills` by default). Live install paths: Claude `~/.claude/skills`, Pi `~/.pi/agent/skills` (also `~/.agents/skills`), Hermes `~/.hermes/skills/<category>/`. None of the exporters write into those live dirs unless `$OUT_ENV` points there.



## harnesses/<name>.yaml

Registers a consumer harness so exporters, harness-notes filtering, tool-map validation and onboarding share one list.

| Field | Type | Required | Meaning |
|-------|------|----------|---------|
| `name` | string | yes | Must match the file stem (`[a-z][a-z0-9_]*`) |
| `display_name` | string | no | Human label |
| `builtin` | bool | no (default false) | `true` only for special-cased exporters in `agentpack.py` (`codex`, `cursor`, `grokbot`). Everyone else uses the generic skills-only exporter. |
| `skills.out_env` | string | yes | Env override for the skills output directory |
| `skills.out_default` | string | yes | Default out dir (relative to `$HOME` unless absolute) |
| `skills.shape` | string | yes | Only `skill_md` today (name+description frontmatter + BODY) |
| `skills.install_hint` | string | no | Where to copy the portable out dir on a live install |
| `agents.export` | bool | no | Reserved; only Codex exports agents today |
| `profile.shipping` | string | no | Default `profiles/<stem>.yaml` stem |
| `profile.env` | string | no | Env var selecting the active profile (`AGENTPACK_PROFILE` for Codex) |
| `model_discovery` | list | no | Ordered discovery steps for `onboard-models` (see below) |

`model_discovery` step `kind` values: `static`, `command_json`, `codex_cache`, `claude_catalog`, `pstack_mdc`, `pi_models_json`, `hermes_config`, `inherit`. Discovery is best-effort; free-text model ids are always allowed with a warning.

Add a harness in five minutes: copy `_template.yaml`, fill `name` / out dirs / discovery, add a `<name>:` row under every verb in `adapters/tool-map.yaml` (and optional `leaks`), optionally add `profiles/<name>.yaml`, then `./adapters/onboard-models.sh --harness <name>` and `python3 adapters/lib/agentpack.py <name>` (or copy an `export-*.sh` wrapper).

## Model onboarding

`adapters/onboard-models.sh` (skill `onboard-models`) writes `profiles/<profile>.yaml` (default `personal-<harness>`) for a harness without editing shipping profiles. Users never run it by hand: they ask an agent to "run onboarding" and the skill drives it. Pack root resolution: workspace (if it looks like this pack), else `$AGENTPACK_ROOT` / `$PACK_ROOT`, else `~/Developer/agent-definition`, else `~/agent-definition` (see `CLOUD.md` for Cursor cloud agents; do not search GitHub for the skill).

```bash
./adapters/onboard-models.sh --harness codex --list-models
./adapters/onboard-models.sh --harness claude --dry-run
./adapters/onboard-models.sh --harness pi --set main=inherit-parent --set orchestrator=inherit-parent ... 
./adapters/onboard-models.sh --harness hermes --answers answers.yaml --export
```

Agent flags: `--list-harnesses`; `--list-models --json` (pack root, harness, profile, `profile_env`, active and shipping profile, slots, `main_required`, current bindings, models, notes); repeatable `--set SLOT=model[:reasoning[:service_tier]]` or `--answers` YAML/JSON with `main:` and `capabilities:`. Interactive TTY prompts when none is passed. `--export` runs the harness exporter with the new profile (Cursor: skills only, no profile). `--activate` writes `profiles/.active/<harness>` (one line: profile name); `--deactivate` removes it. Exporters pick a profile in this order: `--profile`, `$<HARNESS>_PROFILE` (`AGENTPACK_PROFILE` for Codex), `profiles/.active/<harness>`, shipping profile. Refuses to overwrite a shipping profile name (`codex`, `claude`, ...) or a profile bound to another harness (unless `--force`).

Stitch-strict delivery keeps using `profiles/codex.yaml` (no Anthropic). Personal and non-Codex shipping stubs may bind any vendor model the harness can run.

## profiles notes (multi-harness)

## manifest.yaml

```yaml
schema_version: 1
name: ...
description: ...
skills: [id, ...]
agents: [id, ...]
```

## Adapter contract

Given this folder root `$PACK`:

1. Read `manifest.yaml`. Reject if `schema_version` major != 1.
2. For each skill id: read `skills/<id>/skill.yaml` + `BODY.md`. Emit native skill (e.g. Cursor/Codex `SKILL.md` with YAML frontmatter `name` + `description`, body = BODY.md).
3. Load the active profile for the harness and resolve every agent's `capability` (strict profiles fail closed). For each agent id: read `agents/<id>/agent.yaml` + `INSTRUCTIONS.md`. Emit native agent (e.g. Codex `~/.codex/agents/<id>.toml` with `name`, `description`, `model`, `model_reasoning_effort`, optional `service_tier`, `sandbox_mode`, `developer_instructions`).
4. Do not require files under `adapters/` to consume the pack.

### Sandbox mapping (suggested)

| Semantic | Codex | Cursor cloud / notes |
|----------|-------|----------------------|
| `read-only` | `read-only` | no writes |
| `workspace-write` | `workspace-write` | normal coding agent |
| `full` | `danger-full-access` | elevated; avoid by default |

## Companion files

A skill folder may include extra files or directories beside `skill.yaml` and `BODY.md` (for example `sdk/`). Adapters MUST copy those companions into the harness skill directory next to the generated `SKILL.md`. Do not put harness-generated copies under a second root that the same harness also indexes (Codex: user skills only in `~/.agents/skills`).
