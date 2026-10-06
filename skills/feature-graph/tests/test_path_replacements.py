from support import GraphCase
import graph_state
from evidence import committed_snapshot, digest, snapshot


class PathReplacementTests(GraphCase):
    def assert_replacement_publishes(self, removed, added, content):
        captured = snapshot(self.repo, self.baseline)
        self.assertIn([removed, "deleted", None], captured["files"])
        self.assertIn([added, "file", digest(content.encode())], captured["files"])
        self.git("add", "--all")
        self.assertEqual(captured, snapshot(self.repo, self.baseline))
        self.through("reconcile")
        self.commit()
        self.assertEqual(captured, snapshot(self.repo, self.baseline))
        self.assertEqual(captured, committed_snapshot(self.repo, self.baseline, "HEAD"))
        self.finish("publish")

    def test_file_replaced_by_directory_preserves_source_identity(self):
        path = self.repo / "source.txt"
        path.unlink()
        path.mkdir()
        content = "replacement child\n"
        (path / "child.txt").write_text(content)
        self.assert_replacement_publishes("source.txt", "source.txt/child.txt", content)

    def test_directory_replaced_by_file_preserves_source_identity(self):
        path = self.repo / "module"
        path.mkdir()
        (path / "child.txt").write_text("original child\n")
        self.commit()
        self.baseline = self.git("rev-parse", "HEAD").strip()
        self.contract["baseline"] = self.baseline
        self.state = self.initialize()
        (path / "child.txt").unlink()
        path.rmdir()
        content = "replacement file\n"
        path.write_text(content)
        self.assert_replacement_publishes("module/child.txt", "module", content)
