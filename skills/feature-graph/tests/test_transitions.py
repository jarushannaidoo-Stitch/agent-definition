import copy

from support import GraphCase
import graph_state


class TransitionTests(GraphCase):
    def test_cannot_skip_any_prerequisite(self):
        for node in self.state["graph"]:
            if node != "prepare":
                with self.subTest(node=node), self.assertRaises(ValueError):
                    graph_state.start(self.state, node, "worker")

    def test_authors_are_sequential_and_sealed_before_plan(self):
        self.finish("prepare")
        graph_state.start(self.state, "tests", "test-worker")
        for node in ("plan", "implement", "seal_tests", "capture"):
            with self.subTest(node=node), self.assertRaises(ValueError):
                graph_state.start(self.state, node, "other-worker")
        graph_state.complete(self.state, "tests", self.receipt("tests"))
        with self.assertRaisesRegex(ValueError, "seal_tests"):
            graph_state.start(self.state, "plan", "impl-worker")
        self.finish("seal_tests")
        self.finish("plan")
        graph_state.start(self.state, "implement", "impl-worker")

    def test_idempotent_reservation_and_completion(self):
        first = copy.deepcopy(graph_state.start(self.state, "prepare", "stable-id"))
        self.assertEqual(graph_state.start(self.state, "prepare", "stable-id"), first)
        with self.assertRaises(ValueError):
            graph_state.start(self.state, "prepare", "duplicate-worker")
        receipt = self.receipt("prepare")
        completed = copy.deepcopy(graph_state.complete(self.state, "prepare", receipt))
        self.assertEqual(graph_state.complete(self.state, "prepare", receipt), completed)

    def test_stale_receipt_fields_are_rejected(self):
        graph_state.start(self.state, "prepare", "worker")
        for field, wrong in (("attempt", "old"), ("generation", 0),
                             ("spec_sha256", "old"), ("snapshot", "old")):
            receipt = self.receipt("prepare")
            receipt[field] = wrong
            with self.subTest(field=field), self.assertRaises(ValueError):
                graph_state.complete(self.state, "prepare", receipt)
        self.assertEqual(self.state["nodes"]["prepare"]["status"], "running")

    def test_pass_needs_evidence_and_attestations(self):
        graph_state.start(self.state, "prepare", "worker")
        receipt = self.receipt("prepare")
        receipt["details"]["scaffold_verified"] = False
        with self.assertRaises(ValueError):
            graph_state.complete(self.state, "prepare", receipt)
        receipt = self.receipt("prepare")
        receipt["evidence"] = []
        with self.assertRaises(ValueError):
            graph_state.complete(self.state, "prepare", receipt)

    def test_reviews_can_overlap_but_reconcile_waits(self):
        self.contract["arc"]["required"] = True
        self.contract["styla"]["required"] = True
        self.state = self.initialize()
        self.through("checks")
        for node in ("acceptance", "regression", "arc", "styla"):
            graph_state.start(self.state, node, node)
        graph_state.complete(self.state, "acceptance", self.receipt("acceptance"))
        with self.assertRaises(ValueError):
            graph_state.start(self.state, "reconcile", "cos")
        for node in ("regression", "arc", "styla"):
            graph_state.complete(self.state, node, self.receipt(node))
        self.finish("reconcile")

    def test_missing_required_check_and_review_execution_rejected(self):
        self.through("capture")
        graph_state.start(self.state, "checks", "cos")
        receipt = self.receipt("checks")
        receipt["details"]["checks"].pop()
        with self.assertRaisesRegex(ValueError, "Required checks"):
            graph_state.complete(self.state, "checks", receipt)
        graph_state.complete(self.state, "checks", self.receipt("checks"))
        graph_state.start(self.state, "acceptance", "reviewer")
        receipt = self.receipt("acceptance")
        receipt["details"]["checks"] = []
        with self.assertRaises(ValueError):
            graph_state.complete(self.state, "acceptance", receipt)

    def test_failed_stage_blocks_descendants(self):
        self.through("capture")
        graph_state.start(self.state, "checks", "cos")
        graph_state.complete(self.state, "checks", self.receipt("checks", "fail"))
        with self.assertRaises(ValueError):
            graph_state.start(self.state, "acceptance", "reviewer")
