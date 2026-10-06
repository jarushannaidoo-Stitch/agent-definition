# Arena

Fan out N parallel attempts at the same task. Read every candidate end to end. Pick the strongest as the base. Graft the best ideas from the others into it. Verify the synthesized result.

## Start

Open a todolist with one entry per phase before launching anything. The arena runs autonomously and the list keeps phases from silently disappearing.

1. Frame
2. Fan out
3. Cross-judge
4. Pick
5. Graft
6. Verify

## Phase A: Frame

The N candidates will receive the same prompt, so the prompt is the contract. Get it right before spawning anything.

1. State the artifact each candidate is producing.
2. Derive the rubric. State what success looks like for *this* task, then turn it into 3-6 concrete gradeable criteria. Concrete: `Adds a --dry-run flag that skips writes`. Vague: `code is correct`. The rubric is the picker's tool in Phase D; candidates only see the task.
3. Pick the runners. Use panel `arena-runners` (see Model panels; default size four), one runner per entry, unless the caller passes explicit models. Spawn more when the arena covers multiple design directions. Same model N times when the work is generation-bound rather than judgment-sensitive.
4. Assign output paths. Each candidate writes to its own location (a git worktree where possible, otherwise `/tmp/arena-<slug>/candidate-<n>/`). N candidates writing to the same path is shared mutable state and fails the the **separate-before-serializing-shared-state** principle skill test.

## Phase B: Fan out

Spawn all N subagents at once with `spawn_subagent`, in the background, each with the task, the path to the shared grounding, its own output path, and instructions to produce both the artifact and a short rationale.

The rationale is mandatory. Without it, the parent cannot tell whether a candidate's structure is principled or accidental, which makes Phase E grafting unreliable. Each rationale names the alternatives the candidate considered and what it rejected.

If a candidate fails to produce output, proceed with N-1 and note the dropout in the synthesis record.

## Phase C: Cross-judge

After all Phase B candidates complete (`await_subagents`), choose one model from panel `arena-cross-judge` (see Model panels) unless the caller passes an explicit model. Prefer a different model family from the parent's when the panel offers one. Spawn one read-only judge subagent on that model with `spawn_subagent`. It sees the rubric and the candidates by path label, scores each criterion, and recommends a base with rationale. It runs in parallel with the parent's reading in Phase D, not with the candidates themselves. Spawning while candidates are still writing means the judge sees partial or empty outputs and reports them as dropouts.

## Phase D: Pick a base

Read every candidate end to end before picking. Skimming N candidates surfaces only the candidate whose surface looks most familiar.

Score each candidate against the rubric criterion by criterion, not on holistic feel. Compare against the cross-judge. Agreement on the base confirms the pick. Disagreement means one of you is biased or the rubric was ambiguous. Read both rationales before deciding.

Pick the base on which candidate a future maintainer can extend most easily without breaking invariants. Prefer the cleaner boundary or smaller surface area when two feel tied, per the Laziness Protocol.

Record the pick and the reason in a short synthesis note alongside the base artifact, including the cross-judge's verdict.

## Phase E: Graft

Walk each losing candidate once more and identify what is worth porting into the base. The signal is usually one or two things per candidate, not most of it.

Fold each graft in by hand, per the **redesign-from-first-principles** principle skill. Don't paste mechanically. The result has to remain coherent under one mental model.

Record what was grafted, from which candidate, and what was rejected and why. The rejection notes are the highest-signal part of the record. Future readers learn from what you considered and dropped, not just what you kept.

When N candidates converge on the same shape, that is a strong agreement signal. Note the convergence in the record and ship the consensus shape. No graft is needed. When N candidates wildly diverge, Phase A was under-specified. Reframe and re-run rather than averaging the divergence.

## Phase F: Verify

The synthesized artifact has to hold up under the same scrutiny as any other output, per the **prove-it-works** principle skill. The arena does not earn you a pass.

If verification surfaces a problem the arena did not catch, either Phase A was wrong (re-frame and re-run) or one candidate caught it and you missed the graft (go back to Phase E). Don't paper over.

## Outputs

One synthesized artifact. One short synthesis note alongside, naming the base, the grafts (with source candidate), the rejections, the dropouts if any, and the verification result.

## Tools

This skill names harness-neutral tool verbs (SCHEMA.md, "Tool references in skills"). Harness notes below give each harness's real tool.

- `spawn_subagent`. Start a fresh subagent from a standalone brief, with the role, model and access the step names.
- `await_subagents`. Collect spawned subagents' results as each finishes.

## Model panels

Model choices in this skill are named panels, never vendors: `arena-runners`, `arena-cross-judge`. A panel is one model or an ordered list of models; a list means one subagent per entry. Resolve each panel from the harness's model configuration (see Harness notes). An entry of `inherit-parent` or `auto` runs on the parent session model. If a panel is not configured, ask the user once which models to use; if they defer, run every slot on the parent session model as independent subagents and say the panel was single-model. Mixing model families is optional diversity, never a requirement. When this skill runs inside Stitch delivery, the delivery model rules (no Anthropic models, role bindings from the active profile) override any panel.

## Harness notes: cursor

Panels come from `~/.cursor/rules/pstack-models.mdc` when present: `arena-runners` is the `arena runners` line; `arena-cross-judge` is the `arena cross-judge pool` line. For `inherit-parent` or `auto`, omit the Task `model`.

Tools: `spawn_subagent` is the `Task` tool with `subagent_type: generalPurpose` (general-purpose) and `model` from the panel entry (omit it for `inherit-parent` or `auto`). Background is `run_in_background: true`; the judge's read-only access is `readonly: true`. Put parallel spawns in one message as several `Task` calls. A foreground `Task` returns its result; background (`run_in_background: true`) results arrive as completion notifications. Either is `await_subagents`.

## Harness notes: codex

Codex has no panel configuration yet (`panels:` in profiles is reserved and not exported), so use the unconfigured-panel rule above.

Tools: `spawn_subagent` is `spawn_agent` with `agent_type: "default"` (general-purpose), `fork_turns: "none"`, a short `task_name`, the brief in `message`, and `model` plus `reasoning_effort` from the panel entry (omit both for `inherit-parent` or `auto`). Spawned agents run concurrently, which covers background. `spawn_agent` has no read-only flag, so put the read-only access in the brief ("do not edit files"). Issue parallel spawns back to back, then call `wait_agent` (with a `timeout_ms`) until every spawned agent has reported; `list_agents` shows status. That is `await_subagents`.
