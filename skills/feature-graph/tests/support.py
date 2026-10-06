"""Disposable repository and receipts for guard behavior tests."""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / "scripts"))

import graph_state


class GraphCase(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="feature-graph-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.git("init", "-q")
        (self.repo / "source.txt").write_text("original\n")
        (self.repo / "removed.txt").write_text("remove later\n")
        self.commit()
        self.baseline = self.git("rev-parse", "HEAD").strip()
        self.spec = self.root / "spec.md"
        self.spec.write_text("AC-1: approved observable behavior\n")
        self.approval = self.root / "approval.md"
        self.approval.write_text("Fixture approval\n")
        self.report = self.root / "report.md"
        self.report.write_text("Fixture evidence\n")
        self.contract = {"repo": str(self.repo), "baseline": self.baseline,
                         "branch": "approved-branch", "spec": str(self.spec),
                         "approval": str(self.approval), "checks": ["tests", "types"],
                         "ci_checks": ["build"],
                         "arc": {"required": False, "reason": "No contract change"},
                         "styla": {"required": False, "reason": "Mechanical fixture"}}
        self.state = self.initialize()

    def initialize(self):
        with patch.object(graph_state, "WORKFLOW", graph_state.LEGACY_WORKFLOW):
            return graph_state.initialize(self.contract)

    def v2_contract(self):
        plan = self.root / "verification-plan.json"
        if not plan.exists():
            plan.write_text(json.dumps({"kind": "feature", "defer_new_boundary": True,
                                       "criteria": ["AC-1"], "checks": ["tests"],
                                       "early_proof": "Run the baseline harness; boundary absent",
                                       "final_proof": "Drive the new boundary on the candidate"}))
        return {**self.contract, "verification_plan": str(plan), "test_paths": ["new-test.txt"],
                "budget_seconds": 3600, "budget_started_at": graph_state.now(),
                "review_checkpoint_seconds": 60,
                "arc": {"required": True, "reason": "Mandatory"},
                "styla": {"required": True, "reason": "Mandatory"}}

    def git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.repo), *args],
                                       stderr=subprocess.PIPE).decode()

    def commit(self):
        self.git("add", "--all")
        self.git("-c", "user.name=Jarushan Naidoo", "-c", "user.email=jarushan.naidoo@stitch.money",
                 "-c", "core.hooksPath=/dev/null", "commit", "--no-gpg-sign", "--allow-empty",
                 "-qm", "Guard fixture")

    def checks(self):
        return [{"name": name, "command": f"fixture {name}", "exit_code": 0,
                 "log": str(self.report)} for name in self.contract["checks"]]

    def receipt(self, node, outcome="pass"):
        entry = self.state["nodes"][node]
        flags = ["scaffold_verified", "executables_verified", "ownership_disjoint", "stopped",
                 "artifact_verified", "baseline_inputs_only", "matches_freeze", "shared_with_user",
                 "authors_stopped", "complete_artifacts_verified", "all_findings_resolved",
                 "draft", "signatures_verified", "commit_series_preserved", "no_reviewers",
                 "user_notified", "lessons_recorded", "pack_synchronized"]
        details = {flag: True for flag in flags}
        details.update(baseline=self.baseline, checkpoints=["checkpoint-1"], checks=self.checks(),
                       blocking_findings=[], inspected_paths=["source.txt"], criteria_verified=["AC-1"],
                       head=self.git("rev-parse", "HEAD").strip(), branch=self.contract["branch"],
                       url="https://example.test/owner/repo/pull/1")
        if node == "ci":
            details["checks"] = [{"name": "build", "head": details["head"],
                                  "conclusion": "success", "url": "https://example.test/check/1"}]
        return {"attempt": entry["attempt"], "generation": entry["generation"],
                "snapshot": entry.get("snapshot"), "spec_sha256": self.state["spec"]["sha256"],
                "outcome": outcome, "summary": "Fixture result", "evidence": [str(self.report)],
                "details": details}

    def finish(self, node):
        graph_state.start(self.state, node, f"worker-{node}")
        return graph_state.complete(self.state, node, self.receipt(node))

    def through(self, target):
        for node in self.state["graph"]:
            if self.state["nodes"][node]["status"] == "pending":
                self.finish(node)
            if node == target:
                return

    def cli(self, *args):
        if args and args[0] not in {"status", "receipt"} and "--actor" not in args:
            args = (*args, "--actor", "cos-1")
        return subprocess.run([sys.executable, "-B", str(SKILL / "scripts/graph.py"), *map(str, args)],
                              text=True, capture_output=True)

    def v5_contract(self):
        roles = self.root / "roles.json"
        roles.write_text("{\"cos\": \"gpt-6.1-sol high\"}\n")
        return {**self.v2_contract(), "coordination": {"main": "main-1", "cos": "cos-1",
                "roles": str(roles), "admission": str(self.approval), "heavy_lock": str(self.root / "heavy.lock")}}

    def init_cli(self):
        contract = self.root / "contract.json"
        contract.write_text(json.dumps(self.v5_contract()))
        path = self.root / "run.json"
        result = self.cli("init", path, "--contract", contract, "--actor", "cos-1")
        self.assertEqual(result.returncode, 0, result.stderr)
        return path, contract


class GraphV2Case(GraphCase):
    workflow = SKILL / "references/v2/workflow.json"

    def setUp(self):
        workflow_patch = patch.object(graph_state, "WORKFLOW", self.workflow)
        workflow_patch.start()
        self.addCleanup(workflow_patch.stop)
        super().setUp()

    def initialize(self):
        self.contract = self.v2_contract()
        return graph_state.initialize(self.contract)

    def receipt(self, node, outcome="pass"):
        receipt = super().receipt(node, outcome)
        details = receipt["details"]
        details.update(decisions_resolved=True, budget_approved=True, verification_plan_approved=True,
                       coverage_completed=["AC-1"], coverage_remaining=[],
                       paths_traced=["entry -> owner -> observable result"],
                       first_principles_audit=True, test_validity_reviewed=True,
                       deferred_proof_completed=True,
                       repair={"target": "review", "criterion": "AC-1", "reason": "Interrupted audit"},
                       early_proof={"baseline": self.baseline, "checks": self.checks(),
                                    "result": "Baseline harness works", "unavailable": "New boundary absent"})
        return receipt
