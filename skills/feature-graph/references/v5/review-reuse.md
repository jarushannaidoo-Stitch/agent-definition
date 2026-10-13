# Review reuse in version 4

Use this only after a source repair and a new successful `capture`. All initial reviews run in full. Existing version 1, 2 and 3 runs keep their rules. Required repository checks still execute against the new candidate, and publication still requires exact-head CI.

CoS decides whether evidence remains valid and records its reasoning. The guard checks the complete source delta, spec/candidate/attempt identities, pinned evidence hashes, unchanged declared inputs, previous successful checks and complete coverage. It cannot discover omitted dependencies or judge a narrative impact analysis. CoS must trace callers, shared contracts, configuration, dependencies and invariants. If that analysis or any input identity is uncertain, run the full review.

## Record an assessment

Save one immutable JSON file per review outside product source, then run:

```sh
python3 /absolute/path/to/feature-graph/scripts/graph.py review-plan /absolute/private/task/run.json arc --assessment /absolute/private/task/arc-retention.json
```

The node must be pending after capture. An assessment has these fields:

```json
{
  "node": "arc",
  "mode": "retain",
  "approved_by": "cos",
  "prior_attempt": "exact archived attempt ID",
  "prior_snapshot": "exact old candidate SHA256",
  "snapshot": "exact new candidate SHA256",
  "spec_sha256": "exact frozen spec SHA256",
  "changed_paths": ["src/components/amount-label.test.tsx"],
  "reason": "The repair changes only the assertion's readiness condition; ownership and contracts retain their prior inputs.",
  "impact": {
    "uncertain": false,
    "coverage": [],
    "criteria": [],
    "callers": "Name the actual traced callers and why retained coverage remains valid.",
    "contracts": "Identify the unchanged public contracts or affected contracts.",
    "configuration": "Identify relevant configuration, including compiler and runner inputs.",
    "dependencies": "Identify transitive and runtime dependencies and evidence of their identity.",
    "invariants": "Identify each retained invariant and explain why this delta cannot alter it."
  },
  "unchanged_inputs": ["src/components/amount-label.tsx", "package.json", "pnpm-lock.yaml"],
  "retained_coverage": ["Use the exact completed coverage items from the previous review."],
  "review_coverage": [],
  "retained_criteria": [],
  "review_criteria": [],
  "retained_checks": [],
  "rerun_checks": []
}
```

Replace every explanatory value with concrete task evidence. `changed_paths` must equal the full old-to-new manifest delta, including additions, deletions, modes and symlink changes. List the complete input closure for retained coverage in `unchanged_inputs`; every listed path must exist with unchanged bytes and kind in both snapshots. Only regular files and executables can establish retained input identity. Resolve symlinks to captured target files. If relevant runtime, ignored or external inputs cannot be proven unchanged, run the affected checks/review again; the source manifest does not cover them.

Use the most recent archived result for this lens. Do not select an older PASS to bypass a later failure. Prior reports and logs remain immutable, including through further repairs. Assessments are pinned and rechecked on dispatch/completion. A changed assessment, old report or retained check log blocks progress.

## Retain an unaffected review

`mode: "retain"` requires a complete prior PASS, no affected/unfinished coverage, and every prior coverage item in `retained_coverage`. The command records a new explicit retention receipt on the new candidate. Its `retained_from` names the original attempt; its newly completed coverage is empty. It does not pretend the old reviewer executed again, require that reviewer to reconfirm, or modify the original receipt.

For verification, put every planned criterion in `retained_criteria` and every planned independent check in `retained_checks`. Prior successful checks must have pinned logs, and the prior full audit and deferred proof must be complete. Other lenses leave all four criteria/check arrays empty. All four review nodes must have valid full, retained or focused passes before reconciliation.

## Review the affected portion

Use `mode: "focused"`. Keep only previously completed valid items in `retained_coverage`. Put changed, unfinished and no-longer-retained items in `review_coverage`; include the previous finding's `repair.criterion` when the prior outcome was FAIL or BLOCKED. `impact.coverage` must be included in that work. A partial or failed review cannot be retained wholesale.

For verification, `retained_criteria` and `review_criteria` partition the entire pinned criterion list. Affected criteria must be in `review_criteria`. `retained_checks` and `rerun_checks` partition the independent checks in the verification plan. Retained checks require original zero-exit results with logs pinned by that review. Their declared inputs and invariants must be unchanged. Any doubt means rerun. This never waives the separate repository `checks` node.

After `review-plan`, dispatch through the ordinary `start` command. Give the reviewer its focused assignment, frozen spec, exact candidate/delta, its own prior evidence and relevant baseline/caller artifacts. Do not send peer reports or outcomes. The guard's receipt template still supplies the current attempt, generation, snapshot and spec. In the focused receipt's `details`:

- `retained_from` equals the assessment's `prior_attempt`.
- `coverage_completed` equals `review_coverage`; `coverage_remaining` and `blocking_findings` are empty only after all assigned work finishes.
- `previous_findings_resolved` is true only after checking the previous findings. Name newly inspected paths in `inspected_paths`.
- Verification names newly verified `review_criteria` in `criteria_verified`, traces actual affected paths in `paths_traced`, and attests `first_principles_audit` and `test_validity_reviewed` for that scope. Complete deferred proof where required. `checks` contains newly executed results and logs, covering every `rerun_checks` name; do not relabel retained executions as new ones.

The guard records combined validated coverage separately from the new receipt and retains the entire evidence chain. Subsequent repairs may carry that coverage forward only after a fresh impact assessment. Required coverage cannot disappear between repairs.

If the review finds wider impact or invalid retained inputs, return FAIL/BLOCKED with completed and unfinished coverage plus the ordinary repair routing fields. CoS stops any running work, retries that review node through `repair`, and either records a broader focused plan or dispatches a full review without a plan. Never edit a pinned assessment in place. Evidence-only retries on identical source continue to preserve valid independent sibling reviews.
