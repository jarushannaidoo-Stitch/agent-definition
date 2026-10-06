"""Validate completion evidence before a graph node can pass."""

import re

import verification
import coordination

from evidence import committed_snapshot, file_record, git, require


def text(value, label):
    require(isinstance(value, str) and bool(value.strip()), f"Missing {label}")


def strings(value, label):
    require(isinstance(value, list) and bool(value), f"Missing {label}")
    for item in value:
        text(item, label)
    require(len(set(value)) == len(value), f"Duplicate {label}")


def sha(value, label):
    require(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", value),
            f"{label} must be a complete Git object ID")


def passing_checks(results, required):
    require(isinstance(results, list) and bool(results), "Checks need execution results")
    names, records = [], []
    for result in results:
        text(result.get("name"), "check name")
        text(result.get("command"), "executed command")
        require(type(result.get("exit_code")) is int and result["exit_code"] == 0,
                f"Check did not exit zero: {result['name']}")
        records.append(file_record(result["log"]))
        names.append(result["name"])
    require(len(set(names)) == len(names), "Duplicate check results")
    require(set(required) <= set(names), "Required checks are missing")
    return records


def validate(node, receipt, state):
    entry = state["nodes"][node]
    require(receipt.get("attempt") == entry["attempt"], "Stale or wrong attempt")
    require(receipt.get("generation") == entry["generation"], "Stale generation")
    require(receipt.get("snapshot") == entry.get("snapshot"), "Wrong candidate identity")
    require(receipt.get("spec_sha256") == state["spec"]["sha256"], "Wrong frozen spec")
    outcome = receipt.get("outcome")
    require(outcome in {"pass", "fail", "blocked"}, "Invalid outcome")
    text(receipt.get("summary"), "summary")
    strings(receipt.get("evidence"), "evidence paths")
    records = [file_record(path) for path in receipt["evidence"]]
    details = receipt.get("details", {})
    if state["version"] >= 2:
        records.extend(verification.receipt(node, outcome, details, state, passing_checks))
    if outcome != "pass":
        return records

    if state["version"] >= 5 and node in {"handoff", "closeout"}:
        records.append(coordination.require_delivery(state))
    contract = state["contract"]
    flags = {
        "prepare": ["scaffold_verified", "executables_verified", "ownership_disjoint"],
        "tests": ["stopped"],
        "seal_tests": ["artifact_verified", "baseline_inputs_only"],
        "plan": ["matches_freeze", "shared_with_user"],
        "implement": ["stopped"],
        "seal_implementation": ["artifact_verified", "baseline_inputs_only"],
        "capture": ["authors_stopped", "complete_artifacts_verified"],
        "reconcile": ["all_findings_resolved"],
        "publish": ["draft", "signatures_verified", "commit_series_preserved", "no_reviewers"],
        "handoff": ["user_notified"],
        "closeout": ["lessons_recorded", "pack_synchronized"],
    }
    for flag in flags.get(node, []):
        require(details.get(flag) is True, f"Required attestation missing: {flag}")
    if node == "prepare":
        require(details.get("baseline") == contract["baseline"], "Wrong prepared baseline")
    if node in {"tests", "implement"}:
        strings(details.get("checkpoints"), "ordered checkpoints")
    if node == "checks":
        records.extend(passing_checks(details.get("checks"), contract["checks"]))
    if node in {"acceptance", "verification", "regression", "arc", "styla"}:
        require(details.get("blocking_findings") == [], "Review has unresolved blockers")
        retained = entry.get("review_plan", {}).get("data", {}).get("mode") == "retain"
        if not retained:
            strings(details.get("inspected_paths"), "inspected paths")
        if node == "acceptance":
            strings(details.get("criteria_verified"), "verified acceptance criteria")
            records.extend(passing_checks(details.get("checks"), []))
    if node == "publish":
        head = details.get("head")
        sha(head, "Published head")
        require(git(contract["repo"], "rev-parse", "HEAD").decode().strip() == head,
                "Published head differs from local reviewed branch HEAD")
        require(committed_snapshot(contract["repo"], contract["baseline"], head) == state["candidate"],
                "Published commit does not contain the exact reviewed candidate")
        require(details.get("branch") == contract["branch"], "Wrong publication branch")
        url = details.get("url", "")
        require(isinstance(url, str) and re.fullmatch(r"https://[^\s]+/pull/[0-9]+", url),
                "Missing full draft PR URL")
    if node == "ci":
        published = state["nodes"]["publish"]["receipt"]["details"]
        require(details.get("head") == published["head"], "CI belongs to another head")
        require(git(contract["repo"], "rev-parse", "HEAD").decode().strip() == published["head"],
                "Local HEAD changed after publication")
        results = details.get("checks")
        require(isinstance(results, list) and bool(results), "Missing CI checks")
        names = []
        for result in results:
            names.append(result["name"])
            require(result.get("head") == published["head"], "CI check belongs to another head")
            require(result.get("conclusion") == "success", "CI check is not green")
            text(result.get("url"), "CI check URL")
        require(len(set(names)) == len(names), "Duplicate CI checks")
        require(set(contract["ci_checks"]) <= set(names), "Required CI checks are missing")
    return records
