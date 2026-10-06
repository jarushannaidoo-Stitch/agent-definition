# Operating the dependency guard

Requires Python 3.9+, Git, and macOS or Linux. No Python packages, LangGraph, service or network are needed.
Run the script relative to the loaded skill directory. Use absolute paths for all run inputs and evidence.
The command checks recorded prerequisites and content identities. CoS still verifies real approval, stopped workers, honest evidence, author blindness and publication results. A process with write access can bypass or edit this local state; it is not a security boundary.

## Initialize once

Create a durable private task directory outside the product worktree, including author-private evidence directories. Store the exact approved spec export and a record of the user's approval there.
Write `contract.json` with these fields, replacing the illustrative values:

```json
{
  "repo": "/absolute/path/to/integration-worktree",
  "baseline": "0123456789012345678901234567890123456789",
  "branch": "exact-approved-linear-branch",
  "spec": "/absolute/private/task/frozen-spec.md",
  "approval": "/absolute/private/task/approval.md",
  "endpoint": "local",
  "checks": ["tests", "lint", "types"],
  "ci_checks": ["required-workflow-job"],
  "arc": {"required": true, "reason": "Changes a public contract"},
  "styla": {"required": false, "reason": "Mechanical change in existing structure"}
}
```

```sh
python3 /path/to/feature-graph/scripts/graph.py init /private/task/run.json --contract /private/task/contract.json
python3 /path/to/feature-graph/scripts/graph.py status /private/task/run.json
```

The guard validates the baseline commit, pins the spec, approval and workflow bytes, and requires explicit review applicability. It refuses to overwrite an existing run. A changed approved spec requires a new run with new approval evidence; preserve the old run and work, and reconcile existing workers first.
`status` lists eligible nodes and recorded worker IDs. Exit code 2 means invalid input or stale state/evidence. Read the diagnostic; do not bypass it by editing `run.json`.

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
Every node is exclusive except the independent reviews, which can be reserved together after checks pass. `plan` cannot start until tests have been sealed.
After inspecting the real result, fill the receipt template:

- Keep `attempt`, `generation`, `snapshot` and `spec_sha256` unchanged.
- Set `outcome` to `pass`, `fail` or `blocked`, and give a factual `summary`.
- Put absolute paths to immutable reports/logs/manifests in `evidence`. Reports must explain the result; a successful command may have an empty output log. Keep evidence outside mutable worktrees. Never overwrite an earlier generation's log.
- Fill `details` using the node requirements below. Boolean fields are CoS attestations backed by evidence, not independently proven facts.

```sh
python3 /path/to/feature-graph/scripts/graph.py complete /private/task/run.json prepare --receipt /private/task/prepare-receipt.json
```

The guard stores the receipt and evidence hashes atomically. It rejects a stale attempt, spec, generation or snapshot. Exact duplicate completion is idempotent. Every later transition verifies retained passing evidence.
Keep the report immutable and send the completion outcome to CoS immediately. The guard does not send messages or generate Firstmate wakes.

## Passing receipt details

Failed or blocked receipts need the common fields and evidence, but do not need passing attestations.
Passing receipts additionally need:

| Node | Required `details` |
| --- | --- |
| `prepare` | `baseline` equals contract; `scaffold_verified`, `executables_verified`, `ownership_disjoint` are true. Evidence includes prepared author views and their permitted files. |
| `tests`, `implement` | `stopped: true`; nonempty ordered `checkpoints` list with artifact references. Evidence includes complete changed/deleted/new path manifest and checkpoint predecessor identities. A checkpoint may be unchanged in an unaffected repair stage, with evidence. |
| `seal_tests`, `seal_implementation` | `artifact_verified: true`, `baseline_inputs_only: true`. The second flag means original baseline plus the author's own checkpoints, with no peer files or reasoning, including repairs. |
| `plan` | `matches_freeze: true`, `shared_with_user: true`. Evidence is the plan and CoS check. |
| `capture` | `authors_stopped: true`, `complete_artifacts_verified: true`. The guard computes the combined source identity itself. |
| `checks` | `checks` array containing every required local check, as shown below. |
| `acceptance` | `blocking_findings: []`, nonempty `inspected_paths`, nonempty `criteria_verified`, and independently executed `checks`. |
| `regression`, `arc`, `styla` | `blocking_findings: []`, nonempty `inspected_paths`. Evidence must support the actual assigned review. |
| `reconcile` | `all_findings_resolved: true`. Every required review must already pass. |
| `publish` | `head`, exact `branch`, full `url`; `draft`, `signatures_verified`, `commit_series_preserved`, `no_reviewers` all true. The local HEAD must equal the published head. Actual committed blobs and the working files must both match capture, so uncommitted reviewed changes cannot be omitted. |
| `ci` | `head` and `checks` entries with `name`, `head`, `conclusion: "success"`, and check `url`. All required CI names must be present and every head must equal publication. |
| `handoff` | `user_notified: true`, backed by the delivered summary. |
| `closeout` | `lessons_recorded: true`, `pack_synchronized: true`, backed by the existing closeout evidence. |

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
python3 /path/to/feature-graph/scripts/graph.py repair /private/task/run.json implement --reason 'Criterion AC-2 fails for the recorded empty response'
```

Before repair, verify all affected workers have stopped and complete any running reservations honestly as failed or blocked. A failed completion may be recorded after source or earlier evidence drift so the run can recover. It cannot release a successor. The guard does not kill workers.
An author repair invalidates that author stage and all descendants, including capture, checks, reviews, publication and CI. Preserve the prior candidate and receipts in history. Start authors again only on their permitted baseline-plus-own-work views.
Choose `tests` when both authors need work, `plan` when implementation planning needs revision within the freeze, or `implement` for a service-only repair whose plan remains valid. A tests repair conservatively reopens the later implementation stages; unchanged implementation may be reattested without new code.
An environment/check/review retry starts at that node only if source is unchanged. CoS records why retained independent evidence remains valid. Retry `publish` for same-content head changes, and `ci` for an unchanged-head CI rerun. Check actual remote state before retrying publication to avoid duplicate PRs.
Retry a failed or blocked `handoff` or `closeout` directly when content and publication are unchanged; this retains valid CI instead of rerunning it merely to resend a result or finish the lessons record.
After two repair generations, `--diagnosis /absolute/private/task/diagnosis.md` is mandatory for another repair. The file must classify the cause and justify the next bounded action. This conservative count also includes environment and review retries.
No skip, force-pass, waive or automatic publication command exists. A blocker remains a blocker until its prerequisites and evidence are satisfied.

Run guard regression checks with `python3 -B -m unittest discover -s /path/to/feature-graph/tests -v`.
