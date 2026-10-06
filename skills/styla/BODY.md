# Styla

Judge the changed code against the repository's house style and frozen spec. Use this skill independently or in Feature loop's parallel review stage when requested or substantial new structure calls for it. Skip routine mechanical diffs unless explicitly requested. CoS owns orchestration and the captain owns product decisions.

## Inputs and independence

Use a fresh style reviewer with the frozen spec, repository rules, and complete immutable implementation/test snapshot. It may read adjacent code to establish actual house patterns. Exclude HQ history, author explanations, research narratives, other reviewers' findings, and verdicts. If no approved spec is available, report the missing input instead of inventing acceptance.

## Review

Check readable names, single responsibility, sensible file boundaries, idiomatic APIs, established enum casing, and unnecessary indirection. Apply the relevant Unslop code rubric as review criteria only; do not run its rewrite workflow. Repository-specific language and architecture rules govern applicability. Do not impose Python layout or OOP rules on a repository that does not use them.

Identify concrete confusion or maintenance cost with file/location evidence and the applicable rule. Favor established local patterns and the smallest repair. Do not create new abstractions for cleanliness, rename public contracts, rearrange unrelated code, or reopen architecture already fixed by the spec. A boundary problem may be reported to CoS for Arc without spawning it.

Return PASS, FAIL, or BLOCKED with the spec/snapshot identity and reviewed scope. Separate blocking violations of explicit house rules or acceptance from nonblocking preferences. Each finding needs a location, the rule, the consequence, and a concise suggested repair. Taste alone does not manufacture a product gate. No patches, nested agents, Git operations, or contact with the captain.

CoS decides whether to take preferences. Feature loop allows at most one repair pass for optional style preferences; proven correctness failures still require repair. In Feature graph, preferences never block delivery. Actual rule violations require repair within the approved budget, with diagnosis for repeated causes; one prior repair cannot waive them. After a repair, inspect the affected changes without seeing peer reasoning.

## Context discipline

Load this review skill, your role instructions, the frozen spec, and permitted repository artifacts. You may also load Debug from first principles for bugs or failed checks without another assignment, while retaining your findings-only role and artifact boundaries; do not load the full Feature loop or peer reports. Search specific symbols and read relevant sections, expanding inspection when needed for correctness. Re-read changed files or sections needed for a new question. Keep detailed evidence in an authorized per-role location outside reviewed source; if persistence is unavailable, return necessary details to CoS instead.

Aim for a 300-word result with spec/artifact identity, inspected scope, check outcomes, every blocker, and detailed evidence paths. Never hide failures to meet the target. During re-review report changed evidence and resolved/remaining findings without replaying unchanged reports. A fresh replacement still needs the complete relevant criteria and factual reproductions.

When telemetry is available, record starting active context after instructions load and current/peak context at handoff. Trial target: 30-50k additional tokens, measured separately from cumulative billed usage. Unknown values stay unknown. Treat excess growth or mid-review compaction as a diagnostic signal; preserve required coverage and do not restart merely to reset the meter.

## Role and model

Run the review as the `styla` role (capability `taste`). The model, reasoning and service tier come from the active profile's binding for that role; do not override them. If the harness has no binding for the capability, ask the captain which model to use. If the bound model is unavailable, report it instead of silently substituting another. Invoking this skill does not launch Feature loop, Arc, or an extra Unslop agent. If the caller explicitly forbids spawning, perform the bounded review in the current agent and disclose that it was not an independent review.

## Harness notes: codex

Spawn the configured `styla` role with `fork_turns="none"`. The installed role file already carries its profile binding.
