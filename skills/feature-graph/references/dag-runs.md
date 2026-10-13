# DAG run folder (version 6)

Each DAG runs detached. Its state lives in `runs/<dag-id>/` inside the private task directory, outside product source:

```text
runs/<dag-id>/
  status.json    phase, per-node state, work packages, worktrees, bounces, steer queue, escalations, cleanup
  contract.json  frozen contract (Linear issue, spec revision, baseline, branch, checks, CI checks, freeze_ready)
  plan.md        architect's work packages and interface contracts (never given to gate reviewers)
  evidence/      receipts, logs and reviewer reports, one file per node attempt
```

Only the architect writes `status.json`, through `scripts/dag_run.py`. Main never edits it.

## Commands

```bash
python3 /path/to/feature-graph/scripts/dag_run.py init RUNS DAG_ID --contract contract.json --actor ARCHITECT
python3 /path/to/feature-graph/scripts/dag_run.py status RUNS/DAG_ID [--json]      # dag status
python3 /path/to/feature-graph/scripts/dag_run.py list RUNS                        # every DAG
python3 /path/to/feature-graph/scripts/dag_run.py steer RUNS/DAG_ID --message TEXT --actor MAIN   # dag steer
python3 /path/to/feature-graph/scripts/dag_run.py ack-steer RUNS/DAG_ID s1 --note TEXT --actor ARCHITECT
python3 /path/to/feature-graph/scripts/dag_run.py package RUNS/DAG_ID wp1 --engineer ENG --files a.py test_a.py --actor ARCHITECT
python3 /path/to/feature-graph/scripts/dag_run.py worktree RUNS/DAG_ID PATH --branch NAME --purpose wp1|integration --actor ARCHITECT
python3 /path/to/feature-graph/scripts/dag_run.py start|pass RUNS/DAG_ID NODE [--package wp1] [--evidence FILE] --actor ARCHITECT
python3 /path/to/feature-graph/scripts/dag_run.py fail RUNS/DAG_ID NODE --finding TEXT --to ENG --evidence FILE --actor ARCHITECT
python3 /path/to/feature-graph/scripts/dag_run.py bounce RUNS/DAG_ID --from ENG --finding TEXT --evidence FILE --actor ARCHITECT
python3 /path/to/feature-graph/scripts/dag_run.py resolve RUNS/DAG_ID b1 --resolution TEXT --actor ARCHITECT
python3 /path/to/feature-graph/scripts/dag_run.py brief RUNS/DAG_ID NODE --input spec_full=SPEC --input merged_diff=DIFF [--package wp1] --actor ARCHITECT
python3 /path/to/feature-graph/scripts/dag_run.py removed RUNS/DAG_ID PATH --branch-deleted yes|no|unmerged --actor ARCHITECT
```

## dag status / dag steer semantics

- `dag status <dag-id>` returns one bounded line (or `--json`): phase, gate loops used/cap, open bounces, pending steer messages and cleanup state. `dag list` shows every DAG under the runs root. Reading status never blocks the DAG.
- `dag steer <dag-id> "<message>"` appends to the run's steer queue (Main only). The architect reads the queue at every node boundary, applies or declines each message and acknowledges it with `ack-steer`. A steer that changes frozen scope, interfaces or acceptance needs Jarushan's consent before it is applied. Main also notifies the architect through the harness's subagent messaging so a waiting architect wakes up.
- Multiple DAGs run at once; each has its own folder, architect and worktrees. Shared heavyweight commands use one lock per Main.

## Guard rules enforced by dag_run.py

- `init` refuses a contract missing required fields or without `freeze_ready: true` (ask Jarushan).
- Work-package file ownership is disjoint and frozen once build starts.
- Build needs a fresh registered worktree per package; integrate needs a fresh integration worktree. A worktree path is never registered twice.
- A node starts only when its dependencies pass. An open bounce blocks dependent work.
- A gate failure creates a bounce routed via the architect to the owning engineer and reopens build and everything after it for that engineer's package. Gate loops past `loop_cap` escalate to HQ/Jarushan.
- A contract bounce reopens the plan.
- `pass` requires a saved evidence file.
- Every non-architect node needs a brief validated against `context.json` before `start`: unknown or unlisted kinds, missing required kinds, architect artifacts for gate roles and git, files outside an engineer's package, hand-supplied bounced findings and oversize inputs are rejected.
- Worktrees are removed after handoff (or when an escalated run is abandoned). Cleanup passes only when none remain open; closeout requires cleanup `done`.

## Cleanup states

`not_started` -> `in_progress` (some removed) -> `done` (every engineer and integration worktree removed and pruned, merged branches deleted). `branch-deleted: unmerged` records a branch kept because it was not merged; report it in handoff.
