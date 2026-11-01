"""Checks for the local documentation preview server."""

import importlib.util
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.request import urlopen

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "preview_docs.py"
SPEC = importlib.util.spec_from_file_location("preview_docs", SCRIPT)
preview_docs = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(preview_docs)


class PreviewTests(unittest.TestCase):
    def test_snapshot_detects_edits_and_new_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "docs").mkdir()
            page = root / "docs" / "index.qmd"
            page.write_text("first")
            first = preview_docs.source_snapshot(root)
            page.write_text("second version")
            self.assertNotEqual(first, preview_docs.source_snapshot(root))
            second = preview_docs.source_snapshot(root)
            (root / "docs" / "new.qmd").write_text("new")
            self.assertNotEqual(second, preview_docs.source_snapshot(root))

    def test_server_injects_refresh_without_changing_site_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            index = root / "index.html"
            index.write_text("<html><body>Documentation</body></html>")
            state = preview_docs.PreviewState()
            server = preview_docs.make_server(root, state, port=0)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base = f"http://127.0.0.1:{server.server_port}"
                with urlopen(base + "/") as response:
                    content = response.read().decode()
                self.assertIn("/__docs_preview_revision", content)
                self.assertNotIn("/__docs_preview_revision", index.read_text())
                with urlopen(base + "/__docs_preview_revision") as response:
                    self.assertEqual(response.read(), b"0")
                state.advance()
                with urlopen(base + "/__docs_preview_revision") as response:
                    self.assertEqual(response.read(), b"1")
            finally:
                server.shutdown()
                server.server_close()
                thread.join()


if __name__ == "__main__":
    unittest.main()
