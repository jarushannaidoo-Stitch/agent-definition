# Repo spec audit

Input is a **repo** (GitHub `owner/name` or URL). Optional: a git ref (default `origin/main` tip). Optional extra lenses the user names. Everything else the skill fetches.

The auditor is a **blank cloud agent**. It gets the spec and the tree. It does not get HQ chat, hop recaps, taste notes, or "what we just built". Report only. **Do not implement. Do not open a PR. Do not bounce an implementer.**

**Model is always the active profile's `adversarial_audit` binding** (model, reasoning and service tier). Adversarial. Pass that binding explicitly on the cloud-agent launch. Never use an automatic model picker or the account default, and never an Anthropic model (Stitch delivery rule). If the harness has no binding for the capability, ask which model to use; if the launcher cannot take the binding, report it instead of substituting.

## 1. Resolve the repo and the sha

- Confirm the repo exists on the connected host. Do not clone it onto the box or a laptop unless the user explicitly asked.
- Pin `starting_ref` to an exact sha (the default-branch tip, or the ref they named). Never the word `main`.
- If CI is the land gate for that repo, do not start until that sha is green, unless they asked to audit a red tree on purpose.

## 2. Fetch the full spec (do not invent it)

Pull from every connected source that is actually a contract for this repo. Concatenate. Dedup. Do not summarize away acceptance, non-goals, or fail-closed cases.

Typical sources, in order:

1. **Issue tracker (Linear when connected):** every frozen issue whose title/description names this repo or product. Frozen slice text is the source of truth, not chat. Include Done and In Progress slices; skip canceled. Prefer the ticket body over titles.
2. **In-repo contract docs at that sha:** root README, `docs/` that describe behavior/architecture, ADRs. Skip changelog noise and generated API dumps unless they are the contract.
3. **A spec the user pasted or linked in the same message.** That wins on conflict with older tickets.

If you cannot find a spec, stop and say so. Do not audit against HQ memory.

Optional user lenses (apply when named): e.g. **ignore `.env` / env-default docs noise** - still rate runnable honestly, but do not treat IDENTITY_MODE / PROVIDER stub default drift as a High finding unless boot is actually broken.

## 3. Dispatch a blank auditor

Launch a **new** cloud agent on that repo at the pinned sha. Fresh. One shot. **Always the `adversarial_audit` binding, passed explicitly.**

Prompt contains only:

- Role: auditor. Verdict only. No code. No PR. No commits.
- Repo URL and pinned sha.
- The full spec text (tickets + contract docs). Not a CoS recap.
- The question pack below, the **ratings pack**, plus any extra lenses the user named.
- Hard: ASCII hyphen only. Do not implement findings. Return a structured report. You run on the adversarial audit binding; stay adversarial.

Do not include: HQ transcript, implementer prompts, bounce logs, "we just landed X", personal taste, unfrozen hunches.

## 4. Question pack (always)

Answer each against the spec and the tree. Cite files/sha. Separate **fact** from **judgment**.

1. **Does it work?** Spec acceptance vs what the tree actually does. Missing slices, broken wiring, tests that do not cover the contract.
2. **Is it runnable?** Boot, env, local infra, documented how-to-run vs what the repo actually needs. A new engineer following README: yes or no, and where it lies.
3. **Are integrations correct?** Outbound calls hit the right systems and endpoints (provider SDKs, HTTP paths, queues, topics). Name the mismatch if the spec says one contract and the code calls another.
4. **Is the architecture accurate?** Tree vs frozen layout, ownership, planes, facades, fail-closed. Call out drift, not style nits.
5. **Will it scale?** Honest PoC-vs-production. Connection pools, hot-path work, shared failure domains, what breaks at 10x. Do not recommend a rewrite unless the spec already forbade the current path.

Skip empty sections. Do not pad.

## 5. Ratings pack (always)

Score each dimension **integer 0-10** (10 = excellent for that bar). Every score **must** include:

- **Score:** `N/10`
- **Why:** one short paragraph grounded in the tree + spec (cite paths)
- **Gaps to next point:** concrete missing work that would raise the score (or "none" if 10)

Do not give a score without gaps (except a true 10). Do not inflate because the PoC is "fine for now" - rate the named bar honestly.

| Dimension | What 10 means |
|---|---|
| **Architecture** | Layout, ownership, planes, facades, fail-closed, and boundaries match the frozen contract; no structural lies. |
| **Testing coverage** | Tests would catch real contract breaks (hexagon, persistence, Kafka/wire where required); not stub theater; CI actually exercises the critical paths. |
| **Prod readiness** | Ready to run as a production service for the stated product surface: ops, auth, failure domains, observability, deploy packaging, secrets, multi-instance safety. |
| **PoC level** | Fit as a proof of concept: demonstrates the core loop end-to-end with acceptable shortcuts called out as non-goals. |
| **MVP level** | Fit as a minimum viable product for first real users/tenants: enough correctness, operability, and contract fidelity to ship without shame. |
| **North-star level** | Fit versus the long-term target architecture and product north star in the spec (not "nice code"). |

Also give a one-line **overall verdict** (PASS / PARTIAL FAIL / FAIL against frozen acceptance) separate from the scores.

## 6. Deliver

Hand the auditor's report to the user as-is, plus a short CoS index (what to read first, including the ratings table). Do not patch. Do not open tickets from findings unless they ask. Do not start the next slice from this report.

If the auditor implements or opens a PR, that run is invalid. Close the PR, discard the tree, rerun with the same spec-only prompt on the same `adversarial_audit` binding.

## Harness notes: codex

Capability bindings for unnamed launches are recorded in `~/.codex/agents/.agentpack-resolved` (written by the pack exporter from `profiles/codex.yaml`). Use the `adversarial_audit` binding listed there for the auditor launch.
