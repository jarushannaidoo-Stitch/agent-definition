"""Graph state transitions. The coordinator executes work outside this guard."""

from datetime import datetime, timezone
import json
from pathlib import Path
import uuid

import endpoints
import budget
import verification
import review_reuse
import coordination

from evidence import digest, file_record, git, require, snapshot, verify_record
from receipts import passing_checks, sha, strings, text, validate


WORKFLOW = Path(__file__).resolve().parent.parent / "workflow.json"
LEGACY_WORKFLOW = WORKFLOW.parent / "references/v1/workflow.json"
V2_WORKFLOW = WORKFLOW.parent / "references/v2/workflow.json"
V3_WORKFLOW = WORKFLOW.parent / "references/v3/workflow.json"
V4_WORKFLOW = WORKFLOW.parent / "references/v4/workflow.json"


def now():
    return datetime.now(timezone.utc).isoformat()


def initialize(contract):
    repo = str(Path(contract["repo"]).expanduser().resolve(strict=True))
    require(git(repo, "rev-parse", "--show-toplevel").decode().strip() == repo,
            "repo must name the worktree root")
    contract = {**contract, "repo": repo}
    sha(contract.get("baseline"), "Baseline")
    require(git(repo, "rev-parse", contract["baseline"] + "^{commit}").decode().strip()
            == contract["baseline"], "Baseline must be an exact commit")
    endpoint = endpoints.validate(contract.get("endpoint", "draft"))
    text(contract.get("branch"), "approved branch")
    strings(contract.get("checks"), "required local checks")
    strings(contract.get("ci_checks"), "required CI checks")
    graph_bytes = WORKFLOW.read_bytes()
    definition = json.loads(graph_bytes)
    version = definition["version"]
    for name in ("arc", "styla"):
        decision = contract.get(name, {})
        require(type(decision.get("required")) is bool, f"Decide whether {name} applies")
        text(decision.get("reason"), f"{name} applicability reason")
        require(version == 1 or decision["required"], f"{name} is mandatory in versions 2 through 5")
    graph = definition["nodes"]
    state = {
        "version": version, "created": now(), "generation": 1, "repairs": 0,
        "endpoint": endpoint,
        "contract": contract, "spec": file_record(contract["spec"]),
        "approval": file_record(contract["approval"]),
        "workflow_sha256": digest(graph_bytes), "graph": graph,
        "nodes": {name: {"status": "omitted" if rule.get("optional")
                   and not contract[name]["required"] else "pending"}
                  for name, rule in graph.items()},
        "history": [], "candidate": None,
    }
    if version >= 2:
        state["budget"] = budget.initialize(contract, state["created"])
        state["verification_plan"] = verification.plan(contract)
    if version >= 5:
        state["coordination"] = coordination.initialize(contract)
    return state


def verify_run_inputs(state):
    require(state.get("version") in {1, 2, 3, 4, 5}, "Unsupported state version")
    definition = {1: LEGACY_WORKFLOW, 2: V2_WORKFLOW, 3: V3_WORKFLOW, 4: V4_WORKFLOW, 5: WORKFLOW}[state["version"]]
    require(state["workflow_sha256"] == digest(definition.read_bytes()),
            "Workflow definition changed; keep the run's original skill version")
    require(state["graph"] == json.loads(definition.read_bytes())["nodes"], "Recorded graph changed")
    if state["version"] >= 2:
        verify_record(state["verification_plan"]["record"])
        require(state["verification_plan"] == verification.plan(state["contract"]), "Verification plan changed")
        budget.verify(state)
    coordination.verify(state)
    verify_record(state["spec"])
    verify_record(state["approval"])
    endpoints.current(state)
    if "endpoint_approval" in state:
        verify_record(state["endpoint_approval"])


def verify(state, check_source=True):
    verify_run_inputs(state)
    if state["version"] >= 2 and state.get("preserved_implementation"):
        verify_record(state["preserved_implementation"]["evidence"])
    for entry in state["nodes"].values():
        if entry.get("review_plan"):
            for record in review_reuse.records(entry["review_plan"]):
                verify_record(record)
        if entry["status"] == "pass":
            for record in entry["evidence"]:
                verify_record(record)
    if check_source and state["candidate"]:
        current = snapshot(state["contract"]["repo"], state["contract"]["baseline"])
        require(current == state["candidate"], "Source changed; create a repair generation")
    published = state["nodes"]["publish"]
    if check_source and published["status"] == "pass":
        head = git(state["contract"]["repo"], "rev-parse", "HEAD").decode().strip()
        require(head == published["receipt"]["details"]["head"],
                "HEAD changed; refresh publication and exact-head CI")


def select_endpoint(state, endpoint, approval):
    verify(state)
    return endpoints.select(state, endpoint, approval, now())


def unmet(state, node):
    return [name for name in endpoints.prerequisites(state, node)
            if state["nodes"][name]["status"] not in {"pass", "omitted"}]


def start(state, node, worker):
    verify(state)
    require(node in state["graph"], "Unknown node")
    require(endpoints.enabled(state, node), "Publication is disabled at the local endpoint")
    entry = state["nodes"][node]
    if entry["status"] == "running" and entry["worker"] == worker:
        return entry
    budget.available(state, now())
    require(entry["status"] == "pending", "Node is not pending; inspect or repair first")
    require(not unmet(state, node), "Unmet prerequisites: " + ", ".join(unmet(state, node)))
    running = [name for name, value in state["nodes"].items() if value["status"] == "running"]
    require(not running or (state["graph"][node].get("parallel") and
                            all(state["graph"][name].get("parallel") for name in running)),
            "Exclusive node already running: " + ", ".join(running))
    text(worker, "worker identity")
    entry.update(status="running", worker=worker, attempt=uuid.uuid4().hex,
                 generation=state["generation"], started=now(),
                 snapshot=state["candidate"]["sha256"] if state["candidate"] else None)
    return entry


def complete(state, node, receipt):
    require(node in state["graph"], "Unknown node")
    entry = state["nodes"][node]
    if entry.get("receipt") == receipt:
        verify(state)
        return entry
    require(entry["status"] == "running", "Node is not running")
    # A failed result cannot release a successor. Record it even when earlier
    # evidence drifted so a stopped worker does not remain permanently running.
    if receipt.get("outcome") == "pass":
        verify(state)
        coordination.require_commands_stopped(state, node)
    records = validate(node, receipt, state)
    if node == "capture" and receipt["outcome"] == "pass":
        candidate = snapshot(state["contract"]["repo"], state["contract"]["baseline"])
        require(candidate == snapshot(state["contract"]["repo"], state["contract"]["baseline"]),
                "Source changed while capturing candidate")
        if state.get("preserved_implementation"):
            allowed = set(state["contract"]["test_paths"])
            unchanged = [row for row in candidate["files"] if row[0] not in allowed]
            require(unchanged == state["preserved_implementation"]["files"],
                    "Tests-only repair changed implementation; reopen the owning author")
        state["candidate"] = candidate
    if entry.get("review_plan"):
        entry["validated_coverage"] = review_reuse.coverage(entry["review_plan"], receipt["details"])
    entry.update(status=receipt["outcome"], finished=now(), receipt=receipt, evidence=records)
    entry["duration_seconds"] = (datetime.fromisoformat(entry["finished"]) -
                                  datetime.fromisoformat(entry["started"])).total_seconds()
    return entry


def configure_review(state, node, assessment):
    require(state.get("version") in {4, 5}, "Review reuse requires a version 4 or 5 run")
    verify(state)
    require(node in review_reuse.REVIEWS, "Only reviews support evidence reuse")
    require(state["candidate"] and state["nodes"][node]["status"] == "pending",
            "Capture the candidate before assigning a pending review")
    require(not state["nodes"][node].get("review_plan"), "Review plan already pinned")
    require(not unmet(state, node), "Review prerequisites are incomplete")
    budget.available(state, now())
    plan = review_reuse.build(state, node, assessment, passing_checks)
    state["nodes"][node]["review_plan"] = plan
    if plan["data"]["mode"] == "retain":
        entry = start(state, node, "cos-retained-review")
        receipt = {"attempt": entry["attempt"], "generation": entry["generation"],
                   "snapshot": entry["snapshot"], "spec_sha256": state["spec"]["sha256"],
                   "outcome": "pass", "summary": plan["data"]["reason"],
                   "evidence": [plan["record"]["path"]],
                   "details": {"retained_from": plan["data"]["prior_attempt"],
                               "coverage_completed": [], "coverage_remaining": [],
                               "blocking_findings": []}}
        return complete(state, node, receipt)
    return state["nodes"][node]


def has_repair_cause(state, cause):
    if any(item.get("cause") == cause for item in state["history"]):
        return True
    for record in state["budget"]["predecessors"]:
        verify_record(record)
        previous = json.loads(Path(record["path"]).read_text())
        if any(item.get("cause") == cause for item in previous["history"]):
            return True
    return False


def repair(state, node, reason, diagnosis=None, cause=None, preservation=None):
    coordination.require_commands_stopped(state)
    allowed = {"prepare", "tests", "plan", "implement", "checks", "acceptance",
               "regression", "arc", "styla", "publish", "ci", "handoff", "closeout", "verification"}
    require(node in allowed and node in state["nodes"] and state["nodes"][node]["status"] != "omitted",
            "Choose an enabled retryable graph node")
    require(not any(e["status"] == "running" for e in state["nodes"].values()),
            "Record stopped workers before repair; never duplicate live work")
    require(state["nodes"][node]["status"] != "pending", "Node has not run yet")
    text(reason, "factual repair reason")
    budget.available(state, now())
    if state["version"] == 1:
        require(not preservation and not cause, "Version 1 runs retain original repair rules")
        require(state["repairs"] < 2 or diagnosis, "Diagnosis evidence required after two repair rounds")
    else:
        text(cause, "stable repair cause")
        repeated = has_repair_cause(state, cause)
        require(not repeated or diagnosis, "Diagnosis evidence required for a repeated cause")
    diagnosis_record = file_record(diagnosis) if diagnosis else None
    reset = {node}
    if state["version"] >= 3 and node == "tests" and not preservation:
        reset.add("plan")
    for _ in state["graph"]:
        reset.update(name for name, rule in state["graph"].items()
                     if set(rule["needs"]) & reset)
    retained = None
    if preservation:
        require(node == "tests" and (state["candidate"] or state.get("preserved_implementation")),
                "Tests-only retention needs a captured candidate or prior valid retention")
        verify(state)
        for name in ("plan", "implement", "seal_implementation"):
            require(state["nodes"][name]["status"] == "pass", "Implementation stages must be valid passes")
        current = snapshot(state["contract"]["repo"], state["contract"]["baseline"])
        files = [row for row in current["files"] if row[0] not in set(state["contract"]["test_paths"])]
        if not state["candidate"]:
            require(files == state["preserved_implementation"]["files"],
                    "Tests-only retry changed implementation; reopen the owning author")
        retained = {"evidence": file_record(preservation), "files": files}
        reset.difference_update({"plan", "implement", "seal_implementation"})
    if "capture" not in reset and state["candidate"]:
        require(snapshot(state["contract"]["repo"], state["contract"]["baseline"])
                == state["candidate"], "Changed source requires an author repair")
    budget.reopen(state, now())
    old = {name: state["nodes"][name] for name in reset}
    state["history"].append({"generation": state["generation"], "at": now(),
                             "reason": reason, "from": node, "diagnosis": diagnosis_record,
                             "cause": cause, "preservation": retained,
                             "nodes": old, "candidate": state["candidate"]})
    for name in reset:
        state["nodes"][name] = {"status": "omitted" if old[name]["status"] == "omitted" else "pending"}
    if "capture" in reset:
        state["candidate"] = None
        if retained:
            state["preserved_implementation"] = retained
        elif node in {"prepare", "tests", "plan", "implement"}:
            state.pop("preserved_implementation", None)
    if state["version"] >= 5:
        for row in state["coordination"]["commands"].values():
            if row["node"] in reset and row["status"] == "waiting":
                row["status"] = "superseded"
    state["generation"] += 1
    state["repairs"] += 1
    verify(state, check_source=False)
    return {"generation": state["generation"], "invalidated": sorted(reset)}


def status(state):
    problems = []
    try:
        verify(state)
    except (ValueError, OSError) as error:
        problems.append(str(error))
    timing = budget.report(state, now()) if state["version"] >= 2 else None
    if timing and state["nodes"]["closeout"]["status"] != "pass":
        try:
            budget.available(state, now())
        except ValueError as error:
            problems.append(str(error))
    running = [n for n, e in state["nodes"].items() if e["status"] == "running"]
    ready = [n for n, e in state["nodes"].items() if e["status"] == "pending"
             and endpoints.enabled(state, n) and not unmet(state, n)
             and (not running or (state["graph"][n].get("parallel") and
                  all(state["graph"][r].get("parallel") for r in running)))]
    return {"coordination": state.get("coordination"),
            "generation": state["generation"], "repairs": state["repairs"],
            "endpoint": state.get("endpoint", "draft"),
            "complete": not problems and state["nodes"]["closeout"]["status"] == "pass",
            "timing": timing,
            "candidate": state["candidate"]["sha256"] if state["candidate"] else None,
            "ready": [] if problems else ready, "problems": problems, "nodes": state["nodes"]}
