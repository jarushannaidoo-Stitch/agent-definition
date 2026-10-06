"""Elapsed slice budget, explicit external waits, and approved extensions."""

from datetime import datetime
import json
from pathlib import Path

from evidence import file_record, require, verify_record


def instant(value):
    parsed = datetime.fromisoformat(value)
    require(parsed.tzinfo is not None, "Budget timestamps need a timezone")
    return parsed


def initialize(contract, timestamp):
    seconds = contract.get("budget_seconds")
    require(type(seconds) is int and seconds > 0, "Approve a positive per-slice budget_seconds")
    started = contract.get("budget_started_at")
    require(isinstance(started, str), "Record budget_started_at including prior slice work")
    require(instant(started) <= instant(timestamp), "Budget cannot start in the future")
    checkpoint = contract.get("review_checkpoint_seconds")
    require(type(checkpoint) is int and 0 < checkpoint <= seconds,
            "Approve review_checkpoint_seconds within the slice budget")
    result = {"seconds": seconds, "started": started, "waits": [], "extensions": [],
              "inactive": [], "predecessors": []}
    if contract.get("budget_previous_run"):
        record = file_record(contract["budget_previous_run"])
        previous = json.loads(Path(record["path"]).read_text())
        require(previous.get("version") in {2, 3, 4, 5}, "Budget carry-forward needs a version 2 through 5 run")
        require(not any(entry["status"] == "running" for entry in previous["nodes"].values()),
                "Stop previous run workers before carrying its budget forward")
        verify(previous)
        require(previous["budget"]["started"] == started, "Carry the original budget start forward")
        reopen(previous, timestamp)
        result = previous["budget"]
        result["seconds"] = seconds
        result["predecessors"].append(record)
    return result


def report(state, timestamp):
    budget = state["budget"]
    end = instant(timestamp)
    if state["nodes"]["closeout"]["status"] == "pass":
        end = instant(state["nodes"]["closeout"]["finished"])
    elapsed = max(0, (end - instant(budget["started"])).total_seconds())
    waits = {"user": 0, "external_ci": 0}
    for wait in budget["waits"]:
        stop = min(end, instant(wait["finished"]) if "finished" in wait else end)
        waits[wait["kind"]] += max(0, (stop - instant(wait["started"])).total_seconds())
    inactive = sum(max(0, (min(end, instant(item["finished"])) - instant(item["started"])).total_seconds())
                   for item in budget["inactive"])
    active = max(0, elapsed - sum(waits.values()) - inactive)
    return {"total_seconds": elapsed, "active_seconds": active, "wait_seconds": waits,
            "inactive_seconds": inactive,
            "budget_seconds": budget["seconds"], "remaining_seconds": budget["seconds"] - active,
            "waiting": bool(budget["waits"] and "finished" not in budget["waits"][-1])}


def reopen(state, timestamp):
    if state["version"] < 2 or state["nodes"]["closeout"]["status"] != "pass":
        return
    finished = state["nodes"]["closeout"]["finished"]
    state["budget"]["inactive"].append({"started": finished, "finished": timestamp})


def verify(state):
    for record in state["budget"]["predecessors"]:
        verify_record(record)
    for wait in state["budget"]["waits"]:
        verify_record(wait["evidence"])
    for extension in state["budget"]["extensions"]:
        verify_record(extension["approval"])


def available(state, timestamp):
    if state["version"] == 1:
        return
    timing = report(state, timestamp)
    require(not timing["waiting"], "End the recorded external wait before dispatch")
    require(timing["remaining_seconds"] > 0, "Slice budget exhausted; request an approved extension")


def wait(state, kind, evidence, timestamp):
    require(state["version"] >= 2, "Wait accounting applies only to version 2 through 5 runs")
    require(kind in {"user", "external_ci", "end"}, "Unknown wait kind")
    waits = state["budget"]["waits"]
    open_wait = bool(waits and "finished" not in waits[-1])
    if kind == "end":
        require(open_wait, "No external wait is open")
        waits[-1]["finished"] = timestamp
    else:
        require(not open_wait, "An external wait is already open")
        require(state["nodes"]["closeout"]["status"] != "pass",
                "Completed runs already exclude dormant time; reopen before recording a wait")
        running = [n for n, e in state["nodes"].items() if e["status"] == "running"]
        require(not running or (kind == "external_ci" and running == ["ci"]),
                "Stop internal workers before excluding an external wait")
        require(kind != "external_ci" or state["nodes"]["publish"]["status"] == "pass",
                "External CI wait requires publication")
        waits.append({"kind": kind, "started": timestamp, "evidence": file_record(evidence)})
    return report(state, timestamp)


def extend(state, seconds, approval, timestamp):
    require(state["version"] >= 2, "Budget extensions apply only to version 2 through 5 runs")
    require(type(seconds) is int and seconds > state["budget"]["seconds"],
            "Extension must increase the total budget")
    record = file_record(approval)
    state["budget"]["extensions"].append({"at": timestamp, "previous_seconds": state["budget"]["seconds"],
                                           "seconds": seconds, "approval": record})
    state["budget"]["seconds"] = seconds
    return report(state, timestamp)
