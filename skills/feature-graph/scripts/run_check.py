#!/usr/bin/env python3
"""Run one observed check with a durable reservation, log and shared heavy-command slot."""

import argparse
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import shlex
import signal
import subprocess
import sys
import time

sys.dont_write_bytecode = True

import budget
import coordination
import graph
import graph_state
from evidence import file_record, require, snapshot


@contextmanager
def slot(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            yield None
            return
        try:
            yield handle
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def owner_path(handle):
    return Path(str(handle.name) + ".owner.json")


def owner(handle):
    path = owner_path(handle)
    return json.loads(path.read_text()) if path.exists() else {}


def write_owner(handle, value):
    graph.save(owner_path(handle), value)


def update(path, command_id, callback):
    with graph.locked(path):
        state = json.loads(path.read_text())
        result = callback(state, state["coordination"]["commands"][command_id])
        graph.save(path, state)
        return result


def register(args):
    path = args.state.resolve()
    with graph.locked(path):
        state = json.loads(path.read_text())
        require(state["version"] >= 5, "Check helper requires version 5")
        coordination.authorize(state, args.actor)
        graph_state.verify(state)
        budget.available(state, graph_state.now())
        node = state["nodes"][args.node]
        require(node["status"] == "running", "Reserve the graph node first")
        require(args.argv, "Missing check command")
        coordination.nonempty(args.name, "check name")
        require(args.command_id and all(c.isalnum() or c in '-_' for c in args.command_id), "Use a simple stable command ID")
        cwd = Path(args.cwd or state["contract"]["repo"]).resolve(strict=True)
        require(cwd.is_relative_to(Path(state["contract"]["repo"])), "Check directory must be inside the run worktree")
        source = snapshot(state["contract"]["repo"], state["contract"]["baseline"])["sha256"]
        request = {"node": args.node, "attempt": node["attempt"], "generation": state["generation"],
                   "source": source, "name": args.name, "argv": args.argv, "cwd": str(cwd)}
        commands = state["coordination"]["commands"]
        if args.command_id in commands:
            entry = commands[args.command_id]
            require(all(entry.get(k) == v for k, v in request.items()), "Command ID already belongs to different inputs")
            require(entry["status"] in {"waiting", "finished"}, "Ambiguous command launch; reconcile native status before retry")
        else:
            entry = {**request, "status": "waiting", "registered": graph_state.now()}
            commands[args.command_id] = entry
        graph.save(path, state)
        return state, entry


def group_absent(pid):
    try:
        os.killpg(pid, 0)
        return False
    except ProcessLookupError:
        return True


def execute(args):
    state, entry = register(args)
    if entry["status"] == "finished":
        return entry["result"]
    path = args.state.resolve()
    lock_path = Path(state["coordination"]["heavy_lock"])
    with slot(lock_path) as handle:
        if handle is None:
            return {"status": "waiting", "command_id": args.command_id, "lock": str(lock_path)}
        previous = owner(handle)
        if previous and previous.get("status") != "released":
            return {"status": "waiting", "command_id": args.command_id, "lock": str(lock_path),
                    "reason": "owner_cleanup_pending", "owner": previous}
        identity = {"run": str(path), "command_id": args.command_id, "cos": args.actor,
                    "attempt": entry["attempt"], "status": "running", "started": graph_state.now(), "runner_pid": os.getpid()}
        def begin(current, row):
            coordination.authorize(current, args.actor)
            require(row["status"] == "waiting", "Command already launched; inspect saved result")
            require(current["nodes"][args.node]["status"] == "running", "Command node stopped before launch")
            require(current["generation"] == row["generation"] and current["nodes"][args.node].get("attempt") == row["attempt"], "Stale command attempt")
            require(snapshot(current["contract"]["repo"], current["contract"]["baseline"])["sha256"] == row["source"], "Command source changed before launch")
            budget.available(current, graph_state.now())
            row.pop("cleanup", None)
            row.update(status="running", started=identity["started"], runner_pid=os.getpid(), slot_released=False)
        write_owner(handle, identity)
        update(path, args.command_id, begin)
        directory = path.parent / "checks"
        directory.mkdir(exist_ok=True)
        log = directory / (args.command_id + '.log')
        start = time.monotonic()
        process = None
        cancelled = []
        old_handlers = {}
        def cancel(signum, frame):
            cancelled.append(signum)
            if process is not None:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
        try:
            for signum in (signal.SIGINT, signal.SIGTERM):
                old_handlers[signum] = signal.signal(signum, cancel)
            with log.open("x") as output:
                if cancelled:
                    raise InterruptedError("Cancelled before launch")
                process = subprocess.Popen(args.argv, cwd=entry["cwd"], stdin=subprocess.DEVNULL,
                                           stdout=output, stderr=subprocess.STDOUT, start_new_session=True)
                identity["pid"] = process.pid
                write_owner(handle, identity)
                update(path, args.command_id, lambda current, row: row.update(pid=process.pid))
                if cancelled:
                    cancel(cancelled[-1], None)
                exit_code = process.wait()
        except (OSError, InterruptedError) as error:
            if process is not None:
                cancel(signal.SIGTERM, None)
                process.wait()
            exit_code = 127
            error_text = str(error)
        finally:
            for signum, handler in old_handlers.items():
                signal.signal(signum, handler)
        absent = process is None or group_absent(process.pid)
        # A detached descendant cannot be proven absent by the process-group check.
        result = {"status": "finished" if absent else "cleanup_required", "command_id": args.command_id,
                  "name": args.name, "command": shlex.join(args.argv), "cwd": entry["cwd"],
                  "source": entry["source"], "duration_seconds": round(time.monotonic() - start, 3),
                  "exit_code": exit_code, "log": str(log), "cancelled": bool(cancelled),
                  "process_group_absent": absent}
        if 'error_text' in locals():
            result["error"] = error_text
        if log.exists():
            result["log_record"] = file_record(log)
        result["source_unchanged"] = snapshot(state["contract"]["repo"], state["contract"]["baseline"])["sha256"] == entry["source"]
        update(path, args.command_id, lambda current, row: row.update(status=result["status"], result=result))
        write_owner(handle, {**identity, "status": "awaiting_release" if absent else "cleanup_required"})
        return result


def probe(state_path):
    state = json.loads(state_path.read_text())
    with slot(Path(state["coordination"]["heavy_lock"])) as handle:
        if handle is None:
            return {"available": False, "reason": "held"}
        value = owner(handle)
        return {"available": not value or value.get("status") == "released", "owner": value}


def release(args):
    state = json.loads(args.state.read_text())
    is_main = args.actor == state["coordination"]["main"]
    coordination.authorize(state, args.actor, main=is_main)
    record = file_record(args.proof)
    proof = json.loads(Path(record["path"]).read_text())
    if is_main:
        require(proof.get("cos_stopped") is True and proof.get("previous_cos") == state["coordination"]["cos"], "Main cleanup requires stopped coordinator evidence")
    lock_path = Path(state["coordination"]["heavy_lock"])
    with slot(lock_path) as handle:
        require(handle is not None, "Runner still holds the command slot")
        value = owner(handle)
        require(value.get("run") == str(args.state.resolve()) and value.get("command_id") == args.command_id, "Slot belongs to another command")
        require(proof.get("run") == value["run"] and proof.get("command_id") == value["command_id"] and proof.get("started") == value["started"], "Stale cleanup proof")
        for flag in ("runner_stopped", "native_session_closed", "descendants_absent"):
            require(proof.get(flag) is True, f"Native cleanup evidence required: {flag}")
        coordination.nonempty(proof.get("observations"), "process identity and absence observations")
        if value.get("pid"):
            require(group_absent(value["pid"]), "Command process group still exists")
        def finish(current, row):
            coordination.authorize(current, args.actor, main=is_main)
            row["cleanup"] = record
            if row["status"] in {"running", "cleanup_required"}:
                row["status"] = "stopped"
            row["slot_released"] = True
        update(args.state.resolve(), args.command_id, finish)
        write_owner(handle, {**value, "status": "released", "cleanup": record})
        return {"released": args.command_id}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("run", "probe", "release"))
    parser.add_argument("state", type=Path)
    parser.add_argument("--actor")
    parser.add_argument("--node")
    parser.add_argument("--id", dest="command_id")
    parser.add_argument("--name")
    parser.add_argument("--cwd")
    parser.add_argument("--proof", type=Path)
    raw = sys.argv[1:]
    split = raw.index('--') if '--' in raw else len(raw)
    args = parser.parse_args(raw[:split])
    args.argv = raw[split + 1:]
    try:
        result = probe(args.state) if args.mode == 'probe' else release(args) if args.mode == 'release' else execute(args)
        print(json.dumps(result, indent=2))
        if result.get("status") == "waiting":
            return 75
        return 0 if args.mode in {'probe', 'release'} or result.get("status") == "finished" and result.get("exit_code") == 0 else 1
    except (ValueError, OSError, KeyError, TypeError) as error:
        print(f"feature-graph check: {error}", file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
