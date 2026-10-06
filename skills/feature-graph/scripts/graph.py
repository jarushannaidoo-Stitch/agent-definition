#!/usr/bin/env python3
"""Dependency guard for Feature graph. Python 3.9+, macOS/Linux, no packages."""

import argparse
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True

import graph_state
import budget
import coordination
from evidence import require


@contextmanager
def locked(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.with_suffix(path.suffix + ".lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError("Another graph command holds the state lock") from None
        yield


def save(path, state):
    descriptor, temporary = tempfile.mkstemp(prefix=".graph-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w") as output:
            json.dump(state, output, indent=2)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    subcommands = result.add_subparsers(dest="command", required=True)
    for name in ("init", "status", "start", "receipt", "complete", "repair", "endpoint", "wait", "budget", "review-plan", "bind", "coordinator", "notify", "stop-run"):
        command = subcommands.add_parser(name)
        command.add_argument("state", type=Path, help="Run JSON outside the product worktree")
        command.add_argument("--actor", help="Recorded native CoS identity; Main for coordinator/notify")
        if name == "bind":
            command.add_argument("node")
            command.add_argument("--attempt", required=True)
            command.add_argument("--kind", choices=("agent", "command"), required=True)
            command.add_argument("--handle", required=True)
        if name == "stop-run":
            command.add_argument("--proof", required=True, type=Path)
        if name == "coordinator":
            command.add_argument("--cos", required=True)
            command.add_argument("--proof", required=True, type=Path)
        if name == "notify":
            command.add_argument("--delivery", required=True, type=Path)
        if name == "init":
            command.add_argument("--contract", required=True, type=Path)
        if name in {"start", "receipt", "complete", "repair", "review-plan"}:
            command.add_argument("node")
        if name == "review-plan":
            command.add_argument("--assessment", required=True, type=Path)
        if name == "endpoint":
            command.add_argument("endpoint", choices=("local", "draft"))
            command.add_argument("--approval", required=True, type=Path)
        if name == "wait":
            command.add_argument("kind", choices=("user", "external_ci", "end"))
            command.add_argument("--evidence", type=Path)
        if name == "budget":
            command.add_argument("--seconds", type=int, required=True)
            command.add_argument("--approval", type=Path, required=True)
        if name == "start":
            command.add_argument("--worker", required=True, help="Stable dispatch ID; reuse on resume")
        if name == "complete":
            command.add_argument("--receipt", required=True, type=Path)
        if name == "repair":
            command.add_argument("--reason", required=True)
            command.add_argument("--diagnosis", type=Path)
            command.add_argument("--cause")
            command.add_argument("--preserve-implementation", type=Path)
    return result


def run(args):
    path = args.state.expanduser().resolve()
    if args.command == "init":
        contract = json.loads(args.contract.read_text())
        repo = Path(contract["repo"]).expanduser().resolve()
        require(not path.is_relative_to(repo), "Run state must stay outside product source")
    with locked(path):
        if args.command == "init":
            require(not path.exists(), "Run already exists; inspect status instead of reinitializing")
            state = graph_state.initialize(contract)
            coordination.authorize(state, args.actor)
            output = {"created": str(path), "spec_sha256": state["spec"]["sha256"], "ready": ["prepare"]}
        else:
            state = json.loads(path.read_text())
            require(not path.is_relative_to(Path(state["contract"]["repo"])),
                    "Run state must stay outside product source")
            if args.command not in {"status", "receipt"}:
                coordination.authorize(state, args.actor, main=args.command in {"coordinator", "notify", "stop-run"})
            if args.command == "status":
                output = graph_state.status(state)
                output["nodes"] = {
                    name: {key: entry[key] for key in ("status", "worker", "attempt", "generation",
                          "started", "finished", "duration_seconds") if key in entry}
                    for name, entry in output["nodes"].items()
                }
                if output["coordination"]:
                    value = output["coordination"]
                    output["coordination"] = {"main": value["main"], "cos": value["cos"],
                        "pending_commands": {key: {field: row.get(field) for field in ("status", "node", "attempt", "native_session", "pid")}
                                             for key, row in value["commands"].items() if row["status"] not in {"stopped", "superseded"} and not row.get("slot_released")},
                        "user_delivery_current": any(all(row.get(k) == v for k, v in coordination.identity(state).items()) for row in value["deliveries"])}
            elif args.command in {"bind", "coordinator", "notify", "stop-run"}:
                graph_state.verify_run_inputs(state)
                if args.command == "bind":
                    output = coordination.bind(state, args.node, args.attempt, args.kind, args.handle)
                elif args.command == "stop-run":
                    output = coordination.stop_run(state, args.proof, graph_state.now())
                elif args.command == "coordinator":
                    output = coordination.replace(state, args.cos, args.proof)
                else:
                    graph_state.verify(state)
                    output = coordination.delivered(state, json.loads(args.delivery.read_text()), graph_state.now())
            elif args.command == "start":
                output = graph_state.start(state, args.node, args.worker)
            elif args.command == "complete":
                receipt = json.loads(args.receipt.read_text())
                output = graph_state.complete(state, args.node, receipt)
            elif args.command == "review-plan":
                output = graph_state.configure_review(state, args.node, args.assessment)
            elif args.command == "endpoint":
                output = graph_state.select_endpoint(state, args.endpoint, args.approval)
            elif args.command == "repair":
                output = graph_state.repair(state, args.node, args.reason, args.diagnosis,
                                            args.cause, args.preserve_implementation)
            elif args.command in {"wait", "budget"}:
                graph_state.verify_run_inputs(state)
                if args.command == "wait":
                    require(args.kind == "end" or args.evidence, "Wait needs factual evidence")
                    output = budget.wait(state, args.kind, args.evidence, graph_state.now())
                else:
                    output = budget.extend(state, args.seconds, args.approval, graph_state.now())
            else:
                require(args.node in state["nodes"], "Unknown node")
                entry = state["nodes"][args.node]
                require(entry["status"] == "running", "Start the node before preparing its receipt")
                output = {"attempt": entry["attempt"], "generation": entry["generation"],
                          "snapshot": entry.get("snapshot"), "spec_sha256": state["spec"]["sha256"],
                          "outcome": "blocked", "summary": "", "evidence": [], "details": {}}
        if args.command not in {"status", "receipt"}:
            save(path, state)
        print(json.dumps(output, indent=2))
        return 2 if args.command == "status" and output["problems"] else 0


def main():
    try:
        return run(parser().parse_args())
    except (ValueError, OSError, KeyError, TypeError, subprocess.CalledProcessError) as error:
        print(f"feature-graph: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
