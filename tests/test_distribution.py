import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from tofscope.cli import asset_status
from tofscope.science.isotopes import load_catalog


class DistributionTests(unittest.TestCase):
    def test_bundled_assets_and_reference(self):
        self.assertEqual(asset_status()["version"], "0.2.0")
        self.assertTrue(load_catalog())

    def test_windows_checkout_preserves_asset_hashes(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            subprocess.run(
                ["git", "-c", "core.autocrlf=true", "checkout-index",
                 "--prefix=" + directory + os.sep, "--all"],
                cwd=root, check=True, capture_output=True,
            )
            static = Path(directory) / "src" / "tofscope" / "static"
            manifest = json.loads((static / "manifest.json").read_text())
            for name, expected in manifest["assets"].items():
                with self.subTest(asset=name):
                    self.assertEqual(hashlib.sha256((static / name).read_bytes()).hexdigest(), expected)
            script = Path(directory) / "scripts" / "build_frontend.py"
            result = subprocess.run(
                [sys.executable, "-c", "import runpy,sys; print(runpy.run_path(sys.argv[1])['source_hash']())", str(script)],
                check=True, capture_output=True, text=True,
            )
            self.assertEqual(result.stdout.strip(), manifest["source_sha256"])
