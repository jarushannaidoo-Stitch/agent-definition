# Feature loop

Use one small, captain-approved slice. CoS is the sole orchestrator and the captain's only contact. CoS owns the frozen spec, dispatch, findings, and delivery coordination. Agents own their assigned work. The captain owns product freeze, ready status, and merge authority.

## Orchestrator responsibility

CoS is accountable for every subagent doing the assigned work and staying within the frozen spec. Give each assignment explicit ownership, the relevant acceptance criteria, non-goals, and expected evidence. Keep initial authors independent. Git receives only the bounded operational instructions needed for approved work.

Check progress at natural handoffs and inspect returned artifacts against the assignment before accepting them. A subagent's PASS or green tests alone do not establish spec compliance. Compare changed paths, behavior, tests, and review findings with the frozen criteria and repository rules. Read the relevant diffs or evidence when scope, correctness, or complexity is unclear. Require the submitted tests themselves to demonstrate the claimed behavior; a separate probe does not prove that those tests catch the defect.

Redirect side quests, unrelated cleanup, invented requirements, speculative abstractions, and unnecessary dependencies or complexity as soon as they appear. Require the smallest complete solution that satisfies acceptance and preserves existing invariants. Return an over-engineered result to its owner with the specific excess and required scope; do not trade away required behavior or meaningful tests for brevity. Resolve routine implementation choices within the spec and return changed product requirements to the captain.

## Debugging failures and stopping repair loops

Subagents may run [Debug from first principles](../debug-from-first-principles/SKILL.md) for bugs or failed tests/checks within their role and permitted artifacts, without another skill assignment. In the canonical pack, read `../debug-from-first-principles/BODY.md`. Authors may diagnose local failures. CoS assigns an independent verifier to lead repair-loop debugging and investigations requiring the combined candidate. CoS coordinates the stop, assignments, evidence and repair routing; it must not run the skill, trace failure paths or execute diagnostic probes itself. Follow its delivery failure protocol: when repairs recur or uncover successive unexplained failures, stop implementation and test patching across the affected slice, preserve the failing artifact, and concentrate the team on tracing and executing the real paths. Resume only the diagnosed correction first; resume feature work after the affected path and meaningful checks pass.

Before dispatching any repair to a failing test or test-only helper, including the first local failure, require the Debug skill's implementation-first evidence and independent verifier confirmation that the failure is a test/harness fault. Record the source-bound finding and bounded correction in the existing ledger. Implementation, mixed or unknown causes keep test repairs paused. Authors retain their read/write boundaries; CoS routes combined-candidate diagnosis to the verifier and sends only sanitized factual repair inputs to authors.

Include this permission, test-repair evidence requirement and stop rule in author, reviewer and repair handoffs, including resumed older runs. Keep role ownership, permitted artifacts, independent reviews, budgets and source-bound evidence intact. Only CoS assigns diagnostic workers; the verifier conducts the investigation and returns causal evidence, affected paths, a bounded correction and resume checks; this skill does not allow subagents to spawn peers, edit another role's files or inspect forbidden peer work. Required checks and reviews still apply after the repair. No new workflow stage or user-approval gate is introduced.

## Five stages

### 1. Freeze and prepare

Resolve the repository and approved ticket. The frozen Linear document is the only source of task requirements. It must state observable acceptance and failure cases, non-goals, ownership, affected public interfaces, and applicable fail-closed behavior. Include concrete examples and the relevant verification commands or user flow. Mark inapplicable concerns explicitly; do not inflate a small feature into an architecture document.

Before freeze, CoS discusses the architecture and proposed implementation approach with the captain. Explain the owning modules and responsibilities, existing components to reuse, the control/data flow, relevant interface and state boundaries, and how the approach handles required failure cases. Discuss meaningful tradeoffs and why the proposed approach is the simplest complete solution. Record the agreed decisions in an "Architecture and implementation approach" section of the frozen spec. Scale the detail to the change; a small change may need only a few sentences confirming the existing owner and pattern. The freeze covers both behavior and architecture.

Trace the real default caller or UI flow before freeze, including shared controls and fallback paths. For each important criterion, record its real trigger and observable result in the existing spec. Keep this proof map short and inside the existing spec.

CoS fills factual gaps from the repository. Ask the captain for unresolved product or architectural decisions and major spec changes as defined in AGENTS.md. Minor refinements and test-only amendments preserving agreed behavior, architecture and acceptance do not need another user approval, including focused file/fixture ownership and runner changes. Record their classification and reason in the source spec, pin its revised content and give affected agents the updated contract before dependent work. Changing expected behavior or weakening required proof is major even in tests. Existing approval carries forward for routine setup and repairs. Do not launch authors while required behavior or architecture remains unresolved; do not silently edit their pinned inputs.

Git prepares one shared author worktree, isolated from the captain's checkout, from an exact `starting_ref` SHA and the ticket's exact `gitBranchName`. CoS handles dependency preparation and executable/build setup; Git handles only Git operations and normal commit hooks. Verify the expected scaffold already exists and preserve existing work. CoS moves the approved ticket to In Progress and preserves its metadata; tickets CoS creates or updates belong to the current SaaS cycle. Do not pick up another ticket automatically.

### 2. Build independently

Start a fresh test-writer and implementer with the same frozen spec and pinned baseline. Use one shared author worktree with strictly disjoint file ownership. Run them in parallel when the spec fixes shared interfaces. Their task context remains independent: no peer plans, reasoning, findings or newly authored files during the initial attempt. Read unchanged interfaces from the pinned baseline when a peer owns the current file; do not hand tests to the implementer as initial requirements. If a file needs both roles, CoS assigns one owner and sequences the handoff.

- Test-writer owns tests and test-only helpers. Test observable acceptance, meaningful invalid inputs, and relevant boundary cases through real product interfaces. A bug regression must fail on the baseline for the reported bug. Avoid implementation-shaped assertions, fake product surfaces, filler dependencies, and tests that pass when the behavior is absent.
- Implementer owns service code. Make the smallest change satisfying the spec and existing repository patterns. Run available relevant checks. Do not invent scaffolding, abstractions, or dependencies merely to quiet tests.

Before editing service code, the implementer returns a concise implementation plan to CoS and waits for its check. Name the modules to change, existing code to reuse, intended flow, relevant edge/failure handling, and checks. CoS compares the plan with frozen acceptance and architecture, rejects unnecessary complexity, and shares the plan with the captain before releasing implementation. A matching plan proceeds under the existing freeze approval, without another captain approval step. Missing guidance or a material change to agreed ownership, interfaces, state, dependencies, or trust boundaries requires discussion with the captain and an updated frozen spec before affected work proceeds. Routine internal choices within the agreed design stay with CoS and the implementer.

Keep the implementer's private plan out of the test-writer's inputs. Both authors use the agreed architecture in the frozen spec. If that architecture changes, provide both authors the updated pinned spec before affected work resumes. Tests remain grounded in observable acceptance and approved public contracts.

Assign explicit, non-overlapping file ownership. Both authors preserve all other edits and remain independent through their task inputs and permitted reads. Shared worktrees are not access controls; do not claim enforced filesystem isolation. CoS coordinates commands that mutate shared generated outputs and freezes both authors during commit hooks. Report artifacts, changed paths, commands, results, and blockers briefly; do not write a narrative for the next agent.

Keep an ordered series of small, focused changes during authoring and repairs. Each change should have one purpose that can be reviewed and reverted with its dependencies understood. Authors hand CoS immutable per-change patches or checkpoints, including new/deleted files, a message, ordering dependencies, and relevant check results. CoS routes commits through Git in the shared author worktree after both authors pause; authors perform no Git mutations. Git stages only the declared checkpoint paths and preserves other edits. Existing permitted source commits are the handoff when available. Do not wait until the entire feature is complete and hand over only its final file snapshot. Expected failing test checkpoints must state the failing behavior and required implementation dependency.

### 3. Integrate and get green

With the shared author worktree, Git commits each declared checkpoint in place; no extra author-to-integration replay is needed. If work already exists in separate worktrees, preserve it and integrate the supplied ordered artifacts without discarding history. Keep focused checkpoint and repair commits, record their mappings, and never squash them into one snapshot commit. CoS validates artifact completeness before dispatch; Git reports semantic conflicts to CoS and the owning author. Verify the combined tree against both complete author artifacts, including new and deleted files.

During repairs, run focused checks until the candidate is stable, then run the combined required gates once for that snapshot. Record a concrete new change, failure, or coverage gap before repeating a broad check. Independent acceptance still executes its assigned verification. Run the relevant tests, lint, type/build checks, and repository-required gates. Drive the changed user flow using the existing verification skill when applicable. The implementer may now inspect integrated tests as evidence; only the test-writer changes tests. Route a wrong test to its owner rather than adding product code to satisfy it. Stop on authentication failures such as pnpm 401; never add fake dependencies or silently skip gates.

Record the complete source snapshot: baseline SHA plus a content identity covering changed, deleted, and untracked source/test/config files. A clean commit tree SHA also works. Declare generated outputs separately. Reviews start only when required checks are green, with any unavailable evidence reported as a blocker.

Begin combined gates only after every active author explicitly declares the final artifact frozen. Verify final hashes after formatting; finding a patch file on disk does not establish a completed handoff. Check that restoration and flag assertions distinguish the required behavior from unchanged defaults or an unrelated enabled feature.

### 4. Review in parallel

Freeze source mutations. Two fresh reviewers inspect the same complete snapshot independently:

- `slice_spec_audit`: acceptance, scope, test validity, and independent verification. Map each criterion to evidence, check whether tests detect absent or incorrect behavior, and execute relevant checks itself in a scratch copy. Author-reported green is insufficient.
- `researcher`: regressions, affected callers, dependencies, invariants, and basic code quality. Trace beyond the changed lines and look for concrete counterexamples. Inspect the real behavior and identify missing regression coverage.

Add `arc` in this same parallel stage for architecture, ownership, dependency direction, public contracts, security boundaries, or sensitive fail-closed behavior changes, or when requested. Add `styla` when requested or substantial new structure requires a house-style judgment. Purely mechanical changes do not need Styla. These skills also work independently of this loop.

Each review returns PASS, FAIL, or BLOCKED, the snapshot identity, inspected scope, commands/evidence, and concrete findings. Every finding needs a file/location, violated criterion or existing invariant, observable consequence, and reproduction or decisive code evidence. Separate nonblocking preferences. PASS requires the assigned checks to be complete; unavailable runtime evidence is not PASS.

CoS collects one findings batch and removes duplicates. Route tests to test-writer and service code to implementer using the frozen criterion and reproducible factual evidence. Do not forward reviewer arguments, verdict narratives, or proposed solutions as requirements. CoS may dismiss an unsupported finding with a factual reason, but cannot waive a proven acceptance failure or silently change the freeze.

Authors may retain their own context for repairs within this slice. After changes, rerun affected checks and review lenses on a newly identified snapshot. Carry forward unaffected review evidence only when CoS records why its inputs and invariants remain valid. Shared ownership, contract, or invariant changes reopen all affected reviews. A targeted reviewer may receive the affected paths and original criterion, never another reviewer's reasoning. Enter the debugging stop above as soon as a repair loop is apparent, and no later than two unsuccessful repair rounds. Have the verifier classify the blocker and establish its cause before dispatching another patch. Escalate product ambiguity to the captain; do not start an endless fresh-agent carousel. House-style preferences get at most one repair pass.

### 5. Sign, draft, and await CI

Git alone signs and publishes the approved commit series on the captain's machine, in an isolated worktree. Preserve each commit boundary when replaying and signing; verify every signature and the source-to-published mapping. Confirm the final tree matches the tested/reviewed snapshot, including previously untracked files. Rebase, restack, or other content changes invalidate affected evidence before publication. New integration guidance does not authorize rewriting an already published stack; obtain explicit authorization for that history change.

Use Jarushan Naidoo <jarushan.naidoo@stitch.money> as author and committer, `git commit -S` with existing GPG configuration, and no agent trailers or Co-authored-by. Do not request or embed key IDs. CoS supplies a conventional PR title and exact description following the repository's current template. Git opens a draft with no reviewers and verifies its body and draft status.

Wait for required GitHub Actions to be green on the exact published SHA, including after repair or restack. Report the draft URL, tested/published identity, check results, and any remaining captain decision. A green draft is ready for captain review; it is not merged, landed, deployed, or Done. Never mark ready, enqueue, or merge without explicit captain authority. Respect any explicit repository-specific delivery instruction; do not infer a direct-to-main exception.

If the laptop is disconnected, CoS retains the unsigned queue and dispatches Git when it is available. No custom Git retry routines. Keep one slice moving through delivery before starting the next stacked slice.

## Learn after delivery

After each loop reaches its authorized delivery point, CoS updates `~/Developer/agent-definition/DELIVERY-LESSONS.md`. Record what failed, its cause, the responsible role, evidence, and a concrete prevention check. Distinguish a missing rule from a rule that was not enforced; update an existing entry for a recurrence. If nothing new failed, record that briefly without inventing a lesson.

Put reusable corrections in the owning workflow or role file, update the linked current prevention check in DELIVERY-CHECKLIST.md, and keep AGENTS.md as a short pointer. Preserve a matching backup and export affected installed copies. Do this within existing authorization; the learning step does not authorize product changes. Keep prevention unverified until later applicable work demonstrates it. CoS performs this closeout without adding an agent or approval gate.

## Context and cost controls

Every engineering agent starts with only its role, the frozen spec, repository rules, and explicitly permitted artifacts. Exclude HQ history, full-history forks, research narratives, peer messages, summaries, and verdicts. Authors initially see only the pinned baseline; reviewers see the immutable final tree and relevant existing callers. Git is an operational exception: refs, artifacts, signing constraints, and prepared PR content, with no product briefing.

Only CoS loads the full Feature loop. Each subagent loads its role instructions, frozen spec, repository rules, and permitted artifacts. Do not paste the workflow, other role definitions, CoS ledger, or peer reports into handoffs. Load Arc or Styla only for the assigned specialist review. Debug from first principles is the explicit exception available to subagents for failures within their existing permissions. CoS follows the coordination rules above and does not execute the debugging skill. A spec path must be accessible and pinned to its approved revision; read the spec itself before acting.

CoS maintains one small ledger outside the product source tree: spec revision, baseline/current snapshot, agent status, unresolved finding IDs, evidence paths, decisions, and next action. Aim for one page, with every blocker visible even if that takes more space. CoS reads detailed code or logs only to assess a concrete evidence gap, disagreement or delivery check; delegate failure diagnosis under the debugging rules above. Keep full artifacts in files instead of replaying them into chat.

Use these controls throughout the slice:

- **Focused reads:** search for specific symbols and paths, then read relevant sections. Expand inspection whenever correctness requires it. Re-read a file only after it changes or a new question requires it. Reviewers must still inspect relevant callers and complete their assigned coverage.
- **Bounded output:** save complete test/build logs in an authorized per-role evidence directory outside reviewed source. Return command, exit status, and relevant failure excerpts. Inspect further log sections when needed to diagnose; never treat truncated output as complete evidence. Preserve the actual command exit status when redirecting or piping output.
- **Concise handoffs:** aim for 300 words covering outcome, spec/snapshot identity, changed or inspected paths, executed checks, every blocker, and detailed evidence paths. Include enough facts to route each finding. If evidence cannot be saved or accessed, include necessary details in the result and disclose the limit; the target never justifies hiding failures. Keep evidence private to its role and CoS until permitted by the isolation rules.
- **Repairs as changes:** send the violated criterion and reproduction once to the existing owner. Followups identify changed paths, resolved and remaining finding IDs, new evidence, and new failures. Do not repeat complete prior reports or unchanged logs. A genuinely fresh replacement receives the necessary frozen criteria and factual reproductions in full, with no peer reasoning.
- **Context growth:** use available runtime telemetry to record each agent's starting active context after harness/role instructions load, then current and peak context at natural handoffs. Initial trial targets are 10-20k additional tokens for CoS and 30-50k per author or reviewer; Git should remain a narrow operation. Measure active context growth, separately from cumulative input/billed tokens. Mark unavailable values unknown; do not estimate them from word counts or repeatedly poll for telemetry.

Approaching a trial target means diagnose repeated reads, noisy output, repair churn, or excessive scope. These are diagnostic targets, not hard termination limits: preserve work and finish required checks. Never drop acceptance, silently split the frozen scope, or restart a worker merely to reset the meter. Log any mid-slice compaction and its observed cause, or mark the cause unknown. A skill cannot disable automatic compaction or remove material already read from context.

Prefer a fresh CoS execution context at feature boundaries when the harness supports it, restoring only the authorized spec, artifact references, and compact operational ledger. Do not spawn another orchestrator to evade context limits or discard the captain's unresolved decisions. If no fresh-context mechanism is available, say so when material and continue with selective reads; do not claim a reset happened.

Do not run routine outer interrogation, a separate verifier, duplicate code-style rewrites, or whole-repo verification maintenance. Create or maintain a verification skill as a separately authorized slice when needed. Use Unslop for prose without creating another agent gate.

Preserve role bindings unless the captain changes them. Every role runs on the active profile's binding (model, reasoning and service tier) for its capability: CoS `orchestrator`; Arc/`csa`, both default reviewers (`slice-spec-audit`, `researcher`) and the optional `reviewer` `adversarial_audit`; verifier `verify`; Styla `taste`; test-writer and implementer `implement`; Git `fast_narrow`. Architect and other unnamed architecture and audit invocations use the `adversarial_audit` binding. Bindings apply to initial work, followups, and retries. Never silently remap models, and never use Anthropic/Claude models in Stitch delivery whatever a profile says. If a binding is missing or unavailable, report it. `reviewer` is an optional architecture adviser and `verifier` is available for focused execution/diagnosis; neither is another default gate.

Save each agent's useful artifact/result before retirement. Use a close operation only when the harness actually exposes one. An interrupt stops work; it does not prove the agent was closed or its slot released. If close is unavailable, record that limit and avoid accumulating replacement agents. Do not fall back to a swarm to evade capacity limits. Never discard unlanded work during cleanup.

Measure elapsed time, token usage when available, repair rounds, and defects found at each gate across completed slices. Workflow simplification is not evidence that correctness or model efficiency improved.

## Harness notes: codex

Use fresh `fork_turns="none"` agents by configured spawn name: `test_writer`, `implementer`, `slice_spec_audit`, `researcher`, and `git`. Arc uses the existing `csa` role; Styla uses `styla`. Verify the tool's effective model bindings; never claim an override succeeded when the role definition fixed a different model. Capability bindings for unnamed launches are recorded in `~/.codex/agents/.agentpack-resolved` (written by the pack exporter from `profiles/codex.yaml`).
