import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import dag_run  # noqa: E402

GATES = ["lint", "tests", "verification", "spec_audit", "styla", "arc"]
ROLE_INPUTS = {
    "senior_engineer": ["spec_excerpt", "package", "contract"],
    "integrator": ["contract", "worktree_list"],
    "git": ["git_request"],
    "verifier": ["spec_full", "repo_rules", "skill", "merged_diff"],
    "slice_spec_audit": ["spec_full", "merged_diff"],
    "styla": ["spec_full", "merged_diff"],
    "arc": ["spec_full", "skill", "merged_diff"],
    "csa": ["spec_full", "merged_diff"],
}


class DagRunTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.evidence = self.root / "evidence.md"
        self.evidence.write_text("ok\n")
        self.contract = {"linear_issue": "SAA-1", "spec_revision": "r1", "repo": "/repo", "baseline": "a" * 40,
                         "branch": "jarushan/saa-1", "checks": ["lint"], "ci_checks": ["ci"],
                         "freeze_ready": True}
        self.state = dag_run.initialize(self.root / "runs", "saa-1", self.contract, "architect-1")
        self.run_dir = self.root / "runs" / "saa-1"
        self.inputs = self.root / "inputs"
        self.inputs.mkdir()
        for kind in ("spec_full", "spec_excerpt", "package", "contract", "repo_rules", "skill", "merged_diff",
                     "worktree_list", "git_request", "transcript"):
            (self.inputs / f"{kind}.md").write_text(f"{kind}\n")

    def brief(self, node, package=None, kinds=None, extra=()):
        role = self.state["nodes"][node]["owner"]
        pairs = [(k, self.inputs / f"{k}.md") for k in (kinds or ROLE_INPUTS.get(role, []))] + list(extra)
        return dag_run.make_brief(self.state, self.run_dir, node, pairs, package)

    def tearDown(self):
        self.tmp.cleanup()

    def run_node(self, node, package=None):
        if self.state["nodes"][node]["owner"] != "architect":
            self.brief(node, package)
        dag_run.start(self.state, node, package)
        dag_run.passed(self.state, node, self.evidence, package)

    def through_integrate(self):
        self.run_node("freeze_check")
        dag_run.start(self.state, "plan")
        dag_run.add_package(self.state, "wp1", "eng-1", ["a.py", "test_a.py"])
        dag_run.add_package(self.state, "wp2", "eng-2", ["b.py", "test_b.py"])
        dag_run.passed(self.state, "plan", self.evidence)
        self.run_node("setup")
        dag_run.add_worktree(self.state, "/wt/wp1", "dag/wp1", "wp1")
        dag_run.add_worktree(self.state, "/wt/wp2", "dag/wp2", "wp2")
        for wp in ("wp1", "wp2"):
            self.run_node("build", wp)
        dag_run.add_worktree(self.state, "/wt/int", "dag/int", "integration")
        self.run_node("integrate")

    def test_light_freeze_refuses_launch(self):
        with self.assertRaisesRegex(ValueError, "ask Jarushan"):
            dag_run.initialize(self.root / "runs", "other", {**self.contract, "freeze_ready": False}, "a")
        with self.assertRaisesRegex(ValueError, "missing"):
            dag_run.initialize(self.root / "runs", "other2", {"freeze_ready": True}, "a")

    def test_file_ownership_must_be_disjoint(self):
        self.run_node("freeze_check")
        dag_run.start(self.state, "plan")
        dag_run.add_package(self.state, "wp1", "eng-1", ["a.py"])
        with self.assertRaisesRegex(ValueError, "disjoint"):
            dag_run.add_package(self.state, "wp2", "eng-2", ["a.py"])

    def test_build_needs_fresh_worktree_per_package_and_no_reuse(self):
        self.run_node("freeze_check")
        dag_run.start(self.state, "plan")
        dag_run.add_package(self.state, "wp1", "eng-1", ["a.py"])
        dag_run.passed(self.state, "plan", self.evidence)
        self.run_node("setup")
        with self.assertRaisesRegex(ValueError, "fresh worktree"):
            dag_run.start(self.state, "build", "wp1")
        dag_run.add_worktree(self.state, "/wt/wp1", "dag/wp1", "wp1")
        with self.assertRaisesRegex(ValueError, "never reuse"):
            dag_run.add_worktree(self.state, "/wt/wp1", "dag/wp1", "wp1")

    def test_gate_runs_in_parallel_and_csa_waits_for_all(self):
        self.through_integrate()
        for gate in GATES:
            self.brief(gate)
            dag_run.start(self.state, gate)
        with self.assertRaisesRegex(ValueError, "needs"):
            dag_run.start(self.state, "csa_final")
        for gate in GATES:
            dag_run.passed(self.state, gate, self.evidence)
        self.brief("csa_final")
        dag_run.start(self.state, "csa_final")

    def test_gate_failure_bounces_via_architect_and_reopens_build(self):
        self.through_integrate()
        self.brief("styla")
        dag_run.start(self.state, "styla")
        bounce = dag_run.failed(self.state, "styla", "naming rule", "eng-1", self.evidence)
        self.assertEqual(bounce["via"], "architect")
        with self.assertRaisesRegex(ValueError, "open bounce"):
            self.brief("lint")
            dag_run.start(self.state, "lint")
        dag_run.resolve(self.state, bounce["id"], "route to eng-1 as-is")
        self.assertEqual(self.state["packages"]["wp1"]["state"], "pending")
        self.assertEqual(self.state["packages"]["wp2"]["state"], "pass")
        self.assertEqual(self.state["nodes"]["integrate"]["state"], "pending")

    def test_loop_cap_escalates(self):
        self.through_integrate()
        self.state["loop_cap"] = 1
        self.brief("lint")
        dag_run.start(self.state, "lint")
        dag_run.failed(self.state, "lint", "x", "eng-1", self.evidence)
        dag_run.resolve(self.state, "b1", "fix")
        self.state["nodes"]["build"]["state"] = "pass"
        self.state["nodes"]["integrate"]["state"] = "pass"
        self.brief("lint")
        dag_run.start(self.state, "lint")
        bounce = dag_run.failed(self.state, "lint", "x", "eng-1", self.evidence)
        self.assertEqual(bounce["state"], "escalated")
        self.assertEqual(self.state["escalations"][0]["to"], "HQ/Jarushan")

    def test_contract_bounce_reopens_plan(self):
        self.through_integrate()
        dag_run.contract_bounce(self.state, "eng-2", "interface wrong", self.evidence)
        dag_run.resolve(self.state, "b1", "contract v2")
        self.assertEqual(self.state["nodes"]["plan"]["state"], "pending")
        self.assertEqual(self.state["nodes"]["integrate"]["state"], "pending")

    def test_closeout_requires_worktree_cleanup(self):
        self.through_integrate()
        for node in GATES + ["csa_final", "publish", "ci", "handoff"]:
            self.run_node(node)
        self.brief("cleanup")
        dag_run.start(self.state, "cleanup")
        with self.assertRaisesRegex(ValueError, "no worktree remains open"):
            dag_run.passed(self.state, "cleanup", self.evidence)
        for path in ("/wt/wp1", "/wt/wp2"):
            dag_run.removed(self.state, path, "yes")
        self.assertEqual(self.state["cleanup"]["state"], "in_progress")
        dag_run.removed(self.state, "/wt/int", "yes")
        dag_run.passed(self.state, "cleanup", self.evidence)
        self.run_node("closeout")
        self.assertEqual(self.state["phase"], "done")

    def test_start_requires_validated_brief(self):
        self.run_node("freeze_check")
        dag_run.start(self.state, "plan")
        dag_run.add_package(self.state, "wp1", "eng-1", ["a.py"])
        dag_run.passed(self.state, "plan", self.evidence)
        with self.assertRaisesRegex(ValueError, "validated brief"):
            dag_run.start(self.state, "setup")

    def test_unknown_or_unlisted_context_is_denied(self):
        self.through_integrate()
        with self.assertRaisesRegex(ValueError, "unknown context kind"):
            self.brief("styla", extra=[("transcript", self.inputs / "transcript.md")])
        with self.assertRaisesRegex(ValueError, "may not receive contract"):
            self.brief("arc", extra=[("contract", self.inputs / "contract.md")])
        with self.assertRaisesRegex(ValueError, "may not receive spec_full"):
            self.brief("integrate", extra=[("spec_full", self.inputs / "spec_full.md")])
        with self.assertRaisesRegex(ValueError, "may not receive merged_diff"):
            self.brief("publish", extra=[("merged_diff", self.inputs / "merged_diff.md")])

    def test_gate_reviewers_get_nothing_from_architect(self):
        self.through_integrate()
        plan = self.run_dir / "plan.md"
        plan.write_text("plan\n")
        with self.assertRaisesRegex(ValueError, "architect artifacts"):
            self.brief("csa_final", kinds=["merged_diff"], extra=[("spec_full", plan)])
        renamed = self.inputs / "plan.md"
        renamed.write_text("plan\n")
        with self.assertRaisesRegex(ValueError, "architect artifacts"):
            self.brief("styla", kinds=["merged_diff"], extra=[("spec_full", renamed)])

    def test_required_context_and_size_caps(self):
        self.through_integrate()
        with self.assertRaisesRegex(ValueError, "missing required"):
            self.brief("arc", kinds=["spec_full"])
        big = self.inputs / "big.md"
        big.write_text("x" * 5000)
        with self.assertRaisesRegex(ValueError, "cap is 4096"):
            self.brief("publish", kinds=[], extra=[("git_request", big)])

    def test_engineer_brief_owned_files_and_verbatim_deduped_findings(self):
        self.through_integrate()
        other = self.inputs / "b.py"
        other.write_text("b\n")
        with self.assertRaisesRegex(ValueError, "not owned by package wp1"):
            self.state["nodes"]["build"]["state"] = "pending"
            self.brief("build", "wp1", extra=[("owned_files", other)])
        with self.assertRaisesRegex(ValueError, "generated by dag_run"):
            self.brief("build", "wp1", extra=[("bounced_findings", other)])
        self.state["nodes"]["build"]["state"] = "pass"
        for _ in range(2):
            self.brief("styla")
            dag_run.start(self.state, "styla")
            dag_run.failed(self.state, "styla", "Name says Mgr; rule 3", "eng-1", self.evidence)
            dag_run.resolve(self.state, self.state["bounces"][-1]["id"], "route")
            self.state["nodes"]["build"]["state"] = "pass"
            self.state["nodes"]["integrate"]["state"] = "pass"
        self.brief("lint")
        dag_run.start(self.state, "lint")
        dag_run.failed(self.state, "lint", "eng-2 only", "eng-2", self.evidence)
        self.state["bounces"][-1]["state"] = "resolved"
        self.state["nodes"]["build"]["state"] = "pending"
        brief = self.brief("build", "wp1")
        record = next(r for r in brief["inputs"] if r["kind"] == "bounced_findings")
        findings = json.loads(Path(record["path"]).read_text())
        self.assertEqual([f["finding"] for f in findings], ["Name says Mgr; rule 3"])

    def test_findings_over_cap_fail_closed(self):
        self.through_integrate()
        for i in range(21):
            self.state["bounces"].append({"id": f"x{i}", "node": "styla", "to": "eng-1", "finding": f"f{i}",
                                          "evidence": "e", "state": "resolved"})
        self.state["nodes"]["build"]["state"] = "pending"
        with self.assertRaisesRegex(ValueError, "handoff cap"):
            self.brief("build", "wp1")

    def gate_passed(self, run_id="saa-1", stack_parent=None, branch=None):
        if run_id != "saa-1":
            contract = {**self.contract, "branch": branch or f"jarushan/{run_id}", "stack_parent": stack_parent}
            self.state = dag_run.initialize(self.root / "runs", run_id, contract, "architect-1")
            self.run_dir = self.root / "runs" / run_id
        elif stack_parent or branch:
            self.state["contract"].update(stack_parent=stack_parent, branch=branch or self.contract["branch"])
        self.through_integrate()
        for node in GATES + ["csa_final"]:
            self.run_node(node)
        return self.state

    def enqueue(self, run_id, head, **kw):
        state = self.gate_passed(run_id, **kw)
        dag_run.enqueue_signing(state, self.root / "runs", head, "open")
        dag_run.save(self.run_dir, state)
        return state

    def test_queued_for_signing_blocks_publish_but_allows_cleanup(self):
        state = self.enqueue("saa-1", "a" * 40)
        self.assertEqual(state["phase"], "queued-for-signing")
        queue = json.loads((self.root / "runs" / "signing-queue.json").read_text())
        self.assertEqual([e["dag_id"] for e in queue], ["saa-1"])
        self.assertEqual(set(queue[0]), {"dag_id", "repo", "branch", "head_sha", "stack_parent", "pr_intent", "enqueued"})
        self.brief("publish")
        with self.assertRaisesRegex(ValueError, "queued for signing"):
            dag_run.start(state, "publish")
        for path in ("/wt/wp1", "/wt/wp2", "/wt/int"):
            dag_run.removed(state, path, "no")
        self.assertEqual(state["cleanup"]["state"], "done")
        with self.assertRaisesRegex(ValueError, "already queued"):
            dag_run.enqueue_signing(state, self.root / "runs", "a" * 40, "open")

    def test_only_gate_passed_dags_queue(self):
        self.through_integrate()
        with self.assertRaisesRegex(ValueError, "gate-passed"):
            dag_run.enqueue_signing(self.state, self.root / "runs", "a" * 40, "open")

    def test_drain_is_oldest_first_and_respects_stack_order(self):
        self.enqueue("saa-1", "c" * 40, stack_parent="jarushan/parent", branch="jarushan/child")
        self.enqueue("parent", "b" * 40, branch="jarushan/parent")
        self.enqueue("other", "d" * 40, branch="jarushan/other")
        order = [e["dag_id"] for e in dag_run.drain_order(dag_run.load_queue(self.root / "runs"))]
        self.assertEqual(order, ["parent", "saa-1", "other"])
        result, entry = dag_run.sign_next(self.root / "runs", "b" * 40, "git-bot")
        self.assertEqual((result, entry["dag_id"]), ("signed", "parent"))
        signed = dag_run.load(self.root / "runs" / "parent")
        self.assertEqual(signed["signing"]["state"], "signed")
        self.assertEqual(signed["phase"], "publish")
        remaining = [e["dag_id"] for e in dag_run.load_queue(self.root / "runs")]
        self.assertEqual(remaining, ["saa-1", "other"])

    def test_head_mismatch_bounces_to_architect(self):
        self.enqueue("saa-1", "a" * 40)
        result, _ = dag_run.sign_next(self.root / "runs", "e" * 40, "git-bot")
        self.assertEqual(result, "mismatch")
        state = dag_run.load(self.run_dir)
        self.assertEqual(state["signing"]["state"], "mismatch")
        self.assertEqual(state["bounces"][-1]["to"], "architect")
        self.assertEqual(state["phase"], "bounced")
        self.assertEqual(dag_run.load_queue(self.root / "runs"), [])
        self.brief("publish")
        with self.assertRaisesRegex(ValueError, "open bounce"):
            dag_run.start(state, "publish")

    def test_cli_sign_next_exit_codes(self):
        self.enqueue("saa-1", "a" * 40)
        self.assertEqual(dag_run.main(["signing-queue", str(self.root / "runs")]), 0)
        self.assertEqual(dag_run.main(["sign-next", str(self.root / "runs"), "--observed-head", "a" * 40,
                                       "--actor", "git-bot"]), 0)
        self.assertEqual(dag_run.main(["sign-next", str(self.root / "runs"), "--observed-head", "a" * 40,
                                       "--actor", "git-bot"]), 2)

    def test_gate_owners_match_roles(self):
        owners = {name: node["owner"] for name, node in self.state["nodes"].items()}
        self.assertEqual(owners["arc"], "arc")
        self.assertEqual(owners["styla"], "styla")
        self.assertEqual(owners["csa_final"], "csa")
        self.assertEqual(self.state["nodes"]["arc"]["needs"], self.state["nodes"]["styla"]["needs"])

    def test_cli_status_steer_and_list(self):
        run = self.root / "runs" / "saa-1"
        self.assertEqual(dag_run.main(["steer", str(run), "--message", "pause wp2", "--actor", "main"]), 0)
        self.assertEqual(dag_run.main(["steer", str(run), "--message", "x", "--actor", "architect-1"]), 2)
        self.assertEqual(json.loads((run / "status.json").read_text())["steer"][0]["state"], "pending")
        self.assertEqual(dag_run.main(["ack-steer", str(run), "s1", "--actor", "architect-1"]), 0)
        self.assertEqual(dag_run.main(["status", str(run)]), 0)
        self.assertEqual(dag_run.main(["list", str(self.root / "runs")]), 0)
        self.assertEqual(dag_run.main(["start", str(run), "plan", "--actor", "intruder"]), 2)


if __name__ == "__main__":
    unittest.main()
