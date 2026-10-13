#!/usr/bin/env python3
"""Version 6 DAG run folder: runs/<dag-id>/status.json.

The architect (orchestrator) is the only writer. Main reads `status` and
`list`, and sends `steer` messages; it never edits node state. Every command
prints a bounded summary so a detached DAG never needs the main chat.

Commands:
  init RUNS DAG_ID --contract FILE --actor ID
  status RUN [--json]            one DAG
  list RUNS                      every DAG under RUNS
  steer RUN --message TEXT --actor ID     Main -> architect queue
  ack-steer RUN STEER_ID --actor ID [--note TEXT]
  package RUN WP_ID --engineer ID --files PATH... --actor ID
  worktree RUN PATH --branch NAME --purpose PURPOSE --actor ID
  start RUN NODE [--package WP] --actor ID
  pass RUN NODE --evidence PATH [--package WP] --actor ID
  fail RUN NODE --finding TEXT --to OWNER --evidence PATH [--package WP] --actor ID
  bounce RUN --from ROLE --finding TEXT --evidence PATH --actor ID   (contract wrong)
  resolve RUN BOUNCE_ID --resolution TEXT --actor ID
  removed RUN PATH --branch-deleted yes|no|unmerged --actor ID
  enqueue-signing RUN --head SHA --pr-intent open|update --actor ID
                                 machine unavailable: gate-passed DAG -> queued-for-signing
  signing-queue RUNS             list the durable signing queue in drain order
  sign-next RUNS --observed-head SHA --actor SIGNER
                                 Git bot: take the next entry; matching head -> signed,
                                 mismatch -> bounce to the architect
  brief RUN NODE --input KIND=PATH... [--package WP] --actor ID
                                 validate a subagent brief against context.json
                                 (deny by default); required before start
"""

import argparse
import hashlib
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import tempfile

WORKFLOW = Path(__file__).resolve().parent.parent / "workflow.json"
CONTEXT = WORKFLOW.parent / "context.json"
GATE_ROLES = {"verifier", "slice_spec_audit", "styla", "arc", "csa"}
STATES = ("pending", "running", "pass", "fail", "blocked")
REQUIRED_CONTRACT = ("linear_issue", "spec_revision", "repo", "baseline", "branch", "checks", "ci_checks")


def now():
    return datetime.now(timezone.utc).isoformat()


def require(ok, message):
    if not ok:
        raise ValueError(message)


def load(run):
    return json.loads((Path(run) / "status.json").read_text())


def save(run, state):
    state["updated"] = now()
    path = Path(run) / "status.json"
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".status-")
    with os.fdopen(fd, "w") as handle:
        json.dump(state, handle, indent=2, sort_keys=True)
        handle.write("\n")
    os.replace(tmp, path)


def initialize(runs, dag_id, contract, actor):
    require(dag_id and "/" not in dag_id and not dag_id.startswith("."), "dag id must be one folder name")
    missing = [key for key in REQUIRED_CONTRACT if not contract.get(key)]
    require(not missing, f"frozen contract is missing {missing}; ask Jarushan before launch")
    require(contract.get("freeze_ready") is True,
            "freeze is too light for a DAG; ask Jarushan to complete the frozen Linear spec")
    run = Path(runs) / dag_id
    require(not (run / "status.json").exists(), "run already initialized; resume it instead")
    run.mkdir(parents=True, exist_ok=True)
    definition = json.loads(WORKFLOW.read_text())
    state = {
        "schema": 1, "version": definition["version"], "dag_id": dag_id, "architect": actor,
        "created": now(), "phase": "freeze_check", "contract": contract,
        "loop_cap": int(contract.get("loop_cap", definition["loop_cap"])), "gate_loops": 0,
        "nodes": {name: {"owner": spec["owner"], "needs": spec["needs"], "state": "pending", "attempts": 0}
                  for name, spec in definition["nodes"].items()},
        "packages": {}, "worktrees": {}, "bounces": [], "steer": [], "escalations": [],
        "cleanup": {"state": "not_started", "open": []},
    }
    save(run, state)
    return state


def actor_is_architect(state, actor):
    require(actor == state["architect"], "only the run's architect writes DAG state")


def gate_nodes(state):
    definition = json.loads(WORKFLOW.read_text())
    return [name for name, spec in definition["nodes"].items() if spec.get("gate")]


def phase(state):
    """Running nodes if any, else the first node not yet passed, else done."""
    running = [n for n, node in state["nodes"].items() if node["state"] == "running"]
    if running:
        return ",".join(running)
    return next((n for n, node in state["nodes"].items() if node["state"] != "pass"), "done")


def ready(state, name):
    return all(state["nodes"][need]["state"] == "pass" for need in state["nodes"][name]["needs"])


def add_package(state, wp, engineer, files):
    require(state["nodes"]["plan"]["state"] in ("running", "pass"), "packages come from the architect's plan")
    require(state["nodes"]["build"]["state"] == "pending", "packages are frozen once build starts")
    require(files, "a work package owns at least one file")
    owned = {path: other for other, pkg in state["packages"].items() for path in pkg["files"]}
    clash = sorted(path for path in files if path in owned and owned[path] != wp)
    require(not clash, f"file ownership must be disjoint; already owned: {clash}")
    state["packages"][wp] = {"engineer": engineer, "files": sorted(set(files)), "state": "pending",
                             "worktree": None}


def add_worktree(state, path, branch, purpose):
    require(path not in state["worktrees"], "worktree already registered; never reuse a stale worktree")
    if purpose != "integration":
        require(purpose in state["packages"], f"unknown work package {purpose!r}")
        state["packages"][purpose]["worktree"] = path
    state["worktrees"][path] = {"branch": branch, "purpose": purpose, "created": now(), "removed": False}
    state["cleanup"]["open"] = sorted(p for p, w in state["worktrees"].items() if not w["removed"])


def context():
    return json.loads(CONTEXT.read_text())


def brief_key(node, package):
    return f"{node}:{package}" if package else node


def engineer_findings(state, engineer, limit, max_bytes):
    """Bounced findings addressed to one engineer, verbatim, deduplicated, capped."""
    seen, out = set(), []
    for bounce in state["bounces"]:
        if bounce["to"] not in (engineer, "all"):
            continue
        key = (bounce["node"], bounce["finding"].strip())
        if key in seen:
            continue
        seen.add(key)
        out.append({"id": bounce["id"], "node": bounce["node"], "finding": bounce["finding"],
                    "evidence": bounce["evidence"]})
    data = json.dumps(out, indent=2).encode()
    require(len(out) <= limit and len(data) <= max_bytes,
            f"bounced findings for {engineer} exceed the handoff cap ({len(out)} findings, {len(data)} bytes); "
            "escalate instead of truncating")
    return out, data


def make_brief(state, run, node, inputs, package=None):
    """Validate a subagent brief against context.json. Deny by default, fail closed."""
    require(node in state["nodes"], f"unknown node {node!r}")
    ctx = context()
    role = state["nodes"][node]["owner"]
    require(role in ctx["roles"], f"no context allowlist for role {role!r}")
    rule = ctx["roles"][role]
    pkg = None
    if role == "senior_engineer":
        require(package in state["packages"], "an engineer brief names its work package")
        pkg = state["packages"][package]
    else:
        require(package is None, f"{role} briefs are not per package")
    run = Path(run).resolve()
    records, total = [], 0
    for kind, raw in inputs:
        require(kind in ctx["kinds"], f"unknown context kind {kind!r}; denied")
        require(kind in rule["allow"], f"{role} may not receive {kind}; allowed: {rule['allow']}")
        require(kind != "bounced_findings", "bounced findings are generated by dag_run.py, never hand-supplied")
        path = Path(raw).resolve()
        require(path.is_file(), f"{kind} input {raw} is not a file")
        if role in GATE_ROLES or role == "git":
            require(run not in path.parents and path.name not in ctx["architect_artifacts"],
                    f"{role} may not receive architect artifacts ({path.name})")
        if kind == "owned_files":
            require(any(str(path).endswith("/" + f.lstrip("/")) or str(path) == f for f in pkg["files"]),
                    f"{raw} is not owned by package {package}")
        size = path.stat().st_size
        require(size <= ctx["kinds"][kind]["max_bytes"],
                f"{kind} input is {size} bytes; cap is {ctx['kinds'][kind]['max_bytes']}")
        total += size
        records.append({"kind": kind, "path": str(path), "bytes": size,
                        "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    if pkg is not None:
        findings, data = engineer_findings(state, pkg["engineer"], ctx["max_findings"],
                                           ctx["kinds"]["bounced_findings"]["max_bytes"])
        if findings:
            out = run / "briefs" / f"{node}-{package}-findings.json"
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(data)
            total += len(data)
            records.append({"kind": "bounced_findings", "path": str(out), "bytes": len(data),
                            "sha256": hashlib.sha256(data).hexdigest(), "count": len(findings)})
    kinds = {r["kind"] for r in records}
    missing = [k for k in rule.get("required", []) if k not in kinds]
    require(not missing, f"{role} brief is missing required context {missing}")
    require(total <= rule["max_total_bytes"], f"{role} brief is {total} bytes; cap is {rule['max_total_bytes']}")
    brief = {"role": role, "inputs": records, "bytes": total, "created": now()}
    state["nodes"][node].setdefault("briefs", {})[brief_key(node, package)] = brief
    return brief


def start(state, node, package=None):
    require(node in state["nodes"], f"unknown node {node!r}")
    require(ready(state, node), f"{node} needs {state['nodes'][node]['needs']} to pass first")
    open_bounces = [b for b in state["bounces"] if b["state"] == "open"]
    require(not open_bounces or node in ("plan", "cleanup", "closeout"),
            "open bounce: the architect resolves it before dependent work continues")
    if node == "build":
        require(state["packages"], "plan has no work packages")
        missing = [wp for wp, pkg in state["packages"].items() if not pkg["worktree"]]
        require(not missing, f"git must create a fresh worktree for {missing}")
        if package:
            state["packages"][package]["state"] = "running"
    if node == "integrate":
        require(any(w["purpose"] == "integration" and not w["removed"] for w in state["worktrees"].values()),
                "git must create a fresh integration worktree")
    if node == "publish":
        require(state.get("signing", {}).get("state") != "queued",
                "DAG is queued for signing; the Git bot drains the queue when the machine is back")
    if node == "closeout":
        require(state["cleanup"]["state"] == "done", "closeout requires every worktree removed and pruned")
    item = state["nodes"][node]
    if item["owner"] != "architect":
        require(brief_key(node, package) in item.get("briefs", {}),
                f"{node} needs a validated brief (dag_run.py brief) before launch")
    if item["state"] != "running":
        item["attempts"] += 1
    item["state"] = "running"
    state["phase"] = phase(state)


def passed(state, node, evidence, package=None):
    require(evidence and Path(evidence).exists(), "pass needs a saved evidence path")
    item = state["nodes"][node]
    require(item["state"] == "running", f"{node} is not running")
    if node == "build":
        require(package in state["packages"], "build passes per work package")
        state["packages"][package]["state"] = "pass"
        state["packages"][package]["evidence"] = str(evidence)
        if all(pkg["state"] == "pass" for pkg in state["packages"].values()):
            item["state"] = "pass"
    else:
        if node == "cleanup":
            require(state["cleanup"]["state"] == "done", "cleanup passes only when no worktree remains open")
        item["state"] = "pass"
    item["evidence"] = str(evidence)
    state["phase"] = phase(state)


def reopen_from(state, node):
    """Reset node and every dependent so the graph stays acyclic per generation."""
    stack = [node]
    while stack:
        name = stack.pop()
        state["nodes"][name]["state"] = "pending"
        state["nodes"][name].pop("briefs", None)
        stack.extend(n for n, spec in state["nodes"].items() if name in spec["needs"]
                     and spec["state"] != "pending")


def failed(state, node, finding, to, evidence, package=None):
    require(evidence and Path(evidence).exists(), "a failure keeps its evidence")
    require(state["nodes"][node]["state"] == "running", f"{node} is not running")
    state["nodes"][node]["state"] = "fail"
    bounce = {"id": f"b{len(state['bounces']) + 1}", "node": node, "from": state["nodes"][node]["owner"],
              "to": to, "via": "architect", "finding": finding, "evidence": str(evidence),
              "created": now(), "state": "open"}
    if node in gate_nodes(state):
        state["gate_loops"] += 1
        if state["gate_loops"] > state["loop_cap"]:
            state["escalations"].append({"at": now(), "to": "HQ/Jarushan", "reason":
                                         f"gate loop cap {state['loop_cap']} exceeded", "bounce": bounce["id"]})
            bounce["state"] = "escalated"
    state["bounces"].append(bounce)
    if package:
        state["packages"][package]["state"] = "fail"
    state["phase"] = "bounced" if bounce["state"] == "open" else "escalated"
    return bounce


def contract_bounce(state, source, finding, evidence):
    require(evidence and Path(evidence).exists(), "a contract bounce keeps its evidence")
    bounce = {"id": f"b{len(state['bounces']) + 1}", "node": "plan", "from": source, "to": "architect",
              "via": "architect", "finding": finding, "evidence": str(evidence), "created": now(),
              "state": "open", "kind": "contract"}
    state["bounces"].append(bounce)
    state["phase"] = "bounced"
    return bounce


def resolve(state, bounce_id, resolution):
    bounce = next((b for b in state["bounces"] if b["id"] == bounce_id), None)
    require(bounce and bounce["state"] == "open", f"no open bounce {bounce_id}")
    bounce.update(state="resolved", resolution=resolution, resolved=now())
    if bounce.get("kind") == "contract":
        reopen_from(state, "plan")
    elif bounce["node"] in gate_nodes(state) or bounce["node"] == "integrate":
        reopen_from(state, "build")
        for pkg in state["packages"].values():
            if pkg["engineer"] == bounce["to"] or bounce["to"] == "all":
                pkg["state"] = "pending"
    else:
        reopen_from(state, bounce["node"])
    state["phase"] = phase(state)


def removed(state, path, branch_deleted):
    require(path in state["worktrees"], f"unregistered worktree {path!r}")
    queued = state.get("signing", {}).get("state") in ("queued", "signed")
    require(state["nodes"]["handoff"]["state"] == "pass" or state["escalations"] or queued,
            "worktrees are removed after handoff, while queued for signing, or when an escalated run is abandoned")
    require(branch_deleted in ("yes", "no", "unmerged"), "branch-deleted is yes, no or unmerged")
    state["worktrees"][path].update(removed=True, branch_deleted=branch_deleted, removed_at=now())
    state["cleanup"]["open"] = sorted(p for p, w in state["worktrees"].items() if not w["removed"])
    state["cleanup"]["state"] = "done" if not state["cleanup"]["open"] else "in_progress"


QUEUE = "signing-queue.json"


def queue_path(runs):
    return Path(runs) / QUEUE


def load_queue(runs):
    path = queue_path(runs)
    return json.loads(path.read_text()) if path.exists() else []


def save_queue(runs, entries):
    path = queue_path(runs)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".queue-")
    with os.fdopen(fd, "w") as handle:
        json.dump(entries, handle, indent=2)
        handle.write("\n")
    os.replace(tmp, path)


def drain_order(entries):
    """Oldest first, but a stacked child never precedes a queued parent branch."""
    pending = sorted(entries, key=lambda e: (e["enqueued"], e["dag_id"]))
    ordered = []
    while pending:
        queued = {e["branch"] for e in pending}
        nxt = next((e for e in pending if e.get("stack_parent") not in queued), pending[0])
        ordered.append(nxt)
        pending.remove(nxt)
    return ordered


def enqueue_signing(state, runs, head, pr_intent):
    require(state["nodes"]["csa_final"]["state"] == "pass", "only a gate-passed DAG is queued for signing")
    require(state["nodes"]["publish"]["state"] == "pending", "publish already started")
    require(len(head) == 40 and all(c in "0123456789abcdef" for c in head), "head must be an exact commit SHA")
    require(pr_intent in ("open", "update"), "pr intent is open or update")
    entries = load_queue(runs)
    require(all(e["dag_id"] != state["dag_id"] for e in entries), "DAG is already queued for signing")
    contract = state["contract"]
    entry = {"dag_id": state["dag_id"], "repo": contract["repo"], "branch": contract["branch"],
             "head_sha": head, "stack_parent": contract.get("stack_parent"), "pr_intent": pr_intent,
             "enqueued": now()}
    entries.append(entry)
    save_queue(runs, entries)
    state["signing"] = {"state": "queued", **entry}
    state["phase"] = "queued-for-signing"
    return entry


def sign_next(runs, observed_head, signer):
    """Git bot drains one entry: verify the head is unchanged before signing."""
    entries = load_queue(runs)
    require(entries, "signing queue is empty")
    entry = drain_order(entries)[0]
    run = Path(runs) / entry["dag_id"]
    state = load(run)
    entries = [e for e in entries if e["dag_id"] != entry["dag_id"]]
    if observed_head != entry["head_sha"]:
        state["signing"].update(state="mismatch", observed_head=observed_head, checked=now(), signer=signer)
        state["bounces"].append({"id": f"b{len(state['bounces']) + 1}", "node": "publish", "from": "git",
                                 "to": "architect", "via": "architect", "kind": "signing",
                                 "finding": f"queued head {entry['head_sha']} but branch is at {observed_head}",
                                 "evidence": str(queue_path(runs)), "created": now(), "state": "open"})
        state["phase"] = "bounced"
        result = "mismatch"
    else:
        state["signing"].update(state="signed", signed=now(), signer=signer)
        state["phase"] = "publish"
        result = "signed"
    save(run, state)
    save_queue(runs, entries)
    return result, entry


def summary(state):
    nodes = {name: node["state"] for name, node in state["nodes"].items()}
    return {
        "dag_id": state["dag_id"], "phase": state["phase"], "linear_issue": state["contract"]["linear_issue"],
        "nodes": nodes,
        "packages": {wp: pkg["state"] for wp, pkg in state["packages"].items()},
        "open_bounces": [{k: b[k] for k in ("id", "node", "to", "finding")}
                         for b in state["bounces"] if b["state"] == "open"],
        "gate_loops": f"{state['gate_loops']}/{state['loop_cap']}",
        "escalations": state["escalations"],
        "pending_steer": [s for s in state["steer"] if s["state"] == "pending"],
        "cleanup": state["cleanup"], "signing": state.get("signing", {}).get("state", "none"),
        "updated": state["updated"],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    def cmd(name, *positional):
        p = sub.add_parser(name)
        for arg in positional:
            p.add_argument(arg)
        return p
    p = cmd("init", "runs", "dag_id"); p.add_argument("--contract", required=True); p.add_argument("--actor", required=True)
    p = cmd("status", "run"); p.add_argument("--json", action="store_true")
    cmd("list", "runs")
    p = cmd("steer", "run"); p.add_argument("--message", required=True); p.add_argument("--actor", required=True)
    p = cmd("ack-steer", "run", "steer_id"); p.add_argument("--note", default=""); p.add_argument("--actor", required=True)
    p = cmd("package", "run", "wp"); p.add_argument("--engineer", required=True)
    p.add_argument("--files", nargs="+", required=True); p.add_argument("--actor", required=True)
    p = cmd("worktree", "run", "path"); p.add_argument("--branch", required=True)
    p.add_argument("--purpose", required=True); p.add_argument("--actor", required=True)
    for name in ("start", "pass", "fail"):
        p = cmd(name, "run", "node"); p.add_argument("--package"); p.add_argument("--actor", required=True)
        if name != "start":
            p.add_argument("--evidence", required=True)
        if name == "fail":
            p.add_argument("--finding", required=True); p.add_argument("--to", required=True)
    p = cmd("bounce", "run"); p.add_argument("--from", dest="source", required=True)
    p.add_argument("--finding", required=True); p.add_argument("--evidence", required=True)
    p.add_argument("--actor", required=True)
    p = cmd("resolve", "run", "bounce_id"); p.add_argument("--resolution", required=True); p.add_argument("--actor", required=True)
    p = cmd("enqueue-signing", "run"); p.add_argument("--head", required=True)
    p.add_argument("--pr-intent", required=True); p.add_argument("--actor", required=True)
    cmd("signing-queue", "runs")
    p = cmd("sign-next", "runs"); p.add_argument("--observed-head", required=True); p.add_argument("--actor", required=True)
    p = cmd("brief", "run", "node"); p.add_argument("--input", action="append", default=[], required=True)
    p.add_argument("--package"); p.add_argument("--actor", required=True)
    p = cmd("removed", "run", "path"); p.add_argument("--branch-deleted", required=True); p.add_argument("--actor", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "init":
            state = initialize(args.runs, args.dag_id, json.loads(Path(args.contract).read_text()), args.actor)
            print(json.dumps(summary(state), indent=2))
            return 0
        if args.command == "list":
            for status in sorted(Path(args.runs).glob("*/status.json")):
                s = json.loads(status.read_text())
                opened = sum(1 for b in s["bounces"] if b["state"] == "open")
                print(f"{s['dag_id']}\t{s['phase']}\tbounces={opened}\tcleanup={s['cleanup']['state']}\t{s['updated']}")
            return 0
        if args.command == "signing-queue":
            for entry in drain_order(load_queue(args.runs)):
                print(json.dumps(entry))
            return 0
        if args.command == "sign-next":
            result, entry = sign_next(args.runs, args.observed_head, args.actor)
            print(json.dumps({"result": result, **entry}))
            return 0 if result == "signed" else 3
        state = load(args.run)
        if args.command == "status":
            data = summary(state)
            print(json.dumps(data, indent=2) if args.json else
                  f"{data['dag_id']} phase={data['phase']} gate_loops={data['gate_loops']} "
                  f"open_bounces={len(data['open_bounces'])} steer={len(data['pending_steer'])} "
                  f"cleanup={data['cleanup']['state']}")
            return 0
        if args.command == "steer":
            require(args.actor != state["architect"], "steer comes from Main, not the architect")
            state["steer"].append({"id": f"s{len(state['steer']) + 1}", "at": now(), "by": args.actor,
                                   "message": args.message, "state": "pending"})
        else:
            actor_is_architect(state, args.actor)
            if args.command == "ack-steer":
                item = next((s for s in state["steer"] if s["id"] == args.steer_id), None)
                require(item and item["state"] == "pending", f"no pending steer {args.steer_id}")
                item.update(state="applied", note=args.note, applied=now())
            elif args.command == "package":
                add_package(state, args.wp, args.engineer, args.files)
            elif args.command == "worktree":
                add_worktree(state, args.path, args.branch, args.purpose)
            elif args.command == "start":
                start(state, args.node, args.package)
            elif args.command == "pass":
                passed(state, args.node, args.evidence, args.package)
            elif args.command == "fail":
                failed(state, args.node, args.finding, args.to, args.evidence, args.package)
            elif args.command == "bounce":
                contract_bounce(state, args.source, args.finding, args.evidence)
            elif args.command == "resolve":
                resolve(state, args.bounce_id, args.resolution)
            elif args.command == "enqueue-signing":
                enqueue_signing(state, Path(args.run).parent, args.head, args.pr_intent)
            elif args.command == "brief":
                pairs = []
                for item in args.input:
                    require("=" in item, f"--input expects KIND=PATH, got {item!r}")
                    pairs.append(tuple(item.split("=", 1)))
                brief = make_brief(state, args.run, args.node, pairs, args.package)
                save(args.run, state)
                print(json.dumps({"node": args.node, "package": args.package, "role": brief["role"],
                                  "bytes": brief["bytes"], "inputs": [r["kind"] for r in brief["inputs"]]}))
                return 0
            elif args.command == "removed":
                removed(state, args.path, args.branch_deleted)
        save(args.run, state)
        print(json.dumps(summary(state)["nodes"] if args.command in ("start", "pass") else summary(state)))
        return 0
    except (ValueError, KeyError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
