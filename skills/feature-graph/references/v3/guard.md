# Operating the version 3 dependency guard

New runs use version 3. Existing version 1 and 2 states continue through the same script with [version 1 rules](../v1/guard.md) or [version 2 rules](../v2/guard.md). Do not reinitialize or migrate an active run. The current guard selects archived workflow bytes from the saved state version; old author sequencing and review prerequisites remain intact.

Requires Python 3.9+, Git, and macOS or Linux. No Python packages, LangGraph, service or network are needed.
Run the script relative to the loaded skill directory. Use absolute paths for all run inputs and evidence.
The command checks recorded prerequisites and content identities. CoS still verifies real approval, stopped workers, honest evidence, author blindness and publication results. A process with write access can bypass or edit this local state; it is not a security boundary.

## Initialize once

Create a durable private task directory outside the product worktree, including author-private evidence directories. Store the exact approved spec export and a record of the user's approval there.
Write `contract.json` with these fields, replacing the illustrative values:

```json
{
  "repo": "/absolute/path/to/shared-feature-worktree",
  "baseline": "0123456789012345678901234567890123456789",
  "branch": "exact-approved-linear-branch",
  "spec": "/absolute/private/task/frozen-spec.md",
  "approval": "/absolute/private/task/approval.md",
  "endpoint": "local",
  "checks": ["tests", "lint", "types"],
  "ci_checks": ["required-workflow-job"],
  "arc": {"required": true, "reason": "Mandatory architecture review"},
  "styla": {"required": true, "reason": "Mandatory house-style review"},
  "test_paths": ["src/example/__tests__/behavior.test.ts"],
  "verification_plan": "/absolute/private/task/verification-plan.json",
  "budget_seconds": 7200,
  "budget_started_at": "2026-09-22T08:00:00+00:00",
  "review_checkpoint_seconds": 120
}
```

```sh
python3 /path/to/feature-graph/scripts/graph.py init /private/task/run.json --contract /private/task/contract.json
python3 /path/to/feature-graph/scripts/graph.py status /private/task/run.json
```

The guard validates the baseline commit and pins the spec, approval, verification plan and workflow bytes. All four reviews are mandatory. Budget values above are examples, not defaults or recommendations; record the values actually approved for this slice. `test_paths` is the complete approved list of exact test/test-helper paths, including new files. It is used to detect source changes when preserving implementation during tests-only repair. It refuses to overwrite an existing run. A changed approved spec requires a new run with new approval evidence; preserve the old run and work, and reconcile existing workers first.
`status` lists eligible nodes and recorded worker IDs. Exit code 2 means invalid input or stale state/evidence. Read the diagnostic; do not bypass it by editing `run.json`.

## Pin the evidence plan

The approved `verification-plan.json` names the complete criterion IDs, commands the verifier must execute, and the early/final evidence approach:

```json
{
  "kind": "feature",
  "criteria": ["AC-1", "AC-2"],
  "checks": ["behavior", "lifecycle"],
  "defer_new_boundary": true,
  "early_proof": "Execute available baseline contracts; new host entry is absent",
  "final_proof": "Drive both host entry and standalone lifecycle on the combined candidate"
}
```

Use `kind: "bug"` with `defer_new_boundary: false` for bug regressions. Prove the behavioral failure on the exact buggy baseline before sealing tests. For a feature, any deferred boundary must have explicit prior approval and be completed at verification. The guard pins this plan and checks required evidence fields. CoS and the independent verifier judge whether the evidence actually proves the behavior.

## Budget and waits

`budget_started_at` includes the slice's actual prior setup and author work. `budget_seconds` limits elapsed internal work across every attempt and repair. Separately, draft-authorized runs target roughly 30 minutes from freeze to first draft creation; record both timestamps in the existing ledger. Local checks and all four reviews must pass before that draft, while CI completion follows publication. The planning target does not authorize skipped gates or automatic budget extensions. `review_checkpoint_seconds` is the approved maximum interval for CoS to gather findings and remaining coverage after a reviewer reports a blocker. CoS enforces live checkpoints through the existing supervisor. There is no new timer service or worker-killing mechanism.

The `budget` and `wait` commands validate the frozen run inputs, approvals and existing budget ledger without requiring passing delivery reports to remain valid. An overwritten or missing stage report therefore cannot deadlock an approved extension or stopped external wait. These commands do not clear a blocker, reset a node or allow stale evidence to release delivery. Repair the owning node before dispatch or PASS can proceed.

The guard blocks new dispatch and repair after the budget is exhausted. It still accepts completed results so stopped workers and evidence can be recorded honestly. Ask for the specific missing decision or extension, and keep unrelated authorized work separate. An extension preserves elapsed time:

```sh
python3 /path/to/feature-graph/scripts/graph.py budget /private/task/run.json --seconds 9000 --approval /private/task/budget-extension.md
```

Record user-decision and external CI waits separately. Internal handoffs, tool setup, repairs, crashes and resume gaps continue to count. Do not label them as external waits. CoS must confirm internal workers have stopped, except a CI monitoring reservation may remain during an external CI wait.

```sh
python3 /path/to/feature-graph/scripts/graph.py wait /private/task/run.json user --evidence /private/task/pending-decision.md
python3 /path/to/feature-graph/scripts/graph.py wait /private/task/run.json end
```

Use `external_ci` instead of `user` only after publication. Waits cannot overlap. `status.timing` includes total elapsed, elapsed internal work, both external-wait totals and remaining budget. It stops accumulating at completed closeout. Reopening the run records the dormant interval separately as `inactive_seconds`, so it does not consume work budget. For a new approved spec revision of the same slice, pin an immutable copy of the stopped previous state with `budget_previous_run` in the new contract and retain its original `budget_started_at`. This carries previous work, external waits and extensions forward. Budget extensions require recorded user approval. Do not restart a run to reset its budget; carry prior effort into a genuinely new approved run.

## Choose or change the delivery endpoint

`local` finishes after checks, reviews, reconciliation, handoff and closeout. `publish` and `ci` cannot start and remain visibly unperformed. `draft` includes publication and exact-head CI before handoff. Keep the required CI names in the contract for a later authorized draft, even when starting locally.

For compatibility, contracts and saved runs without an endpoint retain the original `draft` flow. This default is not publication authority. CoS must select the endpoint allowed by the user.

Record later user steering in an immutable approval file, then run one of:

```sh
python3 /path/to/feature-graph/scripts/graph.py endpoint /private/task/run.json local --approval /private/task/hold-publication.md
python3 /path/to/feature-graph/scripts/graph.py endpoint /private/task/run.json draft --approval /private/task/publish-approval.md
```

Use the instruction already given as evidence; do not ask for redundant confirmation. Reconcile stopped workers before applying the command. The guard pins the approval, records the previous endpoint and handoff results, and preserves valid work. Only handoff and closeout reopen. An endpoint change does not count as a repair; repeating the current selection is idempotent. Existing publication evidence is retained, and a hold cannot undo a push already performed.

`status` includes `endpoint` and `complete`. A local run can be complete with publication and CI still pending. Changed source or evidence still blocks progress and requires the normal repair path.

## Reserve, execute, complete

```sh
python3 /path/to/feature-graph/scripts/graph.py start /private/task/run.json prepare --worker task-prepare-1
python3 /path/to/feature-graph/scripts/graph.py receipt /private/task/run.json prepare > /private/task/prepare-receipt.json
```

`start` reserves the node before dispatch. Save its attempt ID and bind the actual worker ID in the task ledger. Repeating `start` with the same worker ID returns the existing reservation; it does not authorize another launch. A different worker ID is rejected while that reservation is running.
After `prepare`, `tests` and `plan` may run together; `implement` still requires a passing plan. Each author's seal may overlap the other author's work, but only reads its own stopped artifact. `capture` remains exclusive and directly requires both seals. After capture, `checks`, `verification`, `regression`, `arc` and `styla` may run together. `reconcile` explicitly waits for checks and all four reviews. All other nodes remain exclusive. Parallel node eligibility does not authorize conflicting commands or writes: CoS controls execution against the frozen shared worktree.
After inspecting the real result, fill the receipt template:

- Keep `attempt`, `generation`, `snapshot` and `spec_sha256` unchanged.
- Set `outcome` to `pass`, `fail` or `blocked`, and give a factual `summary`.
- Put absolute paths to immutable reports/logs/manifests in `evidence`. Reports must explain the result; a successful command may have an empty output log. Keep evidence outside mutable worktrees. Never overwrite an earlier generation's log.
- Fill `details` using the node requirements below. Boolean fields are CoS attestations backed by evidence, not independently proven facts.

```sh
python3 /path/to/feature-graph/scripts/graph.py complete /private/task/run.json prepare --receipt /private/task/prepare-receipt.json
```

The guard stores the receipt and evidence hashes atomically. It rejects a stale attempt, spec, generation or snapshot. Exact duplicate completion is idempotent. Every dispatch and passing completion verifies retained passing evidence.
Keep the report immutable and send the completion outcome to CoS immediately. Before completion, send the first substantiated blocker through the existing worker messaging path as soon as its evidence is saved, before another expensive check. Include candidate identity, criterion, consequence and evidence path. CoS acknowledges the notice, starts the agreed collection deadline, gathers independent findings and unfinished coverage, stops workers and routes repair. Record discovery, notification, acknowledgement and stop times in the existing ledger. An early notice does not complete a node or waive the remaining audit. The guard does not send messages or generate Firstmate wakes.

## Passing receipt details

Failed or blocked receipts need the common fields and evidence. Every review receipt also needs `coverage_completed` and `coverage_remaining` lists. A PASS needs nonempty completed coverage and no unfinished coverage. A failed or blocked review needs `repair: {"target": "implement", "criterion": "AC-2", "reason": "observed consequence and evidence"}`. Targets are `tests`, `implement`, `both`, `plan`, `checks`, `environment`, `review`, or `spec`. This recommends a route to CoS; it does not dispatch a repair. Interrupted reviews use BLOCKED with their unfinished coverage.
Passing receipts additionally need:

| Node | Required `details` |
| --- | --- |
| `prepare` | `baseline` equals contract; `scaffold_verified`, `executables_verified`, `ownership_disjoint`, `decisions_resolved`, `budget_approved`, `verification_plan_approved` are true. Evidence includes the single prepared worktree, pinned baseline and disjoint author file ownership. Contexts contain only the frozen spec, repository rules, permitted baseline material and each author's own work; no newly authored peer content. |
| `tests`, `implement` | `stopped: true`; nonempty ordered `checkpoints` list with artifact references. Evidence includes complete changed/deleted/new path manifest and checkpoint predecessor identities. A checkpoint may be unchanged in an unaffected repair stage, with evidence. |
| `seal_tests`, `seal_implementation` | `artifact_verified: true`, `baseline_inputs_only: true`. The second flag means original baseline plus the author's own checkpoints, with no peer files or reasoning, including repairs. |
| `plan` | `matches_freeze: true`, `shared_with_user: true`. Evidence is the plan and CoS check. |
| `capture` | `authors_stopped: true`, `complete_artifacts_verified: true`. The guard computes the combined source identity itself. |
| `checks` | `checks` array containing every required local check, as shown below. |
| `verification` | `blocking_findings: []`, nonempty `inspected_paths`, all planned `criteria_verified`, nonempty `paths_traced`, `first_principles_audit: true`, `test_validity_reviewed: true`, independently executed `checks` covering the evidence plan, and `deferred_proof_completed: true` when proof was deferred. |
| `regression`, `arc`, `styla` | `blocking_findings: []`, nonempty `inspected_paths`. Evidence must support the actual assigned review. |
| `reconcile` | `all_findings_resolved: true`. Required local checks and every review must already pass. |
| `publish` | `head`, exact `branch`, full `url`; `draft`, `signatures_verified`, `commit_series_preserved`, `no_reviewers` all true. The local HEAD must equal the published head. Actual committed blobs and the working files must both match capture, so uncommitted reviewed changes cannot be omitted. |
| `ci` | `head` and `checks` entries with `name`, `head`, `conclusion: "success"`, and check `url`. All required CI names must be present and every head must equal publication. |
| `handoff` | `user_notified: true`, backed by the delivered summary. |
| `closeout` | `lessons_recorded: true`, `pack_synchronized: true`, backed by the delivered retrospective and existing closeout evidence. |

The `tests` PASS also includes `early_proof` with exact `baseline` and a factual `result`. For a bug, add `behavior_failure: true`, the executed `command`, nonzero integer `exit_code` and immutable `log`. For a feature, add successful executed `checks` for the baseline harness/contracts; when the plan defers proof, include `unavailable` describing the absent boundary and later obligation. Otherwise include `behavior_proven: true` backed by the approved early proof. An import error never proves a bug.

A local execution record looks like:

```json
{"name": "tests", "command": "actual command executed", "exit_code": 0, "log": "/absolute/private/task/checks.log"}
```

Record actual command duration and any waiting/repeated-check reason in the report. Node `duration_seconds` includes all elapsed time between start and completion, including waits. It is not CPU time or measured command duration.
For CI, save a current forge query proving the PR head and required check results in the common evidence. URLs and success strings alone are not proof that the forge was queried.

## Source identity and repairs

The identity covers original baseline paths, current tracked paths, and non-ignored untracked paths, including bytes, deletions, executable bits and symlink targets. Signing or committing identical content does not change it. Publication compares committed regular files using line-ending attributes from the committed ref, including Git's built-in `text=auto` classification. Explicit `eol=lf` keeps index bytes, while `eol=crlf` converts qualifying LF text to CRLF. External filters, `ident`, and working-tree encodings are unsupported and fail closed without executing a converter. Uncommitted attributes cannot change the committed representation.
Ignored/generated content and external services are not hashed. Required ignored inputs need an explicit separately pinned evidence policy before use. Submodules are unsupported in this first version and fail closed. Use a complete immutable snapshot policy before extending support.
The guard rehashes the candidate at stage boundaries. It cannot detect a file changed and restored entirely between commands. Source must remain frozen in practice; run tools that mutate generated outputs in scratch copies where necessary.

```sh
python3 /path/to/feature-graph/scripts/graph.py repair /private/task/run.json implement --cause empty-response --reason 'Criterion AC-2 fails for the recorded empty response'
```

Before repair, verify all affected workers have stopped and complete any running reservations honestly as failed or blocked. A failed completion may be recorded after source or earlier evidence drift so the run can recover. It cannot release a successor. The guard does not kill workers.
An author repair invalidates that author stage and all descendants, including capture, checks, reviews, publication and CI. Preserve the prior candidate and receipts in history. Restart authors with only their permitted baseline material and own work, even though the shared worktree also contains peer files.
Choose `tests` when both authors need work, `plan` when implementation planning needs revision within the freeze, or `implement` for a service-only repair whose plan remains valid. An ordinary tests repair conservatively reopens implementation in versions 2 and 3, even though the version 3 author branches are parallel. To retain it for a tests-only repair, use `--preserve-implementation /absolute/private/task/retention.md`. That evidence must establish unchanged plan, source checkpoints, inputs and interfaces. Run the repair command before changing files; retained stages must already pass on the unchanged captured candidate. A further tests-only retry before recapture may reuse valid prior retention if every non-test path is still unchanged. Only the approved `test_paths` may change before capture. The guard retains the implementation stages, requires a current test seal, and rejects any changed, added or deleted non-test file at capture. If the proof is false or source work is needed, record stopped workers and reopen the owning author normally.
An environment/check/review retry starts at that node only if source is unchanged. In version 3, a checks-only retry retains valid independent review receipts on the identical candidate; it still blocks reconciliation until checks pass. CoS records why retained independent evidence remains valid. Retry `publish` for same-content head changes, and `ci` for an unchanged-head CI rerun. Check actual remote state before retrying publication to avoid duplicate PRs.
Retry a failed or blocked `handoff` or `closeout` directly when content and publication are unchanged; this retains valid CI instead of rerunning it merely to resend a result or finish the lessons record.
Every version 2 or 3 repair needs a stable `--cause` identifier. The guard checks both current history and the immutable predecessor runs pinned by `budget_previous_run`, including earlier spec revisions of the same slice. Only recurrence is inherited; old receipts cannot satisfy the new acceptance. Repeating that cause requires `--diagnosis /absolute/private/task/diagnosis.md` before another attempt. The file must classify the actual cause, explain what previous attempts missed and justify the bounded next action. No fixed repair-count limit applies; the approved slice budget bounds recovery. Do not rename a recurrence to evade diagnosis. Version 1 retains its original two-round diagnosis threshold.
No skip, force-pass, waive or automatic publication command exists. A blocker remains a blocker until its prerequisites and evidence are satisfied.

Run guard regression checks with `python3 -B -m unittest discover -s /path/to/feature-graph/tests -v`.
