"""Verification plans and evidence requirements for version 2 onward."""

import json
from pathlib import Path, PurePosixPath

from evidence import file_record, require


def nonempty(value, label):
    require(isinstance(value, str) and bool(value.strip()), f"Missing {label}")


def items(value, label, empty=False):
    require(isinstance(value, list) and (empty or bool(value)), f"Missing {label}")
    for item in value:
        nonempty(item, label)
    require(len(set(value)) == len(value), f"Duplicate {label}")


def plan(contract):
    record = file_record(contract["verification_plan"])
    data = json.loads(Path(record["path"]).read_text())
    items(data.get("criteria"), "planned acceptance criteria")
    items(data.get("checks"), "independent verification checks")
    require(data.get("kind") in {"bug", "feature"}, "Choose bug or feature evidence rules")
    require(type(data.get("defer_new_boundary")) is bool, "Decide whether new boundary proof is deferred")
    require(data["kind"] != "bug" or not data["defer_new_boundary"], "Bug regression proof cannot be deferred")
    nonempty(data.get("early_proof"), "early proof approach and required harness")
    nonempty(data.get("final_proof"), "final runtime evidence plan")
    paths = contract.get("test_paths")
    items(paths, "approved test paths", empty=True)
    for path in paths:
        pure = PurePosixPath(path)
        require(not pure.is_absolute() and '..' not in pure.parts and pure.as_posix() == path
                and path != '.', "Test ownership requires exact relative file paths")
    return {"record": record, "data": data}


def receipt(node, outcome, details, state, passing_checks):
    records = []
    reuse = state["version"] >= 4 and state["nodes"][node].get("review_plan")
    reviews = {"verification", "regression", "arc", "styla"}
    if node in reviews:
        items(details.get("coverage_completed"), "completed review coverage", empty=True)
        items(details.get("coverage_remaining"), "unfinished review coverage", empty=True)
        if outcome == "pass" and not reuse:
            require(details["coverage_completed"] and not details["coverage_remaining"],
                    "An interrupted or incomplete review cannot pass")
        elif outcome != "pass":
            routing = details.get("repair", {})
            require(routing.get("target") in {"tests", "implement", "both", "plan", "checks",
                                               "spec", "environment", "review"},
                    "Return the recommended repair owner to CoS")
            nonempty(routing.get("criterion"), "failed criterion or interrupted coverage")
            nonempty(routing.get("reason"), "repair evidence and consequence")
    if reuse:
        import review_reuse
        return review_reuse.receipt(node, outcome, details, state, passing_checks)
    if outcome != "pass":
        return records
    if node == "prepare":
        for flag in ("decisions_resolved", "budget_approved", "verification_plan_approved"):
            require(details.get(flag) is True, f"Required attestation missing: {flag}")
    evidence_plan = state["verification_plan"]["data"]
    if node == "tests":
        proof = details.get("early_proof", {})
        require(proof.get("baseline") == state["contract"]["baseline"], "Early proof needs the exact baseline")
        nonempty(proof.get("result"), "early proof result")
        if evidence_plan["kind"] == "bug":
            require(proof.get("behavior_failure") is True, "Prove the behavior failure, not a setup failure")
            nonempty(proof.get("command"), "baseline regression command")
            require(type(proof.get("exit_code")) is int and proof["exit_code"] != 0,
                    "Bug regression must fail on the buggy baseline")
            records.append(file_record(proof["log"]))
        else:
            records.extend(passing_checks(proof.get("checks"), []))
            if evidence_plan["defer_new_boundary"]:
                nonempty(proof.get("unavailable"), "unavailable new boundary and deferred proof")
            else:
                require(proof.get("behavior_proven") is True, "Complete the approved early feature proof")
    if node == "verification":
        require(set(details.get("criteria_verified", [])) == set(evidence_plan["criteria"]),
                "Verification must cover every frozen criterion")
        items(details.get("paths_traced"), "actual code paths traced")
        for flag in ("first_principles_audit", "test_validity_reviewed"):
            require(details.get(flag) is True, f"Required attestation missing: {flag}")
        if evidence_plan["defer_new_boundary"]:
            require(details.get("deferred_proof_completed") is True, "Deferred runtime proof is still required")
        records.extend(passing_checks(details.get("checks"), evidence_plan["checks"]))
    return records
