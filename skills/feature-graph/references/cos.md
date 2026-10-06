# Feature graph

Version 5 delivery instructions for the run's dedicated CoS only. Main is the user-facing supervisor. CoS owns this run's graph, assignments, checks and repair routing, and sends decisions/results to Main. Do not spawn another coordinator or load Firstmate. Do not edit implementation, write tests, execute combined checks or run Debug yourself; assign the established owner or executor.

The graph for each candidate is acyclic. A repair creates a new numbered generation and preserves prior evidence. Reopen affected dependencies; an explicitly verified tests-only repair may retain the implementation. Capture directly requires both current test and valid implementation seals.

```text
Approved spec + exact baseline
  -> prepare
  -> [tests -> seal_tests] + [plan -> implement -> seal_implementation]
  -> capture after both author branches finish
  -> checks + verification + regression + Arc + Styla
  -> reconcile after checks and all four reviews pass
  -> publish draft -> exact-head CI
  -> handoff -> closeout
```

The diagram shows the `draft` endpoint. At the `local` endpoint, reconciliation leads directly to handoff and closeout; publication and CI remain unperformed. Read the current endpoint from `status` before dispatch.

## Start with a frozen contract

Read the standing instructions and DELIVERY-CHECKLIST.md; load relevant incident details as needed. Confirm actual implementation authority, repository, frozen spec revision, exact baseline SHA, and the approved delivery endpoint.
The spec must cover observable behavior and failures, acceptance examples, non-goals, disjoint file ownership, public interfaces, agreed architecture and verification.
Discuss meaningful architecture choices before freeze. Trace the real caller or user flow, including fallback paths. Verify discoverable facts before asking questions. No unresolved assumption about behavior, scope, ownership, interfaces, architecture, failure handling, acceptance or test expectations may drive dependent work. Clarify missing decisions with Jarushan and record his answer before dispatch. Silence, elapsed time, a recommendation or approval to implement is not permission to invent requirements. Existing explicit decisions remain valid; do not ask again. Pause affected work if ambiguity emerges later.
Linear remains the source of truth for Stitch specs and branch names. A pinned local export is a run input, not a competing editable spec.

Do not change frozen scope, files, interfaces, acceptance criteria or test expectations without Jarushan's explicit consent. Route proposed changes through Main, update the source spec after approval, pin the revision and reconcile affected assignments before continuing. Preserve existing approval for in-scope factual repairs.

Every version 5 candidate requires verification, regression review, Arc and Styla. Scale their inspection to the actual change; none is optional. Preserve their independent lenses and existing model pins.

Freeze the smallest complete user path that is useful to review. Agree the per-slice elapsed work budget, the bounded checkpoint for collecting review findings, and a verification plan before authoring. Include all previous work on the slice in its starting time. Use no global minute limit or repair-count cap. Name the earliest meaningful proof for each risky boundary. Do not add two universal handoffs when they cannot produce useful evidence. A larger feature may need multiple approved complete slices; CoS cannot split or shrink frozen scope without consent.
For draft-authorized runs, target roughly 30 minutes from the frozen spec to creation of the draft PR. Record the freeze and first publication timestamps in the existing ledger, with work and waits separately visible. Required local checks and all four reviews precede publication; CI completion is a later milestone. Assess known check and setup costs at freeze, and report likely target misses as soon as they become clear, with the exact blocker and bounded next action. The target does not waive correctness or replace the explicitly approved per-slice execution budget. Do not silently extend a run into hours.
List required local and CI checks explicitly. Do not weaken the list because a check is unavailable or fails.

Read [references/guard.md](guard.md) to initialize the run and operate the guard.
Keep `run.json`, approval evidence, receipts, patches and logs in a durable private task directory outside product source.
Use the guard before dispatching every graph node. A rejected transition means stop that dependent action and resolve the missing prerequisite.
Only CoS writes the graph state. Workers return artifacts and evidence to CoS.

## Prepare and prove early

Git prepares the isolated worktree. The executor checks the actual toolchain, dependencies, generated prerequisites, runner discovery and relevant baseline path. Reuse preparation while baseline, toolchain/lockfile, generated inputs and mutable-output ownership remain valid; repair only invalidated prerequisites.

Start the test writer with the smallest representative proof for each uncertain behavior. For a regression it must fail behaviorally on the exact buggy source. For parity/extraction it proves real baseline controls and data. For a genuinely absent feature, use the approved deferred-proof rule and require the first runnable combined proof before dependent expansion. The implementer submits its plan and smallest runnable owned checkpoint before expanding work that relies on a risky integration.

CoS checks proof against the frozen criterion, then releases dependent expansion under existing authority. Reuse the same proof across files sharing that boundary until relevant inputs change. A small artifact may already be complete at its first proof. Do not require a checkpoint exchange per test file or add another review role. Pause both authors for combined checks, assign an executor and return only permitted facts. Run cheap compiler/lint checks early on allowed inputs.

Use `graph.py receipt` for the existing schema. The executor uses `run_check.py` to save complete logs and bounded observed metadata. One owner executes each required command. A busy slot is a persisted resource wait, not a failed check. Register before trying the lock, recheck after receiving a busy result and reconcile on every resume. The native executor verifies process/session completion and descendants before releasing the shared slot. Resource waits consume internal elapsed budget. Do not create waiter processes or polling loops.

## Parallel authors in one worktree

Use one isolated Git worktree for the feature, shared by the test-writer and implementer through authoring, checks and publication. Git prepares it once and assigns disjoint exact file ownership, including one owner for every shared configuration or generated input. Never use the user's active checkout. Existing work in separate worktrees must be preserved rather than reset or discarded.

After preparation, start the test-writer and the implementer's planning turn in parallel. CoS checks and routes the implementation plan through Main before coding starts. Tests do not need to finish before implementation. Both begin with fresh contexts, the same frozen spec and pinned original baseline. The spec is the sole source of task requirements; existing baseline code, tests, interfaces and repository rules are permitted technical context.

Authors must not inspect each other's newly authored files, plans, messages, reasoning, reports or verdicts, including during repairs. Scope searches and reads to their own files and necessary baseline material. Read pre-existing code from the pinned baseline when its working file belongs to the other author; never read the other author's current edits. Do not pass peer output through compiler diagnostics, test failures or checkpoint reports. CoS owns any combined execution that would expose peer changes and supplies only sanitized facts tied to the frozen criterion.

A shared filesystem does not enforce read isolation. Apply real path restrictions where the harness supports them, and otherwise report the limit honestly. If accidental exposure occurs, pause that author, preserve its files, and tell CoS what was read before claiming an independent result. Fresh prompts and disjoint writes reduce bias; they do not prove it is absent.

- Test-writer owns tests and test-only helpers. Assert observable behavior through real interfaces. Prove submitted bug regressions on a fixed snapshot of the original buggy code plus the writer's tests, never the implementation being edited. A temporary baseline execution copy is permitted when needed; it is not a second Git worktree or author-to-integration replay.
- Implementer owns service files. Before coding, return the concrete plan to CoS. CoS checks it against the frozen architecture and sends it to Main for user delivery. A matching plan proceeds under existing approval. Material changes require an amended freeze.
- Both return an ordered series of small, immutable checkpoints for their own changed, deleted and new paths, with predecessors, messages, dependencies and check results. Sealing one author's artifact may overlap the other author's work because the seal inspects only its owner's stopped files. Do not collapse the feature into one final snapshot.

Run author checks only on permitted inputs. CoS and the independent verifier run combined checks after both authors stop. Never reset, switch, stash, commit or run worktree-wide formatting while either author is writing. Git commits declared checkpoints in place after CoS pauses both authors; normal hooks may affect the whole worktree, so disjoint paths alone do not make concurrent Git operations safe.

During repairs, retain only the author's own context and approved work. CoS supplies the violated frozen criterion, concrete inputs, expected/observed output and a sanitized reproduction. Strip peer file excerpts, implementation-shaped fixes and peer outcomes from logs. Both authors may repair in parallel when their file ownership and interfaces remain disjoint and frozen. If a diagnosis needs a major contract change or relaxed independence, return that specific decision to the user. Any frozen-scope amendment follows the approved revision procedure above.

## Debugging failures and stopping repair loops

Subagents may run [Debug from first principles](../../debug-from-first-principles/SKILL.md) for bugs or failed tests/checks within their role and permitted artifacts, without another skill assignment. In the canonical pack, read `../debug-from-first-principles/BODY.md`. Authors may diagnose local failures. CoS assigns an independent verifier to lead repair-loop debugging and investigations requiring the combined candidate. CoS coordinates the stop, assignments, evidence and repair routing; it must not run the skill, trace failure paths or execute diagnostic probes itself. Follow its delivery failure protocol: when repairs recur or uncover successive unexplained failures, stop implementation and test patching across the affected slice, preserve the failing artifact, and concentrate the team on tracing and executing the real paths. Resume only the diagnosed correction first; resume feature work after the affected path and meaningful checks pass.

Before dispatching any repair to a failing test or test-only helper, including the first local failure, require the Debug skill's implementation-first evidence and independent verifier confirmation that the failure is a test/harness fault. Record the source-bound finding and bounded correction in the existing ledger. Implementation, mixed or unknown causes keep test repairs paused. Authors retain their read/write boundaries; CoS routes combined-candidate diagnosis to the verifier and sends only sanitized factual repair inputs to authors.

Include this permission, test-repair evidence requirement and stop rule in author, reviewer and repair handoffs, including resumed older runs. Keep role ownership, permitted artifacts, independent reviews, budgets and source-bound evidence intact. Only CoS assigns diagnostic workers; the verifier conducts the investigation and returns causal evidence, affected paths, a bounded correction and resume checks; this skill does not allow subagents to spawn peers, edit another role's files or inspect forbidden peer work. Required checks and reviews still apply after the repair. No new workflow stage or user-approval gate is introduced.

## Early evidence without extra author handoffs

For a bug, the test-writer must prove a representative regression fails on the exact buggy baseline because the behavior is wrong. A missing import, missing new API or broken harness is not that proof. Complete this evidence before expanding tests or sealing the artifact.

For a feature whose new boundary does not exist yet, exercise the available baseline harness and contracts first. The approved verification plan must identify what cannot run, why, and the mandatory combined-candidate proof at verification. Record the limitation explicitly. Never manufacture product stubs or relax the tests to claim an early pass. If the unavailable boundary was not covered by the approved plan, clarify before proceeding.

Choose additional early probes only when the risk justifies them. Authors stay independent and never inspect each other's new work. CoS may run an approved verification probe against a sealed combined checkpoint without exposing peer work to either author. Probes that investigate a failure belong to the assigned verifier under the debugging rules above. Preserve complete files and actual exit statuses. Early checks supplement the final criterion-by-criterion audit; they do not replace it.

## Capture, check and review

Git owns Git operations and normal commit hooks. CoS owns environment preparation and dependency/executable/build setup. Verify tools actually execute; module resolution alone is insufficient. Stop on authentication failures such as pnpm 401.
Pause every writer while Git operates on its worktree. Preserve checkpoint boundaries and source-to-integrated mappings. Verify all artifacts, including deletions and untracked files, before capture.
`capture` records a complete source identity. Finish formatting and source copying before checks. No reviewed source may change until that candidate is accepted or a repair generation starts.

For the first candidate, start required checks and all four fresh independent reviews in parallel after capture. After repairs, use the evidence-reuse rules below to retain unaffected coverage and dispatch affected reviews against the new immutable candidate. Reviewers can trace code and audit criteria while commands run; they need not wait for the checks node. Run the existing verification skill for the changed user flow. CoS assigns command ownership and coordinates execution in the frozen shared worktree. Overlap commands only when resources and generated outputs do not conflict; serialize heavyweight suites and commands sharing mutable outputs. The verifier still independently executes its required evidence. Preserve actual exit statuses and full logs. Keep generated output outside captured source; use scratch execution only when a command cannot preserve it.

Reconciliation explicitly requires both the checks node and all four reviews to pass. A review PASS cannot compensate for failed or unfinished checks. Every review remains bound to the same candidate:

- `slice_spec_audit`, the `verification` node: reconstruct the feature from the frozen contract and existing interfaces. Trace actual entry points, control/data flow, state owners, side effects, failures and lifecycle paths. Audit implementation and tests against every criterion, challenge whether tests detect missing or wrong behavior, and independently execute the approved evidence against the frozen candidate under the shared execution schedule. Include all deferred runtime proof. Author-reported green is insufficient. This is the renamed acceptance stage, not another serial gate.
- `researcher`: regressions, affected callers, invariants and code quality.
- `csa`, always: architecture, ownership, contracts, dependencies and fail-closed behavior. Check that the chosen structure fits established boundaries without speculative layers.
- `styla`, always: naming, responsibility, structure and idiom, including oversized tests or classes. Read adjacent code; reject unnecessary wrappers, generic scaffolding and mixed responsibilities. Separate concrete rule violations from preferences.

Reviewers may inspect the combined candidate. They do not see peer reports, arguments or even PASS/FAIL outcomes. Save each report before retirement.
Each finding identifies location, violated criterion or invariant, consequence, and reproduction or decisive code evidence. Separate blocking defects from preferences. Unavailable required evidence is BLOCKED.
CoS reconciles facts. Resolve unsupported findings with evidence and have that reviewer re-evaluate its own finding through a review retry. Do not manufacture a passing receipt or waive a proven acceptance failure.
As soon as a reviewer substantiates a blocker, it saves the decisive evidence and notifies CoS through the existing worker messaging path, before starting another expensive check. Include candidate identity, violated criterion, consequence and evidence path. Do not wait for the final audit or verdict. The reviewer may continue useful inexpensive inspection while waiting for CoS's collection checkpoint; an unproven suspicion is not a blocker.

CoS acknowledges the first notice, records discovery and notification times, and starts the approved collection period from receipt of that notice. Give the other reviewers the checkpoint deadline without exposing peer reasoning or verdicts. Stop new redundant expensive execution, collect each reviewer's findings and unfinished coverage, then confirm actual workers have stopped before routing a repair. Record acknowledgement and stop times. An interrupted reviewer returns BLOCKED with remaining coverage, never PASS. All four reviews and unfinished coverage remain required on the repaired candidate. Use the existing supervisor and messaging path; do not add a scheduler or another review stage.

The verifier recommends the owning step for each failed criterion: tests, implementation, both, plan, environment/checks, review evidence, or spec. CoS validates the finding and dispatches the correction. Reviewers never mutate the graph or instruct authors. Spec uncertainty returns to Jarushan before dependent work resumes. Apply the debugging stop above before another repair when failures recur or shift without a causal explanation. Use a stable cause identifier and immutable evidence; this also applies to existing runs without changing their saved graph version. Factual in-scope repairs continue under existing authority while the approved budget remains; do not ask for permission merely because a repair is needed.

For a tests-only repair, first obtain the verifier's causal evidence excluding implementation as the source of the observed failure; unchanged implementation bytes alone are insufficient. CoS then proves the plan, implementation artifact, interfaces and permitted inputs remain valid, then uses `--preserve-implementation` with that evidence. This retains the valid source stages and reopens tests, their seal, capture, checks and all reviews. Capture rejects any non-test file change. For both authors, use the ordinary `tests` repair; for service-only work use `implement`, or `plan` if its agreed approach needs revision within freeze. Keep the authors blind in every path.

Budget exhaustion requires a status report and an approved extension or revised scope. Record the exact cause, attempted fixes, evidence and bounded next action. Never reset the clock by resuming, replacing an agent, opening a new run or renaming a repeated cause. Do not turn style preferences into repeated blocking repairs; only agreed requirements and established rules block.
Source changes reopen capture, required repository checks and the four review nodes. After recapture, CoS records the exact delta, affected criteria/callers/contracts/configuration/dependencies/invariants, coverage to rerun and why retained evidence remains valid. Unchanged files alone are insufficient. Use the guard's `review-plan` command with [the reuse contract](review-reuse.md); never edit a prior receipt or mark a node passed manually.

CoS approves carrying unaffected reviews forward; original reviewers need not reconfirm. The guard creates a new receipt linking the prior immutable evidence to the current candidate. For affected reviews, retain only completed valid coverage and dispatch a focused review of the repair, affected criteria and all unfinished coverage. That reviewer receives its own earlier evidence and permitted artifacts, never peer reasoning or verdicts. A failed or interrupted review cannot be retained wholesale. The focused result must resolve prior findings and complete all assigned work before it passes.

Retained verification checks must have pinned successful execution and unchanged inputs; affected independent checks rerun. Required repository checks and exact-head CI cannot be retained across source changes by this mechanism. Shared contract, ownership or dependency changes reopen every affected lens. If impact or input identity is uncertain, omit the reuse plan and run the full review. A reviewer discovering wider impact returns BLOCKED with the gap; CoS retries the node with broader coverage or a full review. An evidence-only retry may retain independent sibling reviews on the identical candidate.

## Publish and finish

Only after required checks, all four reviews and reconciliation pass may Git sign and publish the ordered series. Read the standing publication guidance.
Preserve the user's authorship, GPG signing on their machine, exact Linear branch, draft status and no-reviewer rule. Verify every signature, checkpoint mapping, and final content identity. Never add agent trailers.
CoS supplies the bounded operational Git assignment, title and description. Authors never publish. A disconnected laptop leaves a durable unsigned queue; no custom retry daemon.
Changes from rebasing or restacking require a new candidate and affected checks. A same-content head change still reopens publication and exact-head CI. Published history rewrites need their own existing or explicit authority.
Wait for every required CI check on the exact published SHA. Send Main the draft URL, source identity, checks and remaining decisions promptly. Main actually delivers the result to Jarushan, then records the candidate-bound notification acknowledgement. Do not mark user_notified, handoff or closeout from an internal message alone; preserve pending delivery on resume. A green draft is ready for user review, not ready-marked, merged, landed, deployed or Done.
The guard does not grant publication or merge authority. Set the delivery endpoint to `local` when the user wants implementation, checks and reviews without publication, or `draft` when a draft PR and CI are authorized. Local runs complete handoff and closeout after reconciliation, with publication and CI recorded as unperformed.
Honor later user steering through the guard's `endpoint` command, using the existing instruction as approval evidence without asking again. Preserve valid author, check and review evidence. Changing the endpoint reopens handoff and closeout; selecting `draft` requires any outstanding publication and exact-head CI before handoff. It does not undo an existing publication or authorize a history rewrite. If workers are running, retain the steering in the task ledger, stop scheduling publication, and apply the command once workers have stopped.
After every run reaches its authorized delivery point, CoS sends Main a short retrospective for Jarushan as part of the existing closeout. Cover the outcome, measured work and waiting time, repair causes, useful review findings, and what to keep or refine next time. Also give this retrospective when a run is deliberately stopped as blocked or abandoned, without marking unfinished gates as passed. Unknown measurements remain unknown.
Record failures and recurrences in the existing lessons register, distinguishing missing guidance from guidance that was not followed. Update the linked DELIVERY-CHECKLIST.md prevention check when current guidance changes. If no new lesson emerged, say so without inventing one. Refine the owning workflow or role from observed evidence within existing authority; the retrospective does not authorize changing frozen specs, model pins or publication boundaries. Synchronize canonical source, complete backup and affected installed copies after a refinement. CoS performs the retrospective without another agent or review gate.

## Native lifecycle

Use Main's run allocation and shared command lock. Persist graph reservations before native launch, bind the returned handle immediately, and never repeat an ambiguous launch until reconciled. Keep existing agents for related repairs and preserve author blindness. On resume inspect the guard, actual worker status, saved results, resource waits and Git refs. Unknown liveness is a blocker for affected dispatch; a timeout is not permission for a replacement.

Before replacing CoS, Main establishes old coordinator, workers and commands have stopped, including descendants, records their final results and the replacement evidence, and changes the recorded CoS through the guard. Neither old nor replacement CoS may dispatch across that transition. Main's exception is whole-run cleanup, not implementation assignment. No daemon or separate task ledger is added.

Record phase times, command durations, waits, repairs and repeat-check reasons. The per-slice budget includes setup, all author attempts, handoffs, internal waiting, checks, repairs and resumed work. Record user-decision waiting and external CI waiting separately; keep total elapsed time visible. Exclude an external wait only when internal work has stopped, except the CI monitoring reservation. Extensions increase the existing budget and preserve elapsed work. Completed dormant intervals are separate from active work. A new approved spec revision of the same slice must carry the stopped previous run's budget ledger through `budget_previous_run`; do not lose earlier external wait records. Measure all started slices, including blocked, abandoned and resumed work, rather than only successful runs.

The guard checks budget at dispatch/repair boundaries and records wall time. CoS uses the existing supervisor to enforce checkpoints and stop live work at the budget; the guard cannot interrupt a process. Unavailable command or token measurements remain unknown. This is a state guard, not a scheduler, wake source, process monitor, assumption detector or sandbox. Passing evidence supports the reviewed paths; it is not a guarantee that no bug exists.

## Assignments and context

Read named-role model, reasoning and service-tier settings by resolving the role's capability in `~/Developer/agent-definition/agents/<role>/agent.yaml` through the active profile (`~/Developer/agent-definition/profiles/codex.yaml` on Codex; `./adapters/export-codex.sh --check --explain` prints it), then pin those effective definitions in the run record. The canonical role definition owns these values; do not copy model lists into this workflow. An older startup AGENTS.md snapshot or archived workflow list is not a new model decision. Apply any explicit current per-run override from Jarushan; otherwise reconcile the installed role to its canonical definition without asking again per ticket. Preserve the recorded configuration of existing workers. If the configured model is genuinely unavailable, report that exact limitation to Main once; never silently substitute or rewrite unrelated root-session settings.

Independent authors/reviewers start from a standalone brief with no forked parent conversation (see the harness notes below), no peer reasoning and no shared IAI retrieval. Confirm the selected native configuration does not inject peer memory before the pilot and after changes. CoS may consult bounded relevant history; canonical spec, instructions and current evidence remain authoritative. Useful handoffs contain changed facts, identity, outcome, next owner/action and evidence paths. Full logs and old generations stay on disk. Record real native tokens/cost when exposed; missing values are unknown.

## Harness notes: codex

- Independent author/reviewer launches use `spawn_agent` with `fork_turns="none"` and the named configured role.
