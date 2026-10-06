import fcntl
import json

from support import GraphCase
import graph_state


class PublicationTests(GraphCase):
    def test_handoff_retry_preserves_ci(self):
        self.through("ci")
        graph_state.start(self.state, "handoff", "cos")
        graph_state.complete(self.state, "handoff", self.receipt("handoff", "blocked"))
        graph_state.repair(self.state, "handoff", "Resume interrupted notification")
        self.assertEqual(self.state["nodes"]["ci"]["status"], "pass")
        self.finish("handoff")

    def test_publish_cannot_omit_uncommitted_reviewed_changes(self):
        (self.repo / "source.txt").write_text("reviewed implementation")
        (self.repo / "new-test.txt").write_text("reviewed test")
        (self.repo / "removed.txt").unlink()
        self.through("reconcile")
        graph_state.start(self.state, "publish", "git")
        with self.assertRaisesRegex(ValueError, "does not contain"):
            graph_state.complete(self.state, "publish", self.receipt("publish"))
        self.commit()
        graph_state.complete(self.state, "publish", self.receipt("publish"))

    def test_publish_rejects_changed_crlf_commit_when_checkout_matches_capture(self):
        (self.repo / ".gitattributes").write_text("*.crlf.txt text eol=crlf\n")
        fixture = self.repo / "fixture.crlf.txt"
        fixture.write_bytes(b"reviewed\n")
        self.commit()
        fixture.unlink()
        self.git("checkout", "--", "fixture.crlf.txt")
        captured = fixture.read_bytes()
        self.through("reconcile")

        fixture.write_bytes(b"different\n")
        self.commit()
        fixture.write_bytes(captured)
        graph_state.start(self.state, "publish", "git")

        with self.assertRaisesRegex(ValueError, "does not contain"):
            graph_state.complete(self.state, "publish", self.receipt("publish"))

    def test_publish_rejects_uncommitted_crlf_content_omitted_from_head(self):
        (self.repo / ".gitattributes").write_text("*.crlf.txt text eol=crlf\n")
        fixture = self.repo / "fixture.crlf.txt"
        fixture.write_bytes(b"committed\n")
        self.commit()
        fixture.write_bytes(b"reviewed\r\n")
        self.through("reconcile")
        graph_state.start(self.state, "publish", "git")

        with self.assertRaisesRegex(ValueError, "does not contain"):
            graph_state.complete(self.state, "publish", self.receipt("publish"))

    def test_complete_graph_and_wrong_head_ci(self):
        self.through("publish")
        graph_state.start(self.state, "ci", "cos")
        receipt = self.receipt("ci")
        receipt["details"]["checks"][0]["head"] = "0" * 40
        with self.assertRaisesRegex(ValueError, "another head"):
            graph_state.complete(self.state, "ci", receipt)
        graph_state.complete(self.state, "ci", self.receipt("ci"))
        self.finish("handoff")
        self.finish("closeout")
        self.assertEqual(graph_state.status(self.state)["ready"], [])
        self.assertTrue(all(e["status"] in {"pass", "omitted"} for e in self.state["nodes"].values()))

    def test_same_content_new_head_requires_publication_and_ci_again(self):
        self.through("ci")
        self.commit()
        with self.assertRaisesRegex(ValueError, "HEAD changed"):
            graph_state.start(self.state, "handoff", "cos")
        graph_state.repair(self.state, "publish", "New signed head with unchanged content")
        self.finish("publish")
        self.finish("ci")
        self.finish("handoff")

    def test_publish_rejects_non_draft_or_wrong_branch(self):
        self.through("reconcile")
        graph_state.start(self.state, "publish", "git")
        for key, value in (("draft", False), ("branch", "invented"), ("head", "0" * 40)):
            receipt = self.receipt("publish")
            receipt["details"][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                graph_state.complete(self.state, "publish", receipt)


class CliTests(GraphCase):
    def test_persistence_and_rejection_without_state_mutation(self):
        path, contract = self.init_cli()
        original = path.read_bytes()
        result = self.cli("start", path, "implement", "--worker", "worker")
        self.assertEqual(result.returncode, 2)
        self.assertIn("prerequisites", result.stderr)
        self.assertEqual(path.read_bytes(), original)
        self.assertEqual(self.cli("init", path, "--contract", contract).returncode, 2)
        self.assertEqual(path.read_bytes(), original)
        self.assertEqual(self.cli("start", path, "prepare", "--worker", "setup").returncode, 0)
        reservation = json.loads(path.read_text())["nodes"]["prepare"]
        resumed = self.cli("start", path, "prepare", "--worker", "setup")
        self.assertEqual(json.loads(resumed.stdout), reservation)

    def test_state_lock_rejects_competing_process(self):
        path, _ = self.init_cli()
        with path.with_suffix(".json.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            result = self.cli("start", path, "prepare", "--worker", "setup")
        self.assertEqual(result.returncode, 2)
        self.assertIn("state lock", result.stderr)

    def test_state_inside_product_is_rejected_before_creation(self):
        _, contract = self.init_cli()
        forbidden = self.repo / "new-state" / "run.json"
        result = self.cli("init", forbidden, "--contract", contract)
        self.assertEqual(result.returncode, 2)
        self.assertFalse(forbidden.parent.exists())

    def test_status_reports_stale_spec_without_claiming_ready(self):
        path, _ = self.init_cli()
        self.spec.write_text("changed")
        result = self.cli("status", path)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(result.stdout)["ready"], [])
