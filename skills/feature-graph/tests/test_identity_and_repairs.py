from support import GraphCase
import graph_state
from evidence import committed_snapshot, digest, snapshot


class IdentityAndRepairTests(GraphCase):
    def test_stale_prior_evidence_allows_failure_then_repair(self):
        self.finish("prepare")
        graph_state.start(self.state, "tests", "writer")
        self.report.write_text("Prior report was overwritten")
        graph_state.complete(self.state, "tests", self.receipt("tests", "blocked"))
        graph_state.repair(self.state, "prepare", "Recreate invalidated setup evidence")
        self.assertEqual(self.state["nodes"]["prepare"]["status"], "pending")

    def test_committed_snapshot_matches_modes_links_and_deletions(self):
        (self.repo / "source.txt").chmod(0o755)
        (self.repo / "link").symlink_to("source.txt")
        (self.repo / "removed.txt").unlink()
        self.commit()
        self.assertEqual(snapshot(self.repo, self.baseline),
                         committed_snapshot(self.repo, self.baseline, "HEAD"))

    def test_committed_snapshot_matches_git_declared_crlf_checkout(self):
        (self.repo / ".gitattributes").write_text("*.crlf.txt text eol=crlf\n")
        fixture = self.repo / "fixture.crlf.txt"
        fixture.write_bytes(b"first\nsecond\n")
        self.commit()
        fixture.unlink()
        self.git("checkout", "--", "fixture.crlf.txt")

        self.assertEqual(self.git("show", "HEAD:fixture.crlf.txt"), "first\nsecond\n")
        self.assertEqual(fixture.read_bytes(), b"first\r\nsecond\r\n")
        self.assertEqual(snapshot(self.repo, self.baseline),
                         committed_snapshot(self.repo, self.baseline, "HEAD"))

    def test_committed_snapshot_respects_text_unset_with_crlf_eol(self):
        (self.repo / ".gitattributes").write_text("fixture.txt -text eol=crlf\n")
        fixture = self.repo / "fixture.txt"
        fixture.write_bytes(b"first\nsecond\n")
        self.commit()
        fixture.unlink()
        self.git("checkout", "--", "fixture.txt")

        self.assertEqual(fixture.read_bytes(), b"first\nsecond\n")
        self.assertEqual(snapshot(self.repo, self.baseline),
                         committed_snapshot(self.repo, self.baseline, "HEAD"))

    def test_committed_snapshot_matches_text_auto_with_explicit_eol(self):
        (self.repo / ".gitattributes").write_text(
            "* text=auto\n*.sh eol=lf\n*.auto-crlf.txt eol=crlf\n")
        shell = self.repo / "fixture.sh"
        shell.write_bytes(b"#!/bin/sh\nprintf ok\n")
        text = self.repo / "fixture.auto-crlf.txt"
        text.write_bytes(b"first\nsecond\n")
        binary = self.repo / "binary.auto-crlf.txt"
        binary.write_bytes(b"one\0two\n")
        self.commit()
        shell.unlink()
        text.unlink()
        binary.unlink()
        self.git("checkout", "--", shell.name, text.name, binary.name)

        self.assertEqual(shell.read_bytes(), b"#!/bin/sh\nprintf ok\n")
        self.assertEqual(text.read_bytes(), b"first\r\nsecond\r\n")
        self.assertEqual(binary.read_bytes(), b"one\0two\n")
        self.assertEqual(snapshot(self.repo, self.baseline),
                         committed_snapshot(self.repo, self.baseline, "HEAD"))

    def test_committed_snapshot_uses_attributes_from_committed_ref(self):
        (self.repo / ".gitattributes").write_text("source.txt text eol=crlf\n")
        (self.repo / "source.txt").write_bytes(b"original\r\n")

        files = committed_snapshot(self.repo, self.baseline, "HEAD")["files"]

        source = next(record for record in files if record[0] == "source.txt")
        self.assertEqual(source, ["source.txt", "file", digest(b"original\n")])

    def test_committed_snapshot_excludes_info_attributes(self):
        info_attributes = self.repo / ".git" / "info" / "attributes"
        info_attributes.write_text("source.txt text eol=crlf\n")
        (self.repo / "source.txt").write_bytes(b"original\r\n")

        files = committed_snapshot(self.repo, self.baseline, "HEAD")["files"]

        source = next(record for record in files if record[0] == "source.txt")
        self.assertEqual(source, ["source.txt", "file", digest(b"original\n")])

    def test_committed_snapshot_rejects_checkout_filters_without_running_them(self):
        (self.repo / ".gitattributes").write_text("source.txt filter=danger\n")
        self.commit()
        marker = self.root / "filter-ran"
        self.git("config", "filter.danger.smudge", f"touch {marker}")

        with self.assertRaisesRegex(ValueError, "Unsupported checkout attribute filter"):
            committed_snapshot(self.repo, self.baseline, "HEAD")
        self.assertFalse(marker.exists())

    def test_new_deleted_modified_and_executable_files_change_identity(self):
        original = snapshot(self.repo, self.baseline)
        (self.repo / "new.txt").write_text("new")
        added = snapshot(self.repo, self.baseline)
        self.assertNotEqual(original, added)
        (self.repo / "removed.txt").unlink()
        deleted = snapshot(self.repo, self.baseline)
        self.assertNotEqual(added, deleted)
        (self.repo / "source.txt").write_text("changed")
        modified = snapshot(self.repo, self.baseline)
        self.assertNotEqual(deleted, modified)
        (self.repo / "source.txt").chmod(0o755)
        self.assertNotEqual(modified, snapshot(self.repo, self.baseline))

    def test_committing_same_content_preserves_identity_including_deletion(self):
        (self.repo / "new.txt").write_text("new")
        (self.repo / "removed.txt").unlink()
        before = snapshot(self.repo, self.baseline)
        self.commit()
        self.assertEqual(before, snapshot(self.repo, self.baseline))

    def test_source_drift_blocks_pass_but_allows_honest_failure_and_repair(self):
        self.through("capture")
        graph_state.start(self.state, "checks", "cos")
        (self.repo / "source.txt").write_text("changed while checking")
        with self.assertRaisesRegex(ValueError, "Source changed"):
            graph_state.complete(self.state, "checks", self.receipt("checks"))
        graph_state.complete(self.state, "checks", self.receipt("checks", "fail"))
        with self.assertRaisesRegex(ValueError, "author repair"):
            graph_state.repair(self.state, "checks", "drift")
        graph_state.repair(self.state, "implement", "repair source")
        self.assertIsNone(self.state["candidate"])
        self.assertEqual(self.state["nodes"]["tests"]["status"], "pass")
        for node in ("implement", "capture", "checks", "acceptance", "publish", "ci"):
            self.assertEqual(self.state["nodes"][node]["status"], "pending")

    def test_spec_and_evidence_changes_block_progress(self):
        self.finish("prepare")
        self.report.write_text("overwritten")
        with self.assertRaisesRegex(ValueError, "Pinned evidence"):
            graph_state.start(self.state, "tests", "worker")
        self.report.write_text("Fixture evidence\n")
        self.spec.write_text("unapproved spec change")
        with self.assertRaisesRegex(ValueError, "Pinned evidence"):
            graph_state.start(self.state, "tests", "worker")

    def test_repair_requires_stopped_workers_and_diagnosis_after_two_rounds(self):
        self.finish("prepare")
        graph_state.start(self.state, "tests", "writer")
        with self.assertRaisesRegex(ValueError, "stopped workers"):
            graph_state.repair(self.state, "prepare", "retry")
        graph_state.complete(self.state, "tests", self.receipt("tests", "blocked"))
        for _ in range(2):
            graph_state.repair(self.state, "prepare", "environment reproduction")
            self.finish("prepare")
        with self.assertRaisesRegex(ValueError, "Diagnosis"):
            graph_state.repair(self.state, "prepare", "third retry")
        graph_state.repair(self.state, "prepare", "diagnosed retry", self.report)
        self.assertEqual(len(self.state["history"]), 3)

    def test_review_retry_keeps_same_candidate_and_independent_sibling(self):
        self.through("regression")
        identity = self.state["candidate"]
        graph_state.repair(self.state, "acceptance", "Rerun own probe; sibling inputs unchanged")
        self.assertEqual(self.state["candidate"], identity)
        self.assertEqual(self.state["nodes"]["regression"]["status"], "pass")
        self.assertEqual(self.state["nodes"]["acceptance"]["status"], "pending")

    def test_old_attempt_cannot_complete_after_repair(self):
        graph_state.start(self.state, "prepare", "old-worker")
        old = self.receipt("prepare")
        graph_state.complete(self.state, "prepare", old)
        graph_state.repair(self.state, "prepare", "repeat actual setup")
        graph_state.start(self.state, "prepare", "new-worker")
        with self.assertRaisesRegex(ValueError, "attempt"):
            graph_state.complete(self.state, "prepare", old)
