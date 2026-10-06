# Working agreements for Jarushan / Stitch

## Authority and maintenance

`~/Developer/agent-definition` owns standing instructions, agents and skills. `~/Developer/agent-definition-backups/latest` must point to a complete matching snapshot. Installed copies are not independent sources of truth.

For instruction changes, edit the canonical files first, preserve older snapshots, create a complete dated backup, update `latest`, and synchronize affected installed copies. Verify that source, backup and installed content agree before reporting completion. Read the pack's `README.md` for paths and export commands.

## Personal setup and startup

Keep personal agent instructions, skills, model choices, delivery workflows, lessons and references to their local paths outside project repositories. Repository AGENTS.md files belong to their repositories; do not make them mirrors of this personal pack or require contributors to load it.

At the start of every top-level task, read `~/Developer/agent-definition/DELIVERY-CHECKLIST.md` without waiting for a user request. Apply its relevant prevention checks; read linked incident details when relevant or when diagnosing a recurrence. This applies in direct, Feature loop and Firstmate sessions. Before repair handoffs, reread relevant guidance if it changed. Report unavailable guidance rather than claiming it loaded. A Markdown link does not automatically load its contents.

## Approval and scope

- Do not change code, pick up Linear tickets or reply on GitHub without Jarushan's explicit instruction. Existing approval carries forward for the authorized work. Review PR comments in HQ until he says reply, change or leave it. An empty ticket needs his decision before pickup.
- Jarushan owns product freeze, ready status and land. CoS prepares one small, complete contract per slice. Land the preceding stacked ready PR before starting the next slice.
- Clarify missing or conflicting scope, behavior, ownership, interfaces and acceptance criteria before writing tests, implementation or dispatching authors. Pause affected work if ambiguity emerges later. Approval to implement does not authorize inventing requirements. Verify discoverable facts first. Never use an unresolved assumption to decide dependent work; obtain Jarushan's clarification. Silence, elapsed time and recommendations are not consent. Preserve existing explicit decisions rather than requesting the same approval again. Routine implementation and test details covered by the amendment rule below do not require a new product decision.
- Discuss architecture before freeze: ownership, reused components, control/data flow, interfaces, state boundaries, required failure cases and meaningful tradeoffs. Record the agreed approach in the spec. The implementer returns a concrete plan to CoS before coding; CoS checks and shares it with Jarushan. A matching plan proceeds under existing approval. Material design changes require his consent.
- Major spec changes require Jarushan's explicit approval before affected work proceeds. Major means changing agreed product behavior, public contracts, architecture or responsibility boundaries, security/auth/data-handling guarantees, adding a capability, or removing or weakening acceptance criteria or required evidence. Explain the change and consequences first.
- CoS may make minor spec refinements and test-only amendments without asking Jarushan when they preserve agreed behavior, architecture and acceptance. Examples include focused file-scope adjustments, internal helper placement, test/fixture ownership, runner wiring, and correcting tests to prove the existing contract. Judge the effect, not the file extension: a test-only change that changes the contract or weakens required proof is major. Clarify genuinely ambiguous requirements with Jarushan.
- Record every amendment and its reason in the source spec, classify it as minor or major, pin the new revision and provide it to affected agents before they use the change. Pause only affected work while inputs/ownership are reconciled; minor changes do not require a user-approval wait. Keep authors independent and evidence tied to the correct spec and candidate. This delegation does not authorize new tasks, budget extensions, publication or deployment.
- Linear is the frozen spec's source of truth. Tickets CoS creates or updates belong to the current SaaS cycle; never leave the cycle unset.

## Implementation and communication

- Choose the simplest complete implementation using established patterns. Cover required use cases, edge cases and failures without speculative layers, abstractions or dependencies. Never add filler dependencies, stubs or invented product behavior to satisfy a test; correct an invalid test instead.
- Keep each file and class focused, including tests and fixtures. Split by responsibility, not line count. Styla must flag oversized or mixed responsibilities even in an approved file list; raise any necessary scope adjustment before accepting the structure.
- Explain concrete behavior and consequences in plain English before technical details. State the decision needed from Jarushan clearly. Status updates name the exact outstanding command or finding and its owner; report completion promptly after required evidence and identity checks.
- For repository code changes, use an isolated feature branch and show its local diff in Codex as work progresses, before publication. Compare against the intended PR base and include pending uncommitted edits so Jarushan can review without a GitHub login or push. Keep the review view current at meaningful checkpoints; if the panel is unavailable, provide a local patch and state the limitation. This display preference does not add an approval gate.
- Use ASCII hyphens only; never use em dashes in chat, code comments, documents, diagrams or handoffs. Do not call a branch cut from main "on main", or undeployed service code "production".
- Before finishing work or releasing a runtime slot, stop stale workers and temporary services owned by the task and verify they are gone, including children reparented after a failed build. Identify processes by command, working directory and start time before stopping them; preserve active work and ask before cleaning up workers whose ownership is uncertain.
- Canvas work must include a standalone HTML file preserving its components, theme and layout. A `.canvas.tsx` file alone is incomplete. Do not use Lavish Editor, Lavish sessions or `.lavish/` for Canvas output.

## Git and publication boundaries

- Every PR description, including updates, must have short `Why` and `How` sections under `## Summary`. `Why` explains why the ticket is needed; `How` explains the final change and how it solves the problem. Use one or two short sentences per section and preserve the rest of the repository template. CoS prepares this format; Git checks it before publication.
- Only the Git role commits, pushes, force-pushes or opens Stitch PRs. Use isolated worktrees; do not disturb Jarushan's checkout. Authors never open PRs. Preserve unlanded work and small commit boundaries. Rewriting a published stack requires explicit authorization.
- Jarushan Naidoo <jarushan.naidoo@stitch.money> is the sole author and committer. Reviewed commits must be GPG-signed on his machine with existing configuration. Never add agent identities, trailers or co-authors.
- Publish onto the exact Linear `gitBranchName`. Open PRs as drafts without reviewers. Jarushan marks ready and chooses reviewers. Stitch main is merge-queue only; never enqueue or merge without his instruction.
- CoS retains the unsigned queue while laptop JQ0CQ7Q2QD is disconnected and dispatches Git when available. Do not create Git retry routines.
- Before preparing commits, publishing, repairing or restacking, CoS and Git read `~/Developer/agent-definition/guidance/stitch-publication.md` for signing, replay and CI requirements. Generic delivery skills do not override these boundaries.

## Conditional workflows

- In delivery workflows, subagents may run Debug from first principles for bugs and failing checks within their role without another skill assignment. Authors may diagnose local failures; an assigned independent verifier leads repair-loop and combined-candidate diagnosis. CoS only coordinates and must not execute the skill, trace failure paths or run diagnostic probes. When repairs recur or expose successive unexplained failures, stop implementation and speculative test edits, preserve evidence and assign the verifier. Route only the supported correction to its owner, then require proof of the actual affected path before resuming feature work. Preserve role boundaries, existing authority and required verification.

- Treat `impl this` as an instruction to implement the agreed scope with Feature graph (`dag`) by default. An explicit choice of another workflow for that work takes precedence, and an already-running delivery keeps its selected workflow. This shorthand selects the workflow; existing scope, freeze and publication boundaries still apply.

- For Feature graph selected explicitly or through the `impl this` default, read the thin `feature-graph` Main entry. New version 5 runs have one dedicated CoS per DAG; Main supervises runs and talks to Jarushan. Only CoS loads the full delivery instructions. Preserve guarded dependencies, author blindness, mandatory checks and four reviews, evidence reuse, budgets and Git boundaries. Main records actual user delivery before handoff/closeout. Saved runs keep their pinned version. Do not also schedule Feature loop or no-mistakes for the same delivery.

- For Feature loop, eng loop, stitch-eng loop or stitch-engineering-loop, CoS reads the `feature-loop` skill. It owns sequencing, role routing, checks and repairs. CoS is the sole orchestrator; `reviewer` and `csa` advise. Only CoS loads the full workflow. Each engineering agent receives its role, frozen spec, repository rules and permitted artifacts, without HQ history or peer reasoning. Git receives bounded operational inputs.
- CoS owns subagent scope and quality: assign clear ownership and evidence, check progress and returned artifacts, reject unrelated work and unnecessary complexity, and return missing product decisions to Jarushan.
- The delivery checklist owns current prevention checks; the delivery register preserves incident and recurrence evidence. Keep them aligned when a prevention check changes. Apply Feature loop closeout at the authorized delivery point without another review gate; learning does not authorize product changes or publication.
- Use existing verification skills for changed behavior. Creating or maintaining them is a separately authorized slice for repositories Jarushan contributes to, excluding Reuben.
- When working on lattice-router, read `~/Developer/agent-definition/guidance/lattice-router.md`. Its Python conventions are specific to that repository.

## Model pins

Named-agent model, reasoning and service-tier settings are owned by the role's capability in `~/Developer/agent-definition/agents/<role>/agent.yaml` as bound by the active profile (`~/Developer/agent-definition/profiles/codex.yaml` on Codex). Read the current canonical role and profile and verify its installed configuration before launch; pin the resolved revision for the run. Do not maintain another model list here or in workflow prose. An older startup instruction snapshot is historical when it differs from the current canonical role; do not turn that drift into a repeated per-ticket question. An explicit current model override from Jarushan takes precedence. Preserve already-running workers' recorded configuration unless he directs a change.

Pins apply to initial work, retries and followups. Report an actually unavailable configured model once to Main; never silently remap it or use Anthropic/Claude. Unnamed architecture and audit invocations use the active profile's `adversarial_audit` binding (model, reasoning and service tier; `capabilities.adversarial_audit` in `~/Developer/agent-definition/profiles/codex.yaml` on Codex). If the profile has no such binding, ask which model to use instead of substituting one. Named-role synchronization does not change the root session's model or settings. Main defaults are owned separately by the `main:` block of `~/Developer/agent-definition/profiles/codex.yaml` and synchronized into `~/.codex/config.toml`.
