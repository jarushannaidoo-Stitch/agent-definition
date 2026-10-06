# Swarm

Fan out N parallel workers (cloud workers where the harness offers them). They may cover separate slices, race the same brief, or mix both. The parent waits, aggregates, and returns one report.

## Start

Open a todolist with one entry per phase before launching anything.

1. Frame
2. Fan out
3. Aggregate
4. Report

## Phase A: Frame

1. State the done predicate and the artifact or report the swarm must return.
2. Choose the shape. Partition into slices, race N workers on identical briefs, or mix both. For a race or mixed shape, declare `first pass`, `rank all`, or `best-of` before spawning.
3. Set N from the user or derive it from the shape. N is total workers, not the cloud concurrency limit.
4. Pick the worker model from panel `swarm-workers` (see Model panels). For a model race, name each arm's model up front.
5. Give each worker its own writable output when it writes. Use a worktree, branch, or `/tmp/swarm-<slug>/worker-<n>/`.

## Phase B: Fan out

Spawn all N workers at once with `spawn_subagent`: role general-purpose, in the background, on the configured model, in the cloud environment where the harness offers one. Use the local environment only when the worker needs access to something on the user's computer.

When a worker must start from a non-default pushed branch, set its base branch (see Harness notes).

Every brief stands alone. Include the goal, scope, exact slice or race arm, how to verify, and what to report. Reports use `PASS`, `ISSUES`, or `BLOCKED` with evidence.

If a worker drops out, proceed with N-1 and note it.

## Phase C: Aggregate

Collect the terminal results with `await_subagents`. For coverage, every required slice needs a result. For a race, apply the selection rule declared up front. Use first pass, rank all, or best-of. Do not paste raw worker dumps.

Keep a compact result table, one-line evidenced issues, and explicit gaps or dropouts.

## Phase D: Report

Return one consolidated in-chat report with the table, issue one-liners, gaps or dropouts, and the race rule when used.

## Tools

This skill names harness-neutral tool verbs (SCHEMA.md, "Tool references in skills"). Harness notes below give each harness's real tool.

- `spawn_subagent`. Start a fresh subagent from a standalone brief, with the role, model and access the step names.
- `await_subagents`. Collect spawned subagents' results as each finishes.

## Model panels

Model choices in this skill are named panels, never vendors: `swarm-workers`. A panel is one model or an ordered list of models; a list means one subagent per entry. `swarm-workers` is the model every worker uses unless a model race names each arm. Resolve each panel from the harness's model configuration (see Harness notes). An entry of `inherit-parent` or `auto` runs on the parent session model. If a panel is not configured, ask the user once which models to use; if they defer, run every slot on the parent session model as independent subagents and say the panel was single-model. Mixing model families is optional diversity, never a requirement. When this skill runs inside Stitch delivery, the delivery model rules (no Anthropic models, role bindings from the active profile) override any panel.

## Harness notes: cursor

Panels come from `~/.cursor/rules/pstack-models.mdc` when present: `swarm-workers` is the `swarm workers` line. For `inherit-parent` or `auto`, omit the Task `model`.

Tools: `spawn_subagent` is the `Task` tool with `subagent_type: generalPurpose` (general-purpose) and `model` from the panel entry (omit it for `inherit-parent` or `auto`). Add `environment: "cloud"` (or `"local"`) and `run_in_background: true`, and issue all N `Task` calls in one message. A cloud worker's base branch is `cloud_base_branch`. Background completions arrive as notifications, which is `await_subagents`.

## Harness notes: codex

Codex has no panel configuration yet (`panels:` in profiles is reserved and not exported), so use the unconfigured-panel rule above.

Tools: `spawn_subagent` is `spawn_agent` with `agent_type: "default"` (general-purpose), `fork_turns: "none"`, a short `task_name`, the brief in `message`, and `model` plus `reasoning_effort` from the panel entry (omit both for `inherit-parent` or `auto`). `spawn_agent` has no cloud environment, so every worker runs locally: give each its own worktree or output path (Phase A step 5) and check out any required branch there before spawning. Spawned agents run concurrently, which covers background. Issue parallel spawns back to back, then call `wait_agent` (with a `timeout_ms`) until every spawned agent has reported; `list_agents` shows status. That is `await_subagents`.
