# Agent definition pack

Harness-agnostic skills and agents/subagents for Jarushan / Stitch.

The authoritative locations are `~/Developer/agent-definition` and `~/Developer/agent-definition-backups`. Edit this source pack first. The backup directory's `latest` link points to a complete verified snapshot of this pack; older snapshots preserve history. Every standing-rule, agent, subagent, or skill change must update both locations and the affected installed copies.

Point any harness at this folder. An adapter should compile native skills and agents from the neutral YAML + markdown sources. See [SCHEMA.md](./SCHEMA.md).

**Set up your models: in any harness, ask the agent to "run onboarding" (or "run onboard-models").** It finds this pack, lists the models your harness can use, asks you to pick, writes and activates `profiles/personal-<harness>.yaml`, and re-exports. No paths or flags to remember.

## Quick start

```bash
# Verify every installed copy against the pack (writes nothing; exit 1 on drift)
./adapters/check.sh            # Codex + Cursor (+ Grok Bot if its out dir exists); --diff for diffs

# Codex: agents, ~/.agents/skills, ~/.codex/AGENTS.md, owned config.toml keys
./adapters/export-codex.sh --check     # verify only
./adapters/export-codex.sh --dry-run   # list pending changes
./adapters/export-codex.sh             # write changed files only
./adapters/export-codex.sh --only agents,skills   # parts: agents,skills,agents-md,config

# Owned config.toml keys only (profiles/codex.yaml main + guidance/codex-main.toml + guidance/codex-context.toml)
./adapters/sync-codex-config.sh --check

# Model binding: roles name a capability, profiles/<name>.yaml binds models
./adapters/export-codex.sh --check --explain        # print capability -> model per role
./adapters/export-codex.sh --profile NAME --dry-run # preview another profile
AGENTPACK_PROFILE=NAME ./adapters/export-codex.sh   # install it (default profile: codex)

# Cursor skill mirrors (~/.cursor/skills + portable ~/agents/skills)
./adapters/export-cursor.sh --check
./adapters/export-cursor.sh

# Grok Bot (sand-workflow) skills-only export to a portable out dir
./adapters/export-grokbot.sh --dry-run --explain   # preview + capability resolution
./adapters/export-grokbot.sh                       # write ~/agents/grokbot-skills
GROKBOT_SKILLS_OUT=/some/dir ./adapters/export-grokbot.sh

# Claude Code / Pi / Hermes (skills-only portable out dirs; see harnesses/*.yaml)
./adapters/export-claude.sh --dry-run --explain
./adapters/export-pi.sh --dry-run
./adapters/export-hermes.sh --dry-run

# Model onboarding (normally agent-driven: say "run onboarding"; these are what the skill runs)
./adapters/onboard-models.sh --list-harnesses
./adapters/onboard-models.sh --harness codex --list-models --json      # models + current bindings
./adapters/onboard-models.sh --harness claude --answers a.json --dry-run
./adapters/onboard-models.sh --harness codex --answers a.json --activate --export
./adapters/onboard-models.sh --harness codex --deactivate              # back to shipping profile
./adapters/onboard-models.sh --harness codex                           # interactive TTY prompts

# List registered harnesses (add one by copying harnesses/_template.yaml)
python3 adapters/lib/agentpack.py list-harnesses
```

Or pass an explicit pack root:

```bash
PACK_ROOT="$(pwd)" ./adapters/export-codex.sh
```

All exporters share `adapters/lib/agentpack.py` (one YAML-subset parser, one renderer per native format, one export/check engine). Check mode compares generated output with installed files and reports `missing`, `changed`, `stale` (extra file inside a pack-owned skill folder), `orphan` (skill folder or agent file not in the pack), `duplicate` (pack skill also under `~/.codex/skills`), `config` (owned key differs), `leak` (harness tool name in skill text outside its harness notes) and `pending` (a `lint.pending` skill that is already clean). Exit codes: 0 clean, 1 drift, 2 pack error.

Skill bodies stay harness- and model-agnostic (SCHEMA.md, "Harness notes sections" and "Model references in skills"): they name roles, capability bindings or exploratory panels, never vendor model ids. `## Harness notes: codex` / `cursor` / `grokbot` sections reach only that harness's install; the portable copy keeps all of them. Tool steps use the neutral verbs in `adapters/tool-map.yaml` (`spawn_subagent`, `await_subagents`, `message_subagent`, `ask_user`, `search_files`, `read_file`, `edit_file`, `run_command`; SCHEMA.md, "Tool references in skills"), and every export and check lints skills for leaked harness tool names (`leak`, `pending`).

Config sync edits only the owned keys in place, verifies the result parses and that no unowned setting changed, and writes `config.toml.agentpack-bak-<timestamp>` beside it before any change. Export never deletes: `--prune` moves stale files and orphan entries to `~/.agentpack-pruned/<timestamp>/` (override with `AGENTPACK_PRUNE_DIR`). Without `--prune`, stale and orphan items stay and are reported. Top-level non-folder files in a skills root (for example `~/agents/skills/README.md`) are ignored. Output paths can be overridden with `CODEX_HOME`, `CODEX_AGENTS_OUT`, `AGENTS_SKILLS_OUT`, `CODEX_AGENTS_MD_OUT`, `CODEX_CONFIG`, `CURSOR_SKILLS_OUT`, `PORTABLE_SKILLS_OUT` and `GROKBOT_SKILLS_OUT` (plus `GROKBOT_PROFILE`).

## Grok Bot

Grok Bot loads user skills as `<name>/SKILL.md` folders in its box workflows directory (`/home/box/agent-data/workflows` on the box). That box is a separate machine, so the laptop exporter only writes `~/agents/grokbot-skills` (keeps `## Harness notes: grokbot`, drops codex/cursor notes). To install, copy or sync that folder into the box workflows directory from a Grok Bot session (for example CopyToBox per file, or an archive copied and unpacked on the box), then compare. There is no automated box sync yet. The box copies seen on 2026-10-06 predate this pack's neutral rewrite and include `stitch-engineering-loop`, which is no longer a pack skill; reconcile those by hand before a first sync. Models come from Grok Bot agent settings (`profiles/grokbot.yaml` binds every capability to `inherit-parent`).

## Claude Code, Pi, and Hermes

Each has a registered harness (`harnesses/claude.yaml`, `pi.yaml`, `hermes.yaml`), a shipping profile, and `adapters/export-<name>.sh` that writes a portable skills tree (`~/agents/claude-skills`, `~/agents/pi-skills`, `~/agents/hermes-skills` by default) plus `.agentpack-resolved`. Live install paths (not written by default):

| Harness | Live skills path | Notes |
|---------|------------------|-------|
| Claude Code | `~/.claude/skills/<skill>/SKILL.md` | Model catalog: `~/.claude/cache/model-catalog/` |
| Pi | `~/.pi/agent/skills/` (also `~/.agents/skills/`) | Models: `~/.pi/agent/models.json` + `settings.json`. Docs: https://pi.dev/docs/latest/skills |
| Hermes | `~/.hermes/skills/<category>/<skill>/SKILL.md` | Install pack skills under `~/.hermes/skills/agentpack/`. Docs: https://hermes-agent.nousresearch.com/docs/user-guide/features/skills |

Neither Pi nor Hermes was installed on the authoring laptop when these adapters shipped; exporters and onboarding still work against portable out dirs and static/catalog discovery. Set `PI_SKILLS_OUT=~/.pi/agent/skills` or `HERMES_SKILLS_OUT=~/.hermes/skills/agentpack` to export into a live tree once installed.

## Registering another harness (5 minutes)

1. Copy `harnesses/_template.yaml` to `harnesses/<name>.yaml` and fill `name`, skills out dirs, and `model_discovery`.
2. Add a `<name>:` string under every verb in `adapters/tool-map.yaml` (mark TBD where unknown); optional `leaks.<name>`.
3. Optional: add `profiles/<name>.yaml` shipping stubs (often `inherit-parent`).
4. Optional: copy `adapters/export-claude.sh` to `export-<name>.sh` and change the harness argument.
5. Run `./adapters/onboard-models.sh --harness <name>` then `python3 adapters/lib/agentpack.py <name>`.

## Model onboarding

In any harness: ask the agent to run onboard-models ("run onboarding", "set up my models", "onboard"). The `onboard-models` skill finds the pack (`$AGENTPACK_ROOT`, else `~/Developer/agent-definition`, else asks once), picks the harness, discovers models with `--list-models --json`, asks one question per capability (widget where the harness has one, numbered list otherwise), previews, then runs `--answers <file> --activate --export` and `check.sh`. It writes `profiles/personal-<harness>.yaml` (one per harness, never a shipping profile) and `profiles/.active/<harness>`, so exporters and `check.sh` use it without env vars. Say "reset my models" to deactivate. Selection order: `--profile`, then the harness env var, then `profiles/.active/<harness>`, then the shipping profile. Personal profiles may mix vendors; Stitch-strict Codex delivery does not. Cursor records the profile but does not apply it yet.


## What lives here

- `skills/` - reusable multi-step recipes (Feature loop, audits, how/why, etc.)
- `agents/` - role personas for subagent spawn (test-writer, implementer, reviewer, researcher, ...)
- `AGENTS.md` - concise canonical standing rules, installed at `~/.codex/AGENTS.md`
- `guidance/` - conditional instructions; read only when the trigger in `AGENTS.md` applies
- `DELIVERY-CHECKLIST.md` - startup prevention checks with links to detailed incidents
- `DELIVERY-LESSONS.md` - preserved incident evidence and recurrence tracking
- `adapters/` - reference exporters (Codex, Cursor, Grok Bot, Claude, Pi, Hermes) plus `onboard-models.sh`; the pack itself has no harness lock-in
- `harnesses/` - registry of consumer hosts (`_template.yaml` to add more)

## Repository boundary

This is a personal pack. Keep its instructions and local-path references outside project repositories. Each repository owns its AGENTS.md; do not synchronize a canonical repository file from this pack. The former Stitch mirror is retained only as historical evidence. The personal AGENTS.md instructs the agent to read DELIVERY-CHECKLIST.md at each top-level task. Incident details load when relevant or when diagnosing recurrence. A reference does not itself inject the file into the prompt.

## Editing

1. Edit `AGENTS.md`, `guidance/`, `skills/<id>/`, or `agents/<id>/`. Update `manifest.yaml` when adding or removing definitions.
2. Save a complete dated copy of this pack under `../agent-definition-backups/` and point its `latest` link at that copy. Preserve previous snapshots.
3. Run the exporters (`./adapters/export-codex.sh`, `./adapters/export-cursor.sh`, and `./adapters/export-grokbot.sh` once Grok Bot is in use). The Codex exporter also installs `AGENTS.md` at `~/.codex/AGENTS.md` and the owned `config.toml` keys. Guidance files stay in this source pack and are read through the explicit paths in the standing rules.
4. Run `./adapters/check.sh` and verify that the source pack and current backup match, and that installed copies match the source or its generated output. If a step cannot finish, report the unsynchronized paths rather than declaring completion.

Generated `~/.codex/agents/*.toml`, mirrored `SKILL.md` files, and `~/.codex/AGENTS.md` are installed copies. Do not edit them without making the same change in the source pack and refreshing its backup.

## Feature loop and review skills

- `feature-graph`, aliased as `dag`, is the default when Jarushan says `impl this` in Firstmate or direct sessions. It can also be selected explicitly with phrases such as `impl with dag`. An explicit choice of another workflow takes precedence, and existing deliveries retain their selected workflow. The shorthand preserves the standing scope, freeze and publication boundaries. Main loads only the launcher; CoS loads the full workflow. Its Python guard records prerequisites, native identities and source identities. The check helper persists resource waits before lock acquisition; Main acknowledges real user delivery before closeout. New version 5 runs use a dedicated CoS under Main, then parallel authors in one worktree with disjoint writes and no peer context or newly authored peer-file reads. Checks and all four reviews overlap on the frozen candidate; reconciliation requires every pass. It preserves current role/model pins. See the skill for the graph and terminal commands.

- `feature-loop` replaces `stitch-engineering-loop`; legacy eng-loop phrases route to the new skill. CoS alone orchestrates five stages: freeze/setup, independent authors, integration/checks, parallel reviews, signed draft/CI.
- `arc` is the standalone architecture review skill. Its Codex role keeps the existing `csa` name for compatibility. The optional `reviewer` role is an adviser, never an orchestrator.
- `styla` is the standalone house-style review skill. Arc and Styla remain conditional in Feature loop and mandatory in Feature graph versions 2 through 5.

Feature loop's two default reviewers are `slice_spec_audit` (acceptance, test validity, independent execution) and `researcher` (regressions, callers, code quality). Feature graph version 2 renames its acceptance node to `verification`, using the same `slice_spec_audit` role for a first-principles audit of the full spec, implementation and tests. It also always runs Arc and Styla. Existing version 1, 2, 3 and 4 runs keep their archived workflow and assigned role rules. Version 4 retains parallel scheduling and budgets, and adds explicit evidence reuse after repairs. CoS approves the impact analysis, the guard validates identities and coverage, and affected reviewers complete focused repairs. Uncertain impact requires full review. Required repository checks and exact-head CI still run. The acceptance role has workspace-write access solely for scratch checks and generated outputs; it must not edit reviewed source/tests. The `verifier` remains optional for routine delivery and leads repair-loop debugging and investigations requiring the combined candidate when CoS assigns it. Subagents execute Debug from first principles within their role; CoS coordinates and does not run the skill or diagnostic probes.

All engineering agents start fresh from the frozen spec and permitted repository artifacts, with no peer reasoning or conversation history. Initial authors work from the same baseline without seeing each other's new output. Git receives operational inputs only. Preserve role pins unless the captain explicitly changes them.

CoS checks every subagent's progress and artifacts against the approved spec and assigned scope. It redirects side quests and returns unnecessary complexity to the owning agent for simplification. Accept work only when the evidence supports the required behavior and repository rules.

Freeze includes discussing architecture and the implementation approach with the captain and recording the agreed design in the spec. Before coding, the implementer returns its concrete plan to CoS. CoS checks and shares it, then releases work under the existing approval when it matches. Material design changes return to the captain before affected work proceeds. Under AGENTS.md, CoS may record minor spec refinements and test-only amendments preserving the agreed behavior, architecture and acceptance without another captain approval. Pin the revised source spec and reconcile affected agents and evidence; changing the product contract or weakening required proof still requires approval.

When migrating an existing install, retire the old `stitch-engineering-loop` source and installed directories outside skill-indexed roots. Exporters overwrite current entries; `--check` reports obsolete directories as `orphan`, and `--prune` moves them to `~/.agentpack-pruned/<timestamp>/`.

Version 5 adds the `cos` native role at GPT-6.1 Sol `high` with Fast mode for the approved dedicated-coordinator launch. Resolve each named role from its canonical `agents/<role>/agent.yaml` and pin that revision per run. Older startup snapshots do not create a new model decision; an explicit current per-run override still wins. Unavailable configured models block that role rather than being silently remapped. This change does not rewrite root-session defaults or other workflows.

## Model pins

Each role's `agents/<role>/agent.yaml` names its capability; the active profile (`profiles/codex.yaml` for Codex) binds that capability to a model. Together they are authoritative. The table below is a reference summary, not a second configuration source; the dedicated DAG CoS uses `agents/cos/agent.yaml` (capability `orchestrator`). Resolve stale startup text against the current role before asking for a model decision. Preserve explicit current user overrides and already-running workers' recorded pins.

Agents declare only a semantic `model.capability`. Profiles in `profiles/<name>.yaml` bind capabilities (plus rare per-role overrides and the root session) to concrete models; `./adapters/export-codex.sh --check --explain` prints the resolution. The default `codex` profile is strict. Feature loop pins are strict: report an unavailable model instead of silently remapping. DAG CoS, Arc/csa, acceptance, regression, Styla and verifier roles use GPT-6.1 Sol at `high` with Fast mode. These shared role pins also apply when another workflow invokes them. Standalone architect and repo-spec-audit skills and the optional reviewer role also use GPT-6.1 Sol at `high` with Fast mode. Pins also apply to retries and followups. Current Stitch map (2026-10-06):

| Capability (profiles/codex.yaml)                | Binding               |
| ----------------------------------------------- | --------------------- |
| orchestrator                                  | gpt-6.1-sol @ high, Fast |
| Arc / acceptance / regression                 | gpt-6.1-sol @ high, Fast |
| optional reviewer                              | gpt-6.1-sol @ high, Fast |
| implement (test-writer and implementer)         | gpt-5.6-sol @ medium, Fast |
| fast_narrow (Git)                               | gpt-5.6-sol @ medium, Fast |
| taste (Styla)                                   | gpt-6.1-sol @ high, Fast |
| verify                                          | gpt-6.1-sol @ high, Fast |

Main defaults are owned separately by the `main:` block of `profiles/codex.yaml`: GPT-6.1 Sol at `high` with Fast mode (`guidance/codex-main.toml` keeps only any other root-session keys). Synchronize its `model`, `model_reasoning_effort`, `service_tier` and `[features].fast_mode` keys into `~/.codex/config.toml`, preserving unrelated settings. Firstmate's Codex launcher inherits these defaults. Named agents keep their explicit role pins; synchronizing CoS must not overwrite Main defaults. `./adapters/export-codex.sh` (or `./adapters/sync-codex-config.sh`) writes and verifies these keys. New sessions use the installed defaults unless an explicit session override applies.

## Codex context window

The requested context setting for new main agents and subagents is 1,000,000 tokens. The canonical settings fragment is `guidance/codex-context.toml`; synchronize its two top-level keys into `~/.codex/config.toml`, preserving all other settings. Custom agents inherit these keys from their parent unless an explicit session or role override changes them. Do not change model, reasoning, sandbox or service-tier pins when applying this fragment.

Automatic compaction is set to 800,000 tokens. On 1 October 2026, the installed Codex catalog advertises a maximum context of 872,000 tokens for the selected GPT-6.1 Sol, GPT-6 Astra and GPT-5.6 Sol models. The requested setting does not increase a model or service limit, and a literal 1,000,000-token usable prompt is not verified. Preserve model limits and compaction headroom. Use newly started sessions to pick up the settings; do not interrupt running agents merely to apply them.

## Codex skill install path

Codex indexes **both** `~/.agents/skills` and `~/.codex/skills`. Keep user skills in **`~/.agents/skills` only** (via `adapters/export-codex.sh`). Do not copy the same skill into `~/.codex/skills` or Codex will list duplicates (e.g. two Feature loop entries). `~/.codex/skills/.system` stays for built-ins.

The Git role is pinned to GPT-5.6 Sol at `medium` with Fast mode for authorized Git operations. It returns semantic conflicts to CoS instead of making implementation decisions. Model choice and reasoning effort should be evaluated by total time, tokens, repair rounds, and missed defects on representative slices.
