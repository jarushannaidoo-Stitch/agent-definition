import copy
import json

from support import GraphCase
import graph_state


class EndpointTests(GraphCase):
    def local_run(self):
        self.contract["endpoint"] = "local"
        self.state = self.initialize()

    def finish_local(self):
        self.through("reconcile")
        self.finish("handoff")
        self.finish("closeout")

    def steering(self, endpoint):
        approval = self.root / f"steer-{endpoint}.md"
        approval.write_text(f"User selected the {endpoint} endpoint\n")
        return approval

    def test_local_run_finishes_without_publication_or_ci(self):
        self.local_run()
        self.through("reconcile")
        self.assertEqual(graph_state.status(self.state)["ready"], ["handoff"])
        for node in ("publish", "ci"):
            with self.subTest(node=node), self.assertRaisesRegex(ValueError, "local endpoint"):
                graph_state.start(self.state, node, "worker")
        self.finish("handoff")
        self.finish("closeout")
        result = graph_state.status(self.state)
        self.assertEqual(result["endpoint"], "local")
        self.assertTrue(result["complete"])
        self.assertEqual(result["ready"], [])
        for node in ("publish", "ci"):
            self.assertEqual(self.state["nodes"][node]["status"], "pending")

    def test_later_draft_authorization_preserves_reviews_and_reopens_handoff(self):
        self.local_run()
        self.finish_local()
        preserved = copy.deepcopy(self.state["nodes"]["acceptance"])
        old_handoff = self.state["nodes"]["handoff"]["receipt"]
        graph_state.select_endpoint(self.state, "draft", self.steering("draft"))
        self.assertEqual(self.state["nodes"]["acceptance"], preserved)
        self.assertEqual(graph_state.status(self.state)["ready"], ["publish"])
        self.assertEqual(self.state["repairs"], 0)
        with self.assertRaisesRegex(ValueError, "prerequisites"):
            graph_state.start(self.state, "handoff", "cos")
        self.finish("publish")
        self.finish("ci")
        graph_state.start(self.state, "handoff", "cos")
        with self.assertRaisesRegex(ValueError, "attempt"):
            graph_state.complete(self.state, "handoff", old_handoff)
        graph_state.complete(self.state, "handoff", self.receipt("handoff"))
        self.finish("closeout")
        self.assertTrue(graph_state.status(self.state)["complete"])

    def test_user_can_stop_at_local_after_planning_a_draft(self):
        self.through("reconcile")
        graph_state.select_endpoint(self.state, "local", self.steering("local"))
        self.finish("handoff")
        self.finish("closeout")
        self.assertEqual(self.state["nodes"]["publish"]["status"], "pending")

    def test_existing_runs_keep_the_draft_endpoint(self):
        self.state.pop("endpoint", None)
        self.through("reconcile")
        self.assertEqual(graph_state.status(self.state)["ready"], ["publish"])
        self.assertEqual(graph_state.status(self.state)["endpoint"], "draft")

    def test_endpoint_change_requires_stopped_workers_and_pinned_approval(self):
        graph_state.start(self.state, "prepare", "worker")
        with self.assertRaisesRegex(ValueError, "stopped workers"):
            graph_state.select_endpoint(self.state, "local", self.steering("local"))
        graph_state.complete(self.state, "prepare", self.receipt("prepare"))
        with self.assertRaises(FileNotFoundError):
            graph_state.select_endpoint(self.state, "local", self.root / "missing.md")
        approval = self.steering("local")
        graph_state.select_endpoint(self.state, "local", approval)
        approval.write_text("changed user instruction")
        with self.assertRaisesRegex(ValueError, "Pinned evidence"):
            graph_state.start(self.state, "tests", "writer")

    def test_author_repair_invalidates_local_completion(self):
        self.local_run()
        self.finish_local()
        (self.repo / "source.txt").write_text("repair\n")
        graph_state.repair(self.state, "implement", "Correct the implementation")
        self.assertFalse(graph_state.status(self.state)["complete"])
        self.assertEqual(self.state["nodes"]["handoff"]["status"], "pending")
        with self.assertRaisesRegex(ValueError, "prerequisites"):
            graph_state.start(self.state, "handoff", "cos")

    def test_cli_persists_steering_idempotently(self):
        path, _ = self.init_cli()
        approval = self.steering("local")
        result = self.cli("endpoint", path, "local", "--approval", approval)
        self.assertEqual(result.returncode, 0, result.stderr)
        stored = path.read_bytes()
        result = self.cli("endpoint", path, "local", "--approval", approval)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(path.read_bytes(), stored)
        state = json.loads(path.read_text())
        self.assertEqual(state["endpoint"], "local")
        self.assertEqual(len(state["history"]), 1)
