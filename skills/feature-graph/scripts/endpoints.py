"""Delivery endpoint selection and recorded user steering."""

import budget
import coordination

from evidence import file_record, require


def validate(value):
    require(value in {"local", "draft"}, "Endpoint must be local or draft")
    return value


def current(state):
    return validate(state.get("endpoint", "draft"))


def enabled(state, node):
    return current(state) == "draft" or node not in {"publish", "ci"}


def prerequisites(state, node):
    if current(state) == "local" and node == "handoff":
        return ["reconcile"]
    return state["graph"][node]["needs"]


def select(state, endpoint, approval, timestamp):
    validate(endpoint)
    coordination.require_commands_stopped(state)
    require(not any(e["status"] == "running" for e in state["nodes"].values()),
            "Record stopped workers before changing the endpoint")
    record = file_record(approval)
    previous = current(state)
    if endpoint == previous:
        return {"endpoint": endpoint, "generation": state["generation"], "invalidated": []}
    budget.reopen(state, timestamp)
    reset = ("handoff", "closeout")
    state["history"].append({
        "kind": "endpoint", "generation": state["generation"], "at": timestamp,
        "from": previous, "to": endpoint, "approval": record,
        "previous_approval": state.get("endpoint_approval", state["approval"]),
        "nodes": {name: state["nodes"][name] for name in reset},
    })
    for name in reset:
        state["nodes"][name] = {"status": "pending"}
    state["endpoint"] = endpoint
    state["endpoint_approval"] = record
    state["generation"] += 1
    return {"endpoint": endpoint, "generation": state["generation"], "invalidated": list(reset)}
