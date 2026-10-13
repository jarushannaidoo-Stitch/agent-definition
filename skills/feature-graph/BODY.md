# Feature graph: engineering-team DAG (version 6)

Version 6 applies to new DAG runs. It is an explicitly selected workflow, including `dag` and `impl with dag`; do not add Feature loop or no-mistakes to the same run. Saved runs keep their archived workflow, guard and roles: [v1](references/v1/BODY.md), [v2](references/v2/BODY.md), [v3](references/v3/BODY.md), [v4](references/v4/BODY.md), [v5](references/v5/BODY.md). Do not migrate them.

The team is built for speed: one architect plans, several senior engineers build in parallel, one git role owns every Git mutation, and an independent gate judges the merged result against the frozen spec only.

```text
Frozen Linear spec (tiny, freeze-ready slice) + exact baseline
  -> freeze_check (architect)
  -> plan (architect: work packages, disjoint files, interface contracts, acceptance checks)
  -> setup (git: one fresh worktree per package + one fresh integration worktree)
  -> build (senior engineers in parallel, TDD inside owned files)
  -> integrate (integrator checks; git merges every package worktree into the integration worktree)
  -> gate in parallel: lint + tests + verification + spec_audit + Styla + Arc
  -> csa_final (CSA)
  -> publish (git: one signed, stacked draft PR) -> ci (exact-head CI green)
  -> handoff (architect -> Main -> Jarushan)
  -> cleanup (git: remove every worktree, prune, delete merged branches)
  -> closeout
```

The graph lives in [workflow.json](workflow.json). The run folder and its commands are in [references/dag-runs.md](references/dag-runs.md). The architect's operating instructions are in [references/architect.md](references/architect.md).

## Roles

| Node | Role (pack agent) | Capability | Owns |
|------|-------------------|------------|------|
| freeze_check, plan, bounces, handoff, closeout | `architect` (senior systems architect) | `orchestrator` | The plan, contracts, assignments, routing; the run status file |
| build | `senior-engineer` (one per work package) | `implement` | Tests first, then code, inside its owned files only |
| integrate | `integrator` + `git` | `verify` / `fast_narrow` | Contract compliance of the merged result; git performs the merge |
| setup, merges, commits, rebases, signing, push, draft PR, cleanup | `git` | `fast_narrow` | Every Git mutation in the DAG |
| lint, tests, verification | `verifier` | `verify` | Running required checks and tracing the user path on the merged worktree |
| spec_audit | `slice-spec-audit` | `adversarial_audit` | Blank-slate audit of the merged result against the frozen spec |
| styla | `styla` | `taste` | House style |
| arc | `reviewer` (Arc) | `adversarial_audit` | Architecture lens, side by side with Styla |
| csa_final | `csa` | `adversarial_audit` | Final architecture review after the gate passes |

Every role runs on the active profile's binding: a per-role override in the profile wins over the capability binding; a strict profile with neither fails closed. Never name or substitute a model in a brief.

## Main entry (non-blocking)

1. Confirm implementation authority, the frozen Linear spec revision, exact baseline, branch name from Linear and the stack parent. Return unresolved product decisions to Jarushan. Approval to implement is not approval to invent requirements.
2. One DAG is one tiny, freeze-ready slice. If the freeze is too light (missing behavior, failures, acceptance examples, non-goals, file ownership, interfaces or verification), do not launch; ask Jarushan.
3. Create `runs/<dag-id>/` under the private task directory and launch the `architect` role detached, as a fresh subagent with no forked conversation, in the background. Supply only the frozen spec, repository rules, run folder, Main identity and allocation. Record the returned handle in the run folder.
4. The main chat stays free. Use `dag status` / `dag list` to read state and `dag steer` to send decisions; never assign engineers, read routine logs or edit node state. Several DAGs may run at once from the main loop, each with its own run folder and architect, within actual native capacity.
5. Land one stacked PR (CI green) before starting the next slice of the same feature. Independent features may run as separate DAGs in parallel.
6. When the architect reports handoff, send the outcome to Jarushan promptly. Worker-to-architect and architect-to-Main messages are not user delivery.

## Hard rules

- The architect never grades itself. Gate reviewers judge only against the frozen Linear spec and repository rules, never the architect's plan, contracts or reasoning.
- An engineer that finds the contract wrong bounces to the architect with evidence; it never quietly works around it. The architect fixes the contract (with Jarushan's consent when scope, interfaces or acceptance change) and the plan reopens.
- Gate failures bounce as-is to the owning engineer via the architect. Loops are capped (`loop_cap`, default 3); past the cap the run escalates to HQ/Jarushan.
- No filler dependencies, stub or fake code to pass tests, weakened checks or skipped required checks.
- Only the `git` role mutates Git. Architect, engineers, integrator and reviewers request Git operations from it. Merge conflicts git cannot resolve mechanically bounce to the architect.
- Every DAG ends with cleanup: git removes every engineer worktree and the integration worktree (`git worktree remove`, then `git worktree prune`) and deletes their branches when merged. Never keep or reuse a stale worktree; more work gets fresh worktrees. The run status records cleanup state.
- Signing follows the standing publication rules. While Jarushan's laptop is disconnected the signing/publish job is queued; no retry routines.
- CI green on the exact published head before anything is called done.
- ASCII hyphen only; never em dashes.

## Harness notes: codex

Launch `architect` with `fork_turns="none"`; installed role files carry their profile binding, including per-role overrides. Bindings for unnamed launches are recorded in `~/.codex/agents/.agentpack-resolved`.

## Harness notes: cursor

Resolved role models, including per-role overrides, are recorded in `~/.cursor/skills/.agentpack-resolved` when a Cursor profile is active. Launch the architect as a background subagent and pass the role's resolved model explicitly.

## Harness notes: grokbot

- The senior systems architect runs as a persistent Grok Bot bot with its own memory (orchestrator). Main messages it through agent-to-agent messaging; it reports back the same way.
- The existing `Git` bot (a Grok Bot teammate) is the `git` role and performs every Git operation: worktrees, branches, merges into the integration worktree, signed commits, restacks, pushes, draft PRs and final cleanup. The architect contacts it through agent-to-agent messaging; when Jarushan's laptop is disconnected, Git queues the signing job without retry routines.
- Senior engineers, integrator checks and gate reviewers (lint/tests/verification, spec audit, Styla, Arc, CSA) run as ephemeral cloud agents launched by the architect, each on the model resolved from the profile (role override > capability binding). Do not create a bot per engineer or reviewer.
- Status lives in `runs/<dag-id>/` so the main chat stays non-blocking; Main reads it with `dag status` and steers with `dag steer`.
