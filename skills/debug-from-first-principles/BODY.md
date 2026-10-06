# Debug from first principles

Input: an **error, symptom, or issue** plus a **codebase** (GitHub `owner/name` or URL, optional ref; and/or paths on a registered machine the user names). Optional: logs, stack traces, repro steps, env hints.

Goal: diagnose from first principles, walk the real code paths and infra, and explain the finding in plain language. Prefer independent parallel investigation when the active role permits delegation. Implement a fix only within explicit existing or new implementation/repair authority.

## Bugs and repair loops in delivery workflows

Subagents in Feature loop, Feature graph and its DAG aliases may run this skill for a bug, failing test or failed check within their assigned role and artifacts, without a separate skill assignment. Authors may diagnose local failures. An assigned independent verifier leads repair-loop debugging and investigations requiring the combined candidate. CoS coordinates only: pause work, assign the investigation, assess returned evidence and route proven repairs. CoS must not run this skill, trace failure paths or execute diagnostic probes itself. This division applies to delivery workflows; a direct agent may still run a standalone debugging task. Existing implementation or repair approval remains valid; using this skill does not require asking the user to authorize the same fix again. Outside an authorized implementation/repair task, diagnose only.

Stop implementation as soon as repairs recur or successive fixes expose further unexplained failures in the affected journey. A changed test name or symptom does not reset the investigation. Do not keep patching assertions, timers, fixtures or service code to chase a green run. Feature loop's two-unsuccessful-round threshold is a latest checkpoint, not a reason to wait when the loop is already apparent.

1. The discovering agent stops speculative edits, preserves its current artifact and failing evidence, and notifies CoS. CoS pauses implementation and test-repair dispatch across the affected slice, confirms its writers have stopped, and assigns the verifier to lead diagnosis with bounded help from permitted roles. Stop redundant broad reruns; preserve unrelated work and do not interrupt other tasks.
2. The verifier pins the failing source, command, environment and observed outcome. Compare a valid baseline/control where available. Trace the real entry point through configuration, callers, state, side effects, asynchronous completion and cleanup. Inspect the test harness and runtime setup as possible causes too. Use focused execution to falsify hypotheses and explain the observed failures together; a passing isolated test does not explain a failing full run.
3. CoS may divide independent diagnostic questions among permitted roles. Subagents keep their file/read boundaries, author independence and no-nested-agent rules. Feature graph authors inspect only their own artifacts and permitted baseline material; the assigned verifier inspects the frozen combined candidate. The verifier reconciles the diagnostic evidence and requests further bounded work through CoS. Send authors sanitized facts and reproductions, not peer code or reasoning. Reviewers remain findings-only; Git keeps its operational role.
4. The verifier returns the causal explanation, failing path and affected callers, evidence that distinguishes it from alternatives, and whether the fault is implementation, test/harness, environment or spec. Include the bounded correction and checks needed to resume; report findings only, without editing source or tests. If the cause is still unknown, report that and continue bounded diagnosis within the existing budget. Do not declare it fixed because a retry passes, weaken assertions, suppress errors or add sleeps/retries to hide it.
5. Once the diagnosis supports a specific correction, CoS releases only that focused repair to its existing owner under current authority. The assigned execution owner verifies the actual affected code path and meaningful regression checks on the corrected artifact before CoS resumes feature implementation. Where applicable, prove the regression fails on the buggy source first. Then run the workflow's required combined checks and reviews against the new candidate; diagnostic probes do not replace those gates.

This is a change of activity within the existing workflow, not a new delivery pipeline, permission to expand the product scope, a budget reset or a new user-approval gate. The test-repair evidence requirement below applies even before a repair loop develops. Spec amendments and evidence invalidation still follow the owning workflow. Record the diagnostic stop, cause and resume evidence in its existing ledger.

## Before repairing a failing test

For delivery authors, apply this rule from the first failure, including a local investigation. Do not repair failing tests, assertions, mocks, fixtures, timing, retries, setup or test-only helpers until evidence proves that the observed failure is not caused by implementation behavior that violates the frozen contract. A test/harness fault must be established and independently verified before its correction. A passing retry, source inspection alone, an unchanged implementation artifact or a green unrelated suite is insufficient.

The author preserves the failing artifact and reports the criterion, inputs, expected and observed behavior, command and environment. Trace permitted real code paths and use focused execution to distinguish an implementation defect from a test/harness fault. If required evidence needs forbidden peer artifacts, stop that investigation and ask CoS to assign the verifier to the pinned combined candidate. Do not relax author independence to obtain proof.

Before CoS dispatches a test repair, the independent verifier must confirm the cause against the frozen contract and actual implementation path. Its findings must identify the source and evidence, explain why implementation behavior is not responsible for this failure, locate the test/harness fault, and bound the correction and rechecks. Missing runtime evidence is a gap, not clearance. Record this finding in the existing workflow ledger. CoS checks the returned evidence and routes the correction; it does not perform the investigation.

If the cause is implementation, mixed or unknown, keep test repairs paused. Route an implementation defect to its owner under existing authority, then reassess any remaining test failure. Environment-only faults go to the environment owner. Never weaken required assertions, suppress errors, add sleeps/retries or reshape fixtures to accommodate buggy behavior. Diagnostic probes and authorized new regression tests that expose a defect may proceed within existing artifact and ownership limits; they do not authorize changing the failing test. Required post-repair checks and reviews still apply.

## 1. Lock the question

- Restate the failure in one sentence (what broke, where it showed up, what "good" looks like).
- List known facts vs assumptions. Mark assumptions clearly.
- If the repo or ref is missing and you cannot infer it from context, ask once. Otherwise proceed.

## 2. Map the surface (fast, parallel)

When delegation is permitted, split independent reads across workers. Inside a delivery workflow, only CoS assigns workers; subagents investigate their permitted inputs and report to CoS:

- **Entry / repro path:** the HTTP handler, CLI, job, or UI action that triggers the symptom.
- **Infra:** how the service boots, env knobs, compose/local Docker, queues, DBs, caches, external APIs named by the code.
- **Nearby tests and docs:** what the contract claims vs what the test asserts.

Do not clone a remote repo onto a laptop or shared box unless the user asked. Prefer remote read (`gh`, API, cloud agent read) for GitHub trees.

## 3. Trace the code path

Follow the call chain from the symptom inward:

1. Where the error is raised or the bad value is produced.
2. Who calls that site and what invariants they assume.
3. What config / feature flags / env change the branch taken.
4. Whether the failure is pre-commit (validation), at the boundary (HTTP/queue/DB), or after side effects.

Cite file paths and symbols. Prefer reading the real source over guessing from names.

## 4. First-principles checks

For each candidate cause, ask:

- Is this consistent with the observed symptom (timing, status code, missing side effect)?
- What would falsify it in one cheap check?
- Is it a contract bug (code matches wrong tests/docs), an infra mismatch (wrong broker, empty key, wrong URL), or a race / lifecycle bug (half-open probe, swallowed stream error)?

Drop causes you can falsify. Keep the smallest set that still explains the facts.

## 5. Parallelize when it helps

Use permitted workers for independent axes, such as the handler path, infra/config and tests/docs. In delivery workflows, the verifier reconciles their factual evidence and reports to CoS; CoS assigns workers and routes their outputs. In standalone debugging, the investigating agent reconciles the evidence. Do not spawn duplicate workers or use this skill to bypass a role's delegation or artifact restrictions.

## 6. Report findings

Report to CoS when working as a delivery subagent; only the coordinator contacts the user. Keep the result short and readable:

1. **Finding** - one or two sentences.
2. **What is happening** - the real path, with file/symbol citations.
3. **Why** - root cause in plain words (no jargon pile).
4. **How sure** - high / medium / low, and what would raise confidence.
5. **Next checks or fixes** - bounded next steps within existing authority; during a repair loop, follow the diagnosis and resume conditions above.

Separate **fact** (seen in code/logs) from **judgment**. ASCII hyphen only.

## Non-goals

- Shipping a fix without an explicit ask.
- Rewriting architecture for taste.
- Auditing the whole repo when the issue is local (unless the user asked for that breadth).
