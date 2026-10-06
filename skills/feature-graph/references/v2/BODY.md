# Feature graph

Version 2 applies to new runs. For an existing version 1 `run.json`, load [the preserved version 1 workflow](../v1/BODY.md) and its guard reference instead. Do not migrate live runs or replace their assigned role instructions. The current guard can operate both saved versions.

Run one approved, frozen feature through the dependency graph in [workflow.json](workflow.json).
CoS is the sole coordinator and user contact. Authors and reviewers receive bounded assignments, never this whole workflow or the coordinator's conversation.
Use this skill when explicitly selected, including its alias `dag`, as in `impl with dag`. The alias routes to `feature-graph` in Firstmate and direct sessions. Feature loop remains a separate workflow.

The graph for each candidate is acyclic. A repair creates a new numbered generation and preserves prior evidence. Reopen affected dependencies; an explicitly verified tests-only repair may retain the implementation. Capture directly requires both current test and valid implementation seals.

```text
Approved spec + exact baseline
  -> prepare
  -> tests -> seal_tests
  -> plan -> implement -> seal_implementation
  -> capture -> checks
  -> verification + regression + Arc + Styla
  -> reconcile -> publish draft -> exact-head CI
  -> handoff -> closeout
```

The diagram shows the `draft` endpoint. At the `local` endpoint, reconciliation leads directly to handoff and closeout; publication and CI remain unperformed. Read the current endpoint from `status` before dispatch.

## Start with a frozen contract

Read the standing instructions and delivery lessons. Confirm actual implementation authority, repository, frozen spec revision, exact baseline SHA, and the approved delivery endpoint.
The spec must cover observable behavior and failures, acceptance examples, non-goals, disjoint file ownership, public interfaces, agreed architecture and verification.
Discuss meaningful architecture choices before freeze. Trace the real caller or user flow, including fallback paths. Verify discoverable facts before asking questions. No unresolved assumption about behavior, scope, ownership, interfaces, architecture, failure handling, acceptance or test expectations may drive dependent work. Clarify missing decisions with Jarushan and record his answer before dispatch. Silence, elapsed time, a recommendation or approval to implement is not permission to invent requirements. Existing explicit decisions remain valid; do not ask again. Pause affected work if ambiguity emerges later.
Linear remains the source of truth for Stitch specs and branch names. A pinned local export is a run input, not a competing editable spec.

Every version 2 candidate requires verification, regression review, Arc and Styla. Scale their inspection to the actual change; none is optional. Preserve their independent lenses and existing model pins.

Freeze the smallest complete user path that is useful to review. Agree the per-slice elapsed work budget, the bounded checkpoint for collecting review findings, and a verification plan before authoring. Include all previous work on the slice in its starting time. Use no global minute limit or repair-count cap. Name the earliest meaningful proof for each risky boundary. Do not add two universal handoffs when they cannot produce useful evidence. A larger feature may need multiple approved complete slices; CoS cannot split or shrink frozen scope without consent.
For draft-authorized runs, target roughly 30 minutes from the frozen spec to creation of the draft PR. Record the freeze and first publication timestamps in the existing ledger, with work and waits separately visible. Required local checks and all four reviews precede publication; CI completion is a later milestone. Assess known check and setup costs at freeze, and report likely target misses as soon as they become clear, with the exact blocker and bounded next action. The target does not waive correctness or replace the explicitly approved per-slice execution budget. Do not silently extend a run into hours.
List required local and CI checks explicitly. Do not weaken the list because a check is unavailable or fails.

Read [references/guard.md](guard.md) to initialize the run and operate the guard.
Keep `run.json`, approval evidence, receipts, patches and logs in a durable private task directory outside product source.
Use the guard before dispatching every graph node. A rejected transition means stop that dependent action and resolve the missing prerequisite.
Only CoS writes the graph state. Workers return artifacts and evidence to CoS.

## Sequential authors, blind throughout

Run the test-writer to explicit completion, seal its artifact, and verify it has stopped before starting the implementer, including its planning turn.
Never overlap author execution, including repairs. Both begin fresh with the same frozen spec and original baseline. Existing baseline code and tests are permitted.
No HQ history, peer plans, conversations, summaries, verdicts, or newly authored peer files are permitted at any authoring or repair stage.

Keep each author's view at the original baseline plus that author's own approved checkpoints. Preserve separate author views through repairs. A shared integration worktree is fine; do not expose its combined files to authors.
Prefer separate prepared author copies to prevent accidental reads. Reusing one physical author worktree requires first preserving all artifacts and having Git materialize the correct baseline-plus-own-work view. Never reset away unlanded work or alter the user's checkout.
These are permitted-read rules. Ordinary worktrees and this guard do not enforce filesystem access isolation. Use actual sandbox restrictions when available and report their limits honestly.

- Test-writer owns tests and test-only helpers. Assert observable behavior through real interfaces. Prove submitted bug regressions fail on the exact buggy source for the claimed reason, not a harness error. Do not invent product scaffolding or filler dependencies.
- Implementer owns service files. Before coding, return the concrete plan to CoS. CoS checks it against the frozen architecture and shares it with the user. A matching plan proceeds under existing approval. Material changes require an amended freeze.
- Both return an ordered series of small, immutable checkpoints covering changed, deleted and new files, their predecessors, messages, dependencies, and check results. Do not collapse the feature into one final snapshot.

During repairs, retain only the author's own context and work. CoS supplies the violated frozen criterion, concrete inputs, expected/observed output, and a sanitized reproduction. Strip peer file excerpts, implementation-shaped fixes and peer outcomes from logs before handoff.
CoS or the verification reviewer executes combined regressions. Authors run checks against their own permitted views. If a diagnosis cannot proceed without changing the contract or relaxing blindness, return that specific decision to the user.

## Early evidence without extra author handoffs

For a bug, the test-writer must prove a representative regression fails on the exact buggy baseline because the behavior is wrong. A missing import, missing new API or broken harness is not that proof. Complete this evidence before expanding tests or sealing the artifact.

For a feature whose new boundary does not exist yet, exercise the available baseline harness and contracts first. The approved verification plan must identify what cannot run, why, and the mandatory combined-candidate proof at verification. Record the limitation explicitly. Never manufacture product stubs or relax the tests to claim an early pass. If the unavailable boundary was not covered by the approved plan, clarify before proceeding.

Choose additional early probes only when the risk justifies them. Authors stay sequential and blind. CoS may run an approved probe against a sealed combined checkpoint without exposing peer work to either author. Preserve complete files and actual exit statuses. Early checks supplement the final criterion-by-criterion audit; they do not replace it.

## Capture, check and review

Git owns Git operations and normal commit hooks. CoS owns environment preparation and dependency/executable/build setup. Verify tools actually execute; module resolution alone is insufficient. Stop on authentication failures such as pnpm 401.
Pause every writer while Git operates on its worktree. Preserve checkpoint boundaries and source-to-integrated mappings. Verify all artifacts, including deletions and untracked files, before capture.
`capture` records a complete source identity. Finish formatting and source copying before checks. No reviewed source may change until that candidate is accepted or a repair generation starts.

Run the required checks and existing verification skill for the changed user flow. Preserve actual exit statuses and full logs. Serialize heavyweight commands and any commands sharing generated outputs. Parallel review does not require simultaneous CPU-heavy test suites.
Then start fresh independent reviewers on the same immutable candidate:

- `slice_spec_audit`, the `verification` node: reconstruct the feature from the frozen contract and existing interfaces. Trace actual entry points, control/data flow, state owners, side effects, failures and lifecycle paths. Audit implementation and tests against every criterion, challenge whether tests detect missing or wrong behavior, and independently execute the approved evidence in scratch. Include all deferred runtime proof. Author-reported green is insufficient. This is the renamed acceptance stage, not another serial gate.
- `researcher`: regressions, affected callers, invariants and code quality.
- `csa`, always: architecture, ownership, contracts, dependencies and fail-closed behavior. Check that the chosen structure fits established boundaries without speculative layers.
- `styla`, always: naming, responsibility, structure and idiom, including oversized tests or classes. Read adjacent code; reject unnecessary wrappers, generic scaffolding and mixed responsibilities. Separate concrete rule violations from preferences.

Reviewers may inspect the combined candidate. They do not see peer reports, arguments or even PASS/FAIL outcomes. Save each report before retirement.
Each finding identifies location, violated criterion or invariant, consequence, and reproduction or decisive code evidence. Separate blocking defects from preferences. Unavailable required evidence is BLOCKED.
CoS reconciles facts. Resolve unsupported findings with evidence and have that reviewer re-evaluate its own finding through a review retry. Do not manufacture a passing receipt or waive a proven acceptance failure.
As soon as a reviewer substantiates a blocker, it saves the decisive evidence and notifies CoS through the existing worker messaging path, before starting another expensive check. Include candidate identity, violated criterion, consequence and evidence path. Do not wait for the final audit or verdict. The reviewer may continue useful inexpensive inspection while waiting for CoS's collection checkpoint; an unproven suspicion is not a blocker.

CoS acknowledges the first notice, records discovery and notification times, and starts the approved collection period from receipt of that notice. Give the other reviewers the checkpoint deadline without exposing peer reasoning or verdicts. Stop new redundant expensive execution, collect each reviewer's findings and unfinished coverage, then confirm actual workers have stopped before routing a repair. Record acknowledgement and stop times. An interrupted reviewer returns BLOCKED with remaining coverage, never PASS. All four reviews and unfinished coverage remain required on the repaired candidate. Use the existing supervisor and messaging path; do not add a scheduler or another review stage.

The verifier recommends the owning step for each failed criterion: tests, implementation, both, plan, environment/checks, review evidence, or spec. CoS validates the finding and dispatches the correction. Reviewers never mutate the graph or instruct authors. Spec uncertainty returns to Jarushan before dependent work resumes. Diagnose the root cause before repairing a recurrence, using a stable cause identifier and immutable evidence. Factual in-scope repairs continue under existing authority while the approved budget remains; do not ask for permission merely because a repair is needed.

For a tests-only repair, CoS proves the plan, implementation artifact, interfaces and permitted inputs remain valid, then uses `--preserve-implementation` with that evidence. This retains the valid source stages and reopens tests, their seal, capture, checks and all reviews. Capture rejects any non-test file change. For both authors, use the ordinary `tests` repair; for service-only work use `implement`, or `plan` if its agreed approach needs revision within freeze. Keep the authors blind in every path.

Budget exhaustion requires a status report and an approved extension or revised scope. Record the exact cause, attempted fixes, evidence and bounded next action. Never reset the clock by resuming, replacing an agent, opening a new run or renaming a repeated cause. Do not turn style preferences into repeated blocking repairs; only agreed requirements and established rules block.
Source changes reopen capture, all checks and reviews. An evidence-only retry can preserve independent sibling reviews on the identical candidate; record why their inputs and invariants remain unchanged.

## Publish and finish

Only after all required reviews and reconciliation pass may Git sign and publish the ordered series. Read the standing publication guidance.
Preserve the user's authorship, GPG signing on their machine, exact Linear branch, draft status and no-reviewer rule. Verify every signature, checkpoint mapping, and final content identity. Never add agent trailers.
CoS supplies the bounded operational Git assignment, title and description. Authors never publish. A disconnected laptop leaves a durable unsigned queue; no custom retry daemon.
Changes from rebasing or restacking require a new candidate and affected checks. A same-content head change still reopens publication and exact-head CI. Published history rewrites need their own existing or explicit authority.
Wait for every required CI check on the exact published SHA. Report the draft URL, source identity, checks and remaining decisions promptly. A green draft is ready for user review, not ready-marked, merged, landed, deployed or Done.
The guard does not grant publication or merge authority. Set the delivery endpoint to `local` when the user wants implementation, checks and reviews without publication, or `draft` when a draft PR and CI are authorized. Local runs complete handoff and closeout after reconciliation, with publication and CI recorded as unperformed.
Honor later user steering through the guard's `endpoint` command, using the existing instruction as approval evidence without asking again. Preserve valid author, check and review evidence. Changing the endpoint reopens handoff and closeout; selecting `draft` requires any outstanding publication and exact-head CI before handoff. It does not undo an existing publication or authorize a history rewrite. If workers are running, retain the steering in the task ledger, stop scheduling publication, and apply the command once workers have stopped.
After every run reaches its authorized delivery point, CoS delivers a short retrospective to Jarushan as part of the existing closeout. Cover the outcome, measured work and waiting time, repair causes, useful review findings, and what to keep or refine next time. Also give this retrospective when a run is deliberately stopped as blocked or abandoned, without marking unfinished gates as passed. Unknown measurements remain unknown.
Record failures and recurrences in the existing lessons register, distinguishing missing guidance from guidance that was not followed. If no new lesson emerged, say so without inventing one. Refine the owning workflow or role from observed evidence within existing authority; the retrospective does not authorize changing frozen specs, model pins or publication boundaries. Synchronize canonical source, complete backup and affected installed copies after a refinement. CoS performs the retrospective without another agent or review gate.

## Firstmate and direct sessions

Firstmate remains the supervisor and CoS. The graph state owns delivery dependencies; Firstmate's existing records own worker lifecycle and fleet status. Record worker/task IDs in the graph and refer to the same run path from the task brief. Never create a second coordinator or scheduler for the same slice.
CoS ownership means responsibility for the decision and receipt, not permission to mutate a project directly. Under Firstmate, delegate environment preparation and combined check execution to a registered worker with a bounded operational assignment. Use the existing verifier role for focused execution when needed, with its current pin, rather than exposing combined files to an author. This worker is an executor, not another coordinator or review gate. Firstmate may run the private state guard itself; all project mutations follow its existing delegation rules.
An explicit user selection of Feature graph selects its authors and review stages for that task. Do not also start Feature loop or no-mistakes over the same delivery. If a mandatory repository gate conflicts with this selection, identify the conflict before dispatch; do not silently disable a required gate.
This skill adds no Firstmate backend or delivery-mode enum. Do not pass `feature-graph` as an unsupported `fm-spawn` mode. Read current Firstmate harness/spawn guidance, use its supported supervision tools, and give each worker only its node assignment. Preserve Firstmate's lock, backlog, isolation, wake acknowledgement and merge-authority requirements.
Outside Firstmate, the current agent is CoS and uses the available agent tools with the same graph state and role boundaries.

On resume, inspect `status`, actual workers, saved results, Git refs and any existing PR before launching anything. A `running` entry is a dispatch reservation, not proof that its worker is alive. Reuse the stable dispatch ID. If a crash occurred between reservation and launch, reconcile before launching once. Never turn a timeout into another worker or another PR automatically.
Record phase times, command durations, waits, repairs and repeat-check reasons. The per-slice budget includes setup, all author attempts, handoffs, internal waiting, checks, repairs and resumed work. Record user-decision waiting and external CI waiting separately; keep total elapsed time visible. Exclude an external wait only when internal work has stopped, except the CI monitoring reservation. Extensions increase the existing budget and preserve elapsed work. Completed dormant intervals are separate from active work. A new approved spec revision of the same slice must carry the stopped previous run's budget ledger through `budget_previous_run`; do not lose earlier external wait records. Measure all started slices, including blocked, abandoned and resumed work, rather than only successful runs.

The guard checks budget at dispatch/repair boundaries and records wall time. CoS uses the existing supervisor to enforce checkpoints and stop live work at the budget; the guard cannot interrupt a process. Unavailable command or token measurements remain unknown. This is a state guard, not a scheduler, wake source, process monitor, assumption detector or sandbox. Passing evidence supports the reviewed paths; it is not a guarantee that no bug exists.

## Harness notes

Use existing role definitions and their current pins. Current pins are CoS/architect/csa/slice_spec_audit/researcher/reviewer/verifier on `gpt-6-astra` at `xhigh`, Styla on Astra at `medium`, test_writer/implementer on `gpt-5.6-sol` at `medium`, and Git on `gpt-5.6-luna` at `xhigh`.
Never silently remap an unavailable model or use Anthropic/Claude. Pins apply to followups and retries.
For Codex native delegation, use `fork_turns="none"` and the named configured roles. Firstmate launches must follow its current supported harness adapter instead of bypassing its worker registry.
Give each author the explicit Feature graph blind-repair contract. Their Feature loop permission to inspect integrated peer artifacts does not apply here.
Only CoS loads this skill; other agents receive their own role, frozen spec, repository rules and permitted artifacts.
