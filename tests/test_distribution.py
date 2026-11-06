import hashlib
import json
import os
import runpy
from pathlib import Path, PurePath
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from tofscope.cli import asset_status
from tofscope.science.isotopes import load_catalog


class DistributionTests(unittest.TestCase):
    def test_bundled_assets_and_reference(self):
        self.assertEqual(asset_status()["version"], "0.3.0")
        self.assertTrue(load_catalog())

    def test_frontend_fingerprint_ignores_platform_path_sorting(self):
        root = Path(__file__).resolve().parents[1]
        source_hash = runpy.run_path(str(root / "scripts" / "build_frontend.py"))["source_hash"]
        manifest = json.loads((root / "src" / "tofscope" / "static" / "manifest.json").read_text())
        def windows_order(left, right):
            return left.as_posix().lower() < right.as_posix().lower()
        with patch.object(PurePath, "__lt__", windows_order):
            self.assertEqual(source_hash(), manifest["source_sha256"])

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
