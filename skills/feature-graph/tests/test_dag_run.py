import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import dag_run  # noqa: E402

GATES = ["lint", "tests", "verification", "spec_audit", "styla", "arc"]


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

    def tearDown(self):
        self.tmp.cleanup()

    def run_node(self, node, package=None):
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
            dag_run.start(self.state, gate)
        with self.assertRaisesRegex(ValueError, "needs"):
            dag_run.start(self.state, "csa_final")
        for gate in GATES:
            dag_run.passed(self.state, gate, self.evidence)
        dag_run.start(self.state, "csa_final")

    def test_gate_failure_bounces_via_architect_and_reopens_build(self):
        self.through_integrate()
        dag_run.start(self.state, "styla")
        bounce = dag_run.failed(self.state, "styla", "naming rule", "eng-1", self.evidence)
        self.assertEqual(bounce["via"], "architect")
        with self.assertRaisesRegex(ValueError, "open bounce"):
            dag_run.start(self.state, "lint")
        dag_run.resolve(self.state, bounce["id"], "route to eng-1 as-is")
        self.assertEqual(self.state["packages"]["wp1"]["state"], "pending")
        self.assertEqual(self.state["packages"]["wp2"]["state"], "pass")
        self.assertEqual(self.state["nodes"]["integrate"]["state"], "pending")

    def test_loop_cap_escalates(self):
        self.through_integrate()
        self.state["loop_cap"] = 1
        dag_run.start(self.state, "lint")
        dag_run.failed(self.state, "lint", "x", "eng-1", self.evidence)
        dag_run.resolve(self.state, "b1", "fix")
        self.state["nodes"]["build"]["state"] = "pass"
        self.state["nodes"]["integrate"]["state"] = "pass"
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
