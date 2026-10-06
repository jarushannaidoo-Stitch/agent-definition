"""Native lifecycle identities and user delivery, stored with the existing graph."""

from pathlib import Path

from evidence import file_record, require, verify_record


def nonempty(value, label):
    require(isinstance(value, str) and bool(value.strip()), f"Missing {label}")
    return value


def initialize(contract):
    value = contract.get("coordination", {})
    main = nonempty(value.get("main"), "Main native identity")
    cos = nonempty(value.get("cos"), "CoS native identity")
    require(main != cos, "Each new DAG needs a dedicated CoS")
    lock = Path(nonempty(value.get("heavy_lock"), "shared command lock")).expanduser().resolve()
    require(not lock.is_relative_to(Path(contract["repo"])), "Command lock must stay outside product source")
    return {"main": main, "cos": cos, "roles": file_record(value["roles"]),
            "admission": file_record(value["admission"]), "heavy_lock": str(lock),
            "replacements": [], "commands": {}, "deliveries": []}


def verify(state):
    if state["version"] >= 5:
        for key in ("roles", "admission"):
            verify_record(state["coordination"][key])


def authorize(state, actor, main=False):
    if state["version"] >= 5:
        role = "main" if main else "cos"
        require(actor == state["coordination"][role], f"Only recorded {role} may perform this action")


def bind(state, node, attempt, kind, handle):
    require(state["version"] >= 5, "Native handles require version 5")
    entry = state["nodes"][node]
    require(entry["status"] == "running" and entry["attempt"] == attempt, "Stale native assignment")
    nonempty(handle, "native handle")
    handles = entry.setdefault("native_handles", {})
    if kind == "command":
        values = handles.setdefault(kind, [])
        if handle not in values:
            values.append(handle)
    else:
        require(kind not in handles or handles[kind] == handle, "Reconcile the original native handle; do not relaunch")
        handles[kind] = handle
    return handles


def stopped_proof(state, proof_path):
    require(state["version"] >= 5, "Coordinator cleanup requires version 5")
    import json
    record = file_record(proof_path)
    proof = json.loads(Path(record["path"]).read_text())
    value = state["coordination"]
    require(proof.get("previous_cos") == value["cos"], "Replacement proof belongs to another CoS")
    for flag in ("cos_stopped", "workers_stopped", "commands_stopped", "descendants_absent", "git_reconciled"):
        require(proof.get(flag) is True, f"Replacement needs native evidence: {flag}")
    nonempty(proof.get("observations"), "native reconciliation observations")
    return record


def stop_run(state, proof_path, timestamp):
    record = stopped_proof(state, proof_path)
    require_commands_stopped(state)
    for entry in state["nodes"].values():
        if entry["status"] == "running":
            entry.update(status="blocked", finished=timestamp, stopped_evidence=record,
                         stopped_by=state["coordination"]["main"])
    for row in state["coordination"]["commands"].values():
        if row["status"] == "waiting":
            row["status"] = "stopped"
    return {"stopped": True, "cos": state["coordination"]["cos"]}


def replace(state, cos, proof_path):
    record = stopped_proof(state, proof_path)
    value = state["coordination"]
    require(not any(e["status"] == "running" for e in state["nodes"].values()), "Reconcile running nodes before replacement")
    require(not any(e["status"] not in {"waiting", "stopped", "superseded"} and not e.get("slot_released") for e in value["commands"].values()), "Reconcile commands before replacement")
    nonempty(cos, "replacement CoS identity")
    require(cos not in {value["cos"], value["main"]}, "Replacement must be a different dedicated CoS")
    value["replacements"].append({"previous": value["cos"], "replacement": cos, "proof": record})
    value["cos"] = cos
    return {"cos": cos}


def identity(state):
    return {"generation": state["generation"], "snapshot": state["candidate"]["sha256"] if state["candidate"] else None,
            "endpoint": state["endpoint"], "spec_sha256": state["spec"]["sha256"]}


def delivered(state, data, timestamp):
    require(state["version"] >= 5, "Delivery acknowledgement requires version 5")
    expected = identity(state)
    require(all(data.get(key) == value for key, value in expected.items()), "Stale delivery identity")
    terminal = "ci" if state["endpoint"] == "draft" else "reconcile"
    require(state["nodes"][terminal]["status"] == "pass", "Authorized endpoint is not complete")
    nonempty(data.get("message_id"), "actual user-facing message identity")
    record = {**expected, "message_id": data["message_id"], "evidence": file_record(data["evidence"])}
    existing = state["coordination"]["deliveries"]
    if not any(all(row.get(k) == v for k, v in record.items()) for row in existing):
        existing.append({**record, "at": timestamp})
    return record


def require_delivery(state):
    expected = identity(state)
    rows = state["coordination"]["deliveries"]
    match = next((row for row in reversed(rows) if all(row.get(k) == v for k, v in expected.items())), None)
    require(match is not None, "Main must deliver the outcome to the user before handoff or closeout")
    verify_record(match["evidence"])
    return match["evidence"]


def require_commands_stopped(state, node=None):
    if state["version"] < 5:
        return
    for row in state["coordination"]["commands"].values():
        if node is not None and (row["node"] != node or row["attempt"] != state["nodes"][node].get("attempt")):
            continue
        require(row["status"] in {"waiting", "stopped", "superseded"} or row.get("slot_released"),
                "Confirm command and descendant cleanup before completing or repairing")
        if node is not None:
            require(row["status"] != "waiting", "A required command is still waiting")
